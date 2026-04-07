"""
DS-STAR: Data Science Agent via Iterative Planning and Verification
====================================================================
Faithful implementation of the DS-STAR framework for SMART SE2026.

Based on: "DS-STAR: Data Science Agent via Iterative Planning and Verification"
(Nam et al., Google Cloud & KAIST, 2025)

Pipeline per query:
  PHASE 1 — DataFileAnalyzerAgent
    LLM generates Python → execute → data_description  (cached 1 hour)

  PHASE 2 — Iterative Planning & Verification
    ┌─→ Planner    → natural language step
    │   Coder      → Python code querying MongoDB
    │   Executor   → stdout result  (+auto-debug on error)
    │   Verifier   → "Yes" / "No"  (LLM-as-Judge)
    │   if "No": Router → "Add Step" / "Step N is wrong!"
    └────────────────────────── loop ←────────────────────┘

  PHASE 3 — Finalizer
    LLM generates code → structured JSON output → execute

  PHASE 4 — Response Generation
    Narrative  → user-facing Indonesian text
    Visualizer → ECharts configs (bar, pie, treemap, heatmap, radar)
    InsightGen → insights + policy recommendations  (3-tier fallback)
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
    """
    Configuration mirroring DSConfig from original DS-STAR.

    model_name is intentionally NOT cached here — it is read from the
    environment on every LLM call so that the value in .env (e.g.
    LLM_MODEL=gemini-2.0-flash-exp) is always respected, regardless of
    when load_dotenv() runs relative to class instantiation.
    """
    max_refinement_rounds: int = 5
    max_debug_attempts: int = 3
    execution_timeout: int = 30
    db_name: str = 'policy_db'
    collection_name: str = 'initial_data'

    def __post_init__(self):
        # Only non-model fields are fixed at init time
        self.db_name = os.environ.get('DB_NAME', 'policy_db')

    @property
    def model_name(self) -> str:
        """
        Read LLM_MODEL from the environment each time it is accessed.
        This ensures .env changes and late load_dotenv() calls are
        always picked up — identical to how ai_analyzer.py works.
        """
        return os.environ.get('LLM_MODEL', 'gemini-2.0-flash-exp')


# ==============================================================================
# LLM + CODE EXECUTION UTILITIES
# ==============================================================================

async def _call_llm(prompt: str, model_name: str, json_output: bool = False) -> str:
    """
    Call Gemini LLM — async-safe wrapper around the synchronous SDK.

    WHY sync-wrapped instead of generate_content_async():
      generate_content_async() routes through Google AI SDK's async path
      which targets API v1 (stable). Experimental models such as
      gemini-2.0-flash-exp are only available on API v1beta, which is the
      path used by the synchronous generate_content().
      Wrapping the sync call with asyncio.to_thread() keeps us on v1beta
      (same routing as ai_analyzer.py) while still being non-blocking.

    model_name is accepted as a parameter but LLM_MODEL from the environment
    always wins, so .env changes are picked up without a server restart.
    """
    import asyncio

    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        raise ValueError("No GEMINI_API_KEY or GOOGLE_API_KEY found in environment")

    # Re-read from env every call — never use a cached value.
    effective_model = (
        os.environ.get('LLM_MODEL')
        or model_name
        or 'gemini-2.0-flash-exp'
    )

    genai.configure(api_key=api_key)

    if json_output:
        model = genai.GenerativeModel(
            model_name=effective_model,
            generation_config={"response_mime_type": "application/json"}
        )
    else:
        model = genai.GenerativeModel(effective_model)

    logger.info(f"[LLM] Calling model: {effective_model}")

    # Use asyncio.to_thread so the synchronous SDK call does not block the
    # event loop, while staying on the v1beta API path that supports
    # experimental models.
    response = await asyncio.to_thread(model.generate_content, prompt)

    text = response.text.strip()
    logger.info(f"[LLM] Response received ({len(text)} chars)")
    return text


def _extract_code_block(response: str) -> str:
    """
    Extract Python code from a markdown code block.
    Mirrors _extract_code_block() from the original DS-STAR implementation.
    Falls back to the full response text if no fenced block is found.
    """
    code_blocks = re.findall(r'```(?:python)?\s*\n(.*?)\n```', response, re.DOTALL)
    if code_blocks:
        return code_blocks[0]
    # If the response itself looks like Python, use it directly
    if 'import ' in response or 'print(' in response or 'def ' in response:
        return response.strip()
    return response.strip()


def _execute_code(code: str, timeout: int = 30) -> Tuple[str, Optional[str]]:
    """
    Execute Python code in an isolated subprocess.
    Mirrors _execute_code() from the original DS-STAR implementation.
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
# PHASE 1: DATA FILE ANALYZER AGENT
# ==============================================================================

