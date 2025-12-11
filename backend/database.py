from motor.motor_asyncio import AsyncIOMotorClient
from models import ScrapedData, ChatSession, ChatMessage, PolicyInsight, PolicyRecommendation
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class PolicyDatabase:
    def __init__(self, mongo_url: str, db_name: str):
        # Menambahkan timeout server selection agar tidak hang jika koneksi lambat
        self.client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=5000,
            uuidRepresentation='standard'
        )
        self.db = self.client[db_name]
        
    async def init_collections(self):
        """Initialize database collections with indexes"""
        try:
            # Cek koneksi terlebih dahulu
            await self.client.admin.command('ping')
            logger.info("Successfully connected to MongoDB Atlas")

            # Create indexes for better performance
            await self.db.scraped_data.create_index("source")
            await self.db.scraped_data.create_index("category") 
            await self.db.scraped_data.create_index("scraped_at")
            # Index text search untuk pencarian konten
            await self.db.scraped_data.create_index([("title", "text"), ("content", "text")])
            
            await self.db.chat_sessions.create_index("created_at")
            await self.db.chat_messages.create_index("session_id")
            await self.db.chat_messages.create_index("timestamp")
            
            logger.info("Database collections initialized")
        except Exception as e:
            logger.error(f"Error connecting or initializing database: {e}")
            raise e

    # Scraped Data operations
    async def save_scraped_data(self, data: List[ScrapedData]) -> int:
        """Save scraped data to database"""
        try:
            if not data:
                return 0
            
            data_dicts = []
            for item in data:
                item_dict = item.dict()
                if 'scraped_at' in item_dict and hasattr(item_dict['scraped_at'], 'isoformat'):
                    item_dict['scraped_at'] = item_dict['scraped_at'].isoformat()
                data_dicts.append(item_dict)
            
            # Use insert_many with ordered=False to continue on duplicates
            result = await self.db.scraped_data.insert_many(data_dicts, ordered=False)
            logger.info(f"Saved {len(result.inserted_ids)} scraped items to database")
            return len(result.inserted_ids)
            
        except Exception as e:
            # Handle bulk write errors specifically
            if hasattr(e, 'details') and 'nInserted' in e.details:
                inserted = e.details['nInserted']
                if inserted > 0:
                    logger.info(f"Saved {inserted} items (some failed due to duplicates)")
                    return inserted
            
            logger.error(f"Error saving scraped data: {e}")
            return 0

    async def get_recent_scraped_data(self, limit: int = 100, category: Optional[str] = None) -> List[ScrapedData]:
        """Get recent scraped data"""
        try:
            query = {}
            if category:
                query["category"] = category
                
            cursor = self.db.scraped_data.find(query).sort("scraped_at", -1).limit(limit)
            data = await cursor.to_list(length=limit)
            return [ScrapedData(**item) for item in data]
        except Exception as e:
            logger.error(f"Error fetching scraped data: {e}")
            return []

    async def search_scraped_data(self, query: str, limit: int = 50) -> List[ScrapedData]:
        """Search scraped data by text"""
        try:
            # Menggunakan text index yang lebih efisien jika tersedia
            text_query = {
                "$text": {"$search": query}
            }
            # Fallback ke regex jika text index belum siap atau query spesifik
            regex_query = {
                "$or": [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"content": {"$regex": query, "$options": "i"}}
                ]
            }
            
            try:
                cursor = self.db.scraped_data.find(text_query).limit(limit)
                data = await cursor.to_list(length=limit)
                if not data:
                    raise Exception("No text match")
            except:
                cursor = self.db.scraped_data.find(regex_query).sort("scraped_at", -1).limit(limit)
                data = await cursor.to_list(length=limit)

            return [ScrapedData(**item) for item in data]
        except Exception as e:
            logger.error(f"Error searching scraped data: {e}")
            return []

    # Chat Session operations
    async def create_chat_session(self, title: str = "Policy Analysis Session") -> ChatSession:
        """Create a new chat session"""
        try:
            session = ChatSession(title=title)
            await self.db.chat_sessions.insert_one(session.dict())
            return session
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise

    async def get_chat_session(self, session_id: str) -> Optional[ChatSession]:
        """Get chat session by ID"""
        try:
            session_data = await self.db.chat_sessions.find_one({"id": session_id})
            if session_data:
                messages_cursor = self.db.chat_messages.find({"session_id": session_id}).sort("timestamp", 1)
                messages_data = await messages_cursor.to_list(length=1000)
                messages = [ChatMessage(**msg) for msg in messages_data]
                
                session_data["messages"] = messages
                return ChatSession(**session_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching chat session: {e}")
            return None

    async def save_chat_message(self, message: ChatMessage) -> bool:
        """Save a chat message"""
        try:
            await self.db.chat_messages.insert_one(message.dict())
            await self.db.chat_sessions.update_one(
                {"id": message.session_id},
                {"$set": {"updated_at": datetime.utcnow()}}
            )
            return True
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")
            return False

    async def get_chat_sessions(self, limit: int = 10) -> List[ChatSession]:
        """Get recent chat sessions"""
        try:
            cursor = self.db.chat_sessions.find().sort("updated_at", -1).limit(limit)
            sessions_data = await cursor.to_list(length=limit)
            
            sessions = []
            for session_data in sessions_data:
                message_count = await self.db.chat_messages.count_documents({"session_id": session_data["id"]})
                session_data["message_count"] = message_count
                sessions.append(ChatSession(**session_data))
            
            return sessions
        except Exception as e:
            logger.error(f"Error fetching chat sessions: {e}")
            return []

    # Policy data operations
    async def save_policy_insights(self, insights: List[PolicyInsight]) -> int:
        """Save policy insights"""
        try:
            if not insights:
                return 0
            insights_dicts = [insight.dict() for insight in insights]
            result = await self.db.policy_insights.insert_many(insights_dicts)
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"Error saving policy insights: {e}")
            return 0

    async def save_policy_recommendations(self, recommendations: List[PolicyRecommendation]) -> int:
        """Save policy recommendations"""
        try:
            if not recommendations:
                return 0
            recs_dicts = [rec.dict() for rec in recommendations]
            result = await self.db.policy_recommendations.insert_many(recs_dicts)
            return len(result.inserted_ids)
        except Exception as e:
            logger.error(f"Error saving policy recommendations: {e}")
            return 0

    async def get_database_stats(self) -> dict:
        """Get database statistics"""
        try:
            stats = {}
            stats["scraped_data_count"] = await self.db.scraped_data.count_documents({})
            stats["chat_sessions_count"] = await self.db.chat_sessions.count_documents({})
            stats["chat_messages_count"] = await self.db.chat_messages.count_documents({})
            stats["policy_insights_count"] = await self.db.policy_insights.count_documents({})
            stats["policy_recommendations_count"] = await self.db.policy_recommendations.count_documents({})
            
            recent_scraping = await self.db.scraped_data.find().sort("scraped_at", -1).limit(1).to_list(length=1)
            if recent_scraping:
                stats["last_scraping"] = recent_scraping[0]["scraped_at"]
            
            return stats
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    async def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()

# Dependency for FastAPI routes
_db_instance = None

async def get_database():
    """Get database instance for dependency injection"""
    global _db_instance
    if _db_instance is None:
        mongo_url = os.environ.get('MONGO_URL')
        if not mongo_url:
            raise ValueError("MONGO_URL not found in environment variables")
            
        db_name = os.environ.get('DB_NAME', 'policy_db')
        _db_instance = PolicyDatabase(mongo_url, db_name)
        await _db_instance.init_collections()
    return _db_instance.db