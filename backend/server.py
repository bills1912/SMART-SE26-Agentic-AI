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
from web_scraper import PolicyDataScraper
from auth_routes import router as auth_router
from report_generator import ReportGenerator
# Import data_sources untuk trigger scraping manual/otomatis
from data_sources import populate_real_data

# --- 4. INISIALISASI DATABASE & AI (CRITICAL FIX) ---
# Mengambil URL dari environment variable
mongo_url = os.environ.get('MONGO_URL')
db_name = os.environ.get('DB_NAME', 'policy_db')

if not mongo_url:
    logger.error("CRITICAL: MONGO_URL not found in .env file!")
    raise ValueError("MONGO_URL is not set. Please check your .env file.")

# Inisialisasi Database Object (Global Variable)
# Ini yang sebelumnya hilang sehingga menyebabkan error
policy_db = PolicyDatabase(mongo_url, db_name)

# Inisialisasi AI & Report Generator
ai_analyzer = PolicyAIAnalyzer()
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
    try:
        # Ini akan otomatis membuat koleksi dan index di MongoDB Atlas Anda
        await policy_db.init_collections()
        logger.info("Application started & Connected to MongoDB Atlas successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")

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
            "ai_analyzer": "ready",
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
        
        # Get relevant data
        scraped_data = await policy_db.search_scraped_data(request.message, limit=20)
        
        # Analyze with AI
        analysis_result = await ai_analyzer.analyze_policy_query(
            request.message,
            session_id,
            scraped_data
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
            await policy_db.save_policy_recommendations(analysis_result['policies'])
        
        # Trigger background scraping if idle
        if not scraping_in_progress:
            background_tasks.add_task(trigger_data_scraping)
        
        return PolicyAnalysisResponse(
            message=analysis_result['message'],
            session_id=session_id,
            visualizations=analysis_result.get('visualizations', []),
            insights=analysis_result.get('insights', []),
            policies=analysis_result.get('policies', []),
            supporting_data_count=analysis_result.get('supporting_data_count', 0)
        )
        
    except Exception as e:
        logger.error(f"Error in policy analysis: {e}")
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
    global scraping_in_progress
    if scraping_in_progress:
        return {"message": "Scraping already in progress", "status": "in_progress"}
    
    background_tasks.add_task(trigger_data_scraping)
    return {"message": "Scraping triggered", "status": "started"}

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
        stats["scraping_status"] = "in_progress" if scraping_in_progress else "idle"
        stats["last_scraping"] = last_scraping_time
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

# --- 8. BACKGROUND TASKS ---
async def trigger_data_scraping():
    """Background task to collect real data"""
    global scraping_in_progress, last_scraping_time
    try:
        scraping_in_progress = True
        logger.info("Starting real data collection...")
        
        # 1. Try web scraping (Basic)
        async with PolicyDataScraper() as scraper:
            scraped_data = await scraper.scrape_all_sources()
            if scraped_data:
                await policy_db.save_scraped_data(scraped_data)

        # 2. Get real data from API/Sources (Robust)
        real_data_count = await populate_real_data()
        
        logger.info(f"Data collection completed. Real data points added: {real_data_count}")
        
        from datetime import datetime
        last_scraping_time = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"Error in data collection: {e}")
    finally:
        scraping_in_progress = False

# --- 9. REGISTER ROUTERS ---
app.include_router(api_router)
app.include_router(auth_router)

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