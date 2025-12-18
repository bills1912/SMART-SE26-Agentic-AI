from motor.motor_asyncio import AsyncIOMotorClient
from models import ScrapedData, ChatSession, ChatMessage, PolicyInsight, PolicyRecommendation
import os
import logging
from datetime import datetime
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class PolicyDatabase:
    def __init__(self, mongo_url: str, db_name: str):
        # Optimized connection settings for better performance and reliability
        self.client = AsyncIOMotorClient(
            mongo_url,
            serverSelectionTimeoutMS=30000,  # 30 seconds for initial connection
            connectTimeoutMS=30000,          # 30 seconds connection timeout
            socketTimeoutMS=60000,           # 60 seconds socket timeout for operations
            maxPoolSize=50,                  # Connection pool size
            minPoolSize=5,                   # Minimum connections to maintain
            maxIdleTimeMS=60000,             # Close idle connections after 60s
            retryWrites=True,                # Retry failed writes
            retryReads=True,                 # Retry failed reads
            waitQueueTimeoutMS=30000,        # Wait for connection from pool
            uuidRepresentation='standard'
        )
        self.db = self.client[db_name]
        self._connected = False
        
    async def init_collections(self):
        """Initialize database collections with indexes"""
        try:
            # Test connection with ping
            await self.client.admin.command('ping')
            self._connected = True
            logger.info("Successfully connected to MongoDB Atlas")

            # Create indexes for better performance (run in background)
            try:
                await self.db.scraped_data.create_index("source", background=True)
                await self.db.scraped_data.create_index("category", background=True)
                await self.db.scraped_data.create_index("scraped_at", background=True)
                
                # Text search index
                try:
                    await self.db.scraped_data.create_index(
                        [("title", "text"), ("content", "text")],
                        background=True
                    )
                except Exception as e:
                    # Text index might already exist
                    logger.debug(f"Text index already exists or error: {e}")
                
                # Chat session indexes - UPDATED with user_id
                await self.db.chat_sessions.create_index("user_id", background=True)  # NEW
                await self.db.chat_sessions.create_index("created_at", background=True)
                await self.db.chat_sessions.create_index("updated_at", background=True)
                await self.db.chat_sessions.create_index(
                    [("user_id", 1), ("updated_at", -1)], 
                    background=True
                )  # Compound index for efficient user session queries
                
                await self.db.chat_messages.create_index("session_id", background=True)
                await self.db.chat_messages.create_index("timestamp", background=True)
                
                # Auth indexes - critical for login performance
                await self.db.users.create_index("email", unique=True, background=True)
                await self.db.users.create_index("user_id", unique=True, background=True)
                await self.db.user_sessions.create_index("session_token", unique=True, background=True)
                await self.db.user_sessions.create_index("user_id", background=True)
                await self.db.user_sessions.create_index("expires_at", background=True)
                
                logger.info("Database indexes created/verified")
            except Exception as e:
                logger.warning(f"Error creating some indexes (may already exist): {e}")
                
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise e

    @property
    def is_connected(self) -> bool:
        return self._connected

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
            # Try text search first
            text_query = {"$text": {"$search": query}}
            
            try:
                cursor = self.db.scraped_data.find(text_query).limit(limit)
                data = await cursor.to_list(length=limit)
                if data:
                    return [ScrapedData(**item) for item in data]
            except Exception:
                pass  # Text index might not exist
            
            # Fallback to regex search
            regex_query = {
                "$or": [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"content": {"$regex": query, "$options": "i"}}
                ]
            }
            cursor = self.db.scraped_data.find(regex_query).sort("scraped_at", -1).limit(limit)
            data = await cursor.to_list(length=limit)
            return [ScrapedData(**item) for item in data]
            
        except Exception as e:
            logger.error(f"Error searching scraped data: {e}")
            return []

    # ============================================
    # CHAT SESSION OPERATIONS - UPDATED WITH USER_ID
    # ============================================
    
    async def create_chat_session(self, title: str = "Policy Analysis Session", user_id: Optional[str] = None) -> ChatSession:
        """
        Create a new chat session for a specific user
        
        Args:
            title: Session title
            user_id: User ID who owns this session (None for anonymous/legacy)
        """
        try:
            session = ChatSession(title=title, user_id=user_id)
            await self.db.chat_sessions.insert_one(session.dict())
            logger.info(f"Created chat session {session.id} for user {user_id or 'anonymous'}")
            return session
        except Exception as e:
            logger.error(f"Error creating chat session: {e}")
            raise

    async def get_chat_session(self, session_id: str, user_id: Optional[str] = None) -> Optional[ChatSession]:
        """
        Get chat session by ID, optionally verifying user ownership
        
        Args:
            session_id: Session ID to fetch
            user_id: If provided, verify the session belongs to this user
        """
        try:
            query = {"id": session_id}
            
            # If user_id provided, add ownership check
            if user_id:
                query["user_id"] = user_id
            
            session_data = await self.db.chat_sessions.find_one(query)
            
            if session_data:
                return ChatSession(**session_data)
            return None
        except Exception as e:
            logger.error(f"Error fetching chat session: {e}")
            return None

    async def save_chat_message(self, message: ChatMessage) -> bool:
        """
        Save a chat message DIRECTLY into the session document (Embedded Pattern).
        """
        try:
            # 1. Konversi pesan ke dictionary
            message_dict = message.dict()
            
            # 2. Pastikan timestamp dalam format string ISO
            if 'timestamp' in message_dict and isinstance(message_dict['timestamp'], datetime):
                message_dict['timestamp'] = message_dict['timestamp'].isoformat()
            
            # 3. Gunakan $push untuk memasukkan pesan ke dalam array 'messages'
            result = await self.db.chat_sessions.update_one(
                {"id": message.session_id},
                {
                    "$push": {"messages": message_dict},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                return True
            else:
                logger.warning(f"Session {message.session_id} not found when saving message.")
                return False
                
        except Exception as e:
            logger.error(f"Error saving chat message: {e}")
            return False

    async def get_chat_sessions(self, limit: int = 10, user_id: Optional[str] = None) -> List[ChatSession]:
        """
        Get recent chat sessions for a specific user
        
        Args:
            limit: Maximum number of sessions to return
            user_id: Filter sessions by user (required for user-specific queries)
        """
        try:
            # Build query based on user_id
            query = {}
            if user_id:
                query["user_id"] = user_id
            else:
                # For backwards compatibility: if no user_id, only return sessions without user_id
                # This prevents leaking other users' sessions
                query["user_id"] = {"$exists": False}
            
            cursor = self.db.chat_sessions.find(query).sort("updated_at", -1).limit(limit)
            sessions_data = await cursor.to_list(length=limit)
            
            sessions = []
            for session_data in sessions_data:
                # Count embedded messages instead of separate collection
                message_count = len(session_data.get("messages", []))
                session_data["message_count"] = message_count
                sessions.append(ChatSession(**session_data))
            
            logger.info(f"Fetched {len(sessions)} sessions for user {user_id or 'anonymous'}")
            return sessions
        except Exception as e:
            logger.error(f"Error fetching chat sessions: {e}")
            return []

    async def delete_chat_session(self, session_id: str, user_id: Optional[str] = None) -> bool:
        """
        Delete a single chat session with optional user ownership verification
        
        Args:
            session_id: Session ID to delete
            user_id: If provided, verify the session belongs to this user before deleting
        """
        try:
            query = {"id": session_id}
            
            # If user_id provided, add ownership check (prevents deleting other users' sessions)
            if user_id:
                query["user_id"] = user_id
            
            result = await self.db.chat_sessions.delete_one(query)
            
            if result.deleted_count > 0:
                logger.info(f"Deleted session {session_id} for user {user_id or 'any'}")
                return True
            else:
                logger.warning(f"Session {session_id} not found or not owned by user {user_id}")
                return False
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False

    async def delete_chat_sessions(self, session_ids: List[str], user_id: Optional[str] = None) -> int:
        """
        Delete multiple chat sessions (Bulk) with optional user ownership verification
        
        Args:
            session_ids: List of session IDs to delete
            user_id: If provided, only delete sessions belonging to this user
        """
        try:
            query = {"id": {"$in": session_ids}}
            
            # If user_id provided, add ownership check
            if user_id:
                query["user_id"] = user_id
            
            result = await self.db.chat_sessions.delete_many(query)
            logger.info(f"Bulk deleted {result.deleted_count} sessions for user {user_id or 'any'}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error bulk deleting sessions: {e}")
            return 0

    async def delete_all_chat_sessions(self, user_id: Optional[str] = None) -> int:
        """
        Delete ALL chat sessions for a specific user
        
        Args:
            user_id: If provided, only delete sessions belonging to this user
                     If None, deletes ALL sessions (admin operation)
        """
        try:
            query = {}
            
            # If user_id provided, only delete that user's sessions
            if user_id:
                query["user_id"] = user_id
            
            result = await self.db.chat_sessions.delete_many(query)
            logger.info(f"Deleted all {result.deleted_count} sessions for user {user_id or 'ALL USERS'}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting all sessions: {e}")
            return 0

    async def verify_session_ownership(self, session_id: str, user_id: str) -> bool:
        """
        Verify that a session belongs to a specific user
        
        Args:
            session_id: Session ID to check
            user_id: User ID to verify ownership
            
        Returns:
            True if the session belongs to the user, False otherwise
        """
        try:
            session = await self.db.chat_sessions.find_one(
                {"id": session_id, "user_id": user_id},
                {"_id": 0, "id": 1}  # Only fetch id field for efficiency
            )
            return session is not None
        except Exception as e:
            logger.error(f"Error verifying session ownership: {e}")
            return False

    async def migrate_anonymous_sessions_to_user(self, user_id: str, session_ids: List[str]) -> int:
        """
        Migrate anonymous sessions to a user (for users who created sessions before logging in)
        
        Args:
            user_id: User ID to assign sessions to
            session_ids: List of session IDs to migrate
            
        Returns:
            Number of sessions migrated
        """
        try:
            result = await self.db.chat_sessions.update_many(
                {
                    "id": {"$in": session_ids},
                    "user_id": {"$exists": False}  # Only migrate anonymous sessions
                },
                {"$set": {"user_id": user_id}}
            )
            logger.info(f"Migrated {result.modified_count} sessions to user {user_id}")
            return result.modified_count
        except Exception as e:
            logger.error(f"Error migrating sessions: {e}")
            return 0

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
            stats["users_count"] = await self.db.users.count_documents({})
            stats["active_sessions_count"] = await self.db.user_sessions.count_documents({})
            
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
            self._connected = False
            logger.info("Database connection closed")

        
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