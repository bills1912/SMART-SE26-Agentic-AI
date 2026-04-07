"""
PolicyAIAnalyzer — DS-STAR Edition
====================================
Drop-in replacement for ai_analyzer.py that delegates all analysis
to the DS-STAR (Data Science Agent via Iterative Planning and Verification)
framework implemented in dsstar_agents.py.

Usage — in server.py change the import from:
    from ai_analyzer import PolicyAIAnalyzer
to:
    from ai_analyzer_dsstar import PolicyAIAnalyzer

Public API contract (unchanged):
    Input:  analyze_policy_query(query, language, scraped_data)
    Output: {
        'message':               str,
        'visualizations':        list[dict],   # ECharts configs
        'insights':              list[str],    # ≥ 2 guaranteed
        'policies':              list[dict],   # ≥ 1 guaranteed
        'supporting_data_count': int
    }

The DS-STAR pipeline handles ALL query types adaptively:
  - Rankings, comparisons, distributions, province detail, sector analysis
  - Conversational / greeting queries (shortcut path, no data pipeline)
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
    Main analyzer class consumed by server.py.

    Wraps DSStarOrchestrator and preserves the same public interface
    as the original ai_analyzer.PolicyAIAnalyzer so that no changes
    are needed in the rest of the codebase.
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

        # Gemini is initialised here for any direct fallback usage,
        # but the primary model calls are managed inside dsstar_agents.py.
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            model_name = os.environ.get('LLM_MODEL', 'gemini-2.5-flash')
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"[PolicyAIAnalyzer] Gemini ready: {model_name}")
        else:
            logger.warning("[PolicyAIAnalyzer] No Gemini API key found")
            self.model = None

        # DS-STAR orchestrator — handles the full pipeline
        self.dsstar = DSStarOrchestrator(db)
        logger.info("[PolicyAIAnalyzer] DS-STAR framework initialised")

    # --------------------------------------------------------------------------
    # PUBLIC API (same signature as original ai_analyzer.py)
    # --------------------------------------------------------------------------

    async def analyze_policy_query(
        self,
        query: str,
        language: str = "Indonesian",
        scraped_data: Optional[str] = None   # kept for API compatibility; not used
    ) -> Dict[str, Any]:
        """
        Analyse a user query using the full DS-STAR pipeline.

        The pipeline adaptively:
          Phase 1 — describes the MongoDB collection structure (cached)
          Phase 2 — iteratively plans, codes, executes, verifies, and routes
          Phase 3 — produces a structured JSON result
          Phase 4 — generates narrative, visualizations, insights, and policies
        """
        try:
            logger.info(f"[PolicyAIAnalyzer] Incoming query: {query[:80]}...")

            result = await self.dsstar.analyze(query, language)

            logger.info(
                f"[PolicyAIAnalyzer] Done — "
                f"msg={len(result.get('message', ''))}ch, "
                f"viz={len(result.get('visualizations', []))}, "
                f"insights={len(result.get('insights', []))}, "
                f"policies={len(result.get('policies', []))}"
            )
            return result

        except Exception as e:
            logger.error(f"[PolicyAIAnalyzer] Unhandled error: {e}", exc_info=True)
            return {
                'message': (
                    f"Maaf, terjadi kesalahan sistem: {str(e)}. "
                    "Silakan coba lagi."
                ),
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }

    # --------------------------------------------------------------------------
    # DIAGNOSTIC / DEBUG HELPERS
    # --------------------------------------------------------------------------

    async def get_data_context(self) -> Dict[str, Any]:
        """
        Debug endpoint: returns the current cached data description
        and DS-STAR configuration.
        """
        try:
            desc = await self.dsstar.analyzer.get_data_description()
            cfg = self.dsstar.config
            return {
                'description_length': len(desc),
                'description_preview': desc[:500],
                'config': {
                    'collection': cfg.collection_name,
                    'db': cfg.db_name,
                    'model': cfg.model_name,
                    'max_rounds': cfg.max_refinement_rounds,
                    'max_debug': cfg.max_debug_attempts,
                    'cache_ttl_s': self.dsstar.analyzer._cache_ttl_seconds,
                },
            }
        except Exception as e:
            return {'error': str(e)}

    async def refresh_data_context(self) -> bool:
        """
        Force-refresh the Phase 1 cached data description.
        Useful after schema or data changes in MongoDB.
        """
        try:
            await self.dsstar.analyzer.get_data_description(force_refresh=True)
            logger.info("[PolicyAIAnalyzer] Data context cache refreshed")
            return True
        except Exception as e:
            logger.error(f"[PolicyAIAnalyzer] Cache refresh failed: {e}")
            return False


# Public re-exports so other modules can import KBLI tables from here
__all__ = ['PolicyAIAnalyzer', 'KBLI_MAPPING', 'KBLI_SHORT_NAMES']