class DataFileAnalyzerAgent:
    """
    Mirrors analyze_data() from the original DS-STAR paper.

    Generates Python code to describe the MongoDB collection structure,
    executes it, and caches the result for reuse within the same session.
    """

    def __init__(self, config: DSStarConfig):
        self.config = config
        self._cached_description: Optional[str] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 3600  # 1 hour

    async def get_data_description(self, force_refresh: bool = False) -> str:
        """
        Return cached data description, or generate a fresh one via LLM-generated code.
        This is Phase 1 of DS-STAR: understand the data before planning.
        """
        if not force_refresh and self._is_cache_valid():
            logger.info("[Phase 1] Using cached data description")
            return self._cached_description

        logger.info("[Phase 1] Generating data description via LLM code...")

        prompt = PROMPT_TEMPLATES["analyzer"].format(
            collection_name=self.config.collection_name,
            db_name=self.config.db_name
        )

        llm_response = await _call_llm(prompt, self.config.model_name)
        code = _extract_code_block(llm_response)

        result, error = _execute_code(code, timeout=self.config.execution_timeout)

        if error:
            logger.warning(f"[Phase 1] Analyzer code failed: {error[:200]}, attempting debug...")
            debug_prompt = PROMPT_TEMPLATES["debugger"].format(
                code=code, bug=error,
                collection_name=self.config.collection_name,
                db_name=self.config.db_name
            )
            fixed_response = await _call_llm(debug_prompt, self.config.model_name)
            fixed_code = _extract_code_block(fixed_response)
            result, error2 = _execute_code(fixed_code, timeout=self.config.execution_timeout)

            if error2:
                logger.warning("[Phase 1] Debugged analyzer also failed, using pymongo fallback")
                result = await self._fallback_description()

        self._cached_description = result
        self._cache_timestamp = datetime.utcnow()
        logger.info(f"[Phase 1] Data description ready ({len(result)} chars)")
        return result

    def _is_cache_valid(self) -> bool:
        if not self._cached_description or not self._cache_timestamp:
            return False
        elapsed = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds

    async def _fallback_description(self) -> str:
        """Direct pymongo fallback when LLM-generated code cannot execute."""
        import pymongo
        try:
            mongo_url = os.environ.get('MONGO_URL', '')
            client = pymongo.MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
            db = client[self.config.db_name]
            coll = db[self.config.collection_name]

            count = coll.count_documents({})
            sample = coll.find_one({}, {'_id': 0})
            provinces = sorted(coll.distinct('provinsi'))

            pipeline = [{"$group": {"_id": None, "grand_total": {"$sum": "$total"}}}]
            agg = list(coll.aggregate(pipeline))
            grand_total = agg[0]['grand_total'] if agg else 0

            desc = f"MongoDB Collection: {self.config.collection_name}\n"
            desc += f"Total documents (provinces): {count}\n"
            desc += f"Grand total usaha: {grand_total}\n"
            desc += f"Provinces ({len(provinces)}): {', '.join(provinces)}\n\n"

            if sample:
                desc += f"Fields: {list(sample.keys())}\n"
                sector_codes = [k for k in sample.keys() if k in KBLI_MAPPING]
                desc += f"Sector codes present: {sector_codes}\n"
                desc += (
                    f"Sector data structure: nested dict, "
                    f"e.g. doc['G'] = {json.dumps(sample.get('G', {}), ensure_ascii=False)}\n"
                )
                desc += f"\nSample document:\n{json.dumps(sample, indent=2, ensure_ascii=False, default=str)[:3000]}\n"

            client.close()
            return desc
        except Exception as e:
            logger.error(f"[Phase 1] Fallback description failed: {e}")
            return (
                f"MongoDB collection '{self.config.collection_name}' in database "
                f"'{self.config.db_name}'. Contains Sensus Ekonomi 2016 data with "
                f"province-level business counts by sector (KBLI A-U). "
                f"Each doc has 'provinsi', 'total', and nested sector fields like "
                f"doc['G'] = {{\"Perdagangan\": 1234567}}."
            )


