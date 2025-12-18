from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from auth_models import User, LoginRequest, RegisterRequest
from auth_service import AuthService
from google_auth import google_oauth
from database import get_database
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

def get_auth_service(db: AsyncIOMotorDatabase = Depends(get_database)) -> AuthService:
    return AuthService(db)


# ============================================
# GOOGLE OAUTH ENDPOINTS (NEW)
# ============================================

@router.get("/google/login")
async def google_login():
    """
    Redirect user to Google OAuth consent screen
    Frontend calls this endpoint to start OAuth flow
    """
    try:
        if not google_oauth.is_configured:
            logger.error("Google OAuth not configured")
            raise HTTPException(
                status_code=503, 
                detail="Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET"
            )
        
        auth_url = google_oauth.get_authorization_url()
        logger.info(f"Redirecting to Google OAuth: {auth_url[:80]}...")
        
        return RedirectResponse(url=auth_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Google login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: str = None,
    error: str = None,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Handle Google OAuth callback
    Google redirects here after user authorizes
    """
    frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
    
    try:
        # Check for errors from Google
        if error:
            logger.error(f"Google OAuth error: {error}")
            return RedirectResponse(
                url=f"{frontend_url}/login?error={error}",
                status_code=302
            )
        
        if not code:
            logger.error("No authorization code received from Google")
            return RedirectResponse(
                url=f"{frontend_url}/login?error=no_code",
                status_code=302
            )
        
        logger.info("Processing Google OAuth callback...")
        
        # Exchange code for user info
        google_user = await google_oauth.authenticate(code)
        
        if not google_user or not google_user.get("email"):
            logger.error("Failed to get user info from Google")
            return RedirectResponse(
                url=f"{frontend_url}/login?error=auth_failed",
                status_code=302
            )
        
        logger.info(f"Google user authenticated: {google_user.get('email')}")
        
        # Create or update user in database
        user = await auth_service.create_or_update_user_from_google(google_user)
        
        # Create session
        session_token = await auth_service.create_session(user.user_id, response)
        
        # Redirect to frontend with success
        # Include session token in URL fragment for frontend to capture
        # Fragment (#) is not sent to server, so it's safe
        redirect_url = f"{frontend_url}/auth/callback#session_token={session_token}&user_id={user.user_id}&email={user.email}&name={user.name}"
        
        logger.info(f"OAuth success, redirecting to frontend")
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except Exception as e:
        logger.error(f"Google callback error: {e}", exc_info=True)
        return RedirectResponse(
            url=f"{frontend_url}/login?error=server_error",
            status_code=302
        )


@router.get("/google/status")
async def google_oauth_status():
    """
    Check if Google OAuth is properly configured
    Useful for frontend to decide whether to show Google login button
    """
    return {
        "configured": google_oauth.is_configured,
        "redirect_uri": google_oauth.redirect_uri if google_oauth.is_configured else None
    }


# ============================================
# LEGACY OAUTH ENDPOINT (DEPRECATED - KEEP FOR BACKWARDS COMPATIBILITY)
# ============================================

@router.post("/oauth/callback")
async def oauth_callback_legacy(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    DEPRECATED: Legacy Emergent OAuth callback
    Kept for backwards compatibility during transition
    Will be removed in future versions
    """
    logger.warning("Legacy OAuth callback called - this endpoint is deprecated")
    
    try:
        body = await request.json()
        session_id = body.get("session_id")
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        # Return error suggesting to use new Google OAuth
        raise HTTPException(
            status_code=410,  # Gone
            detail="Emergent OAuth is no longer supported. Please use Google OAuth at /api/auth/google/login"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Legacy OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# EXISTING AUTH ENDPOINTS (UNCHANGED)
# ============================================

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