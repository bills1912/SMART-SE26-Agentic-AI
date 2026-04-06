"""
DS-STAR: Data Science Agent via Iterative Planning and Verification
====================================================================
Faithful implementation of the DS-STAR framework for SMART SE2026.

Based on: "DS-STAR: Data Science Agent via Iterative Planning and Verification"
(Nam et al., Google Cloud & KAIST, 2025)

This implementation mirrors the EXACT pipeline from the original dsstar.py:

  run_pipeline(query):
    1. PHASE 1 — analyze_data():
       - LLM generates Python code to describe MongoDB collection
       - Code is executed → stdout captured as data_description
       - Cached for subsequent queries

    2. PHASE 2 — iterative planning & execution:
       - plan_next_step() → natural language step (PLANNER agent)
       - generate_code() → Python code (CODER agent)
       - _execute_and_debug_code() → run code + auto-debug on error
       - verify_plan() → "Yes"/"No" (VERIFIER agent, LLM-as-Judge)
       - if "No": route_plan() → "Add Step" or "Step N is wrong!" (ROUTER agent)
       - loop until verified or max_refinement_rounds

    3. PHASE 3 — finalize_solution():
       - Produce structured JSON output code
       - Execute → final JSON result

    4. PHASE 4 (new for chatbot) — response generation:
       - Narrative text from JSON (NARRATIVE agent)
       - Visualizations from JSON (existing VisualizationAgent)
       - Insights + Policies from JSON (existing InsightGenerationAgent)

Each agent call uses the prompt templates from prompt_templates.py which are
adapted from the original prompt.yaml to work with MongoDB Sensus Ekonomi data.
"""

import os
import re
import sys
import json
import uuid
import logging
import subprocess
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from dotenv import load_dotenv

from prompt_templates import PROMPT_TEMPLATES

logger = logging.getLogger(__name__)

# Load environment
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)


# ==============================================================================
# KBLI MAPPING (shared with other modules)
# ==============================================================================

KBLI_MAPPING = {
    'A': 'Pertanian, Kehutanan, dan Perikanan',
    'B': 'Pertambangan dan Penggalian',
    'C': 'Industri Pengolahan',
    'D': 'Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin',
    'E': 'Pengelolaan Air, Pengelolaan Air Limbah, Daur Ulang Sampah',
    'F': 'Konstruksi',
    'G': 'Perdagangan Besar dan Eceran',
    'H': 'Transportasi dan Pergudangan',
    'I': 'Penyediaan Akomodasi dan Penyediaan Makan Minum',
    'J': 'Informasi dan Komunikasi',
    'K': 'Jasa Keuangan dan Asuransi',
    'L': 'Real Estat',
    'M': 'Jasa Profesional, Ilmiah dan Teknis',
    'N': 'Jasa Persewaan dan Penunjang Usaha Lainnya',
    'O': 'Administrasi Pemerintahan',
    'P': 'Jasa Pendidikan',
    'Q': 'Jasa Kesehatan dan Kegiatan Sosial',
    'R': 'Kesenian, Hiburan dan Rekreasi',
    'S': 'Kegiatan Jasa Lainnya',
    'T': 'Jasa Perorangan yang Melayani Rumah Tangga',
    'U': 'Kegiatan Badan Internasional'
}

KBLI_SHORT_NAMES = {
    'A': 'Pertanian', 'B': 'Pertambangan', 'C': 'Industri Pengolahan',
    'D': 'Listrik & Gas', 'E': 'Pengelolaan Air', 'F': 'Konstruksi',
    'G': 'Perdagangan', 'H': 'Transportasi', 'I': 'Akomodasi & Makan Minum',
    'J': 'Informasi & Komunikasi', 'K': 'Keuangan & Asuransi', 'L': 'Real Estat',
    'M': 'Jasa Profesional', 'N': 'Jasa Persewaan', 'O': 'Administrasi Pemerintahan',
    'P': 'Pendidikan', 'Q': 'Kesehatan', 'R': 'Hiburan & Rekreasi',
    'S': 'Jasa Lainnya', 'T': 'Jasa Rumah Tangga', 'U': 'Badan Internasional'
}

