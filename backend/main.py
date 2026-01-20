from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio
from pydantic import BaseModel

# --- 1. KONFIGURASI ENV (FIXED) ---
load_dotenv()
# --- 2. LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 3. IMPORT CUSTOM MODULES ---
# Import models & database
from models import (
    PolicyAnalysisRequest, 
    PolicyAnalysisResponse, 
    ChatSession, 
    ChatMessage,
    ScrapedData
)
from database import PolicyDatabase
from ai_analyzer import PolicyAIAnalyzer
from report_generator import ReportGenerator

# --- 4. INISIALISASI DATABASE & AI (CRITICAL FIX) ---
# Mengambil URL dari environment variable
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'policy_db')

if not mongo_url:
    logger.error("CRITICAL: MONGO_URL not found in .env file!")
    raise ValueError("MONGO_URL is not set. Please check your .env file.")

# Inisialisasi Database Object (Global Variable)
policy_db = PolicyDatabase(mongo_url, db_name)

# AI Analyzer akan diinit di startup event setelah database ready
ai_analyzer = None

# Report Generator
report_generator = ReportGenerator()

# --- 5. SETUP APLIKASI FASTAPI ---
app = FastAPI(title="AI Policy & Insight Generator", version="1.0.0")

# ============================================
# CRITICAL FIX: ADD CORS MIDDLEWARE FIRST (BEFORE ANYTHING ELSE)
# ============================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://smart-se26-agentic-ai-chatbot-web.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

logger.info("✓ CORS middleware configured")

# Create router
api_router = APIRouter(prefix="/api")

# Global variables for background tasks
scraping_in_progress = False
last_scraping_time = None

# ============================================
# AUTHENTICATION DEPENDENCY - FIXED
# ============================================
from auth_service import AuthService

async def get_current_user_from_request(request: Request) -> Optional[dict]:
    """
    Extract current user from request using AuthService
    Returns user dict if authenticated, None otherwise
    
    This function directly uses the global policy_db instead of dependency injection
    to avoid issues with FastAPI's dependency system in certain contexts.
    """
    try:
        # Debug: Log request info
        cookies = dict(request.cookies)
        session_cookie = cookies.get("session_token")
        auth_header = request.headers.get("Authorization")
        
        logger.info(f"[Auth Debug] Cookies count: {len(cookies)}")
        logger.info(f"[Auth Debug] Has session_token cookie: {session_cookie is not None}")
        if session_cookie:
            logger.info(f"[Auth Debug] Session token preview: {session_cookie[:30]}...")
        logger.info(f"[Auth Debug] Has Authorization header: {auth_header is not None}")
        
        # Create AuthService with the database
        auth_service = AuthService(policy_db.db)
        
        # Try to authenticate user
        user = await auth_service.authenticate_user(request)
        
        if user:
            logger.info(f"✓ Authenticated user: {user.email} (ID: {user.user_id})")
            return {
                "user_id": user.user_id, 
                "email": user.email, 
                "name": user.name
            }
        
        logger.warning("[Auth Debug] authenticate_user returned None")
        return None
        
    except HTTPException as e:
        logger.warning(f"[Auth Debug] HTTPException: {e.status_code} - {e.detail}")
        return None
    except Exception as e:
        logger.error(f"[Auth Debug] Exception: {type(e).__name__}: {e}")
        return None


async def get_current_user_optional(request: Request) -> Optional[dict]:
    """
    Dependency for endpoints that work with or without authentication
    """
    return await get_current_user_from_request(request)


async def get_current_user_required(request: Request) -> dict:
    """
    Dependency for endpoints that require authentication
    Raises 401 if not authenticated
    """
    user = await get_current_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


