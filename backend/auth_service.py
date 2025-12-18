import os
import uuid
import hashlib
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
        self.session_duration_days = 30  # Extended from 7 to 30 days
        self.session_refresh_threshold_days = 7  # Auto-refresh if less than 7 days remaining
        
        # Determine environment
        self.is_production = os.environ.get('ENVIRONMENT', 'production') == 'production'
        
        # CRITICAL: Check if cross-origin deployment
        # If frontend and backend are on different domains, we need SameSite=None
        self.is_cross_origin = self._check_cross_origin()
        
        logger.info(f"AuthService initialized: production={self.is_production}, cross_origin={self.is_cross_origin}")

    def _check_cross_origin(self) -> bool:
        """
        Check if frontend and backend are on different origins.
        This determines if we need SameSite=None for cookies.
        """
        # Check environment variable first
        cross_origin_env = os.environ.get('CROSS_ORIGIN_AUTH', 'true').lower()
        if cross_origin_env in ('true', '1', 'yes'):
            return True
        
        # Check if running on Render (different subdomains = cross-origin)
        render_service = os.environ.get('RENDER_SERVICE_NAME', '')
        if render_service:
            return True  # Render deployments are typically cross-origin
        
        return False

    def _get_cookie_settings(self) -> Dict[str, Any]:
        """
        Get cookie settings based on environment.
        
        CRITICAL for cross-origin:
        - SameSite=None requires Secure=True
        - This allows cookies to be sent in cross-origin requests
        """
        if self.is_cross_origin and self.is_production:
            # Cross-origin production (e.g., Render with separate frontend/backend)
            return {
                "httponly": True,
                "secure": True,  # MUST be True when SameSite=None
                "samesite": "none",  # Allows cross-origin cookie sending
                "path": "/",
            }
        elif self.is_production:
            # Same-origin production
            return {
                "httponly": True,
                "secure": True,
                "samesite": "lax",
                "path": "/",
            }
        else:
            # Development (localhost)
            return {
                "httponly": True,
                "secure": False,
                "samesite": "lax",
                "path": "/",
            }

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
            logger.debug(f"Found session token in cookies: {session_token[:20]}...")
            return session_token
        
        # Fallback to Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            logger.debug(f"Found session token in Authorization header: {token[:20]}...")
            return token
        
        logger.debug("No session token found in request")
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
                logger.debug(f"Session not found: {session_token[:20]}...")
                return None
            
            # Check expiration with proper timezone handling
            expires_at = session_doc.get("expires_at")
            if expires_at is None:
                logger.warning(f"Session has no expires_at field")
                return None
            
            # Handle different datetime formats
            if isinstance(expires_at, str):
                try:
                    # Try ISO format first
                    expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                except ValueError:
                    # Try other common formats
                    try:
                        expires_at = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%S.%f")
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    except ValueError:
                        logger.error(f"Cannot parse expires_at: {expires_at}")
                        return None
            
            # Ensure timezone aware
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            now = datetime.now(timezone.utc)
            
            # Check if expired
            if expires_at < now:
                logger.info(f"Session expired at {expires_at}, current time {now}")
                # Delete expired session
                await self.db.user_sessions.delete_one({"session_token": session_token})
                return None
            
            # Session is valid, get user
            user_doc = await self.db.users.find_one(
                {"user_id": session_doc["user_id"]},
                {"_id": 0}
            )
            
            if not user_doc:
                logger.warning(f"User not found for session: {session_doc['user_id']}")
                return None
            
            # Auto-extend session if it's going to expire within threshold
            time_until_expiry = expires_at - now
            if time_until_expiry < timedelta(days=self.session_refresh_threshold_days):
                new_expires_at = now + timedelta(days=self.session_duration_days)
                await self.db.user_sessions.update_one(
                    {"session_token": session_token},
                    {
                        "$set": {
                            "expires_at": new_expires_at,
                            "last_activity": now
                        }
                    }
                )
                logger.info(f"Extended session for user {session_doc['user_id']} to {new_expires_at}")
            else:
                # Just update last activity
                await self.db.user_sessions.update_one(
                    {"session_token": session_token},
                    {"$set": {"last_activity": now}}
                )
            
            return User(**user_doc)
            
        except Exception as e:
            logger.error(f"Error verifying session: {e}", exc_info=True)
            return None

    async def authenticate_user(self, request: Request) -> User:
        """Authenticate user from request (middleware helper)"""
        session_token = await self.get_session_token_from_request(request)
        
        if not session_token:
            logger.debug("No session token in request")
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        user = await self.verify_session_token(session_token)
        
        if not user:
            logger.debug("Session token invalid or expired")
            raise HTTPException(status_code=401, detail="Invalid or expired session")
        
        return user

    async def create_or_update_user_from_google(self, google_data: Dict[str, Any]) -> User:
        """
        Create or update user from Google OAuth data
        Replaces the old Emergent OAuth method
        """
        email = google_data.get("email")
        if not email:
            raise ValueError("No email provided from Google")
        
        now = datetime.now(timezone.utc)
        
        # Check if user exists
        existing_user = await self.db.users.find_one(
            {"email": email},
            {"_id": 0}
        )
        
        if existing_user:
            # Update user data
            update_data = {
                "name": google_data.get("name", existing_user.get("name")),
                "picture": google_data.get("picture"),
                "google_id": google_data.get("google_id"),
                "last_login": now
            }
            
            await self.db.users.update_one(
                {"email": email},
                {"$set": update_data}
            )
            
            # Refresh the user data
            existing_user.update(update_data)
            logger.info(f"Updated existing user: {email}")
            return User(**existing_user)
        else:
            # Create new user
            user_id = self.generate_user_id()
            new_user = {
                "user_id": user_id,
                "email": email,
                "name": google_data.get("name", email.split("@")[0]),
                "picture": google_data.get("picture"),
                "google_id": google_data.get("google_id"),
                "auth_provider": "google",
                "created_at": now,
                "last_login": now
            }
            await self.db.users.insert_one(new_user)
            logger.info(f"Created new user from Google: {email}")
            return User(**new_user)

    async def create_session(self, user_id: str, response: Response, custom_token: Optional[str] = None) -> str:
        """Create new session for user and set cookie"""
        session_token = custom_token or self.generate_session_token()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self.session_duration_days)
        
        # Store session in database
        session_doc = {
            "user_id": user_id,
            "session_token": session_token,
            "expires_at": expires_at,
            "created_at": now,
            "last_activity": now
        }
        
        # Use upsert to handle duplicate session tokens
        await self.db.user_sessions.update_one(
            {"session_token": session_token},
            {"$set": session_doc},
            upsert=True
        )
        
        # Get cookie settings based on environment
        cookie_settings = self._get_cookie_settings()
        
        # Set httpOnly cookie with proper settings
        response.set_cookie(
            key="session_token",
            value=session_token,
            max_age=self.session_duration_days * 24 * 60 * 60,  # 30 days in seconds
            expires=expires_at,
            **cookie_settings
        )
        
        logger.info(f"Created session for user {user_id}, expires at {expires_at}")
        logger.debug(f"Cookie settings: {cookie_settings}")
        return session_token

    async def register_user(self, register_data: RegisterRequest) -> User:
        """Register new user with email/password"""
        now = datetime.now(timezone.utc)
        
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
            "auth_provider": "email",
            "created_at": now,
            "last_login": now
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
        
        # Check if user has password (might be Google-only user)
        if not user_doc.get("password"):
            logger.warning(f"User {login_data.email} has no password (Google-only account)")
            return None
        
        # Verify password
        if not self.verify_password(login_data.password, user_doc.get("password", "")):
            return None
        
        # Update last login
        await self.db.users.update_one(
            {"email": login_data.email},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )
        
        # Return user without password
        user_data = {k: v for k, v in user_doc.items() if k != "password"}
        return User(**user_data)

    async def logout_user(self, session_token: str, response: Response):
        """Logout user by deleting session"""
        # Delete session from database
        result = await self.db.user_sessions.delete_one({"session_token": session_token})
        logger.info(f"Deleted {result.deleted_count} session(s)")
        
        # Get cookie settings for deletion (must match set_cookie settings)
        cookie_settings = self._get_cookie_settings()
        
        # Clear cookie with matching parameters
        response.delete_cookie(
            key="session_token",
            path=cookie_settings["path"],
            samesite=cookie_settings["samesite"],
            secure=cookie_settings["secure"],
        )

    async def cleanup_expired_sessions(self):
        """Cleanup expired sessions - call this periodically"""
        now = datetime.now(timezone.utc)
        result = await self.db.user_sessions.delete_many({
            "expires_at": {"$lt": now}
        })
        if result.deleted_count > 0:
            logger.info(f"Cleaned up {result.deleted_count} expired sessions")
        return result.deleted_count