from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio

# Import our custom modules
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize database
mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
policy_db = PolicyDatabase(mongo_url, db_name)

# Initialize AI analyzer
ai_analyzer = PolicyAIAnalyzer()

# Create the main app
app = FastAPI(title="AI Policy & Insight Generator", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Global variables for background tasks
scraping_in_progress = False
last_scraping_time = None


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup"""
    try:
        await policy_db.init_collections()
        logger.info("Application started successfully")
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


# Health check endpoints
@api_router.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "AI Policy & Insight Generator API is running", "version": "1.0.0"}


@api_router.get("/health")
async def health_check():
    """Comprehensive health check"""
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


# Chat endpoints
@api_router.post("/chat", response_model=PolicyAnalysisResponse)
async def analyze_policy(request: PolicyAnalysisRequest, background_tasks: BackgroundTasks):
    """Main policy analysis endpoint"""
    try:
        logger.info(f"Received policy analysis request: {request.message[:100]}...")
        
        # Get or create session
        session_id = request.session_id
        if not session_id:
            # Create new session
            session = await policy_db.create_chat_session()
            session_id = session.id
        else:
            # Verify session exists
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
        
        # Get relevant scraped data for analysis
        scraped_data = await policy_db.search_scraped_data(request.message, limit=20)
        if not scraped_data:
            scraped_data = await policy_db.get_recent_scraped_data(limit=20)
        
        # Perform AI analysis
        analysis_result = await ai_analyzer.analyze_policy_query(
            request.message,
            session_id,
            scraped_data
        )
        
        # Create AI response message
        ai_message = ChatMessage(
            session_id=session_id,
            sender="ai",
            content=analysis_result['message'],
            visualizations=analysis_result.get('visualizations', []),
            insights=analysis_result.get('insights', []),
            policies=analysis_result.get('policies', [])
        )
        
        # Save AI message to database
        await policy_db.save_chat_message(ai_message)
        
        # Save policy recommendations if any
        if analysis_result.get('policies'):
            await policy_db.save_policy_recommendations(analysis_result['policies'])
        
        # Trigger background data scraping if needed
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
        raise HTTPException(
            status_code=500, 
            detail=f"Error analyzing policy: {str(e)}"
        )


@api_router.get("/sessions", response_model=List[ChatSession])
async def get_chat_sessions():
    """Get recent chat sessions"""
    try:
        sessions = await policy_db.get_chat_sessions(limit=20)
        return sessions
    except Exception as e:
        logger.error(f"Error fetching sessions: {e}")
        raise HTTPException(status_code=500, detail="Error fetching sessions")


@api_router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(session_id: str):
    """Get specific chat session"""
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


# Data scraping endpoints
@api_router.post("/scrape/trigger")
async def trigger_scraping(background_tasks: BackgroundTasks):
    """Trigger data scraping manually"""
    global scraping_in_progress
    
    if scraping_in_progress:
        return {"message": "Scraping already in progress", "status": "in_progress"}
    
    background_tasks.add_task(trigger_data_scraping)
    return {"message": "Scraping triggered", "status": "started"}


@api_router.get("/data/recent", response_model=List[ScrapedData])
async def get_recent_data(limit: int = 50, category: Optional[str] = None):
    """Get recent scraped data"""
    try:
        data = await policy_db.get_recent_scraped_data(limit=limit, category=category)
        return data
    except Exception as e:
        logger.error(f"Error fetching recent data: {e}")
        raise HTTPException(status_code=500, detail="Error fetching data")


@api_router.get("/data/search", response_model=List[ScrapedData])
async def search_data(query: str, limit: int = 50):
    """Search scraped data"""
    try:
        data = await policy_db.search_scraped_data(query, limit=limit)
        return data
    except Exception as e:
        logger.error(f"Error searching data: {e}")
        raise HTTPException(status_code=500, detail="Error searching data")


@api_router.get("/stats")
async def get_stats():
    """Get application statistics"""
    try:
        stats = await policy_db.get_database_stats()
        stats["scraping_status"] = "in_progress" if scraping_in_progress else "idle"
        stats["last_scraping"] = last_scraping_time
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Error getting statistics")


# Background task functions
async def trigger_data_scraping():
    """Background task to collect real data from reliable sources"""
    global scraping_in_progress, last_scraping_time
    
    try:
        scraping_in_progress = True
        logger.info("Starting real data collection...")
        
        # Try web scraping first (may be blocked)
        async with PolicyDataScraper() as scraper:
            scraped_data = await scraper.scrape_all_sources()
        
        # Always add real data from reliable sources
        from data_sources import populate_real_data
        real_data_count = await populate_real_data()
        
        total_saved = len(scraped_data) + real_data_count
        
        if total_saved > 0:
            logger.info(f"Data collection completed. Saved {total_saved} items ({real_data_count} from reliable sources).")
        else:
            logger.warning("Limited data collection - using fallback data sources")
        
        from datetime import datetime
        last_scraping_time = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"Error in data collection: {e}")
        # Fallback to basic real data
        try:
            from data_sources import populate_real_data
            fallback_count = await populate_real_data()
            logger.info(f"Fallback data collection: {fallback_count} items saved")
        except Exception as fallback_error:
            logger.error(f"Fallback data collection also failed: {fallback_error}")
    finally:
        scraping_in_progress = False


# Include the router in the main app
app.include_router(api_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
