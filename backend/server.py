from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio

# --- 1. KONFIGURASI ENV (FIXED) ---
# Mengambil path folder backend saat ini
BACKEND_DIR = Path(__file__).resolve().parent
# Naik satu level ke root, lalu masuk ke frontend/.env
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

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

# Create router
api_router = APIRouter(prefix="/api")

# Global variables for background tasks
scraping_in_progress = False
last_scraping_time = None

# --- 6. EVENT HANDLERS (STARTUP/SHUTDOWN) ---
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    global ai_analyzer
    try:
        # Initialize database collections
        await policy_db.init_collections()
        logger.info("Connected to MongoDB Atlas successfully")
        
        # Initialize AI Analyzer with RAW database object (not PolicyDatabase wrapper)
        # PolicyAnalyzer expects AsyncIOMotorDatabase
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

# --- 7. ROUTES / ENDPOINTS ---

@api_router.get("/")
async def root():
    return {"message": "AI Policy & Insight Generator API is running", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    try:
        stats = await policy_db.get_database_stats()
        return {
            "status": "healthy",
            "database": "connected",
            "ai_analyzer": "ready" if ai_analyzer else "not_initialized",
            "scraping_status": "in_progress" if scraping_in_progress else "idle",
            "last_scraping": last_scraping_time,
            "data_stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Service unhealthy")

@api_router.post("/chat", response_model=PolicyAnalysisResponse)
async def analyze_policy(request: PolicyAnalysisRequest, background_tasks: BackgroundTasks):
    try:
        if not ai_analyzer:
            raise HTTPException(status_code=503, detail="AI Analyzer not initialized")
        
        # Get or create session
        session_id = request.session_id
        if not session_id:
            session = await policy_db.create_chat_session()
            session_id = session.id
        else:
            existing_session = await policy_db.get_chat_session(session_id)
            if not existing_session:
                session = await policy_db.create_chat_session()
                session_id = session.id

        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            sender="user",
            content=request.message
        )
        await policy_db.save_chat_message(user_message)
        
        # ========================================
        # MULTI-AGENT ANALYSIS
        # Data diambil langsung dari initial_data collection
        # ========================================
        
        # Analyze with AI using multi-agent system
        analysis_result = await ai_analyzer.analyze_policy_query(
            query=request.message,
            language="Indonesian",
            scraped_data=None  # Not used - agents get data from initial_data
        )
        
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
        
    except Exception as e:
        logger.error(f"Error in policy analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error analyzing policy: {str(e)}")

@api_router.get("/sessions", response_model=List[ChatSession])
async def get_chat_sessions():
    try:
        sessions = await policy_db.get_chat_sessions(limit=20)
        return sessions
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching sessions")

@api_router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str):
    try:
        session = await policy_db.get_chat_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error fetching session")

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

@api_router.get("/report/{session_id}/{format}")
async def generate_report(session_id: str, format: str):
    try:
        if format not in ['pdf', 'docx']:
            raise HTTPException(status_code=400, detail="Format must be 'pdf' or 'docx'")
        
        session = await policy_db.get_chat_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        if format == 'pdf':
            buffer = report_generator.generate_pdf(session)
            media_type = 'application/pdf'
            filename = f"Laporan_Sensus_{session_id[:8]}.pdf"
        else:
            buffer = report_generator.generate_docx(session)
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            filename = f"Laporan_Sensus_{session_id[:8]}.docx"
        
        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

# --- 8. REGISTER ROUTERS ---
app.include_router(api_router)

# Try to include auth router if available
try:
    from auth_routes import router as auth_router
    app.include_router(auth_router)
    logger.info("Auth routes registered")
except ImportError:
    logger.warning("Auth routes not available")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[
        "https://smart-se26-agentic-ai-chatbot-web.onrender.com",
        "http://localhost:3000"
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)