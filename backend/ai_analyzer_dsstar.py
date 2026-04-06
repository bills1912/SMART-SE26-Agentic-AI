"""
PolicyAIAnalyzer with DS-STAR Framework Integration
====================================================
Drop-in replacement for ai_analyzer.py that uses the DS-STAR
(Data Science Agent via Iterative Planning and Verification) framework.

To switch from the old analyzer to DS-STAR, change your server.py import:
  FROM: from ai_analyzer import PolicyAIAnalyzer
  TO:   from ai_analyzer_dsstar import PolicyAIAnalyzer

DS-STAR Pipeline (per query):
  ┌──────────────────────────────────────────────────────┐
  │ PHASE 1: DataFileAnalyzer                            │
  │   LLM generates Python → execute → data_description  │
  │   (cached 1 hour)                                    │
  ├──────────────────────────────────────────────────────┤
  │ PHASE 2: Iterative Planning & Verification           │
  │   ┌─→ Planner → natural language step                │
  │   │   Coder → Python code querying MongoDB           │
  │   │   Execute → stdout result                        │
  │   │   Verifier (LLM-as-Judge) → Yes/No               │
  │   │   if No: Router → "Add Step"/"Step N is wrong!"  │
  │   └─────────────────────────── loop ←────────────────│
  ├──────────────────────────────────────────────────────┤
  │ PHASE 3: Finalizer                                   │
  │   LLM generates code → structured JSON output        │
  ├──────────────────────────────────────────────────────┤
  │ PHASE 4: Response Generation                         │
  │   Narrative  → user-facing text                      │
  │   Visualizer → ECharts configs (bar, pie, treemap)   │
  │   InsightGen → insights + policy recommendations     │
  │   (3-tier fallback: InsightAgent → LLM → rules)      │
  └──────────────────────────────────────────────────────┘
"""

import os
import logging
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

from dsstar_agents import (
    DSStarOrchestrator,
    DataFileAnalyzerAgent,
    DSStarConfig,
    KBLI_MAPPING,
    KBLI_SHORT_NAMES,
)

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)


class PolicyAIAnalyzer:
    """
    Main analyzer class used by server.py.
    
    API contract (unchanged from original ai_analyzer.py):
      Input:  analyze_policy_query(query, language, scraped_data)
      Output: {
          'message': str,           # narrative response
          'visualizations': list,   # ECharts configs
          'insights': list[str],    # insight strings (guaranteed ≥2)
          'policies': list[dict],   # policy recommendations (guaranteed ≥1)
          'supporting_data_count': int
      }
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

        # Initialize Gemini (for fallback direct usage)
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            model_name = os.environ.get('LLM_MODEL', 'gemini-2.0-flash-exp')
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini initialized: {model_name}")
        else:
            logger.warning("No Gemini API key found")
            self.model = None

        # Initialize DS-STAR orchestrator
        self.dsstar = DSStarOrchestrator(db)
        logger.info("PolicyAIAnalyzer initialized with DS-STAR framework")

    async def analyze_policy_query(
        self,
        query: str,
        language: str = "Indonesian",
        scraped_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point. Delegates to DS-STAR orchestrator.
        
        The DS-STAR pipeline handles ALL query types adaptively:
        - Rankings ("provinsi mana yang terbanyak?")
        - Comparisons ("bandingkan Jakarta dan Jatim")
        - Distributions ("distribusi sektor di Indonesia")
        - Province detail ("analisis Jawa Barat")
        - Sector analysis ("sektor perdagangan di semua provinsi")
        - Overview ("gambaran umum sensus ekonomi")
        - Conversational ("halo", "bisa apa saja?")
        
        The LLM adaptively plans and generates code based on the 
        actual user question — no hardcoded intent detection needed.
        """
        try:
            logger.info(f"DS-STAR analyze: {query[:60]}...")
            result = await self.dsstar.analyze(query, language)

            logger.info(
                f"DS-STAR done: msg={len(result.get('message',''))}ch, "
                f"viz={len(result.get('visualizations', []))}, "
                f"ins={len(result.get('insights', []))}, "
                f"pol={len(result.get('policies', []))}"
            )
            return result

        except Exception as e:
            logger.error(f"DS-STAR error: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan: {str(e)}. Silakan coba lagi.",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }

    async def get_data_context(self) -> Dict[str, Any]:
        """Debug endpoint: get current data description."""
        try:
            desc = await self.dsstar.analyzer.get_data_description()
            return {
                'description_length': len(desc),
                'description_preview': desc[:500],
                'config': {
                    'collection': self.dsstar.config.collection_name,
                    'db': self.dsstar.config.db_name,
                    'model': self.dsstar.config.model_name,
                    'max_rounds': self.dsstar.config.max_refinement_rounds,
                    'max_debug': self.dsstar.config.max_debug_attempts,
                }
            }
        except Exception as e:
            return {'error': str(e)}

    async def refresh_data_context(self) -> bool:
        """Force refresh cached data description."""
        try:
            await self.dsstar.analyzer.get_data_description(force_refresh=True)
            return True
        except Exception as e:
            logger.error(f"Refresh failed: {e}")
            return False


__all__ = ['PolicyAIAnalyzer', 'KBLI_MAPPING', 'KBLI_SHORT_NAMES']