# ==============================================================================
# PHASE 2–3: DS-STAR ORCHESTRATOR
# ==============================================================================

class DSStarOrchestrator:
    """
    Faithful implementation of run_pipeline() from the original DS-STAR paper.

    Phase 1: analyze_data()       → data_description
    Phase 2: iterative loop       → plan + code + execute + verify + route
    Phase 3: finalize_solution()  → structured JSON
    Phase 4: response generation  → narrative + visualizations + insights
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.config = DSStarConfig()
        self.analyzer = DataFileAnalyzerAgent(self.config)

    # --------------------------------------------------------------------------
    # PUBLIC ENTRY POINT
    # --------------------------------------------------------------------------

    async def analyze(self, query: str, language: str = "Indonesian") -> Dict[str, Any]:
        """
        Run the full DS-STAR pipeline and return the chatbot response dict.
        """
        logger.info("=" * 60)
        logger.info(f"[DS-STAR] Pipeline start: {query[:80]}")
        logger.info("=" * 60)

        try:
            # Non-data (conversational) queries take a shortcut
            if not self._is_data_query(query):
                return await self._handle_conversational(query, language)

            # ------------------------------------------------------------------
            # PHASE 1: Understand data structure
            # ------------------------------------------------------------------
            logger.info("=== PHASE 1: DATA ANALYSIS ===")
            data_desc = await self.analyzer.get_data_description()

            # ------------------------------------------------------------------
            # PHASE 2: Iterative planning, coding, execution, verification
            # ------------------------------------------------------------------
            logger.info("=== PHASE 2: ITERATIVE PLANNING & VERIFICATION ===")

            plan: List[str] = []
            current_code: Optional[str] = None
            exec_result: str = ""

            # --- Initial step ---
            first_step = await self._planner(query, data_desc, plan, exec_result)
            plan.append(first_step)
            logger.info(f"[Phase 2] Plan[1]: {first_step[:120]}")

            # --- Initial code + execution ---
            current_code = await self._coder(plan, data_desc, base_code=None)
            exec_result = await self._execute_and_debug(current_code, data_desc)
            logger.info(f"[Phase 2] Initial exec result ({len(exec_result)} chars)")

            # --- Refinement loop (exactly as described in the DS-STAR paper) ---
            verified = False
            for round_idx in range(self.config.max_refinement_rounds):
                logger.info(f"[Phase 2] --- Refinement round {round_idx + 1} ---")

                # Verifier: is the current plan sufficient?
                verdict = await self._verifier(
                    plan, current_code, exec_result, query, data_desc
                )
                logger.info(f"[Phase 2] Verifier verdict: {verdict[:80]}")

                if verdict.strip().lower().startswith("yes"):
                    logger.info("[Phase 2] Plan verified as sufficient!")
                    verified = True
                    break

                # Router: how should we fix the plan?
                routing = await self._router(plan, query, exec_result, data_desc)
                logger.info(f"[Phase 2] Router decision: {routing}")

                if "is wrong!" in routing.lower():
                    # Truncate plan at the faulty step (mirrors original DS-STAR)
                    match = re.search(r'(\d+)', routing)
                    if match:
                        faulty_step = int(match.group(1)) - 1  # 0-indexed
                        plan = plan[:faulty_step]
                        logger.info(f"[Phase 2] Truncated plan to {len(plan)} steps")
                    else:
                        plan = []
                        logger.info("[Phase 2] Reset plan entirely")
                else:
                    logger.info("[Phase 2] Adding a new step to the plan")

                # Planner: propose the next step
                next_step = await self._planner(query, data_desc, plan, exec_result)
                plan.append(next_step)
                logger.info(f"[Phase 2] Plan[{len(plan)}]: {next_step[:120]}")

                # Coder: extend/revise code for the updated plan
                current_code = await self._coder(plan, data_desc, base_code=current_code)
                exec_result = await self._execute_and_debug(current_code, data_desc)

            if not verified:
                logger.warning(
                    f"[Phase 2] Reached max refinement rounds ({self.config.max_refinement_rounds}) "
                    f"without verification; proceeding with best result."
                )

            # ------------------------------------------------------------------
            # PHASE 3: Finalize — produce structured JSON
            # ------------------------------------------------------------------
            logger.info("=== PHASE 3: FINALIZATION ===")
            final_code = await self._finalizer(current_code, exec_result, query, data_desc)
            final_output = await self._execute_and_debug(final_code, data_desc)
            result_data = self._parse_json_result(final_output)

            logger.info(
                f"[Phase 3] JSON parsed: analysis_type={result_data.get('analysis_type')}, "
                f"top_items={len(result_data.get('top_items', []))}"
            )

            # ------------------------------------------------------------------
            # PHASE 4: Response generation
            # ------------------------------------------------------------------
            logger.info("=== PHASE 4: RESPONSE GENERATION ===")

            message = await self._generate_narrative(query, final_output, language)
            visualizations = self._build_visualizations(result_data)
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

            logger.info(
                f"[DS-STAR] Pipeline complete — "
                f"viz={len(visualizations)}, "
                f"insights={len(insights_data['insights'])}, "
                f"policies={len(insights_data['policies'])}"
            )
            return response

        except Exception as e:
            logger.error(f"[DS-STAR] Pipeline error: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan dalam analisis: {str(e)}. Silakan coba lagi.",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }

    # --------------------------------------------------------------------------
    # PHASE 2 AGENT METHODS
    # Each mirrors the corresponding method in the original DS-STAR codebase.
    # --------------------------------------------------------------------------

    async def _planner(
        self,
        query: str,
        data_desc: str,
        current_plan: List[str],
        last_result: str
    ) -> str:
        """
        Mirrors plan_next_step() from the original DS-STAR.
        Uses planner_init for the very first step; planner_next for subsequent steps.
        """
        if not current_plan:
            prompt = PROMPT_TEMPLATES["planner_init"].format(
                question=query,
                summaries=data_desc
            )
        else:
            plan_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(current_plan))
            prompt = PROMPT_TEMPLATES["planner_next"].format(
                question=query,
                summaries=data_desc,
                plan=plan_str,
                result=last_result,
                current_step=current_plan[-1]
            )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _coder(
        self,
        plan: List[str],
        data_desc: str,
        base_code: Optional[str] = None
    ) -> str:
        """
        Mirrors generate_code() from the original DS-STAR.
        Uses coder_init for the first code; coder_next to extend existing code.
        """
        plan_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan))

        if not base_code:
            prompt = PROMPT_TEMPLATES["coder_init"].format(
                summaries=data_desc,
                plan=plan_str,
                db_name=self.config.db_name,
                collection_name=self.config.collection_name
            )
        else:
            prompt = PROMPT_TEMPLATES["coder_next"].format(
                summaries=data_desc,
                base_code=base_code,
                plan=plan_str,
                current_plan=plan[-1],
                db_name=self.config.db_name,
                collection_name=self.config.collection_name
            )

        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _verifier(
        self,
        plan: List[str],
        code: str,
        result: str,
        query: str,
        data_desc: str
    ) -> str:
        """
        Mirrors verify_plan() from the original DS-STAR.
        Acts as an LLM-as-Judge: answers "Yes" if the result fully answers the query,
        "No" otherwise.
        """
        plan_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan))
        prompt = PROMPT_TEMPLATES["verifier"].format(
            plan=plan_str,
            code=code,
            result=result,
            question=query,
            summaries=data_desc,
            current_step=plan[-1] if plan else ""
        )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _router(
        self,
        plan: List[str],
        query: str,
        result: str,
        data_desc: str
    ) -> str:
        """
        Mirrors route_plan() from the original DS-STAR.
        Decides whether the plan needs a new step or an existing step must be fixed.
        Output is always one of: "Step N is wrong!" or "Add Step".
        """
        plan_str = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(plan))
        prompt = PROMPT_TEMPLATES["router"].format(
            question=query,
            summaries=data_desc,
            plan=plan_str,
            result=result,
            current_step=plan[-1] if plan else ""
        )
        return (await _call_llm(prompt, self.config.model_name)).strip()

    async def _debugger(self, code: str, error: str) -> str:
        """
        Mirrors _debug_code() from the original DS-STAR.
        Given broken code and its error traceback, returns corrected code.
        """
        prompt = PROMPT_TEMPLATES["debugger"].format(
            code=code,
            bug=error,
            collection_name=self.config.collection_name,
            db_name=self.config.db_name
        )
        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _finalizer(
        self,
        code: str,
        result: str,
        query: str,
        data_desc: str
    ) -> str:
        """
        Mirrors finalize_solution() from the original DS-STAR.
        Produces code that prints a single structured JSON object to stdout.
        """
        guidelines = (
            "Print ONLY a single JSON object to stdout (no other text). "
            "Required keys: answer, analysis_type, total, top_items, data, "
            "province_focus, sector_focus. See the detailed schema in the prompt."
        )
        prompt = PROMPT_TEMPLATES["finalizer"].format(
            summaries=data_desc,
            code=code,
            result=result,
            question=query,
            guidelines=guidelines,
            db_name=self.config.db_name,
            collection_name=self.config.collection_name
        )
        response = await _call_llm(prompt, self.config.model_name)
        return _extract_code_block(response)

    async def _execute_and_debug(self, code: str, data_desc: str) -> str:
        """
        Mirrors _execute_and_debug_code() from the original DS-STAR.
        Executes code; on failure, calls the Debugger up to max_debug_attempts times.
        Returns stdout on success, or a prefixed error string on permanent failure.
        """
        exec_result, error = _execute_code(code, timeout=self.config.execution_timeout)

        attempts = 0
        while error and attempts < self.config.max_debug_attempts:
            logger.warning(f"[Debug] Attempt {attempts + 1}: {error[:150]}")
            code = await self._debugger(code, error)
            exec_result, error = _execute_code(code, timeout=self.config.execution_timeout)
            attempts += 1

        if error:
            logger.error(
                f"[Debug] Code failed after {attempts} debug attempt(s): {error[:300]}"
            )
            return f"EXECUTION_ERROR: {error}"

        return exec_result

    # --------------------------------------------------------------------------
    # PHASE 4: RESPONSE GENERATION
    # --------------------------------------------------------------------------

    async def _generate_narrative(
        self, query: str, result_json: str, language: str
    ) -> str:
        """Generate a human-readable Indonesian narrative from the JSON result."""
        try:
            prompt = PROMPT_TEMPLATES["narrative"].format(
                question=query,
                result_json=result_json,
                language=language
            )
            narrative = await _call_llm(prompt, self.config.model_name)
            if narrative and len(narrative) > 20:
                return narrative
        except Exception as e:
            logger.error(f"[Phase 4] Narrative generation failed: {e}")

        # Fallback: surface the 'answer' field from the JSON result
        try:
            data = json.loads(result_json)
            return data.get(
                'answer',
                'Data telah dianalisis. Lihat visualisasi untuk detail.'
            )
        except Exception:
            return (
                "Data telah berhasil dianalisis. "
                "Silakan lihat visualisasi untuk informasi lebih detail."
            )

    def _build_visualizations(self, result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build ECharts configs using the existing VisualizationAgent."""
        try:
            from visualization_agent import VisualizationAgent
            viz_agent = VisualizationAgent()

            analysis_type = result_data.get('analysis_type', 'overview')
            top_items = result_data.get('top_items', [])
            data = result_data.get('data', {})

            analysis = {'total_usaha': result_data.get('total', 0)}
            aggregated = {'type': analysis_type}

            if not top_items:
                return []

            # Determine whether top_items represent provinces or sectors
            is_province = any(
                item.get('name', '').upper() in _KNOWN_PROVINCES
                for item in top_items[:3]
            )

            # --- Province-based item types ---
            if is_province or analysis_type in ('ranking', 'overview', 'comparison'):
                analysis['top_provinces'] = [
                    {
                        'provinsi': it['name'],
                        'total': it['value'],
                        'percentage': it.get('percentage', 0)
                    }
                    for it in top_items
                ]
                analysis['all_provinces'] = analysis['top_provinces']

            # --- Sector-based item types ---
            if not is_province or analysis_type in ('distribution', 'overview'):
                sector_items = (
                    top_items if not is_province
                    else data.get('top_sectors', [])
                )
                if sector_items and isinstance(sector_items, list):
                    analysis['top_sectors'] = [
                        {
                            'code': it.get('code', ''),
                            'name': it['name'],
                            'short_name': it.get('short_name', it['name'][:20]),
                            'total': it['value'],
                            'percentage': it.get('percentage', 0)
                        }
                        for it in sector_items
                    ]

            # --- Distribution ---
            if analysis_type == 'distribution':
                analysis['distribution_detail'] = [
                    {
                        'sector_code': it.get('code', ''),
                        'sector_name': it['name'],
                        'short_name': it.get('short_name', it['name'][:20]),
                        'total': it['value'],
                        'percentage': it.get('percentage', 0)
                    }
                    for it in top_items
                ]

            # --- Province detail ---
            if analysis_type == 'province_detail':
                analysis['provinsi'] = result_data.get('province_focus', '')
                analysis['all_sectors'] = [
                    {
                        'code': it.get('code', ''),
                        'name': it['name'],
                        'short_name': it.get('short_name', it['name'][:20]),
                        'total': it['value'],
                        'percentage': it.get('percentage', 0)
                    }
                    for it in top_items
                ]
                analysis['top_sectors'] = analysis['all_sectors'][:5]

            # --- Sector analysis ---
            if analysis_type == 'sector_analysis' and is_province:
                analysis['all_provinces'] = analysis.get('top_provinces', [])
                analysis['sector_names'] = result_data.get('sector_focus', [])
                aggregated['type'] = 'sector_analysis'

            visualizations = viz_agent.create_visualizations(analysis, aggregated)
            return [viz.dict() for viz in visualizations]

        except Exception as e:
            logger.error(f"[Phase 4] Visualization build failed: {e}", exc_info=True)
            return []

    async def _generate_insights_and_policies(
        self,
        result_data: Dict[str, Any],
        query: str,
        language: str
    ) -> Dict[str, Any]:
        """
        GUARANTEED insight and policy generation.

        Three-tier fallback strategy:
          1. Existing InsightGenerationAgent (uses Gemini with structured output)
          2. Direct LLM call with JSON mode (if Tier 1 is insufficient)
          3. Rule-based generation (always produces ≥2 insights and ≥1 policy)
        """
        insights: List[str] = []
        policies: List[Dict[str, Any]] = []

        # --- Tier 1: InsightGenerationAgent ---
        try:
            from insight_agent import InsightGenerationAgent
            agent = InsightGenerationAgent()

            # Build a minimal analysis dict compatible with InsightGenerationAgent
            analysis = {
                'total_usaha': result_data.get('total', 0),
                'top_provinces': [
                    {
                        'provinsi': it['name'],
                        'total': it['value'],
                        'percentage': it.get('percentage', 0)
                    }
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

                for p in insight_result.get('policies', []):
                    if hasattr(p, 'dict'):
                        policies.append(p.dict())
                    elif isinstance(p, dict):
                        policies.append(p)

            logger.info(
                f"[Phase 4 Tier 1] InsightAgent: {len(insights)} insights, {len(policies)} policies"
            )
        except Exception as e:
            logger.warning(f"[Phase 4 Tier 1] InsightAgent failed: {e}")

        # --- Tier 2: Direct LLM call ---
        if len(insights) < 2 or len(policies) < 1:
            try:
                logger.info("[Phase 4 Tier 2] Generating insights via direct LLM call...")
                analysis_json = json.dumps(result_data, ensure_ascii=False, default=str)
                prompt = PROMPT_TEMPLATES["insight_generation"].format(
                    question=query,
                    analysis_json=analysis_json
                )
                llm_response = await _call_llm(
                    prompt, self.config.model_name, json_output=True
                )
                parsed = json.loads(llm_response)

                if isinstance(parsed, dict):
                    llm_insights = parsed.get('insights', [])
                    if isinstance(llm_insights, list) and len(llm_insights) >= 2:
                        insights = [i for i in llm_insights if isinstance(i, str)]

                    from models import PolicyCategory
                    for rec in parsed.get('policy_recommendations', []):
                        if isinstance(rec, dict):
                            policies.append({
                                'id': str(datetime.utcnow().timestamp()),
                                'title': rec.get('title', 'Rekomendasi'),
                                'description': rec.get('description', ''),
                                'priority': rec.get('priority', 'medium'),
                                'category': rec.get('category', 'economic').lower(),
                                'impact': rec.get('impact', ''),
                                'implementation_steps': rec.get('implementation_steps', []),
                                'supporting_insights': [],
                                'supporting_data_ids': [],
                                'created_at': datetime.utcnow().isoformat()
                            })

                logger.info(
                    f"[Phase 4 Tier 2] LLM: {len(insights)} insights, {len(policies)} policies"
                )
            except Exception as e:
                logger.warning(f"[Phase 4 Tier 2] Direct LLM insight generation failed: {e}")

        # --- Tier 3: Rule-based fallback (always runs if still insufficient) ---
        if len(insights) < 2:
            top_items = result_data.get('top_items', [])
            total = result_data.get('total', 0)

            insights = [
                f"Data Sensus Ekonomi 2016 menunjukkan total {total:,} unit usaha di Indonesia."
                if total else "Data Sensus Ekonomi 2016 telah berhasil dianalisis."
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
            logger.info(f"[Phase 4 Tier 3] Fallback: {len(insights)} insights")

        if len(policies) < 1:
            now = datetime.utcnow().isoformat()
            policies = [
                {
                    'id': str(datetime.utcnow().timestamp()),
                    'title': 'Pemerataan Pembangunan Ekonomi',
                    'description': (
                        'Mendorong pemerataan distribusi usaha melalui insentif fiskal '
                        'dan kemudahan perizinan di daerah tertinggal.'
                    ),
                    'priority': 'high',
                    'category': 'economic',
                    'impact': (
                        'Meningkatkan pertumbuhan ekonomi inklusif dan mengurangi '
                        'kesenjangan antar wilayah.'
                    ),
                    'implementation_steps': [
                        'Identifikasi provinsi dengan jumlah usaha rendah',
                        'Buat program insentif pajak untuk daerah tertinggal',
                        'Sederhanakan prosedur perizinan usaha',
                        'Tingkatkan infrastruktur pendukung ekonomi'
                    ],
                    'supporting_insights': [],
                    'supporting_data_ids': [],
                    'created_at': now
                },
                {
                    'id': str(datetime.utcnow().timestamp()) + '_2',
                    'title': 'Diversifikasi Sektor Ekonomi',
                    'description': (
                        'Mendorong pengembangan sektor non-perdagangan untuk mengurangi '
                        'ketergantungan pada satu sektor dominan.'
                    ),
                    'priority': 'medium',
                    'category': 'economic',
                    'impact': (
                        'Meningkatkan ketahanan ekonomi daerah terhadap guncangan sektoral.'
                    ),
                    'implementation_steps': [
                        'Analisis sektor potensial per wilayah',
                        'Buat program pelatihan kewirausahaan sektor baru',
                        'Fasilitasi akses permodalan untuk sektor underserved'
                    ],
                    'supporting_insights': [],
                    'supporting_data_ids': [],
                    'created_at': now
                }
            ]
            logger.info(f"[Phase 4 Tier 3] Fallback: {len(policies)} policies")

        return {'insights': insights, 'policies': policies}

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------

    def _parse_json_result(self, raw_output: str) -> Dict[str, Any]:
        """
        Parse the structured JSON object from code execution stdout.
        Tries direct parse first; falls back to regex extraction for cases
        where the code also prints debug text before the JSON.
        """
        _empty = {
            'answer': 'Tidak dapat menganalisis data.',
            'analysis_type': 'unknown',
            'total': 0,
            'top_items': [],
            'data': {},
            'province_focus': None,
            'sector_focus': []
        }

        if not raw_output or raw_output.startswith("EXECUTION_ERROR:"):
            return _empty

        # Try direct parse
        try:
            return json.loads(raw_output.strip())
        except json.JSONDecodeError:
            pass

        # Find the last complete JSON object in the output
        # (code may emit debug prints before the final JSON)
        json_candidates = re.findall(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_output
        )
        for candidate in reversed(json_candidates):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict) and (
                    'answer' in parsed or 'top_items' in parsed
                ):
                    return parsed
            except json.JSONDecodeError:
                continue

        # Last resort: treat the whole output as the answer string
        return {
            **_empty,
            'answer': raw_output.strip()[:500],
        }

    def _is_data_query(self, query: str) -> bool:
        """
        Determine whether a query needs data analysis or is purely conversational.
        Conversational queries (greetings, capability questions) are handled by a
        lightweight Gemini call without the full DS-STAR pipeline.
        """
        q = query.lower()

        data_keywords = [
            'berapa', 'jumlah', 'total', 'banyak',
            'bandingkan', 'compare', 'versus', 'vs',
            'terbanyak', 'tertinggi', 'terendah', 'top', 'ranking', 'urut', 'paling',
            'distribusi', 'sebaran', 'komposisi', 'proporsi', 'persentase',
            'provinsi', 'sektor', 'wilayah', 'daerah', 'kbli',
            'analisis', 'analyze', 'analisa', 'data', 'statistik',
            'usaha', 'bisnis', 'perusahaan', 'industri',
            'perdagangan', 'pertanian', 'pertambangan', 'konstruksi',
            'peta', 'map', 'persebaran', 'overview', 'gambaran',
            'sensus', 'ekonomi',
            'jawa', 'sumatera', 'kalimantan', 'sulawesi', 'papua',
            'bali', 'jakarta', 'sumut', 'jabar', 'jatim', 'jateng',
        ]

        conversational_only = [
            'halo', 'hello', 'hi ', 'hai ', 'hey',
            'terima kasih', 'thanks', 'thank',
            'siapa kamu', 'who are you', 'apa itu', 'what is',
            'selamat pagi', 'selamat siang', 'selamat malam', 'assalamualaikum',
            'tolong jelaskan', 'bisa apa', 'kemampuan', 'fitur',
        ]

        has_data = any(kw in q for kw in data_keywords)
        is_conv = any(kw in q for kw in conversational_only)

        # If only conversational keywords and no data keywords → conversational
        if is_conv and not has_data:
            return False
        # Otherwise, treat as a data query (default)
        return has_data or not is_conv

    async def _handle_conversational(
        self, query: str, language: str
    ) -> Dict[str, Any]:
        """Handle non-data queries (greetings, capability questions, etc.)."""
        try:
            prompt = PROMPT_TEMPLATES["conversational"].format(
                question=query,
                language=language
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
# PUBLIC EXPORTS
# ==============================================================================

__all__ = [
    'DSStarOrchestrator',
    'DataFileAnalyzerAgent',
    'DSStarConfig',
    'KBLI_MAPPING',
    'KBLI_SHORT_NAMES',
]