# Province names for detection
_KNOWN_PROVINCES = {
    'ACEH', 'SUMATERA UTARA', 'SUMATERA BARAT', 'RIAU', 'JAMBI',
    'SUMATERA SELATAN', 'BENGKULU', 'LAMPUNG', 'KEP. BANGKA BELITUNG',
    'KEPULAUAN RIAU', 'DKI JAKARTA', 'JAWA BARAT', 'JAWA TENGAH',
    'DI YOGYAKARTA', 'JAWA TIMUR', 'BANTEN', 'BALI',
    'NUSA TENGGARA BARAT', 'NUSA TENGGARA TIMUR',
    'KALIMANTAN BARAT', 'KALIMANTAN TENGAH', 'KALIMANTAN SELATAN',
    'KALIMANTAN TIMUR', 'KALIMANTAN UTARA',
    'SULAWESI UTARA', 'SULAWESI TENGAH', 'SULAWESI SELATAN',
    'SULAWESI TENGGARA', 'GORONTALO', 'SULAWESI BARAT',
    'MALUKU', 'MALUKU UTARA', 'PAPUA', 'PAPUA BARAT',
}


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class DSStarConfig:
    """Mirrors DSConfig from original dsstar.py."""
    max_refinement_rounds: int = 5
    max_debug_attempts: int = 3
    execution_timeout: int = 30  # seconds per code execution
    model_name: str = None
    db_name: str = 'policy_db'
    collection_name: str = 'initial_data'

    def __post_init__(self):
        if self.model_name is None:
            self.model_name = os.environ.get('LLM_MODEL', 'gemini-2.5-flash')
        self.db_name = os.environ.get('DB_NAME', 'policy_db')


# ==============================================================================
# LLM + CODE EXECUTION UTILITIES
# ==============================================================================

async def _call_llm(prompt: str, model_name: str, json_output: bool = False) -> str:
    """Call Gemini LLM. Mirrors _call_model() from original DS-STAR."""
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("No GEMINI_API_KEY or GOOGLE_API_KEY found in environment")

    genai.configure(api_key=api_key)

    if json_output:
        model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={"response_mime_type": "application/json"}
        )
    else:
        model = genai.GenerativeModel(model_name)

    response = await model.generate_content_async(prompt)
    text = response.text.strip()
    logger.info(f"[LLM] Response received ({len(text)} chars)")
    return text


def _extract_code_block(response: str) -> str:
    """Extract Python code from markdown. Mirrors _extract_code_block() from original DS-STAR."""
    code_blocks = re.findall(r'```(?:python)?\s*\n(.*?)\n```', response, re.DOTALL)
    if code_blocks:
        return code_blocks[0]
    # Fallback: if no markdown block found, treat entire response as code
    # (only if it looks like Python)
    if 'import ' in response or 'print(' in response or 'def ' in response:
        return response.strip()
    return response.strip()