# --- 6. EVENT HANDLERS (STARTUP/SHUTDOWN) ---
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    global ai_analyzer
    try:
        # Initialize database collections
        await policy_db.init_collections()
        logger.info("✓ Connected to MongoDB Atlas successfully")
        
        # Initialize AI Analyzer with RAW database object (not PolicyDatabase wrapper)
        # PolicyAnalyzer expects AsyncIOMotorDatabase
        ai_analyzer = PolicyAIAnalyzer(policy_db.db)
        logger.info("✓ AI Analyzer initialized successfully")
        
    except Exception as e:
        logger.error(f"✗ Error during startup: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        await policy_db.close()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# --- 7. ROOT ENDPOINT (HEALTH CHECK) ---
@app.get("/")
async def root():
    """Root endpoint - serve SPA or API info"""
    # Check if frontend build exists
    index_path = FRONTEND_BUILD_PATH / "index.html"
    if index_path.exists():
        return FileResponse(index_path, media_type="text/html")
    
    # Fallback to API info if no frontend
    return {
        "message": "AI Policy & Insight Generator API", 
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "api": "/api",
            "health": "/api/health",
            "auth": "/api/auth",
            "docs": "/docs"
        }
    }

# --- 8. API ROUTES / ENDPOINTS ---

@api_router.get("/")
async def api_root():
    return {"message": "API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    try:
        stats = await policy_db.get_database_stats()
        return {
            "status": "healthy",
            "database": "connected" if policy_db.is_connected else "disconnected",
            "ai_analyzer": "ready" if ai_analyzer else "not_initialized",
            "scraping_status": "in_progress" if scraping_in_progress else "idle",
            "last_scraping": last_scraping_time,
            "data_stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )


# ============================================
# CHAT ENDPOINTS - NOW WITH USER AUTHENTICATION
# ============================================

@api_router.post("/chat", response_model=PolicyAnalysisResponse)
async def analyze_policy(
    request: PolicyAnalysisRequest, 
    http_request: Request,
    background_tasks: BackgroundTasks
):
    """
    Analyze policy query and generate response
    
    - If user is authenticated: session is linked to their account
    - If user is not authenticated: session is anonymous (legacy behavior)
    """
    try:
        if not ai_analyzer:
            raise HTTPException(status_code=503, detail="AI Analyzer not initialized")
        
        # Get current user from request
        current_user = await get_current_user_from_request(http_request)
        user_id = current_user.get("user_id") if current_user else None
        
        logger.info(f"📝 Chat request - User: {user_id or 'anonymous'}, Message: {request.message[:50]}...")
        
        # Get or create session
        session_id = request.session_id
        if not session_id:
            # Create new session with user_id
            session = await policy_db.create_chat_session(user_id=user_id)
            session_id = session.id
            logger.info(f"✓ Created new session {session_id} for user {user_id or 'anonymous'}")
        else:
            # Verify session exists and user has access
            existing_session = await policy_db.get_chat_session(session_id)
            
            if not existing_session:
                # Session doesn't exist, create new one
                session = await policy_db.create_chat_session(user_id=user_id)
                session_id = session.id
                logger.info(f"✓ Session not found, created new session {session_id}")
            else:
                # Session exists, check ownership
                session_owner = existing_session.user_id
                
                if session_owner and user_id and session_owner != user_id:
                    # Session belongs to different user
                    raise HTTPException(status_code=403, detail="Access denied to this session")
                
                # If session is anonymous (no owner) and user is logged in,
                # optionally claim the session
                if not session_owner and user_id:
                    # Claim anonymous session for logged-in user
                    await policy_db.db.chat_sessions.update_one(
                        {"id": session_id},
                        {"$set": {"user_id": user_id}}
                    )
                    logger.info(f"✓ Claimed anonymous session {session_id} for user {user_id}")
                
                logger.info(f"✓ Using existing session {session_id}")

        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            sender="user",
            content=request.message
        )
        await policy_db.save_chat_message(user_message)
        
        # Analyze with AI using multi-agent system
        analysis_result = await ai_analyzer.analyze_policy_query(
            query=request.message,
            language="Indonesian",
            scraped_data=None  # Not used - agents get data from initial_data
        )
        
        logger.info(f"✓ Analysis completed for session {session_id}")
        
        # Save AI response
        ai_message = ChatMessage(
            session_id=session_id,
            sender="ai",
            content=analysis_result['message'],
            visualizations=analysis_result.get('visualizations', []),
            insights=analysis_result.get('insights', []),
            policies=analysis_result.get('policies', [])
        )
        await policy_db.save_chat_message(ai_message)
        
        # Save recommendations if any
        if analysis_result.get('policies'):
            # Convert dict policies to PolicyRecommendation objects
            from models import PolicyRecommendation, PolicyCategory
            policy_objects = []
            for policy_dict in analysis_result['policies']:
                try:
                    policy_obj = PolicyRecommendation(
                        title=policy_dict.get('title', ''),
                        description=policy_dict.get('description', ''),
                        priority=policy_dict.get('priority', 'medium'),
                        category=PolicyCategory(policy_dict.get('category', 'economic')),
                        impact=policy_dict.get('impact', ''),
                        implementation_steps=policy_dict.get('implementation_steps', [])
                    )
                    policy_objects.append(policy_obj)
                except Exception as e:
                    logger.error(f"Error creating policy object: {e}")
            
            if policy_objects:
                await policy_db.save_policy_recommendations(policy_objects)
        
        return PolicyAnalysisResponse(
            message=analysis_result['message'],
            session_id=session_id,
            visualizations=analysis_result.get('visualizations', []),
            insights=analysis_result.get('insights', []),
            policies=analysis_result.get('policies', []),
            supporting_data_count=analysis_result.get('supporting_data_count', 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in policy analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing policy: {str(e)}")


@api_router.get("/sessions", response_model=List[ChatSession])
async def get_chat_sessions(request: Request):
    """
    Get chat sessions for the current user
    
    - If authenticated: returns only user's sessions
    - If not authenticated: returns empty list (to prevent data leakage)
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        if not user_id:
            # Not authenticated - return empty list
            logger.info("📋 Anonymous user requesting sessions - returning empty list")
            return []
        
        logger.info(f"📋 Fetching sessions for user {user_id}...")
        sessions = await policy_db.get_chat_sessions(limit=20, user_id=user_id)
        logger.info(f"✓ Found {len(sessions)} sessions for user {user_id}")
        return sessions
    except Exception as e:
        logger.error(f"❌ Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching sessions")


@api_router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str, request: Request):
    """
    Get a specific chat session by ID
    
    - Verifies user has access to the session
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        logger.info(f"📋 Fetching session {session_id} for user {user_id or 'anonymous'}")
        
        # Get the session
        session = await policy_db.get_chat_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check access rights
        if session.user_id:
            # Session belongs to a user
            if session.user_id != user_id:
                # Different user trying to access
                raise HTTPException(status_code=403, detail="Access denied to this session")
        # If session.user_id is None, it's an anonymous session - allow access for backwards compatibility
        
        logger.info(f"✓ Session found with {len(session.messages)} messages")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching session")


@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    """
    Delete a specific chat session
    
    - Verifies user owns the session before deleting
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required to delete sessions")
        
        # Verify ownership and delete
        success = await policy_db.delete_chat_session(session_id, user_id=user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or access denied")
        
        logger.info(f"✓ Deleted session {session_id} for user {user_id}")
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")


class BulkDeleteRequest(BaseModel):
    session_ids: List[str]


@api_router.delete("/sessions/batch")
async def delete_multiple_sessions(delete_request: BulkDeleteRequest, request: Request):
    """
    Delete multiple chat sessions at once
    
    - Only deletes sessions belonging to the authenticated user
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required to delete sessions")
        
        count = await policy_db.delete_chat_sessions(delete_request.session_ids, user_id=user_id)
        logger.info(f"✓ Bulk deleted {count} sessions for user {user_id}")
        return {"message": f"Successfully deleted {count} sessions", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting multiple sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete sessions")


@api_router.delete("/sessions/all")
async def delete_all_sessions(request: Request):
    """
    Delete ALL chat sessions for the current user
    
    - Only deletes sessions belonging to the authenticated user
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Authentication required to delete sessions")
        
        count = await policy_db.delete_all_chat_sessions(user_id=user_id)
        logger.info(f"✓ Deleted all {count} sessions for user {user_id}")
        return {"message": f"Successfully deleted {count} sessions", "count": count}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting all sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete all sessions")


# ============================================
# REPORT ENDPOINTS - WITH USER AUTHENTICATION
# ============================================

@api_router.get("/report/{session_id}/{format}")
async def generate_report(session_id: str, format: str, request: Request):
    """
    Generate comprehensive report with visualizations and policies
    
    Supported formats:
    - pdf: PDF document with tables and formatted content
    - docx: Word document with full formatting
    - html: Interactive HTML with embedded charts (can be printed to PDF)
    """
    try:
        # Validate format
        if format not in ['pdf', 'docx', 'html']:
            raise HTTPException(
                status_code=400, 
                detail="Format must be 'pdf', 'docx', or 'html'"
            )
        
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        # Get session with access check
        session = await policy_db.get_chat_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check access rights
        if session.user_id and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        logger.info(f"Generating {format} report for session {session_id}")
        
        if format == 'pdf':
            buffer = report_generator.generate_pdf(session)
            media_type = 'application/pdf'
            filename = f"Laporan_Sensus_Ekonomi_{session_id[:8]}.pdf"
            
            return StreamingResponse(
                buffer,
                media_type=media_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Access-Control-Expose-Headers': 'Content-Disposition'
                }
            )
        
        elif format == 'docx':
            buffer = report_generator.generate_docx(session)
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            filename = f"Laporan_Sensus_Ekonomi_{session_id[:8]}.docx"
            
            return StreamingResponse(
                buffer,
                media_type=media_type,
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"',
                    'Access-Control-Expose-Headers': 'Content-Disposition'
                }
            )
        
        else:  # html
            html_content = report_generator.generate_html_report(session)
            
            # Return as downloadable HTML file
            return HTMLResponse(
                content=html_content,
                headers={
                    'Content-Disposition': f'attachment; filename="Laporan_Sensus_Ekonomi_{session_id[:8]}.html"',
                    'Access-Control-Expose-Headers': 'Content-Disposition'
                }
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")


@api_router.get("/report/{session_id}/preview")
async def preview_report(session_id: str, request: Request):
    """
    Preview report as HTML in browser (tidak download, langsung tampil)
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        session = await policy_db.get_chat_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Check access rights
        if session.user_id and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        
        html_content = report_generator.generate_html_report(session)
        
        # Return as viewable HTML (tanpa Content-Disposition attachment)
        return HTMLResponse(content=html_content)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error previewing report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error previewing report: {str(e)}")


# ============================================
# DEBUG ENDPOINT - Check Auth Status
# ============================================

@api_router.get("/debug/auth")
async def debug_auth(request: Request):
    """
    Debug endpoint to check authentication status
    Shows what user info is being extracted from the request
    """
    try:
        # Check cookies
        cookies = dict(request.cookies)
        session_token = cookies.get("session_token", None)
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization", None)
        
        # Try to get user
        current_user = await get_current_user_from_request(request)
        
        return {
            "authenticated": current_user is not None,
            "user": current_user,
            "debug": {
                "has_session_cookie": session_token is not None,
                "session_token_preview": session_token[:20] + "..." if session_token else None,
                "has_auth_header": auth_header is not None,
                "cookies_count": len(cookies)
            }
        }
    except Exception as e:
        return {
            "authenticated": False,
            "user": None,
            "error": str(e)
        }


@api_router.get("/debug/sessions")
async def debug_sessions(request: Request):
    """
    Debug endpoint to see what sessions exist for the current user
    """
    try:
        current_user = await get_current_user_from_request(request)
        user_id = current_user.get("user_id") if current_user else None
        
        # Get sessions for this user
        user_sessions = await policy_db.get_chat_sessions(limit=50, user_id=user_id)
        
        # Also get raw count from database
        if user_id:
            raw_count = await policy_db.db.chat_sessions.count_documents({"user_id": user_id})
        else:
            raw_count = await policy_db.db.chat_sessions.count_documents({
                "$or": [
                    {"user_id": {"$exists": False}},
                    {"user_id": None}
                ]
            })
        
        # Get total sessions in database
        total_sessions = await policy_db.db.chat_sessions.count_documents({})
        
        # Get sample of all sessions to see user_id distribution
        sample_sessions = await policy_db.db.chat_sessions.find(
            {}, 
            {"id": 1, "user_id": 1, "title": 1, "_id": 0}
        ).limit(10).to_list(length=10)
        
        return {
            "current_user": current_user,
            "query_user_id": user_id,
            "sessions_found": len(user_sessions),
            "raw_db_count": raw_count,
            "total_sessions_in_db": total_sessions,
            "sessions": [
                {
                    "id": s.id,
                    "user_id": s.user_id,
                    "title": s.title,
                    "message_count": len(s.messages) if s.messages else 0
                }
                for s in user_sessions
            ],
            "sample_all_sessions": sample_sessions
        }
    except Exception as e:
        logger.error(f"Debug sessions error: {e}", exc_info=True)
        return {
            "error": str(e),
            "current_user": None
        }


# ============================================
# OTHER API ENDPOINTS (NO AUTH REQUIRED)
# ============================================

@api_router.post("/scrape/trigger")
async def trigger_scraping(background_tasks: BackgroundTasks):
    """Deprecated - data is now from initial_data collection"""
    return {
        "message": "Scraping is deprecated. Using initial_data collection.",
        "status": "not_needed"
    }

@api_router.get("/data/recent", response_model=List[ScrapedData])
async def get_recent_data(limit: int = 50, category: Optional[str] = None):
    try:
        data = await policy_db.get_recent_scraped_data(limit=limit, category=category)
        return data
    except Exception as e:
        logger.error(f"Error fetching recent data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching data")

@api_router.get("/data/search", response_model=List[ScrapedData])
async def search_data(query: str, limit: int = 50):
    try:
        data = await policy_db.search_scraped_data(query, limit=limit)
        return data
    except Exception as e:
        logger.error(f"Error searching data: {e}")
        raise HTTPException(status_code=500, detail="Error searching data")

@api_router.get("/stats")
async def get_stats():
    try:
        stats = await policy_db.get_database_stats()
        stats["scraping_status"] = "deprecated"
        stats["last_scraping"] = last_scraping_time
        
        # Add initial_data stats
        try:
            initial_data_count = await policy_db.db.initial_data.count_documents({})
            stats["initial_data_count"] = initial_data_count
        except:
            stats["initial_data_count"] = 0
        
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error getting statistics")


# --- 9. REGISTER API ROUTER ---
app.include_router(api_router)
logger.info("✓ API routes registered at /api/*")

# --- 10. REGISTER AUTH ROUTER ---
try:
    from auth_routes import router as auth_router
    app.include_router(auth_router)
    logger.info("✓ Auth routes registered at /api/auth/*")
except ImportError as e:
    logger.error(f"✗ Failed to import auth routes: {e}")
    logger.error("⚠️  Authentication will not work!")
    
    # Fallback auth endpoint for testing
    @app.get("/api/auth/me")
    async def fallback_auth_me():
        return JSONResponse(
            status_code=401,
            content={"detail": "Auth module not loaded"}
        )
except Exception as e:
    logger.error(f"✗ Error registering auth routes: {e}")

# --- 11. EXCEPTION HANDLERS ---
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Custom 404 handler - serve SPA for frontend routes"""
    path = request.url.path
    
    # If it's an API call, return JSON error
    if path.startswith("/api/"):
        logger.warning(f"404 API endpoint not found: {path}")
        return JSONResponse(
            status_code=404,
            content={
                "detail": f"API endpoint not found: {path}",
                "available_endpoints": [
                    "/api/health",
                    "/api/chat",
                    "/api/sessions",
                    "/api/auth/me",
                    "/api/debug/auth"
                ]
            }
        )
    
    # For ALL non-API paths, serve index.html (SPA routing)
    # This handles /login, /register, /dashboard, /auth/callback, etc.
    index_path = FRONTEND_BUILD_PATH / "index.html"
    if index_path.exists():
        logger.info(f"Serving SPA index.html for path: {path}")
        return FileResponse(index_path, media_type="text/html")
    
    # Only return 404 if index.html doesn't exist
    logger.error(f"Frontend index.html not found at {index_path}")
    return JSONResponse(
        status_code=404,
        content={"detail": "Frontend not deployed. Please build the frontend first."}
    )

@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Custom 500 handler"""
    logger.error(f"500 Internal Error at {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "path": request.url.path}
    )

# --- 12. STATIC FILES & SPA FALLBACK (FOR PRODUCTION) ---
# Check if frontend build exists
if FRONTEND_BUILD_PATH.exists() and (FRONTEND_BUILD_PATH / "index.html").exists():
    logger.info(f"✓ Frontend build found at: {FRONTEND_BUILD_PATH}")
    
    # Serve static files (JS, CSS, images, etc) - MUST be before catch-all
    static_path = FRONTEND_BUILD_PATH / "static"
    if static_path.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(static_path)),
            name="static"
        )
        logger.info("✓ Static files mounted at /static")
    
    @app.get("/favicon.ico")
    async def favicon():
        favicon_path = FRONTEND_BUILD_PATH / "favicon.ico"
        if favicon_path.exists():
            return FileResponse(favicon_path)
        # Try .png version
        favicon_png = FRONTEND_BUILD_PATH / "favicon.png"
        if favicon_png.exists():
            return FileResponse(favicon_png)
        raise HTTPException(status_code=404)

    @app.get("/manifest.json")
    async def manifest():
        manifest_path = FRONTEND_BUILD_PATH / "manifest.json"
        if manifest_path.exists():
            return FileResponse(manifest_path)
        raise HTTPException(status_code=404)

    @app.get("/robots.txt")
    async def robots():
        robots_path = FRONTEND_BUILD_PATH / "robots.txt"
        if robots_path.exists():
            return FileResponse(robots_path)
        raise HTTPException(status_code=404)
    
    # ============================================
    # CRITICAL FIX: SPA Catch-All Route
    # This MUST handle all frontend routes like /login, /register, /dashboard
    # ============================================
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """
        Catch-all route untuk serve React SPA.
        Semua client-side routes akan serve index.html
        """
        # Skip if it's an API route (already handled by routers)
        if full_path.startswith("api/") or full_path.startswith("api"):
            logger.warning(f"API endpoint not found: /{full_path}")
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # Check if it's a static file request
        static_file = FRONTEND_BUILD_PATH / full_path
        if static_file.exists() and static_file.is_file():
            return FileResponse(static_file)
        
        # Serve index.html untuk semua SPA routes
        # This handles: /login, /register, /dashboard, /auth/callback, etc.
        index_path = FRONTEND_BUILD_PATH / "index.html"
        if index_path.exists():
            logger.info(f"Serving SPA for route: /{full_path}")
            return FileResponse(index_path, media_type="text/html")
        
        logger.error("Frontend index.html not found")
        raise HTTPException(status_code=404, detail="Frontend not found")
    
    logger.info("✓ SPA fallback routing configured")
else:
    logger.warning(f"✗ Frontend build NOT found at: {FRONTEND_BUILD_PATH}")
    logger.warning("⚠️  SPA routing will not work! Frontend must be built and deployed separately.")
    
    # Add fallback route when no frontend is built
    @app.get("/{full_path:path}")
    async def no_frontend_fallback(request: Request, full_path: str):
        """Fallback when frontend is not built"""
        if full_path.startswith("api/") or full_path.startswith("api"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Frontend not deployed",
                "message": "Please build the frontend first using 'npm run build'",
                "path": f"/{full_path}"
            }
        )

# --- 13. LOG ALL ROUTES ON STARTUP ---
@app.on_event("startup")
async def log_routes():
    """Log all registered routes for debugging"""
    logger.info("=" * 80)
    logger.info("REGISTERED ROUTES:")
    logger.info("=" * 80)
    
    routes_by_path = {}
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            path = route.path
            methods = ', '.join(sorted(route.methods))
            if path not in routes_by_path:
                routes_by_path[path] = []
            routes_by_path[path].append(methods)
    
    for path in sorted(routes_by_path.keys()):
        methods = ', '.join(routes_by_path[path])
        logger.info(f"  {methods:20} {path}")
    
    logger.info("=" * 80)
    logger.info(f"Total routes: {len(routes_by_path)}")
    logger.info(f"Frontend build path: {FRONTEND_BUILD_PATH}")
    logger.info(f"Frontend exists: {FRONTEND_BUILD_PATH.exists()}")
    logger.info("=" * 80)