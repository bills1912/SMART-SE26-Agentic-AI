from fastapi import APIRouter, Depends, HTTPException, Request, Response
from auth_models import User, LoginRequest, RegisterRequest
from auth_service import AuthService
from database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_auth_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthService:
    return AuthService(db)

@router.post("/oauth/callback")
async def oauth_callback(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Handle Emergent OAuth callback
    Frontend sends session_id from URL fragment
    """
    try:
        body = await request.json()
        session_id = body.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        # Get user data from Emergent
        oauth_data = await auth_service.process_emergent_oauth(session_id)
        
        # Create or update user
        user = await auth_service.create_or_update_user_from_oauth(oauth_data)
        
        # Create session with OAuth session token
        session_token = await auth_service.create_session(
            user.user_id,
            response,
            oauth_session_token=oauth_data.get("session_token")
        )
        
        return {
            "success": True,
            "user": user.dict(),
            "session_token": session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/register")
async def register(
    register_data: RegisterRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Register new user with email/password"""
    try:
        # Register user
        user = await auth_service.register_user(register_data)
        
        # Create session
        session_token = await auth_service.create_session(user.user_id, response)
        
        return {
            "success": True,
            "user": user.dict(),
            "session_token": session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(
    login_data: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Login user with email/password"""
    try:
        # Authenticate user
        user = await auth_service.login_user(login_data)
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Create session
        session_token = await auth_service.create_session(user.user_id, response)
        
        return {
            "success": True,
            "user": user.dict(),
            "session_token": session_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Get current authenticated user"""
    try:
        user = await auth_service.authenticate_user(request)
        return {
            "success": True,
            "user": user.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get current user error: {e}")
        raise HTTPException(status_code=401, detail="Not authenticated")

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """Logout current user"""
    try:
        session_token = await auth_service.get_session_token_from_request(request)
        
        if session_token:
            await auth_service.logout_user(session_token, response)
        
        return {"success": True, "message": "Logged out successfully"}
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
