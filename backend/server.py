from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio

# --- 1. KONFIGURASI ENV ---
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

# --- 2. LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 3. SETUP APLIKASI FASTAPI ---
app = FastAPI(title="AI Policy & Insight Generator", version="1.0.0")

# --- 4. CORS MIDDLEWARE (PENTING: SEBELUM SEMUA MIDDLEWARE LAIN) ---
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

# --- 5. IMPORT CUSTOM MODULES ---
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

# --- 6. INISIALISASI DATABASE & AI ---
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'policy_db')

if not mongo_url:
    logger.error("CRITICAL: MONGO_URL not found in .env file!")
    raise ValueError("MONGO_URL is not set. Please check your .env file.")

policy_db = PolicyDatabase(mongo_url, db_name)
ai_analyzer = None
report_generator = ReportGenerator()

# Global variables
scraping_in_progress = False
last_scraping_time = None

# --- 7. EVENT HANDLERS ---
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    global ai_analyzer
    try:
        await policy_db.init_collections()
        logger.info("Connected to MongoDB Atlas successfully")
        
        ai_analyzer = PolicyAIAnalyzer(policy_db.db)
        logger.info("AI Analyzer initialized successfully")
        
    except Exception as e:
        logger.error(f"Error during startup: {e}", exc_info=True)
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    try:
        await policy_db.close()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# --- 8. API ROUTER ---
api_router = APIRouter(prefix="/api")

# --- 9. API ENDPOINTS ---
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

# ... (sisanya dari API routes kamu, chat, sessions, dll)

# --- 10. REGISTER API ROUTER ---
app.include_router(api_router)

# --- 11. REGISTER AUTH ROUTER ---
try:
    from auth_routes import router as auth_router
    app.include_router(auth_router)
    logger.info("✓ Auth routes registered successfully")
except ImportError as e:
    logger.error(f"✗ Failed to import auth routes: {e}")
except Exception as e:
    logger.error(f"✗ Error registering auth routes: {e}")

# --- 12. STATIC FILES & SPA FALLBACK (CRITICAL FIX) ---
# Path ke frontend build
FRONTEND_BUILD_PATH = BACKEND_DIR.parent / "frontend" / "build"

# Check if frontend build exists
if FRONTEND_BUILD_PATH.exists():
    logger.info(f"✓ Frontend build found at: {FRONTEND_BUILD_PATH}")
    
    # Serve static files (JS, CSS, images, etc)
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_BUILD_PATH / "static")),
        name="static"
    )
    
    # SPA Fallback - Serve index.html untuk semua routes yang tidak match
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Catch-all route untuk serve React SPA.
        Semua client-side routes (/login, /dashboard, dll) akan serve index.html
        """
        # Jangan intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        
        # Serve file statis jika ada (favicon, manifest, dll)
        file_path = FRONTEND_BUILD_PATH / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Fallback ke index.html untuk semua route lainnya
        index_path = FRONTEND_BUILD_PATH / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Frontend not found")
else:
    logger.warning(f"✗ Frontend build NOT found at: {FRONTEND_BUILD_PATH}")
    logger.warning("SPA routing will not work in production!")

# --- 13. ROOT ENDPOINT (BEFORE SPA FALLBACK) ---
@app.get("/", include_in_schema=True)
async def root():
    """Root endpoint - health check"""
    return {
        "message": "AI Policy & Insight Generator API", 
        "version": "1.0.0",
        "status": "online",
        "endpoints": {
            "api": "/api",
            "health": "/api/health",
            "auth": "/api/auth/me"
        }
    }

# --- 14. LOG ALL ROUTES ON STARTUP ---
@app.on_event("startup")
async def log_routes():
    """Log all registered routes for debugging"""
    logger.info("=" * 60)
    logger.info("REGISTERED ROUTES:")
    logger.info("=" * 60)
    for route in app.routes:
        if hasattr(route, 'methods'):
            methods = ', '.join(route.methods)
            logger.info(f"{methods:10} {route.path}")
    logger.info("=" * 60)