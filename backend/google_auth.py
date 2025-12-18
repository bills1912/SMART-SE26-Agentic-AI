"""
Google OAuth 2.0 Authentication Handler
Standalone implementation tanpa Emergent
"""

import os
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlencode
import httpx
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
# Naik satu level ke root, lalu masuk ke frontend/.env
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)
class GoogleOAuth:
    """
    Handle Google OAuth 2.0 flow:
    1. Generate authorization URL
    2. Exchange code for tokens
    3. Get user info from Google
    """
    
    # Google OAuth endpoints
    GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    def __init__(self):
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        self.frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:3000')
        
        # Determine backend URL for callback
        # In production, this should be set explicitly
        self.backend_url = os.environ.get('REACT_APP_BACKEND_URL')
        if not self.backend_url:
            # Try to construct from environment
            host = os.environ.get('HOST', 'localhost')
            port = os.environ.get('PORT', '8001')
            if os.environ.get('RENDER_SERVICE_NAME'):
                # Running on Render
                service_name = os.environ.get('RENDER_SERVICE_NAME', '')
                self.backend_url = f"https://{service_name}.onrender.com"
            else:
                self.backend_url = f"http://{host}:{port}"
        
        self.redirect_uri = f"{self.backend_url}/api/auth/google/callback"
        
        # Scopes for Google OAuth
        self.scopes = [
            "openid",
            "email", 
            "profile"
        ]
        
        logger.info(f"GoogleOAuth initialized:")
        logger.info(f"  Client ID: {'SET' if self.client_id else 'NOT SET'}")
        logger.info(f"  Client Secret: {'SET' if self.client_secret else 'NOT SET'}")
        logger.info(f"  Redirect URI: {self.redirect_uri}")
        logger.info(f"  Frontend URL: {self.frontend_url}")
    
    @property
    def is_configured(self) -> bool:
        """Check if Google OAuth is properly configured"""
        return bool(self.client_id and self.client_secret)
    
    def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL
        User akan di-redirect ke URL ini untuk login
        """
        if not self.is_configured:
            raise ValueError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET")
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "access_type": "offline",  # Get refresh token
            "prompt": "select_account",  # Always show account selector
        }
        
        if state:
            params["state"] = state
        
        url = f"{self.GOOGLE_AUTH_URL}?{urlencode(params)}"
        logger.info(f"Generated authorization URL: {url[:100]}...")
        return url
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token and id token
        """
        if not self.is_configured:
            raise ValueError("Google OAuth is not configured")
        
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.GOOGLE_TOKEN_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Token exchange failed: {response.status_code} - {error_detail}")
                raise Exception(f"Failed to exchange code: {error_detail}")
            
            tokens = response.json()
            logger.info("Successfully exchanged code for tokens")
            return tokens
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """
        Get user information from Google using access token
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                self.GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if response.status_code != 200:
                error_detail = response.text
                logger.error(f"Failed to get user info: {response.status_code} - {error_detail}")
                raise Exception(f"Failed to get user info: {error_detail}")
            
            user_info = response.json()
            logger.info(f"Got user info for: {user_info.get('email')}")
            return user_info
    
    async def authenticate(self, code: str) -> Dict[str, Any]:
        """
        Complete authentication flow:
        1. Exchange code for tokens
        2. Get user info
        3. Return user data
        """
        # Step 1: Exchange code for tokens
        tokens = await self.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        
        if not access_token:
            raise Exception("No access token received from Google")
        
        # Step 2: Get user info
        user_info = await self.get_user_info(access_token)
        
        # Step 3: Format and return user data
        return {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
            "google_id": user_info.get("id"),
            "verified_email": user_info.get("verified_email", False),
            "access_token": access_token,
            "refresh_token": tokens.get("refresh_token"),
            "token_expiry": tokens.get("expires_in"),
        }


# Singleton instance
google_oauth = GoogleOAuth()