def _execute_code(code: str, timeout: int = 30) -> Tuple[str, Optional[str]]:
    """
    Execute Python code in a subprocess. Mirrors _execute_code() from original DS-STAR.
    Returns (stdout, error_or_None).
    """
    exec_dir = Path("/tmp/dsstar_exec")
    exec_dir.mkdir(exist_ok=True)
    exec_id = uuid.uuid4().hex[:8]
    exec_path = exec_dir / f"exec_{exec_id}.py"
    exec_path.write_text(code, encoding='utf-8')

    try:
        env = os.environ.copy()
        result = subprocess.run(
            [sys.executable, str(exec_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=str(BACKEND_DIR)
        )

        if result.returncode == 0:
            logger.info("Code execution successful")
            return result.stdout, None
        else:
            error_msg = result.stderr or "Unknown execution error"
            logger.error(f"Code execution failed: {error_msg[:200]}")
            return result.stdout, error_msg

    except subprocess.TimeoutExpired:
        return "", f"Timeout after {timeout}s"
    except Exception as e:
        return "", f"Execution error: {str(e)}"
    finally:
        try:
            exec_path.unlink(missing_ok=True)
        except Exception:
            pass


# ==============================================================================
# DATA FILE ANALYZER — Phase 1
# ==============================================================================

class DataFileAnalyzerAgent:
    """
    Mirrors analyze_data() from original DS-STAR.
    Generates code to describe the MongoDB collection, executes it,
    and caches the result.
    """

    def __init__(self, config: DSStarConfig):
        self.config = config
        self._cached_description: Optional[str] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 3600  # 1 hour

    async def get_data_description(self, force_refresh: bool = False) -> str:
        """Get data description string. Uses cache if available."""
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached data description")
            return self._cached_description

        logger.info("PHASE 1: Analyzing data structure via code generation...")

        prompt = PROMPT_TEMPLATES["analyzer"].format(
            collection_name=self.config.collection_name,
            db_name=self.config.db_name
        )

        # LLM generates analysis code
        llm_response = await _call_llm(prompt, self.config.model_name)
        code = _extract_code_block(llm_response)

        # Execute the analysis code
        result, error = _execute_code(code, timeout=self.config.execution_timeout)

        if error:
            logger.warning(f"Analyzer code failed: {error[:200]}, using fallback")
            # Auto-debug once
            debug_prompt = PROMPT_TEMPLATES["debugger"].format(
                code=code, bug=error,
                collection_name=self.config.collection_name,
                db_name=self.config.db_name
            )
            fixed_code_response = await _call_llm(debug_prompt, self.config.model_name)
            fixed_code = _extract_code_block(fixed_code_response)
            result, error2 = _execute_code(fixed_code, timeout=self.config.execution_timeout)

            if error2:
                logger.warning(f"Debugged analyzer also failed, using pymongo fallback")
                result = await self._fallback_description()

        self._cached_description = result
        self._cache_timestamp = datetime.utcnow()
        logger.info(f"Data description ready ({len(result)} chars)")
        return result

    def _is_cache_valid(self) -> bool:
        if not self._cached_description or not self._cache_timestamp:
            return False
        elapsed = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds

    async def _fallback_description(self) -> str:
        """Direct pymongo fallback if LLM-generated code fails."""
        import pymongo
        try:
            mongo_url = os.environ.get('MONGO_URL', '')
            client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
            db = client[self.config.db_name]
            coll = db[self.config.collection_name]

            count = coll.count_documents({})
            sample = coll.find_one({}, {'_id': 0})
            provinces = sorted(coll.distinct('provinsi'))

            # Calculate grand total
            pipeline = [{"$group": {"_id": None, "grand_total": {"$sum": "$total"}}}]
            agg = list(coll.aggregate(pipeline))
            grand_total = agg[0]['grand_total'] if agg else 0

            desc = f"MongoDB Collection: {self.config.collection_name}\n"
            desc += f"Total documents (provinces): {count}\n"
            desc += f"Grand total usaha: {grand_total}\n"
            desc += f"Provinces ({len(provinces)}): {', '.join(provinces)}\n\n"

            if sample:
                desc += f"Fields: {list(sample.keys())}\n"
                # Show sector structure
                sector_codes = [k for k in sample.keys() if k in KBLI_MAPPING]
                desc += f"Sector codes present: {sector_codes}\n"
                desc += f"Sector data structure: nested dict, e.g. doc['G'] = {json.dumps(sample.get('G', {}), ensure_ascii=False)}\n"
                desc += f"\nSample document:\n{json.dumps(sample, indent=2, ensure_ascii=False, default=str)[:3000]}\n"

            client.close()
            return desc
        except Exception as e:
            logger.error(f"Fallback description failed: {e}")
            return (f"MongoDB collection '{self.config.collection_name}' in database '{self.config.db_name}'. "
                    f"Contains Sensus Ekonomi 2016 data with province-level business counts by sector (KBLI A-U).")


# ==============================================================================
# DS-STAR ORCHESTRATOR — Main Pipeline
# ==============================================================================

class DSStarOrchestrator:
    """
    Mirrors run_pipeline() from original DS-STAR.

    Pipeline:
      PHASE 1: analyze_data() → data_description
      PHASE 2: iterative plan → code → execute → verify → route loop
      PHASE 3: finalize_solution() → structured JSON
      PHASE 4: narrative + visualizations + insights + policies (chatbot-specific)
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.config = DSStarConfig()
        self.analyzer = DataFileAnalyzerAgent(self.config)

    async def analyze(self, query: str, language: str = "Indonesian") -> Dict[str, Any]:
        """Main entry point. Returns the complete chatbot response dict."""
        logger.info(f"{'='*60}")
        logger.info(f"DS-STAR Pipeline Start: {query[:80]}")
        logger.info(f"{'='*60}")

        try:
            # ── Check if conversational (non-data) query ─────────
            if not self._is_data_query(query):
                return await self._handle_conversational(query, language)

            # ── PHASE 1: Data File Analysis ──────────────────────
            logger.info("=== PHASE 1: ANALYZING DATA ===")
            data_desc = await self.analyzer.get_data_description()

            # ── PHASE 2: Iterative Planning & Verification ───────
            logger.info("=== PHASE 2: ITERATIVE PLANNING & VERIFICATION ===")
            plan: List[str] = []
            code: Optional[str] = None
            exec_result: str = ""

            # Step 1: Initial plan
            initial_step = await self._planner(query, data_desc, plan, "")
            plan.append(initial_step)
            logger.info(f"Plan[1]: {initial_step[:100]}")

            # Step 2: Initial code generation + execution
            code = await self._coder(plan, data_desc, base_code=None)
            exec_result = await self._execute_and_debug(code, data_desc)

            # Step 3: Refinement loop (mirrors original DS-STAR exactly)
            verified = False
            for round_idx in range(self.config.max_refinement_rounds):
                logger.info(f"--- Refinement Round {round_idx + 1} ---")

                # Verify
                verdict = await self._verifier(plan, code, exec_result, query, data_desc)

                if verdict.strip().lower().startswith("yes"):
                    logger.info("Plan verified as SUFFICIENT!")
                    verified = True
                    break

                # Route
                routing = await self._router(plan, query, exec_result, data_desc)
                logger.info(f"Router: {routing}")

                if "is wrong!" in routing.lower():
                    # Truncate plan at faulty step (mirrors original DS-STAR)
                    try:
                        step_num = int(re.search(r'(\d+)', routing).group(1))
                        step_to_remove = step_num - 1  # 0-indexed
                        plan = plan[:step_to_remove]
                        logger.info(f"Truncated plan to {len(plan)} steps")
                    except Exception:
                        plan = []
                        logger.info("Reset plan entirely")
                else:
                    logger.info("Adding new step...")

                # Generate next plan step
                next_step = await self._planner(query, data_desc, plan, exec_result)
                plan.append(next_step)
                logger.info(f"Plan[{len(plan)}]: {next_step[:100]}")

                # Generate and execute new code
                code = await self._coder(plan, data_desc, base_code=code)
                exec_result = await self._execute_and_debug(code, data_desc)

            if not verified:
                logger.warning("Max refinement rounds reached without verification")

            # ── PHASE 3: Finalization ────────────────────────────
            logger.info("=== PHASE 3: FINALIZING ===")
            final_code = await self._finalizer(code, exec_result, query, data_desc)
            final_output = await self._execute_and_debug(final_code, data_desc)

            # Parse JSON from final output
            result_data = self._parse_json_result(final_output)
            logger.info(f"Final JSON parsed: analysis_type={result_data.get('analysis_type')}, "
                        f"top_items={len(result_data.get('top_items', []))}")

            # ── PHASE 4: Response Generation (chatbot-specific) ──
            logger.info("=== PHASE 4: RESPONSE GENERATION ===")

            # 4a. Narrative message
            message = await self._generate_narrative(query, final_output, language)

            # 4b. Visualizations
            visualizations = self._build_visualizations(result_data)

            # 4c. Insights & Policy Recommendations (GUARANTEED)
            insights_data = await self._generate_insights_and_policies(
                result_data, query, language
            )

            response = {
                'message': message,
                'visualizations': visualizations,
                'insights': insights_data['insights'],
                'policies': insights_data['policies'],
                'supporting_data_count': len(result_data.get('top_items', []))
            }

            logger.info(f"DS-STAR Complete: viz={len(visualizations)}, "
                        f"insights={len(insights_data['insights'])}, "
                        f"policies={len(insights_data['policies'])}")

            return response

        except Exception as e:
            logger.error(f"DS-STAR Pipeline error: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan dalam analisis: {str(e)}. Silakan coba lagi.",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }

    # ─────────────────────────────────────────────────────────────────────────
    # AGENT METHODS — Each mirrors a method from original DS-STAR
    # ─────────────────────────────────────────────────────────────────────────

    async def _planner(self, query: str, data_desc: str,
                       current_plan: List[str], last_result: str) -> str:
        """Mirrors plan_next_step() from original DS-STAR."""
        if not current_plan:
            prompt = PROMPT_TEMPLATES["planner_init"].format(
                question=query, summaries=data_desc
            )
        else:
            plan_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(current_plan))
            prompt = PROMPT_TEMPLATES["planner_next"].format(
                question=query, summaries=data_desc,
                plan=plan_str, result=last_result,
                current_step=current_plan[-1]
            )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _coder(self, plan: List[str], data_desc: str,
                     base_code: Optional[str] = None) -> str:
        """Mirrors generate_code() from original DS-STAR."""
        plan_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan))

        if not base_code:
            prompt = PROMPT_TEMPLATES["coder_init"].format(
                summaries=data_desc, plan=plan_str,
                db_name=self.config.db_name,
                collection_name=self.config.collection_name
            )
        else:
            prompt = PROMPT_TEMPLATES["coder_next"].format(
                summaries=data_desc, base_code=base_code,
                plan=plan_str, current_plan=plan[-1],
                db_name=self.config.db_name,
                collection_name=self.config.collection_name
            )

        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _verifier(self, plan: List[str], code: str,
                        result: str, query: str, data_desc: str) -> str:
        """Mirrors verify_plan() from original DS-STAR."""
        plan_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan))
        prompt = PROMPT_TEMPLATES["verifier"].format(
            plan=plan_str, code=code, result=result,
            question=query, summaries=data_desc,
            current_step=plan[-1] if plan else ""
        )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _router(self, plan: List[str], query: str,
                      result: str, data_desc: str) -> str:
        """Mirrors route_plan() from original DS-STAR."""
        plan_str = "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan))
        prompt = PROMPT_TEMPLATES["router"].format(
            question=query, summaries=data_desc,
            plan=plan_str, result=result,
            current_step=plan[-1] if plan else ""
        )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _debugger(self, code: str, error: str) -> str:
        """Mirrors _debug_code() from original DS-STAR."""
        prompt = PROMPT_TEMPLATES["debugger"].format(
            code=code, bug=error,
            collection_name=self.config.collection_name,
            db_name=self.config.db_name
        )
        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _finalizer(self, code: str, result: str,
                         query: str, data_desc: str) -> str:
        """Mirrors finalize_solution() from original DS-STAR."""
        guidelines = (
            "Print a single JSON object to stdout. "
            "Include keys: answer, analysis_type, total, top_items, data, province_focus, sector_focus. "
            "See the detailed JSON schema in the prompt."
        )
        prompt = PROMPT_TEMPLATES["finalizer"].format(
            summaries=data_desc, code=code,
            result=result, question=query,
            guidelines=guidelines,
            db_name=self.config.db_name,
            collection_name=self.config.collection_name
        )
        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _execute_and_debug(self, code: str, data_desc: str) -> str:
        """Mirrors _execute_and_debug_code() from original DS-STAR."""
        exec_result, error = _execute_code(code, timeout=self.config.execution_timeout)

        attempts = 0
        while error and attempts < self.config.max_debug_attempts:
            logger.warning(f"Debugging attempt {attempts + 1}: {error[:150]}")
            code = await self._debugger(code, error)
            exec_result, error = _execute_code(code, timeout=self.config.execution_timeout)
            attempts += 1

        if error:
            logger.error(f"Code failed after {attempts} debug attempts: {error[:300]}")
            return f"EXECUTION_ERROR: {error}"

        return exec_result

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 4: Response Generation
    # ─────────────────────────────────────────────────────────────────────────

    async def _generate_narrative(self, query: str, result_json: str,
                                  language: str) -> str:
        """Generate human-readable narrative from JSON result."""
        try:
            prompt = PROMPT_TEMPLATES["narrative"].format(
                question=query, result_json=result_json, language=language
            )
            narrative = await _call_llm(prompt, self.config.model_name)
            if narrative and len(narrative) > 20:
                return narrative
        except Exception as e:
            logger.error(f"Narrative generation failed: {e}")

        # Fallback: extract 'answer' field from JSON
        try:
            data = json.loads(result_json)
            return data.get('answer', 'Data telah dianalisis. Lihat visualisasi untuk detail.')
        except Exception:
            return "Data telah berhasil dianalisis. Silakan lihat visualisasi untuk informasi lebih detail."

    def _build_visualizations(self, result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build ECharts configs using existing VisualizationAgent."""
        try:
            from visualization_agent import VisualizationAgent
            viz_agent = VisualizationAgent()

            analysis_type = result_data.get('analysis_type', 'overview')
            top_items = result_data.get('top_items', [])
            data = result_data.get('data', {})

            # Build analysis dict matching VisualizationAgent's expected format
            analysis = {'total_usaha': result_data.get('total', 0)}
            aggregated = {'type': analysis_type}

            if not top_items:
                return []

            # Determine if top_items are provinces or sectors
            is_province = any(
                item.get('name', '').upper() in _KNOWN_PROVINCES
                for item in top_items[:3]
            )

            # For ranking/overview/comparison → top_provinces
            if is_province or analysis_type in ('ranking', 'overview', 'comparison'):
                analysis['top_provinces'] = [
                    {'provinsi': it['name'], 'total': it['value'],
                     'percentage': it.get('percentage', 0)}
                    for it in top_items
                ]
                analysis['all_provinces'] = analysis['top_provinces']

            # For distribution/overview → top_sectors
            if not is_province or analysis_type in ('distribution', 'overview'):
                sector_items = top_items if not is_province else data.get('top_sectors', [])
                if sector_items:
                    analysis['top_sectors'] = [
                        {'code': it.get('code', ''), 'name': it['name'],
                         'short_name': it.get('short_name', it['name'][:20]),
                         'total': it['value'], 'percentage': it.get('percentage', 0)}
                        for it in (sector_items if isinstance(sector_items, list) else [])
                    ]

            # For distribution → distribution_detail
            if analysis_type == 'distribution':
                analysis['distribution_detail'] = [
                    {'sector_code': it.get('code', ''), 'sector_name': it['name'],
                     'short_name': it.get('short_name', it['name'][:20]),
                     'total': it['value'], 'percentage': it.get('percentage', 0)}
                    for it in top_items
                ]

            # For province_detail
            if analysis_type == 'province_detail':
                analysis['provinsi'] = result_data.get('province_focus', '')
                analysis['all_sectors'] = [
                    {'code': it.get('code', ''), 'name': it['name'],
                     'short_name': it.get('short_name', it['name'][:20]),
                     'total': it['value'], 'percentage': it.get('percentage', 0)}
                    for it in top_items
                ]
                analysis['top_sectors'] = analysis['all_sectors'][:5]

            # For sector_analysis
            if analysis_type == 'sector_analysis' and is_province:
                analysis['all_provinces'] = analysis.get('top_provinces', [])
                analysis['sector_names'] = result_data.get('sector_focus', [])
                aggregated['type'] = 'sector_analysis'

            visualizations = viz_agent.create_visualizations(analysis, aggregated)
            return [viz.dict() for viz in visualizations]

        except Exception as e:
            logger.error(f"Visualization build failed: {e}", exc_info=True)
            return []

    async def _generate_insights_and_policies(
        self, result_data: Dict[str, Any], query: str, language: str
    ) -> Dict[str, Any]:
        """
        GUARANTEED insight + policy generation.
        Uses InsightGenerationAgent first, falls back to direct LLM call,
        and finally falls back to rule-based generation.
        """
        insights: List[str] = []
        policies: List[Dict[str, Any]] = []

        # ── Attempt 1: Use existing InsightGenerationAgent ────────
        try:
            from insight_agent import InsightGenerationAgent
            agent = InsightGenerationAgent()

            analysis = {
                'total_usaha': result_data.get('total', 0),
                'top_provinces': [
                    {'provinsi': it['name'], 'total': it['value'],
                     'percentage': it.get('percentage', 0)}
                    for it in result_data.get('top_items', [])
                ],
            }
            aggregated = {'type': result_data.get('analysis_type', 'overview')}

            insight_result = await agent.generate_insights(
                analysis, aggregated, query, language
            )

            if isinstance(insight_result, dict):
                raw_insights = insight_result.get('insights', [])
                if isinstance(raw_insights, list) and len(raw_insights) >= 2:
                    insights = [i for i in raw_insights if isinstance(i, str) and len(i) > 10]

                raw_policies = insight_result.get('policies', [])
                for p in raw_policies:
                    if hasattr(p, 'dict'):
                        policies.append(p.dict())
                    elif isinstance(p, dict):
                        policies.append(p)

            logger.info(f"InsightAgent produced {len(insights)} insights, {len(policies)} policies")
        except Exception as e:
            logger.warning(f"InsightAgent failed: {e}")

        # ── Attempt 2: Direct LLM call if InsightAgent was insufficient ───
        if len(insights) < 2 or len(policies) < 1:
            try:
                logger.info("Generating insights via direct LLM call...")
                analysis_json = json.dumps(result_data, ensure_ascii=False, default=str)
                prompt = PROMPT_TEMPLATES["insight_generation"].format(
                    question=query, analysis_json=analysis_json
                )
                llm_response = await _call_llm(prompt, self.config.model_name, json_output=True)
                parsed = json.loads(llm_response)

                if isinstance(parsed, dict):
                    llm_insights = parsed.get('insights', [])
                    if isinstance(llm_insights, list) and len(llm_insights) >= 2:
                        insights = [i for i in llm_insights if isinstance(i, str)]

                    llm_policies = parsed.get('policy_recommendations', [])
                    if isinstance(llm_policies, list) and len(llm_policies) >= 1:
                        from models import PolicyCategory
                        policies = []
                        for rec in llm_policies:
                            if isinstance(rec, dict):
                                category_str = rec.get('category', 'economic').lower()
                                policies.append({
                                    'id': str(datetime.utcnow().timestamp()),
                                    'title': rec.get('title', 'Rekomendasi'),
                                    'description': rec.get('description', ''),
                                    'priority': rec.get('priority', 'medium'),
                                    'category': category_str,
                                    'impact': rec.get('impact', ''),
                                    'implementation_steps': rec.get('implementation_steps', []),
                                    'supporting_insights': [],
                                    'supporting_data_ids': [],
                                    'created_at': datetime.utcnow().isoformat()
                                })

                logger.info(f"Direct LLM produced {len(insights)} insights, {len(policies)} policies")
            except Exception as e:
                logger.warning(f"Direct LLM insight generation failed: {e}")

        # ── Attempt 3: Guaranteed fallback ────────────────────────
        if len(insights) < 2:
            top_items = result_data.get('top_items', [])
            total = result_data.get('total', 0)
            analysis_type = result_data.get('analysis_type', 'overview')

            insights = [
                f"Data Sensus Ekonomi 2016 menunjukkan total {total:,} unit usaha di Indonesia." if total else
                "Data Sensus Ekonomi 2016 telah berhasil dianalisis.",
            ]
            if top_items:
                top = top_items[0]
                insights.append(
                    f"{top['name']} menempati posisi teratas dengan {top['value']:,} unit usaha "
                    f"({top.get('percentage', 0):.1f}% dari total)."
                )
            if len(top_items) >= 3:
                top3_total = sum(it['value'] for it in top_items[:3])
                top3_pct = (top3_total / total * 100) if total > 0 else 0
                insights.append(
                    f"Tiga teratas menguasai {top3_pct:.1f}% dari total, "
                    f"menunjukkan konsentrasi ekonomi yang signifikan."
                )
            logger.info(f"Fallback produced {len(insights)} insights")

        if len(policies) < 1:
            policies = [{
                'id': str(datetime.utcnow().timestamp()),
                'title': 'Pemerataan Pembangunan Ekonomi',
                'description': 'Mendorong pemerataan distribusi usaha melalui insentif fiskal dan kemudahan perizinan di daerah tertinggal.',
                'priority': 'high',
                'category': 'economic',
                'impact': 'Meningkatkan pertumbuhan ekonomi inklusif dan mengurangi kesenjangan antar wilayah.',
                'implementation_steps': [
                    'Identifikasi provinsi dengan jumlah usaha rendah',
                    'Buat program insentif pajak untuk daerah tertinggal',
                    'Sederhanakan prosedur perizinan usaha',
                    'Tingkatkan infrastruktur pendukung ekonomi'
                ],
                'supporting_insights': [],
                'supporting_data_ids': [],
                'created_at': datetime.utcnow().isoformat()
            }, {
                'id': str(datetime.utcnow().timestamp()) + '_2',
                'title': 'Diversifikasi Sektor Ekonomi',
                'description': 'Mendorong pengembangan sektor non-perdagangan untuk mengurangi ketergantungan pada satu sektor dominan.',
                'priority': 'medium',
                'category': 'economic',
                'impact': 'Meningkatkan ketahanan ekonomi daerah terhadap guncangan sektoral.',
                'implementation_steps': [
                    'Analisis sektor potensial per wilayah',
                    'Buat program pelatihan kewirausahaan sektor baru',
                    'Fasilitasi akses permodalan untuk sektor underserved'
                ],
                'supporting_insights': [],
                'supporting_data_ids': [],
                'created_at': datetime.utcnow().isoformat()
            }]
            logger.info(f"Fallback produced {len(policies)} policies")

        return {'insights': insights, 'policies': policies}

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _parse_json_result(self, raw_output: str) -> Dict[str, Any]:
        """Parse JSON from code execution stdout."""
        if not raw_output or raw_output.startswith("EXECUTION_ERROR:"):
            return {
                'answer': 'Tidak dapat menganalisis data.',
                'analysis_type': 'unknown',
                'total': 0, 'top_items': [], 'data': {},
                'province_focus': None, 'sector_focus': []
            }

        # Try direct parse
        try:
            return json.loads(raw_output.strip())
        except json.JSONDecodeError:
            pass

        # Find JSON object in output (might have print() text before/after)
        # Look for the LAST complete JSON object
        json_candidates = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_output)
        for candidate in reversed(json_candidates):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and ('answer' in parsed or 'top_items' in parsed):
                    return parsed
            except json.JSONDecodeError:
                continue

        # Last resort: treat as text answer
        return {
            'answer': raw_output.strip()[:500],
            'analysis_type': 'unknown',
            'total': 0, 'top_items': [], 'data': {},
            'province_focus': None, 'sector_focus': []
        }

    def _is_data_query(self, query: str) -> bool:
        """Check if query needs data analysis or is just conversational."""
        q = query.lower()

        data_keywords = [
            'berapa', 'jumlah', 'total', 'banyak', 'bandingkan', 'compare', 'versus', 'vs',
            'terbanyak', 'tertinggi', 'terendah', 'top', 'ranking', 'urut', 'paling',
            'distribusi', 'sebaran', 'komposisi', 'proporsi', 'persentase',
            'provinsi', 'sektor', 'wilayah', 'daerah', 'kbli',
            'analisis', 'analyze', 'analisa', 'data', 'statistik',
            'usaha', 'bisnis', 'perusahaan', 'industri',
            'perdagangan', 'pertanian', 'pertambangan', 'konstruksi',
            'peta', 'map', 'persebaran', 'overview', 'gambaran',
            'sensus', 'ekonomi', 'jawa', 'sumatera', 'kalimantan',
            'sulawesi', 'papua', 'bali', 'jakarta', 'sumut', 'jabar', 'jatim', 'jateng',
        ]

        conversational_only = [
            'halo', 'hello', 'hi ', 'hai ', 'hey', 'terima kasih', 'thanks', 'thank',
            'siapa kamu', 'who are you', 'apa itu', 'what is',
            'selamat pagi', 'selamat siang', 'selamat malam', 'assalamualaikum',
            'tolong jelaskan', 'bisa apa', 'kemampuan', 'fitur',
        ]

        has_data = any(kw in q for kw in data_keywords)
        is_conv = any(kw in q for kw in conversational_only)

        # If only conversational keywords and no data keywords
        if is_conv and not has_data:
            return False
        return has_data or not is_conv  # default to data query if unclear

    async def _handle_conversational(self, query: str, language: str) -> Dict[str, Any]:
        """Handle non-data queries (greetings, capability questions, etc.)."""
        try:
            prompt = PROMPT_TEMPLATES["conversational"].format(
                question=query, language=language
            )
            message = await _call_llm(prompt, self.config.model_name)
        except Exception:
            message = (
                "Halo! Saya asisten analisis Sensus Ekonomi Indonesia 2016. "
                "Saya dapat membantu menganalisis data seperti jumlah usaha per provinsi, "
                "distribusi sektor, dan perbandingan antar wilayah. Silakan ajukan pertanyaan!"
            )

        return {
            'message': message,
            'visualizations': [],
            'insights': [],
            'policies': [],
            'supporting_data_count': 0
        }


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    'DSStarOrchestrator',
    'DataFileAnalyzerAgent',
    'DSStarConfig',
    'KBLI_MAPPING',
    'KBLI_SHORT_NAMES',
]
