import os
import uuid
import hashlib
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Request, Response
from motor.motor_asyncio import AsyncIOMotorDatabase
from auth_models import User, UserSession, LoginRequest, RegisterRequest
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.session_duration_days = 7
        self.emergent_auth_url = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

    def generate_user_id(self) -> str:
        """Generate unique user ID"""
        return f"user_{uuid.uuid4().hex[:12]}"

    def generate_session_token(self) -> str:
        """Generate unique session token"""
        return f"session_{uuid.uuid4().hex}"

    def hash_password(self, password: str) -> str:
        """Hash password using SHA256"""
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return self.hash_password(password) == hashed_password

    async def get_session_token_from_request(self, request: Request) -> Optional[str]:
        """Extract session token from cookies or Authorization header"""
        # Check cookies first
        session_token = request.cookies.get('session_token')
        if session_token:
            return session_token
        
        # Fallback to Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            return auth_header.split(' ')[1]
        
        return None

    async def verify_session_token(self, session_token: str) -> Optional[User]:
        """Verify session token and return user"""
        try:
            # Find session in database
            session_doc = await self.db.user_sessions.find_one(
                {"session_token": session_token},
                {"_id": 0}
            )
            
            if not session_doc:
                return None
            
            # Check expiration
            expires_at = session_doc["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            if expires_at < datetime.now(timezone.utc):
                # Delete expired session
                await self.db.user_sessions.delete_one({"session_token": session_token})
                return None
            
            # Get user
            user_doc = await self.db.users.find_one(
                {"user_id": session_doc["user_id"]},
                {"_id": 0}
            )
            
            if not user_doc:
                return None
            
            return User(**user_doc)
            
        except Exception as e:
            logger.error(f"Error verifying session: {e}")
            return None

    async def authenticate_user(self, request: Request) -> User:
        """Authenticate user from request (middleware helper)"""
        session_token = await self.get_session_token_from_request(request)
        
        if not session_token:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user = await self.verify_session_token(session_token)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        return user

    async def process_emergent_oauth(self, session_id: str) -> Dict[str, Any]:
        """Process Emergent OAuth session ID and get user data"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.emergent_auth_url,
                    headers={"X-Session-ID": session_id},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail="Failed to fetch session data from Emergent"
                    )
                
                return response.json()
        
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during OAuth: {e}")
            raise HTTPException(status_code=500, detail="OAuth service unavailable")

    async def create_or_update_user_from_oauth(self, oauth_data: Dict[str, Any]) -> User:
        """Create or update user from OAuth data"""
        email = oauth_data["email"]
        
        # Check if user exists
        existing_user = await self.db.users.find_one(
            {"email": email},
            {"_id": 0}
        )
        
        if existing_user:
            # Update user data
            await self.db.users.update_one(
                {"email": email},
                {
                    "$set": {
                        "name": oauth_data["name"],
                        "picture": oauth_data.get("picture")
                    }
                }
            )
            return User(**existing_user)
        else:
            # Create new user
            user_id = self.generate_user_id()
            new_user = {
                "user_id": user_id,
                "email": email,
                "name": oauth_data["name"],
                "picture": oauth_data.get("picture"),
                "created_at": datetime.now(timezone.utc)
            }
            await self.db.users.insert_one(new_user)
            return User(**new_user)

    async def create_session(self, user_id: str, response: Response) -> str:
        """Create new session for user and set cookie"""
        session_token = oauth_data.get("session_token") or self.generate_session_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=self.session_duration_days)
        
        # Store session in database
        await self.db.user_sessions.insert_one({
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "created_at": datetime.now(timezone.utc)
        })
        
        # Set httpOnly cookie
        response.set_cookie(
            key="session_token",
            value=session_token,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            path="/",
            max_age=self.session_duration_days * 24 * 60 * 60
        )
        
        return session_token

    async def register_user(self, register_data: RegisterRequest) -> User:
        """Register new user with email/password"""
        # Check if user exists
        existing_user = await self.db.users.find_one(
            {"email": register_data.email},
            {"_id": 0}
        )
        
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create new user
        user_id = self.generate_user_id()
        hashed_password = self.hash_password(register_data.password)
        
        new_user = {
            "user_id": user_id,
            "email": register_data.email,
            "name": register_data.name,
            "password": hashed_password,
            "picture": None,
            "created_at": datetime.now(timezone.utc)
        }
        
        await self.db.users.insert_one(new_user)
        
        # Return user without password
        user_data = {k: v for k, v in new_user.items() if k != "password"}
        return User(**user_data)

    async def login_user(self, login_data: LoginRequest) -> Optional[User]:
        """Login user with email/password"""
        # Find user
        user_doc = await self.db.users.find_one(
            {"email": login_data.email},
            {"_id": 0}
        )
        
        if not user_doc:
            return None
        
        # Verify password
        if not self.verify_password(login_data.password, user_doc.get("password", "")):
            return None
        
        # Return user without password
        user_data = {k: v for k, v in user_doc.items() if k != "password"}
        return User(**user_data)

    async def logout_user(self, session_token: str, response: Response):
        """Logout user by deleting session"""
        # Delete session from database
        await self.db.user_sessions.delete_one({"session_token": session_token})
        
        # Clear cookie
        response.delete_cookie(key="session_token", path="/")
