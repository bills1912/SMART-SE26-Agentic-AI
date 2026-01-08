"""
PolicyAIAnalyzer with DS-STAR Framework Integration
====================================================
Optimized version yang menggunakan DS-STAR framework untuk
analisis data science yang lebih robust dan terverifikasi.

Key Improvements:
1. Iterative Planning & Verification
2. LLM-as-Judge untuk memastikan kecukupan plan
3. Automatic debugging untuk error recovery
4. Data file analysis untuk konteks yang lebih baik
"""

import os
import logging
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Import DS-STAR components
from dsstar_agents import (
    DSStarOrchestrator,
    DataFileAnalyzerAgent,
    KBLI_MAPPING,
    KBLI_SHORT_NAMES
)

logger = logging.getLogger(__name__)

# Load environment
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)


class PolicyAIAnalyzer:
    """
    Enhanced Policy Analyzer with DS-STAR Framework.
    
    Menggunakan iterative planning dan verification untuk memastikan
    hasil analisis yang akurat dan komprehensif.
    
    Features:
    - Automatic data structure analysis
    - Iterative plan refinement with LLM-as-Judge
    - Robust error handling with debugging agent
    - Advanced visualizations (Heatmap, Treemap, Radar)
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Initialize Gemini for direct use (conversational, etc.)
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            model_name = os.environ.get('LLM_MODEL', 'gemini-2.0-flash-exp')
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini initialized with model: {model_name}")
        else:
            logger.warning("No Gemini API key found")
            self.model = None
        
        # Initialize DS-STAR Orchestrator
        self.dsstar = DSStarOrchestrator(db)
        
        # Cache for data description
        self._data_description = None
        
        logger.info("PolicyAIAnalyzer initialized with DS-STAR framework")
    
    async def analyze_policy_query(
        self,
        query: str,
        language: str = "Indonesian",
        scraped_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main analysis endpoint using DS-STAR framework.
        
        DS-STAR Process:
        1. Data File Analysis - Understand data structure
        2. Initial Plan Creation - Create first executable step
        3. Iterative Execution - Execute and verify plan
        4. Plan Refinement - Add/modify steps based on verification
        5. Final Response - Generate comprehensive answer
        
        Args:
            query: User's question in natural language
            language: Response language (default: Indonesian)
            scraped_data: Optional scraped data (not used in DS-STAR)
        
        Returns:
            Dict with message, visualizations, insights, policies
        """
        try:
            logger.info(f"DS-STAR Analysis: {query[:50]}...")
            
            # Use DS-STAR orchestrator for analysis
            result = await self.dsstar.analyze(query, language)
            
            # Log analysis metrics
            logger.info(
                f"DS-STAR Complete: "
                f"viz={len(result.get('visualizations', []))}, "
                f"insights={len(result.get('insights', []))}, "
                f"policies={len(result.get('policies', []))}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"DS-STAR Analysis Error: {e}", exc_info=True)
            
            # Fallback to simple response
            return {
                'message': f"Maaf, terjadi kesalahan dalam analisis. Silakan coba lagi. Error: {str(e)}",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
    
    async def get_data_context(self) -> Dict[str, Any]:
        """
        Get current data context from DS-STAR analyzer.
        Useful for debugging and monitoring.
        """
        try:
            if not self._data_description:
                self._data_description = await self.dsstar.analyzer.analyze_data_structure()
            
            return {
                'collection': self._data_description.collection_name,
                'document_count': self._data_description.document_count,
                'provinces': self._data_description.available_provinces,
                'sectors': self._data_description.available_sectors,
                'statistics': self._data_description.field_statistics,
                'summary': self._data_description.summary
            }
        except Exception as e:
            logger.error(f"Error getting data context: {e}")
            return {'error': str(e)}
    
    async def refresh_data_context(self) -> bool:
        """Force refresh of data context cache."""
        try:
            self._data_description = await self.dsstar.analyzer.analyze_data_structure(
                force_refresh=True
            )
            return True
        except Exception as e:
            logger.error(f"Error refreshing data context: {e}")
            return False


# ==============================================================================
# COMPATIBILITY LAYER
# ==============================================================================

# For backward compatibility with existing code that imports from ai_analyzer
# These exports allow existing code to work without modification

__all__ = [
    'PolicyAIAnalyzer',
    'KBLI_MAPPING',
    'KBLI_SHORT_NAMES'
]
