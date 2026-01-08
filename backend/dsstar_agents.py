"""
DS-STAR: Data Science Agent via Iterative Planning and Verification
====================================================================
Implementasi framework DS-STAR untuk SMART SE 2026 Agentic AI

Framework ini berdasarkan paper:
"DS-STAR: Data Science Agent via Iterative Planning and Verification"
(Nam et al., Google Cloud & KAIST, 2025)

Komponen Utama:
1. DataFileAnalyzer - Menganalisis struktur data dari MongoDB
2. PlannerAgent - Membuat rencana analisis
3. CoderAgent - Mengimplementasikan rencana ke dalam operasi data
4. VerifierAgent - Memverifikasi kecukupan rencana (LLM-as-Judge)
5. RouterAgent - Menentukan apakah menambah step atau memperbaiki
6. DebuggerAgent - Memperbaiki error secara otomatis
7. DSStarOrchestrator - Mengkoordinasikan semua agent
"""

import os
import logging
import json
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv

# Load environment
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & DATA CLASSES
# ==============================================================================

class PlanStepStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class VerificationResult(str, Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    ERROR = "error"


class RouterDecision(str, Enum):
    ADD_STEP = "add_step"
    REMOVE_STEP = "remove_step"  # Returns index of step to remove


@dataclass
class PlanStep:
    """Representasi satu langkah dalam rencana analisis"""
    id: int
    description: str
    operation_type: str  # 'data_retrieval', 'aggregation', 'analysis', 'visualization', 'insight'
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int = 0


@dataclass
class AnalysisPlan:
    """Rencana analisis lengkap"""
    query: str
    steps: List[PlanStep] = field(default_factory=list)
    current_step_index: int = 0
    is_sufficient: bool = False
    verification_feedback: str = ""
    iteration_count: int = 0
    max_iterations: int = 20
    final_result: Optional[Dict[str, Any]] = None


@dataclass
class DataDescription:
    """Deskripsi struktur data dari analyzer"""
    collection_name: str
    document_count: int
    sample_documents: List[Dict[str, Any]]
    field_types: Dict[str, str]
    field_statistics: Dict[str, Any]
    available_provinces: List[str]
    available_sectors: Dict[str, str]
    summary: str


# ==============================================================================
# KBLI MAPPING (Shared across agents)
# ==============================================================================

KBLI_MAPPING = {
    'A': 'Pertanian, Kehutanan, dan Perikanan',
    'B': 'Pertambangan dan Penggalian',
    'C': 'Industri Pengolahan',
    'D': 'Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin',
    'E': 'Pengelolaan Air, Pengelolaan Air Limbah, Pengelolaan dan Daur Ulang Sampah',
    'F': 'Konstruksi',
    'G': 'Perdagangan Besar dan Eceran; Reparasi dan Perawatan Mobil dan Sepeda Motor',
    'H': 'Transportasi dan Pergudangan',
    'I': 'Penyediaan Akomodasi dan Penyediaan Makan Minum',
    'J': 'Informasi dan Komunikasi',
    'K': 'Jasa Keuangan dan Asuransi',
    'L': 'Real Estat',
    'M': 'Jasa Profesional, Ilmiah dan Teknis',
    'N': 'Jasa Persewaan, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha Lainnya',
    'O': 'Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib',
    'P': 'Jasa Pendidikan',
    'Q': 'Jasa Kesehatan dan Kegiatan Sosial',
    'R': 'Kesenian, Hiburan dan Rekreasi',
    'S': 'Kegiatan Jasa Lainnya',
    'T': 'Jasa Perorangan yang Melayani Rumah Tangga',
    'U': 'Kegiatan Badan Internasional dan Badan Ekstra Internasional Lainnya'
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


# ==============================================================================
# BASE AGENT CLASS
# ==============================================================================

class BaseAgent:
    """Base class untuk semua DS-STAR agents"""
    
    def __init__(self, db: AsyncIOMotorDatabase, model_name: str = None):
        self.db = db
        self.collection = db.initial_data
        
        # Initialize Gemini
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            self.model_name = model_name or os.environ.get('LLM_MODEL', 'gemini-2.0-flash-exp')
            self.model = genai.GenerativeModel(self.model_name)
            self.has_llm = True
        else:
            self.model = None
            self.has_llm = False
            logger.warning(f"{self.__class__.__name__}: No LLM API key found")
    
    async def _call_llm(self, prompt: str, json_output: bool = False) -> str:
        """Call LLM with error handling"""
        if not self.has_llm:
            return ""
        
        try:
            if json_output:
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    generation_config={"response_mime_type": "application/json"}
                )
                response = await model.generate_content_async(prompt)
            else:
                response = await self.model.generate_content_async(prompt)
            
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""


# ==============================================================================
# 1. DATA FILE ANALYZER AGENT
# ==============================================================================

class DataFileAnalyzerAgent(BaseAgent):
    """
    Agent untuk menganalisis struktur data dari MongoDB.
    Sesuai DS-STAR Section 3.1: "Analyzing data files"
    
    Agent ini menghasilkan deskripsi kontekstual dari data yang akan digunakan
    oleh agent lain untuk membuat keputusan yang lebih baik.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
        self._cached_description: Optional[DataDescription] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 3600  # Cache for 1 hour
    
    async def analyze_data_structure(self, force_refresh: bool = False) -> DataDescription:
        """
        Analyze the structure of data in MongoDB collection.
        Returns DataDescription with comprehensive metadata.
        """
        # Check cache
        if not force_refresh and self._is_cache_valid():
            logger.info("Using cached data description")
            return self._cached_description
        
        logger.info("Analyzing data structure from MongoDB...")
        
        try:
            # 1. Get document count
            doc_count = await self.collection.count_documents({})
            
            # 2. Get sample documents
            cursor = self.collection.find({}, {'_id': 0}).limit(5)
            samples = await cursor.to_list(length=5)
            
            # 3. Analyze field types and statistics
            field_types = {}
            field_stats = {}
            
            if samples:
                sample = samples[0]
                for key, value in sample.items():
                    if key in ['provinsi', 'kode_provinsi', 'total']:
                        field_types[key] = type(value).__name__
                    elif key in KBLI_MAPPING:
                        # Sector fields have nested structure
                        if isinstance(value, dict):
                            field_types[key] = "dict (nested sector data)"
                        else:
                            field_types[key] = type(value).__name__
            
            # 4. Get all provinces
            provinces = await self.collection.distinct('provinsi')
            
            # 5. Identify available sectors from sample
            available_sectors = {}
            if samples:
                for key in samples[0].keys():
                    if key in KBLI_MAPPING:
                        available_sectors[key] = KBLI_SHORT_NAMES.get(key, key)
            
            # 6. Calculate statistics
            pipeline = [
                {"$group": {
                    "_id": None,
                    "total_usaha": {"$sum": "$total"},
                    "avg_per_province": {"$avg": "$total"},
                    "max_province": {"$max": "$total"},
                    "min_province": {"$min": "$total"}
                }}
            ]
            stats_cursor = self.collection.aggregate(pipeline)
            stats_list = await stats_cursor.to_list(length=1)
            
            if stats_list:
                field_stats = {
                    'total_usaha_nasional': stats_list[0].get('total_usaha', 0),
                    'rata_rata_per_provinsi': stats_list[0].get('avg_per_province', 0),
                    'maximum_per_provinsi': stats_list[0].get('max_province', 0),
                    'minimum_per_provinsi': stats_list[0].get('min_province', 0)
                }
            
            # 7. Generate summary
            summary = self._generate_summary(
                doc_count, provinces, available_sectors, field_stats
            )
            
            # Create description object
            description = DataDescription(
                collection_name='initial_data',
                document_count=doc_count,
                sample_documents=samples,
                field_types=field_types,
                field_statistics=field_stats,
                available_provinces=sorted(provinces),
                available_sectors=available_sectors,
                summary=summary
            )
            
            # Update cache
            self._cached_description = description
            self._cache_timestamp = datetime.utcnow()
            
            logger.info(f"Data analysis complete: {doc_count} documents, {len(provinces)} provinces, {len(available_sectors)} sectors")
            
            return description
            
        except Exception as e:
            logger.error(f"Error analyzing data structure: {e}", exc_info=True)
            # Return minimal description on error
            return DataDescription(
                collection_name='initial_data',
                document_count=0,
                sample_documents=[],
                field_types={},
                field_statistics={},
                available_provinces=[],
                available_sectors={},
                summary="Error analyzing data structure"
            )
    
    def _is_cache_valid(self) -> bool:
        """Check if cached description is still valid"""
        if not self._cached_description or not self._cache_timestamp:
            return False
        
        elapsed = (datetime.utcnow() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl_seconds
    
    def _generate_summary(
        self, 
        doc_count: int, 
        provinces: List[str], 
        sectors: Dict[str, str],
        stats: Dict[str, Any]
    ) -> str:
        """Generate human-readable summary of data structure"""
        total_usaha = stats.get('total_usaha_nasional', 0)
        avg_per_prov = stats.get('rata_rata_per_provinsi', 0)
        
        return f"""
Data Sensus Ekonomi Indonesia 2016:
- Total dokumen: {doc_count} provinsi
- Total unit usaha: {total_usaha:,}
- Rata-rata per provinsi: {avg_per_prov:,.0f} usaha
- Provinsi tersedia: {len(provinces)} ({', '.join(provinces[:5])}...)
- Sektor KBLI tersedia: {len(sectors)} sektor (A-U)
- Struktur data: Setiap dokumen memiliki data per sektor dalam format nested dict

Sektor-sektor utama:
{chr(10).join([f"  - {code}: {name}" for code, name in list(sectors.items())[:8]])}
        """.strip()
    
    def get_context_for_prompt(self) -> str:
        """Get formatted context string for LLM prompts"""
        if not self._cached_description:
            return "Data context not available"
        
        desc = self._cached_description
        return f"""
=== KONTEKS DATA SENSUS EKONOMI ===
Collection: {desc.collection_name}
Jumlah Provinsi: {desc.document_count}
Total Usaha Nasional: {desc.field_statistics.get('total_usaha_nasional', 0):,}

PROVINSI TERSEDIA:
{', '.join(desc.available_provinces)}

SEKTOR KBLI TERSEDIA:
{json.dumps(desc.available_sectors, indent=2, ensure_ascii=False)}

STATISTIK:
{json.dumps(desc.field_statistics, indent=2, ensure_ascii=False)}
        """.strip()


# ==============================================================================
# 2. PLANNER AGENT
# ==============================================================================

class PlannerAgent(BaseAgent):
    """
    Agent untuk membuat dan memperluas rencana analisis.
    Sesuai DS-STAR Section 3.2: "Iterative plan generation"
    
    Planner menghasilkan high-level steps yang kemudian diimplementasikan
    oleh CoderAgent.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
    
    async def create_initial_plan(
        self, 
        query: str, 
        data_description: DataDescription
    ) -> AnalysisPlan:
        """
        Create initial plan with a single executable step.
        DS-STAR starts with simple plan and iteratively refines.
        """
        logger.info(f"Creating initial plan for query: {query[:50]}...")
        
        # Detect query intent
        intent = self._detect_intent(query, data_description)
        
        # Create first step based on intent
        first_step = PlanStep(
            id=0,
            description=f"Retrieve data based on intent: {intent['type']}",
            operation_type="data_retrieval",
            parameters={
                'intent_type': intent['type'],
                'provinces': intent.get('provinces', []),
                'sectors': intent.get('sectors', []),
                'aggregation': intent.get('aggregation', 'sum')
            }
        )
        
        plan = AnalysisPlan(
            query=query,
            steps=[first_step]
        )
        
        logger.info(f"Initial plan created with intent: {intent['type']}")
        return plan
    
    async def add_next_step(
        self, 
        plan: AnalysisPlan, 
        execution_result: Dict[str, Any],
        data_description: DataDescription
    ) -> PlanStep:
        """
        Generate next step based on current plan state and execution results.
        """
        current_steps = len(plan.steps)
        last_step = plan.steps[-1] if plan.steps else None
        
        # Determine next step based on workflow
        if last_step:
            if last_step.operation_type == "data_retrieval":
                # After data retrieval, do aggregation
                next_step = PlanStep(
                    id=current_steps,
                    description="Aggregate retrieved data according to intent",
                    operation_type="aggregation",
                    parameters={
                        'aggregation_type': self._determine_aggregation_type(plan),
                        'data_from_step': last_step.id
                    }
                )
            elif last_step.operation_type == "aggregation":
                # After aggregation, do analysis
                next_step = PlanStep(
                    id=current_steps,
                    description="Perform statistical analysis on aggregated data",
                    operation_type="analysis",
                    parameters={
                        'analysis_type': 'statistical',
                        'data_from_step': last_step.id
                    }
                )
            elif last_step.operation_type == "analysis":
                # After analysis, create visualizations
                next_step = PlanStep(
                    id=current_steps,
                    description="Generate visualizations from analysis results",
                    operation_type="visualization",
                    parameters={
                        'data_from_step': last_step.id
                    }
                )
            elif last_step.operation_type == "visualization":
                # After visualization, generate insights
                next_step = PlanStep(
                    id=current_steps,
                    description="Generate insights and policy recommendations",
                    operation_type="insight",
                    parameters={
                        'data_from_step': last_step.id,
                        'language': 'Indonesian'
                    }
                )
            else:
                # Final step - generate response
                next_step = PlanStep(
                    id=current_steps,
                    description="Compile final response with narrative",
                    operation_type="response_generation",
                    parameters={
                        'include_all_results': True
                    }
                )
        else:
            # No steps yet, start with data retrieval
            next_step = PlanStep(
                id=0,
                description="Initial data retrieval",
                operation_type="data_retrieval",
                parameters={}
            )
        
        logger.info(f"Added step {next_step.id}: {next_step.operation_type}")
        return next_step
    
    def _detect_intent(self, query: str, data_desc: DataDescription) -> Dict[str, Any]:
        """Detect query intent using rule-based approach (fast, no LLM needed)"""
        query_lower = query.lower()
        
        intent = {
            'type': 'overview',
            'provinces': [],
            'sectors': [],
            'aggregation': 'sum'
        }
        
        # Detect intent type
        if any(w in query_lower for w in ['bandingkan', 'compare', 'vs', 'versus']):
            intent['type'] = 'comparison'
        elif any(w in query_lower for w in ['ranking', 'tertinggi', 'terendah', 'top', 'terbanyak']):
            intent['type'] = 'ranking'
        elif any(w in query_lower for w in ['distribusi', 'sebaran', 'komposisi', 'proporsi']):
            intent['type'] = 'distribution'
        elif any(w in query_lower for w in ['berapa', 'jumlah', 'total']):
            intent['type'] = 'specific_value'
        elif any(w in query_lower for w in ['analisis', 'analyze', 'gambaran']):
            intent['type'] = 'overview'
        
        # Extract provinces
        intent['provinces'] = self._extract_provinces(query, data_desc.available_provinces)
        
        # Extract sectors
        intent['sectors'] = self._extract_sectors(query)
        
        # Refine intent based on entities
        if intent['provinces'] and len(intent['provinces']) == 1:
            if intent['type'] in ['overview', 'specific_value']:
                intent['type'] = 'province_detail'
        elif intent['provinces'] and len(intent['provinces']) > 1:
            intent['type'] = 'comparison'
        
        if intent['sectors'] and not intent['provinces']:
            if intent['type'] in ['overview', 'specific_value']:
                intent['type'] = 'sector_analysis'
        
        return intent
    
    def _extract_provinces(self, query: str, available: List[str]) -> List[str]:
        """Extract province names from query"""
        query_lower = query.lower()
        found = []
        
        # Province name variations
        province_map = {
            'aceh': 'ACEH', 'sumut': 'SUMATERA UTARA', 'sumatera utara': 'SUMATERA UTARA',
            'sumbar': 'SUMATERA BARAT', 'sumatera barat': 'SUMATERA BARAT',
            'riau': 'RIAU', 'jambi': 'JAMBI', 'sumsel': 'SUMATERA SELATAN',
            'sumatera selatan': 'SUMATERA SELATAN', 'bengkulu': 'BENGKULU',
            'lampung': 'LAMPUNG', 'babel': 'KEP. BANGKA BELITUNG',
            'bangka belitung': 'KEP. BANGKA BELITUNG', 'kepri': 'KEPULAUAN RIAU',
            'kepulauan riau': 'KEPULAUAN RIAU', 'dki': 'DKI JAKARTA',
            'jakarta': 'DKI JAKARTA', 'jabar': 'JAWA BARAT', 'jawa barat': 'JAWA BARAT',
            'jateng': 'JAWA TENGAH', 'jawa tengah': 'JAWA TENGAH',
            'yogya': 'DI YOGYAKARTA', 'yogyakarta': 'DI YOGYAKARTA', 'diy': 'DI YOGYAKARTA',
            'jatim': 'JAWA TIMUR', 'jawa timur': 'JAWA TIMUR', 'banten': 'BANTEN',
            'bali': 'BALI', 'ntb': 'NUSA TENGGARA BARAT', 'ntt': 'NUSA TENGGARA TIMUR',
            'kalbar': 'KALIMANTAN BARAT', 'kalteng': 'KALIMANTAN TENGAH',
            'kalsel': 'KALIMANTAN SELATAN', 'kaltim': 'KALIMANTAN TIMUR',
            'kaltara': 'KALIMANTAN UTARA', 'sulut': 'SULAWESI UTARA',
            'sulteng': 'SULAWESI TENGAH', 'sulsel': 'SULAWESI SELATAN',
            'sultra': 'SULAWESI TENGGARA', 'gorontalo': 'GORONTALO',
            'sulbar': 'SULAWESI BARAT', 'maluku': 'MALUKU', 'malut': 'MALUKU UTARA',
            'papua': 'PAPUA', 'papua barat': 'PAPUA BARAT'
        }
        
        # Sort by length descending to match longer names first
        for key in sorted(province_map.keys(), key=len, reverse=True):
            if key in query_lower:
                value = province_map[key]
                if value not in found and value in available:
                    found.append(value)
        
        return found
    
    def _extract_sectors(self, query: str) -> List[str]:
        """Extract sector codes from query"""
        query_lower = query.lower()
        found = []
        
        sector_keywords = {
            'pertanian': 'A', 'kehutanan': 'A', 'perikanan': 'A',
            'pertambangan': 'B', 'tambang': 'B',
            'industri': 'C', 'manufaktur': 'C', 'pengolahan': 'C',
            'listrik': 'D', 'gas': 'D', 'energi': 'D',
            'air': 'E', 'limbah': 'E', 'sampah': 'E',
            'konstruksi': 'F', 'bangunan': 'F',
            'perdagangan': 'G', 'retail': 'G', 'eceran': 'G', 'dagang': 'G',
            'transportasi': 'H', 'logistik': 'H',
            'hotel': 'I', 'restoran': 'I', 'akomodasi': 'I', 'kuliner': 'I',
            'informasi': 'J', 'komunikasi': 'J', 'it': 'J',
            'keuangan': 'K', 'bank': 'K', 'asuransi': 'K',
            'real estat': 'L', 'properti': 'L',
            'profesional': 'M', 'konsultan': 'M',
            'persewaan': 'N', 'travel': 'N',
            'pemerintah': 'O', 'administrasi': 'O',
            'pendidikan': 'P', 'sekolah': 'P',
            'kesehatan': 'Q', 'rumah sakit': 'Q', 'klinik': 'Q',
            'hiburan': 'R', 'rekreasi': 'R', 'seni': 'R',
            'jasa lainnya': 'S'
        }
        
        for keyword, code in sector_keywords.items():
            if keyword in query_lower and code not in found:
                found.append(code)
        
        return found
    
    def _determine_aggregation_type(self, plan: AnalysisPlan) -> str:
        """Determine aggregation type based on intent"""
        if plan.steps:
            params = plan.steps[0].parameters
            intent_type = params.get('intent_type', 'overview')
            
            aggregation_map = {
                'overview': 'full_overview',
                'ranking': 'ranking',
                'comparison': 'comparison',
                'distribution': 'distribution',
                'province_detail': 'province_detail',
                'sector_analysis': 'sector_analysis',
                'specific_value': 'specific_value'
            }
            
            return aggregation_map.get(intent_type, 'full_overview')
        
        return 'full_overview'


# ==============================================================================
# 3. VERIFIER AGENT (LLM-as-Judge)
# ==============================================================================

class VerifierAgent(BaseAgent):
    """
    Agent untuk memverifikasi apakah rencana sudah cukup untuk menjawab query.
    Sesuai DS-STAR Section 3.2: "Plan verification"
    
    Menggunakan LLM-as-Judge untuk menilai kecukupan plan.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
    
    async def verify_plan(
        self,
        plan: AnalysisPlan,
        execution_results: Dict[str, Any],
        data_description: DataDescription
    ) -> Tuple[VerificationResult, str]:
        """
        Verify if current plan is sufficient to answer the query.
        Returns (result, feedback_message)
        """
        logger.info(f"Verifying plan sufficiency (iteration {plan.iteration_count})...")
        
        # First, do rule-based verification (fast check)
        rule_result, rule_feedback = self._rule_based_verification(plan, execution_results)
        
        if rule_result == VerificationResult.SUFFICIENT:
            return rule_result, rule_feedback
        
        # If rule-based is insufficient, use LLM for deeper analysis
        if self.has_llm and plan.iteration_count > 0:
            llm_result, llm_feedback = await self._llm_verification(
                plan, execution_results, data_description
            )
            return llm_result, llm_feedback
        
        return rule_result, rule_feedback
    
    def _rule_based_verification(
        self, 
        plan: AnalysisPlan, 
        results: Dict[str, Any]
    ) -> Tuple[VerificationResult, str]:
        """Fast rule-based verification"""
        
        # Check if we have all necessary components
        required_operations = {'data_retrieval', 'aggregation', 'analysis', 'visualization'}
        completed_operations = {
            step.operation_type 
            for step in plan.steps 
            if step.status == PlanStepStatus.COMPLETED
        }
        
        # Check minimum requirements
        has_data = 'data_retrieval' in completed_operations
        has_aggregation = 'aggregation' in completed_operations
        has_analysis = 'analysis' in completed_operations
        has_visualization = 'visualization' in completed_operations
        
        # Check if we have actual results
        has_message = bool(results.get('message'))
        has_visualizations = bool(results.get('visualizations'))
        has_supporting_data = results.get('supporting_data_count', 0) > 0
        
        # Determine sufficiency
        if has_data and has_aggregation and has_analysis and has_visualization:
            if has_message or has_visualizations:
                return VerificationResult.SUFFICIENT, "Plan has all required components with results"
        
        # Determine what's missing
        missing = []
        if not has_data:
            missing.append("data retrieval")
        if not has_aggregation:
            missing.append("aggregation")
        if not has_analysis:
            missing.append("analysis")
        if not has_visualization:
            missing.append("visualization")
        
        if not has_supporting_data and has_data:
            missing.append("valid data (no records found)")
        
        feedback = f"Plan incomplete. Missing: {', '.join(missing)}" if missing else "Plan needs refinement"
        return VerificationResult.INSUFFICIENT, feedback
    
    async def _llm_verification(
        self,
        plan: AnalysisPlan,
        results: Dict[str, Any],
        data_desc: DataDescription
    ) -> Tuple[VerificationResult, str]:
        """LLM-based verification for complex cases"""
        
        prompt = f"""Anda adalah verifier untuk sistem analisis data. Tugas Anda adalah menentukan apakah rencana analisis sudah CUKUP untuk menjawab pertanyaan user.

PERTANYAAN USER:
{plan.query}

RENCANA SAAT INI (Step yang sudah dieksekusi):
{self._format_plan_steps(plan)}

HASIL EKSEKUSI:
- Ada pesan respons: {bool(results.get('message'))}
- Jumlah visualisasi: {len(results.get('visualizations', []))}
- Jumlah insight: {len(results.get('insights', []))}
- Data pendukung: {results.get('supporting_data_count', 0)} records

KONTEKS DATA:
{data_desc.summary}

Jawab dengan format JSON:
{{
    "is_sufficient": true/false,
    "reason": "alasan singkat",
    "missing_components": ["komponen yang kurang"] atau []
}}
"""
        
        try:
            response = await self._call_llm(prompt, json_output=True)
            result = json.loads(response)
            
            if result.get('is_sufficient', False):
                return VerificationResult.SUFFICIENT, result.get('reason', 'LLM verified as sufficient')
            else:
                missing = result.get('missing_components', [])
                return VerificationResult.INSUFFICIENT, f"LLM feedback: {result.get('reason', 'Needs improvement')}. Missing: {missing}"
                
        except Exception as e:
            logger.error(f"LLM verification error: {e}")
            return VerificationResult.INSUFFICIENT, "Verification error, continuing with default flow"
    
    def _format_plan_steps(self, plan: AnalysisPlan) -> str:
        """Format plan steps for prompt"""
        lines = []
        for step in plan.steps:
            status_icon = "✓" if step.status == PlanStepStatus.COMPLETED else "○"
            lines.append(f"{status_icon} Step {step.id}: {step.operation_type} - {step.description}")
        return "\n".join(lines)


# ==============================================================================
# 4. ROUTER AGENT
# ==============================================================================

class RouterAgent(BaseAgent):
    """
    Agent untuk menentukan aksi selanjutnya saat plan belum cukup.
    Sesuai DS-STAR Section 3.2: "Plan refinement"
    
    Memutuskan apakah akan:
    - ADD_STEP: Menambah step baru
    - REMOVE_STEP: Menghapus step yang salah dan regenerate
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
    
    async def decide_action(
        self,
        plan: AnalysisPlan,
        verification_feedback: str,
        execution_results: Dict[str, Any]
    ) -> Tuple[RouterDecision, Optional[int]]:
        """
        Decide whether to add step or remove incorrect step.
        Returns (decision, step_index_to_remove or None)
        """
        logger.info(f"Router deciding action. Feedback: {verification_feedback[:50]}...")
        
        # Check for errors in recent steps
        error_step = self._find_error_step(plan)
        if error_step is not None:
            logger.info(f"Router: Found error at step {error_step}, recommending removal")
            return RouterDecision.REMOVE_STEP, error_step
        
        # Check if we need more steps
        completed_types = {step.operation_type for step in plan.steps if step.status == PlanStepStatus.COMPLETED}
        
        # Standard workflow order
        workflow = ['data_retrieval', 'aggregation', 'analysis', 'visualization', 'insight']
        
        for op_type in workflow:
            if op_type not in completed_types:
                logger.info(f"Router: Missing {op_type}, adding next step")
                return RouterDecision.ADD_STEP, None
        
        # If all standard steps complete but still insufficient
        if plan.iteration_count < 3:
            logger.info("Router: All steps complete but insufficient, adding refinement step")
            return RouterDecision.ADD_STEP, None
        
        # Fallback: Add step
        return RouterDecision.ADD_STEP, None
    
    def _find_error_step(self, plan: AnalysisPlan) -> Optional[int]:
        """Find first step with error"""
        for step in plan.steps:
            if step.status == PlanStepStatus.FAILED or step.error:
                return step.id
        return None


# ==============================================================================
# 5. DEBUGGER AGENT
# ==============================================================================

class DebuggerAgent(BaseAgent):
    """
    Agent untuk memperbaiki error secara otomatis.
    Sesuai DS-STAR Section 3.3: "Debugging agent"
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
    
    async def debug_step(
        self,
        step: PlanStep,
        error: str,
        data_description: DataDescription
    ) -> PlanStep:
        """
        Attempt to fix a failed step.
        Returns modified step with corrected parameters.
        """
        logger.info(f"Debugger attempting to fix step {step.id}: {error[:50]}...")
        
        # Common error patterns and fixes
        fixes_applied = []
        
        # Fix 1: Empty data issues
        if 'no data' in error.lower() or 'empty' in error.lower():
            if step.parameters.get('provinces'):
                # Try removing province filter
                step.parameters['provinces'] = []
                fixes_applied.append("Removed province filter to broaden search")
        
        # Fix 2: Invalid province name
        if 'province' in error.lower() and 'not found' in error.lower():
            provinces = step.parameters.get('provinces', [])
            valid_provinces = data_description.available_provinces
            step.parameters['provinces'] = [p for p in provinces if p in valid_provinces]
            fixes_applied.append("Filtered to valid province names")
        
        # Fix 3: Invalid sector code
        if 'sector' in error.lower() or 'kbli' in error.lower():
            sectors = step.parameters.get('sectors', [])
            valid_sectors = list(data_description.available_sectors.keys())
            step.parameters['sectors'] = [s for s in sectors if s in valid_sectors]
            fixes_applied.append("Filtered to valid sector codes")
        
        # Reset step status for retry
        step.status = PlanStepStatus.PENDING
        step.error = None
        
        if fixes_applied:
            logger.info(f"Debugger fixes applied: {', '.join(fixes_applied)}")
        else:
            logger.info("Debugger could not identify specific fix, step reset for retry")
        
        return step


# ==============================================================================
# 6. CODER AGENT (Execution Engine)
# ==============================================================================

class CoderAgent(BaseAgent):
    """
    Agent untuk mengeksekusi step plan menjadi operasi database aktual.
    Sesuai DS-STAR Section 3.2: "Plan implement and execution"
    
    Mengimplementasikan high-level plan steps menjadi query MongoDB
    dan operasi data processing.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db)
        self._aggregated_data = {}
        self._analysis_results = {}
    
    async def execute_step(
        self,
        step: PlanStep,
        previous_results: Dict[str, Any],
        data_description: DataDescription
    ) -> Tuple[PlanStep, Dict[str, Any]]:
        """
        Execute a plan step and return results.
        """
        import time
        start_time = time.time()
        
        step.status = PlanStepStatus.EXECUTING
        logger.info(f"Executing step {step.id}: {step.operation_type}")
        
        try:
            result = {}
            
            if step.operation_type == "data_retrieval":
                result = await self._execute_data_retrieval(step, data_description)
            elif step.operation_type == "aggregation":
                result = await self._execute_aggregation(step, previous_results)
            elif step.operation_type == "analysis":
                result = await self._execute_analysis(step, previous_results)
            elif step.operation_type == "visualization":
                result = await self._execute_visualization(step, previous_results)
            elif step.operation_type == "insight":
                result = await self._execute_insight_generation(step, previous_results)
            elif step.operation_type == "response_generation":
                result = await self._execute_response_generation(step, previous_results)
            else:
                raise ValueError(f"Unknown operation type: {step.operation_type}")
            
            step.status = PlanStepStatus.COMPLETED
            step.result = result
            step.execution_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(f"Step {step.id} completed in {step.execution_time_ms}ms")
            return step, result
            
        except Exception as e:
            step.status = PlanStepStatus.FAILED
            step.error = str(e)
            step.execution_time_ms = int((time.time() - start_time) * 1000)
            
            logger.error(f"Step {step.id} failed: {e}")
            return step, {'error': str(e)}
    
    async def _execute_data_retrieval(
        self, 
        step: PlanStep, 
        data_desc: DataDescription
    ) -> Dict[str, Any]:
        """Execute data retrieval from MongoDB"""
        params = step.parameters
        
        query_filter = {}
        
        # Apply province filter
        provinces = params.get('provinces', [])
        if provinces:
            query_filter['provinsi'] = {'$in': provinces}
        
        # Fetch data
        cursor = self.collection.find(query_filter, {'_id': 0})
        data = await cursor.to_list(length=None)
        
        if not data:
            raise ValueError("No data found for the specified criteria")
        
        # Calculate totals if not present
        for doc in data:
            if 'total' not in doc or not doc['total']:
                doc['total'] = self._calculate_province_total(doc)
        
        # Filter by sectors if specified
        sectors = params.get('sectors', [])
        if sectors:
            for doc in data:
                sector_total = sum(
                    self._get_sector_value(doc, sector) 
                    for sector in sectors
                )
                doc['filtered_total'] = sector_total
                doc['filtered_sectors'] = sectors
        
        # Store for later steps
        self._aggregated_data['raw_data'] = data
        self._aggregated_data['intent_type'] = params.get('intent_type', 'overview')
        self._aggregated_data['provinces'] = provinces
        self._aggregated_data['sectors'] = sectors
        
        return {
            'data': data,
            'count': len(data),
            'intent_type': params.get('intent_type', 'overview')
        }
    
    async def _execute_aggregation(
        self, 
        step: PlanStep, 
        prev: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute data aggregation"""
        aggregation_type = step.parameters.get('aggregation_type', 'full_overview')
        data = self._aggregated_data.get('raw_data', prev.get('data', []))
        intent_type = self._aggregated_data.get('intent_type', 'overview')
        sectors = self._aggregated_data.get('sectors', [])
        
        if aggregation_type == 'ranking' or intent_type == 'ranking':
            result = self._aggregate_ranking(data, sectors)
        elif aggregation_type == 'comparison' or intent_type == 'comparison':
            result = self._aggregate_comparison(data, sectors)
        elif aggregation_type == 'distribution' or intent_type == 'distribution':
            result = self._aggregate_distribution(data, sectors)
        elif aggregation_type == 'province_detail' or intent_type == 'province_detail':
            result = self._aggregate_province_detail(data)
        elif aggregation_type == 'sector_analysis' or intent_type == 'sector_analysis':
            result = self._aggregate_sector_analysis(data, sectors)
        else:
            result = self._aggregate_overview(data)
        
        self._aggregated_data['aggregated'] = result
        return result
    
    async def _execute_analysis(
        self, 
        step: PlanStep, 
        prev: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute statistical analysis"""
        aggregated = self._aggregated_data.get('aggregated', prev)
        data_type = aggregated.get('type', 'overview')
        
        analysis = {}
        
        if data_type == 'overview':
            analysis = self._analyze_overview(aggregated)
        elif data_type == 'ranking':
            analysis = self._analyze_ranking(aggregated)
        elif data_type == 'comparison':
            analysis = self._analyze_comparison(aggregated)
        elif data_type == 'distribution':
            analysis = self._analyze_distribution(aggregated)
        elif data_type == 'province_detail':
            analysis = self._analyze_province_detail(aggregated)
        elif data_type == 'sector_analysis':
            analysis = self._analyze_sector_analysis(aggregated)
        
        # Enrich with advanced metrics
        analysis = self._enrich_with_advanced_metrics(analysis, aggregated)
        
        self._analysis_results = analysis
        return analysis
    
    async def _execute_visualization(
        self, 
        step: PlanStep, 
        prev: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create visualizations"""
        # Import visualization agent
        from visualization_agent import VisualizationAgent
        
        viz_agent = VisualizationAgent()
        analysis = self._analysis_results if self._analysis_results else prev
        aggregated = self._aggregated_data.get('aggregated', {})
        
        visualizations = viz_agent.create_visualizations(analysis, aggregated)
        
        return {
            'visualizations': [viz.dict() for viz in visualizations],
            'count': len(visualizations)
        }
    
    async def _execute_insight_generation(
        self, 
        step: PlanStep, 
        prev: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        FIXED: Generate insights using LLM with proper error handling
        """
        from insight_agent import InsightGenerationAgent
        
        logger.info("🔍 Starting insight generation...")
        
        try:
            insight_agent = InsightGenerationAgent()
            
            # Get analysis data
            analysis = self._analysis_results if self._analysis_results else prev
            aggregated = self._aggregated_data.get('aggregated', {})
            query = self._aggregated_data.get('query', '')
            language = step.parameters.get('language', 'Indonesian')
            
            # Validate we have data
            if not analysis:
                logger.warning("⚠️ No analysis data available for insight generation")
                return {
                    'insights': ["Data telah dianalisis. Silakan lihat visualisasi untuk detail."],
                    'policies': [],
                    'insights_count': 1,
                    'policies_count': 0
                }
            
            logger.info(f"📊 Generating insights with query: {query[:50]}...")
            
            # Call insight agent
            insights_result = await insight_agent.generate_insights(
                analysis, aggregated, query, language
            )
            
            # ===== CRITICAL FIX: Validate result structure =====
            if not isinstance(insights_result, dict):
                logger.error(f"❌ Insight agent returned non-dict: {type(insights_result)}")
                insights_result = {'insights': [], 'policies': []}
            
            # Extract insights and policies
            insights = insights_result.get('insights', [])
            policies = insights_result.get('policies', [])
            
            # ===== CRITICAL FIX: Convert policy objects to dicts =====
            policies_as_dicts = []
            for policy in policies:
                if hasattr(policy, 'dict'):
                    # It's a PolicyRecommendation object
                    policies_as_dicts.append(policy.dict())
                elif isinstance(policy, dict):
                    # Already a dict
                    policies_as_dicts.append(policy)
                else:
                    logger.warning(f"⚠️ Unknown policy type: {type(policy)}")
            
            logger.info(f"✅ Generated {len(insights)} insights and {len(policies_as_dicts)} policies")
            
            # Log samples for debugging
            if insights:
                logger.info(f"📝 Sample insight: {insights[0][:100]}...")
            if policies_as_dicts:
                logger.info(f"📋 Sample policy: {policies_as_dicts[0].get('title', 'N/A')}")
            
            return {
                'insights': insights,
                'policies': policies_as_dicts,
                'insights_count': len(insights),
                'policies_count': len(policies_as_dicts)
            }
            
        except Exception as e:
            logger.error(f"❌ Error in insight generation: {e}", exc_info=True)
            
            # ===== FALLBACK: Return default insights =====
            return {
                'insights': [
                    "Data menunjukkan variasi signifikan dalam distribusi usaha di Indonesia.",
                    "Terdapat konsentrasi ekonomi di beberapa provinsi utama."
                ],
                'policies': [{
                    'id': f"policy_{datetime.utcnow().timestamp()}",
                    'title': 'Pemerataan Pembangunan Ekonomi',
                    'description': 'Mendorong pemerataan distribusi usaha di seluruh Indonesia melalui insentif fiskal dan kemudahan perizinan.',
                    'priority': 'high',
                    'category': 'economic',
                    'impact': 'Meningkatkan pertumbuhan ekonomi inklusif dan mengurangi kesenjangan antar wilayah.',
                    'implementation_steps': [
                        'Identifikasi provinsi dengan jumlah usaha rendah',
                        'Buat program insentif pajak untuk daerah tertinggal',
                        'Sederhanakan prosedur perizinan usaha',
                        'Tingkatkan infrastruktur pendukung'
                    ],
                    'supporting_insights': [],
                    'supporting_data_ids': [],
                    'created_at': datetime.utcnow().isoformat()
                }],
                'insights_count': 2,
                'policies_count': 1,
                'fallback': True
            }
    
    async def _execute_response_generation(
        self, 
        step: PlanStep, 
        prev: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate final response narrative"""
        analysis = self._analysis_results
        aggregated = self._aggregated_data.get('aggregated', {})
        
        message = self._generate_fallback_response(analysis, aggregated)
        
        return {
            'message': message,
            'generated': True
        }
    
    # ========================
    # HELPER METHODS
    # ========================
    
    def _get_sector_value(self, doc: Dict[str, Any], sector_code: str) -> int:
        """Get sector value from nested document structure"""
        try:
            sector_obj = doc.get(sector_code)
            if isinstance(sector_obj, dict):
                values = list(sector_obj.values())
                return int(values[0]) if values else 0
            elif isinstance(sector_obj, (int, float)):
                return int(sector_obj)
            return 0
        except:
            return 0
    
    def _calculate_province_total(self, doc: Dict[str, Any]) -> int:
        """Calculate total usaha for a province"""
        if 'total' in doc and doc['total']:
            return int(doc['total'])
        
        total = 0
        for sector_code in KBLI_MAPPING.keys():
            total += self._get_sector_value(doc, sector_code)
        return total
    
    # Aggregation methods
    def _aggregate_overview(self, data: List[Dict]) -> Dict[str, Any]:
        """Aggregate for overview analysis"""
        provinces_data = []
        for doc in data:
            total = doc.get('filtered_total', doc.get('total', self._calculate_province_total(doc)))
            provinces_data.append({
                'provinsi': doc.get('provinsi', ''),
                'total': total
            })
        
        provinces_data.sort(key=lambda x: x['total'], reverse=True)
        
        sector_totals = {}
        for sector_code in KBLI_MAPPING.keys():
            total = sum(self._get_sector_value(doc, sector_code) for doc in data)
            if total > 0:
                sector_totals[sector_code] = {
                    'total': total,
                    'name': KBLI_MAPPING.get(sector_code),
                    'short_name': KBLI_SHORT_NAMES.get(sector_code)
                }
        
        grand_total = sum(p['total'] for p in provinces_data)
        
        return {
            'type': 'overview',
            'data': provinces_data,
            'sectors': sector_totals,
            'grand_total': grand_total,
            'provinces_count': len(provinces_data),
            'sectors_count': len(sector_totals),
            'top_provinces': provinces_data[:10],
            'all_provinces': provinces_data,
            'top_sectors': sorted([{'code': k, **v} for k, v in sector_totals.items()], 
                                 key=lambda x: x['total'], reverse=True)
        }
    
    def _aggregate_ranking(self, data: List[Dict], sectors: List[str]) -> Dict[str, Any]:
        """Aggregate for ranking"""
        if sectors:
            ranked = sorted(data, key=lambda x: x.get('filtered_total', 0), reverse=True)
        else:
            ranked = sorted(data, key=lambda x: x.get('total', 0), reverse=True)
        
        return {
            'type': 'ranking',
            'data': ranked[:10],
            'all_data': ranked,
            'sectors': sectors if sectors else 'all'
        }
    
    def _aggregate_comparison(self, data: List[Dict], sectors: List[str]) -> Dict[str, Any]:
        """Aggregate for comparison"""
        comparison_data = []
        
        for doc in data:
            total = doc.get('filtered_total', doc.get('total', self._calculate_province_total(doc)))
            entry = {
                'provinsi': doc.get('provinsi', ''),
                'total': total
            }
            
            if sectors:
                entry['breakdown'] = {
                    sector: self._get_sector_value(doc, sector)
                    for sector in sectors
                }
            
            comparison_data.append(entry)
        
        comparison_data.sort(key=lambda x: x['total'], reverse=True)
        
        return {
            'type': 'comparison',
            'data': comparison_data,
            'sectors': sectors if sectors else 'all'
        }
    
    def _aggregate_distribution(self, data: List[Dict], sectors: List[str]) -> Dict[str, Any]:
        """Aggregate for distribution"""
        distribution = {}
        
        target_sectors = sectors if sectors else list(KBLI_MAPPING.keys())
        
        for sector_code in target_sectors:
            total = sum(self._get_sector_value(doc, sector_code) for doc in data)
            if total > 0:
                distribution[sector_code] = {
                    'total': total,
                    'name': KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}'),
                    'short_name': KBLI_SHORT_NAMES.get(sector_code, sector_code)
                }
        
        sorted_dist = sorted(distribution.values(), key=lambda x: x['total'], reverse=True)
        
        return {
            'type': 'distribution',
            'data': distribution,
            'provinces': 'all',
            'distribution_detail': sorted_dist
        }
    
    def _aggregate_province_detail(self, data: List[Dict]) -> Dict[str, Any]:
        """Aggregate for single province detail"""
        if not data:
            return {'type': 'province_detail', 'data': None}
        
        doc = data[0]
        provinsi = doc.get('provinsi', '')
        
        sectors = []
        for sector_code in KBLI_MAPPING.keys():
            value = self._get_sector_value(doc, sector_code)
            if value > 0:
                sectors.append({
                    'code': sector_code,
                    'name': KBLI_MAPPING.get(sector_code),
                    'short_name': KBLI_SHORT_NAMES.get(sector_code),
                    'total': value
                })
        
        sectors.sort(key=lambda x: x['total'], reverse=True)
        total = sum(s['total'] for s in sectors)
        
        return {
            'type': 'province_detail',
            'data': doc,
            'provinsi': provinsi,
            'sectors': sectors,
            'total': total
        }
    
    def _aggregate_sector_analysis(self, data: List[Dict], sectors: List[str]) -> Dict[str, Any]:
        """Aggregate for sector analysis"""
        sector_codes = sectors if sectors else list(KBLI_MAPPING.keys())
        
        province_data = []
        for doc in data:
            total = sum(self._get_sector_value(doc, code) for code in sector_codes)
            if total > 0:
                province_data.append({
                    'provinsi': doc.get('provinsi', ''),
                    'total': total,
                    'breakdown': {
                        code: self._get_sector_value(doc, code)
                        for code in sector_codes
                    }
                })
        
        province_data.sort(key=lambda x: x['total'], reverse=True)
        
        sector_names = [KBLI_SHORT_NAMES.get(code, code) for code in sector_codes]
        grand_total = sum(p['total'] for p in province_data)
        
        return {
            'type': 'sector_analysis',
            'data': province_data,
            'sectors': sector_codes,
            'sector_names': sector_names,
            'total': grand_total,
            'all_provinces': province_data
        }
    
    # Analysis methods
    def _analyze_overview(self, data: Dict) -> Dict[str, Any]:
        """Analyze overview data"""
        provinces = data.get('data', [])
        sectors = data.get('sectors', {})
        grand_total = data.get('grand_total', 0)
        
        if not provinces:
            return {'message': 'No data to analyze'}
        
        top_provinces = [
            {
                'provinsi': p['provinsi'],
                'total': p['total'],
                'percentage': (p['total'] / grand_total * 100) if grand_total > 0 else 0
            }
            for p in provinces[:10]
        ]
        
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1]['total'], reverse=True)
        top_sectors = [
            {
                'code': code,
                'name': info['name'],
                'short_name': info.get('short_name', info['name'][:20]),
                'total': info['total'],
                'percentage': (info['total'] / grand_total * 100) if grand_total > 0 else 0
            }
            for code, info in sorted_sectors[:10]
        ]
        
        top3_prov_concentration = sum(p['total'] for p in provinces[:3]) / grand_total * 100 if grand_total > 0 else 0
        top3_sector_concentration = sum(s[1]['total'] for s in sorted_sectors[:3]) / grand_total * 100 if grand_total > 0 else 0
        
        return {
            'total_usaha': grand_total,
            'total_provinces': len(provinces),
            'total_sectors': len(sectors),
            'top_provinces': top_provinces,
            'top_sectors': top_sectors,
            'all_provinces': [
                {
                    'provinsi': p['provinsi'],
                    'total': p['total'],
                    'percentage': (p['total'] / grand_total * 100) if grand_total > 0 else 0
                }
                for p in provinces
            ],
            'province_concentration_top3': top3_prov_concentration,
            'sector_concentration_top3': top3_sector_concentration,
            'average_per_province': grand_total / len(provinces) if provinces else 0
        }
    
    def _analyze_ranking(self, data: Dict) -> Dict[str, Any]:
        """Analyze ranking data"""
        ranked_data = data.get('data', [])
        all_data = data.get('all_data', ranked_data)
        
        if not ranked_data:
            return {'message': 'No data to analyze'}
        
        total_all = sum(item.get('filtered_total', item.get('total', 0)) for item in all_data)
        top_3 = ranked_data[:3]
        
        return {
            'top_provinces': [
                {
                    'provinsi': item.get('provinsi'),
                    'total': item.get('filtered_total', item.get('total', 0)),
                    'percentage': (item.get('filtered_total', item.get('total', 0)) / total_all * 100) if total_all > 0 else 0
                }
                for item in top_3
            ],
            'all_ranked': [
                {
                    'rank': i + 1,
                    'provinsi': item.get('provinsi'),
                    'total': item.get('filtered_total', item.get('total', 0)),
                    'percentage': (item.get('filtered_total', item.get('total', 0)) / total_all * 100) if total_all > 0 else 0
                }
                for i, item in enumerate(all_data)
            ],
            'total_provinces': len(all_data),
            'total_usaha': total_all,
            'concentration': (sum(item.get('filtered_total', item.get('total', 0)) for item in top_3) / total_all * 100) if total_all > 0 else 0,
            'average': total_all / len(all_data) if all_data else 0
        }
    
    def _analyze_comparison(self, data: Dict) -> Dict[str, Any]:
        """Analyze comparison data"""
        comparison_data = data.get('data', [])
        
        if not comparison_data:
            return {'message': 'No data to compare'}
        
        totals = [item.get('total', 0) for item in comparison_data]
        total_sum = sum(totals)
        
        return {
            'max_province': comparison_data[0] if comparison_data else None,
            'min_province': comparison_data[-1] if comparison_data else None,
            'average': total_sum / len(totals) if totals else 0,
            'total': total_sum,
            'provinces_count': len(comparison_data),
            'comparison_data': [
                {
                    **item,
                    'percentage': (item['total'] / total_sum * 100) if total_sum > 0 else 0
                }
                for item in comparison_data
            ]
        }
    
    def _analyze_distribution(self, data: Dict) -> Dict[str, Any]:
        """Analyze distribution data"""
        distribution = data.get('data', {})
        
        if not distribution:
            return {'message': 'No distribution data'}
        
        total = sum(item['total'] for item in distribution.values())
        sorted_sectors = sorted(distribution.items(), key=lambda x: x[1]['total'], reverse=True)
        
        return {
            'top_sector': sorted_sectors[0] if sorted_sectors else None,
            'total_sectors': len(distribution),
            'total_usaha': total,
            'distribution_detail': [
                {
                    'sector_code': code,
                    'sector_name': info['name'],
                    'short_name': info.get('short_name', info['name'][:20]),
                    'total': info['total'],
                    'percentage': (info['total'] / total * 100) if total > 0 else 0
                }
                for code, info in sorted_sectors
            ]
        }
    
    def _analyze_province_detail(self, data: Dict) -> Dict[str, Any]:
        """Analyze province detail data"""
        if data.get('data') is None:
            return {'message': 'No province data'}
        
        sectors = data.get('sectors', [])
        total = data.get('total', 0)
        provinsi = data.get('provinsi', '')
        
        return {
            'provinsi': provinsi,
            'total_usaha': total,
            'total_sectors': len(sectors),
            'top_sectors': [
                {
                    **s,
                    'percentage': (s['total'] / total * 100) if total > 0 else 0
                }
                for s in sectors[:5]
            ],
            'all_sectors': [
                {
                    **s,
                    'percentage': (s['total'] / total * 100) if total > 0 else 0
                }
                for s in sectors
            ],
            'sector_concentration_top3': sum(s['total'] for s in sectors[:3]) / total * 100 if total > 0 and len(sectors) >= 3 else 0
        }
    
    def _analyze_sector_analysis(self, data: Dict) -> Dict[str, Any]:
        """Analyze sector analysis data"""
        province_data = data.get('data', [])
        total = data.get('total', 0)
        
        return {
            'sectors': data.get('sectors', []),
            'sector_names': data.get('sector_names', []),
            'total_usaha': total,
            'total_provinces': len(province_data),
            'top_provinces': [
                {
                    **p,
                    'percentage': (p['total'] / total * 100) if total > 0 else 0
                }
                for p in province_data[:10]
            ],
            'all_provinces': [
                {
                    **p,
                    'percentage': (p['total'] / total * 100) if total > 0 else 0
                }
                for p in province_data
            ],
            'average_per_province': total / len(province_data) if province_data else 0
        }
    
    def _enrich_with_advanced_metrics(self, analysis: Dict, aggregated: Dict) -> Dict[str, Any]:
        """Add advanced metrics for visualization"""
        try:
            data_type = aggregated.get('type', 'unknown')
            
            # Heatmap matrix data
            if data_type in ['overview', 'comparison']:
                raw_data = self._aggregated_data.get('raw_data', [])
                if raw_data:
                    provinces = sorted(raw_data, key=lambda x: x.get('total', 0), reverse=True)[:10]
                    prov_names = [p.get('provinsi') for p in provinces]
                    
                    top_sector_codes = list(KBLI_SHORT_NAMES.keys())[:8]
                    sector_names = [KBLI_SHORT_NAMES[c] for c in top_sector_codes]
                    
                    matrix_values = []
                    for p_idx, prov in enumerate(provinces):
                        for s_idx, code in enumerate(top_sector_codes):
                            val = self._get_sector_value(prov, code)
                            matrix_values.append([s_idx, p_idx, val])
                    
                    analysis['matrix_data'] = {
                        'provinces': prov_names,
                        'sectors': sector_names,
                        'values': matrix_values
                    }
            
            # LQ data for radar chart
            if data_type == 'province_detail':
                prov_total = analysis.get('total_usaha', 1)
                lq_data = []
                all_sectors = analysis.get('all_sectors', [])
                
                for sector in all_sectors:
                    sect_val = sector['total']
                    sect_share_prov = sect_val / prov_total if prov_total > 0 else 0
                    national_share_approx = 0.05
                    lq = sect_share_prov / national_share_approx if national_share_approx > 0 else 0
                    
                    lq_data.append({
                        'code': sector['code'],
                        'short_name': sector['short_name'],
                        'lq': lq
                    })
                
                analysis['lq_data'] = lq_data
        
        except Exception as e:
            logger.warning(f"Failed to calculate advanced metrics: {e}")
        
        return analysis
    
    def _generate_fallback_response(self, analysis: Dict, aggregated: Dict) -> str:
        """Generate response without LLM"""
        data_type = aggregated.get('type', 'unknown')
        
        try:
            if data_type == 'overview':
                total_usaha = analysis.get('total_usaha', 0)
                total_provinces = analysis.get('total_provinces', 0)
                top_provinces = analysis.get('top_provinces', [])
                top_sectors = analysis.get('top_sectors', [])
                
                response = f"Berdasarkan data Sensus Ekonomi 2016, tercatat total {total_usaha:,} unit usaha di {total_provinces} provinsi Indonesia. "
                
                if top_provinces:
                    top = top_provinces[0]
                    response += f"{top['provinsi']} memiliki jumlah usaha terbanyak dengan {top['total']:,} unit usaha ({top.get('percentage', 0):.1f}% dari total nasional). "
                
                if top_sectors:
                    top_sector = top_sectors[0]
                    response += f"Sektor {top_sector.get('short_name', top_sector.get('name', ''))} mendominasi dengan {top_sector['total']:,} usaha."
                
                return response
            
            elif data_type == 'ranking':
                top_provinces = analysis.get('top_provinces', [])
                if top_provinces:
                    top = top_provinces[0]
                    response = f"Berdasarkan data Sensus Ekonomi 2016, {top['provinsi']} memiliki jumlah usaha terbanyak dengan total {top['total']:,} unit usaha"
                    
                    if top.get('percentage', 0) > 0:
                        response += f" ({top['percentage']:.1f}% dari total nasional)"
                    
                    response += ". "
                    
                    if len(top_provinces) >= 3:
                        top3_names = ', '.join([p['provinsi'] for p in top_provinces[:3]])
                        concentration = analysis.get('concentration', 0)
                        response += f"Tiga provinsi teratas ({top3_names}) menguasai {concentration:.1f}% dari total usaha nasional."
                    
                    return response
            
            elif data_type == 'distribution':
                dist_detail = analysis.get('distribution_detail', [])
                if dist_detail:
                    top_sector = dist_detail[0]
                    response = f"Analisis distribusi menunjukkan bahwa sektor {top_sector.get('short_name', top_sector.get('sector_name'))} mendominasi dengan total {top_sector['total']:,} unit usaha ({top_sector.get('percentage', 0):.1f}% dari total). "
                    
                    if len(dist_detail) >= 3:
                        top3_sectors = ', '.join([s.get('short_name', s.get('sector_name')) for s in dist_detail[:3]])
                        response += f"Tiga sektor teratas adalah {top3_sectors}."
                    
                    return response
            
            elif data_type == 'province_detail':
                provinsi = analysis.get('provinsi', '')
                total_usaha = analysis.get('total_usaha', 0)
                top_sectors = analysis.get('top_sectors', [])
                
                response = f"Di {provinsi}, tercatat total {total_usaha:,} unit usaha. "
                
                if top_sectors:
                    top = top_sectors[0]
                    response += f"Sektor {top.get('short_name', top.get('name', ''))} mendominasi dengan {top['total']:,} usaha ({top.get('percentage', 0):.1f}%)."
                
                return response
            
            # Generic fallback
            total_usaha = analysis.get('total_usaha', 0)
            if total_usaha > 0:
                return f"Data telah berhasil dianalisis dengan total {total_usaha:,} unit usaha. Silakan lihat visualisasi dan insight untuk informasi lebih detail."
            
            return "Data telah berhasil dianalisis. Silakan lihat visualisasi dan insight untuk informasi lebih detail."
        
        except Exception as e:
            logger.error(f"Error in fallback response generation: {e}")
            return "Data telah berhasil dianalisis. Silakan lihat visualisasi dan insight untuk informasi lebih detail."


# ==============================================================================
# 7. DS-STAR ORCHESTRATOR
# ==============================================================================

class DSStarOrchestrator:
    """
    Main orchestrator yang mengkoordinasikan semua DS-STAR agents.
    Implementasi Algorithm 1 dari paper DS-STAR.
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Initialize all agents
        self.analyzer = DataFileAnalyzerAgent(db)
        self.planner = PlannerAgent(db)
        self.coder = CoderAgent(db)
        self.verifier = VerifierAgent(db)
        self.router = RouterAgent(db)
        self.debugger = DebuggerAgent(db)
        
        self.max_iterations = 20
        self.max_debug_attempts = 3
    
    async def analyze(self, query: str, language: str = "Indonesian") -> Dict[str, Any]:
        """
        Main DS-STAR analysis pipeline.
        
        Steps:
        1. Analyze data files (get context)
        2. Create initial plan
        3. Execute plan iteratively until verified sufficient
        4. Return final results
        """
        logger.info(f"DS-STAR: Starting analysis for query: {query[:50]}...")
        
        try:
            # Step 1: Analyze data structure
            data_description = await self.analyzer.analyze_data_structure()
            logger.info("DS-STAR: Data structure analyzed")
            
            # Check if this is a conversational query (not data-related)
            if not self._is_data_query(query):
                return await self._handle_conversational_query(query, language)
            
            # Step 2: Create initial plan
            plan = await self.planner.create_initial_plan(query, data_description)
            
            # Store query in coder for later use
            self.coder._aggregated_data['query'] = query
            
            # Step 3: Iterative execution loop
            all_results = {
                'message': '',
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
            
            while plan.iteration_count < self.max_iterations:
                plan.iteration_count += 1
                logger.info(f"DS-STAR: Iteration {plan.iteration_count}")
                
                # Execute current step
                if plan.current_step_index < len(plan.steps):
                    current_step = plan.steps[plan.current_step_index]
                    
                    # Try executing with debugging
                    step, result = await self._execute_with_debugging(
                        current_step, all_results, data_description
                    )
                    
                    plan.steps[plan.current_step_index] = step
                    
                    # Update results
                    self._merge_results(all_results, result)
                    
                    logger.info(f"📦 After merge - Step {step.id} ({step.operation_type})")
                    logger.info(f"📊 Current totals: "
                            f"viz={len(all_results['visualizations'])}, "
                            f"insights={len(all_results['insights'])}, "
                            f"policies={len(all_results['policies'])}")
                    
                    if step.status == PlanStepStatus.COMPLETED:
                        plan.current_step_index += 1
                
                # Verify plan sufficiency
                verification_result, feedback = await self.verifier.verify_plan(
                    plan, all_results, data_description
                )
                
                plan.verification_feedback = feedback
                
                if verification_result == VerificationResult.SUFFICIENT:
                    logger.info("DS-STAR: Plan verified as sufficient")
                    plan.is_sufficient = True
                    break
                
                # Route to next action
                decision, step_index = await self.router.decide_action(
                    plan, feedback, all_results
                )
                
                if decision == RouterDecision.REMOVE_STEP and step_index is not None:
                    # Remove steps from index onwards
                    plan.steps = plan.steps[:step_index]
                    plan.current_step_index = step_index
                    logger.info(f"DS-STAR: Removed steps from {step_index}")
                
                if decision == RouterDecision.ADD_STEP or plan.current_step_index >= len(plan.steps):
                    # Add next step
                    next_step = await self.planner.add_next_step(
                        plan, all_results, data_description
                    )
                    plan.steps.append(next_step)
                    logger.info(f"DS-STAR: Added step {next_step.id}: {next_step.operation_type}")
            
            # Generate final message if not present
            if not all_results.get('message'):
                all_results['message'] = self.coder._generate_fallback_response(
                    self.coder._analysis_results,
                    self.coder._aggregated_data.get('aggregated', {})
                )
            
            # Try to generate LLM-enhanced message
            if self.coder.has_llm:
                try:
                    all_results['message'] = await self._generate_llm_response(
                        query, all_results, data_description, language
                    )
                except Exception as e:
                    logger.warning(f"LLM response generation failed: {e}")
            
            logger.info(f"DS-STAR: Analysis complete. Iterations: {plan.iteration_count}")
            
            return all_results
            
        except Exception as e:
            logger.error(f"DS-STAR: Critical error: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan dalam analisis. Error: {str(e)}",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
    
    async def _execute_with_debugging(
        self,
        step: PlanStep,
        prev_results: Dict[str, Any],
        data_desc: DataDescription
    ) -> Tuple[PlanStep, Dict[str, Any]]:
        """Execute step with automatic debugging on failure"""
        
        for attempt in range(self.max_debug_attempts):
            step, result = await self.coder.execute_step(step, prev_results, data_desc)
            
            if step.status == PlanStepStatus.COMPLETED:
                return step, result
            
            if step.status == PlanStepStatus.FAILED and attempt < self.max_debug_attempts - 1:
                logger.info(f"Step failed, debugging attempt {attempt + 1}")
                step = await self.debugger.debug_step(step, step.error or "", data_desc)
        
        return step, result
    
    def _merge_results(self, all_results: Dict[str, Any], new_result: Dict[str, Any]):
        """
        FIXED: Merge new results into accumulated results with proper type handling
        """
        
        # Merge message
        if 'message' in new_result and new_result['message']:
            all_results['message'] = new_result['message']
            logger.debug(f"  ✓ Updated message")
        
        # Merge visualizations
        if 'visualizations' in new_result:
            new_viz = new_result.get('visualizations', [])
            if new_viz:
                all_results['visualizations'].extend(new_viz)
                logger.debug(f"  ✓ Added {len(new_viz)} visualizations")
        
        # ===== CRITICAL FIX: Merge insights with type validation =====
        if 'insights' in new_result:
            new_insights = new_result.get('insights', [])
            
            # Ensure it's a list
            if isinstance(new_insights, str):
                new_insights = [new_insights]
            elif not isinstance(new_insights, list):
                logger.warning(f"  ⚠️ Insights is not a list: {type(new_insights)}")
                new_insights = []
            
            if new_insights:
                # Filter out empty strings and duplicates
                valid_insights = [i for i in new_insights if i and isinstance(i, str) and i not in all_results['insights']]
                if valid_insights:
                    all_results['insights'].extend(valid_insights)
                    logger.info(f"  ✅ Added {len(valid_insights)} insights (total now: {len(all_results['insights'])})")
        
        # ===== CRITICAL FIX: Merge policies with object-to-dict conversion =====
        if 'policies' in new_result:
            new_policies = new_result.get('policies', [])
            
            # Ensure it's a list
            if not isinstance(new_policies, list):
                logger.warning(f"  ⚠️ Policies is not a list: {type(new_policies)}")
                new_policies = []
            
            for policy in new_policies:
                # Convert to dict if it's a PolicyRecommendation object
                if hasattr(policy, 'dict'):
                    policy_dict = policy.dict()
                elif isinstance(policy, dict):
                    policy_dict = policy
                else:
                    logger.warning(f"  ⚠️ Unknown policy type: {type(policy)}, skipping")
                    continue
                
                # Avoid duplicates based on title
                existing_titles = [p.get('title') for p in all_results['policies']]
                if policy_dict.get('title') not in existing_titles:
                    all_results['policies'].append(policy_dict)
            
            if new_policies:
                logger.info(f"  ✅ Added {len(new_policies)} policies (total now: {len(all_results['policies'])})")
        
        # Merge data count
        if 'count' in new_result:
            all_results['supporting_data_count'] = max(
                all_results.get('supporting_data_count', 0),
                new_result.get('count', 0)
            )
            logger.debug(f"  ✓ Updated data count to {all_results['supporting_data_count']}")
        
        # Log metrics from insight step
        if 'insights_count' in new_result:
            logger.info(f"  📊 Step reported {new_result['insights_count']} insights")
        if 'policies_count' in new_result:
            logger.info(f"  📋 Step reported {new_result['policies_count']} policies")
        
    def _is_data_query(self, query: str) -> bool:
        """Check if query requires data analysis"""
        query_lower = query.lower()
        
        data_keywords = [
            'berapa', 'jumlah', 'total', 'banyak', 'bandingkan', 'compare',
            'terbanyak', 'tertinggi', 'terendah', 'top', 'ranking',
            'distribusi', 'sebaran', 'komposisi', 'proporsi',
            'provinsi', 'sektor', 'wilayah', 'daerah',
            'analisis', 'analyze', 'data', 'statistik', 'usaha', 'bisnis'
        ]
        
        conversational_only = [
            'halo', 'hello', 'hi', 'hai', 'terima kasih', 'thanks',
            'siapa kamu', 'apa itu', 'selamat pagi', 'selamat siang'
        ]
        
        has_data_keyword = any(keyword in query_lower for keyword in data_keywords)
        is_conversational = any(keyword in query_lower for keyword in conversational_only)
        
        if is_conversational and not has_data_keyword:
            return False
        
        return has_data_keyword
    
    async def _handle_conversational_query(self, query: str, language: str) -> Dict[str, Any]:
        """Handle non-data queries"""
        
        if not self.coder.has_llm:
            return {
                'message': "Halo! Saya asisten analisis Sensus Ekonomi Indonesia. Saya dapat membantu Anda menganalisis data ekonomi seperti jumlah usaha per provinsi, sektor dominan, perbandingan antar wilayah, dan trend ekonomi. Silakan ajukan pertanyaan Anda!",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
        
        try:
            prompt = f"""Kamu adalah asisten analisis Sensus Ekonomi Indonesia yang ramah dan membantu.

Pertanyaan user: "{query}"

Tugas kamu:
1. Jawab dengan ramah dan informatif
2. Jika user bertanya tentang kemampuan, jelaskan bahwa kamu bisa:
   - Analisis jumlah usaha per provinsi dan sektor
   - Perbandingan antar wilayah (provinsi)
   - Distribusi per sektor KBLI (A-U)
   - Menampilkan Heatmap, Treemap, dan Radar Chart
   - Insight dan rekomendasi kebijakan
3. Jika user menyapa, balas dengan ramah dan tawarkan bantuan spesifik

Bahasa: {language}
Panjang: 2-3 kalimat maksimal.
Tone: Ramah, helpful, profesional.
"""
            
            response = await self.coder._call_llm(prompt)
            return {
                'message': response.strip() if response else "Halo! Ada yang bisa saya bantu terkait data Sensus Ekonomi Indonesia?",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
            
        except Exception as e:
            logger.error(f"Conversational handler error: {e}")
            return {
                'message': "Halo! Ada yang bisa saya bantu terkait data Sensus Ekonomi Indonesia?",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
    
    async def _generate_llm_response(
        self,
        query: str,
        results: Dict[str, Any],
        data_desc: DataDescription,
        language: str
    ) -> str:
        """Generate narrative response using LLM"""
        
        # Prepare context
        analysis = self.coder._analysis_results
        aggregated = self.coder._aggregated_data.get('aggregated', {})
        
        context_str = self._prepare_context(analysis, aggregated)
        
        prompt = f"""Kamu adalah asisten analisis data Sensus Ekonomi Indonesia yang profesional, akurat, dan berwawasan luas.

Pertanyaan User: "{query}"

DATA ANALISIS YANG TERSEDIA:
{context_str}

INSTRUKSI PENJAWABAN:
1. **Gunakan Data Konkret**: Setiap klaim harus didukung oleh angka dari data yang disediakan di atas. Jangan mengarang angka.
2. **Struktur Jawaban**:
   - **Paragraf 1 (Headline)**: Jawab pertanyaan secara langsung. Sebutkan angka total, nama provinsi/sektor tertinggi, atau poin utama.
   - **Paragraf 2 (Deep Dive)**: Berikan perbandingan, persentase, atau detail menarik.
   - **Paragraf 3 (Insight/Implikasi)**: Jelaskan apa arti data ini secara singkat.
3. **Tone**: Profesional, Objektif, Informatif.
4. **Visualisasi**: Jika ada data kompleks, sebutkan "Seperti terlihat pada visualisasi..." untuk mengarahkan user.

PANJANG RESPON: 3-5 kalimat per paragraf (Concise namun padat).
BAHASA: {language}
"""
        
        try:
            response = await self.coder._call_llm(prompt)
            return response if response else self.coder._generate_fallback_response(analysis, aggregated)
        except Exception as e:
            logger.error(f"LLM response generation error: {e}")
            return self.coder._generate_fallback_response(analysis, aggregated)
    
    def _prepare_context(self, analysis: Dict, aggregated: Dict) -> str:
        """Prepare context for LLM prompt"""
        simplified = {
            'tipe_analisis': aggregated.get('type', 'unknown'),
            'hasil_analisis': {}
        }
        
        if 'top_provinces' in analysis:
            simplified['hasil_analisis']['provinsi_teratas'] = [
                {
                    'provinsi': prov['provinsi'],
                    'total_usaha': prov['total'],
                    'persentase': round(prov.get('percentage', 0), 2)
                }
                for prov in analysis['top_provinces'][:5]
            ]
        
        if 'top_sectors' in analysis:
            simplified['hasil_analisis']['sektor_teratas'] = [
                {
                    'kode': s.get('code', ''),
                    'nama': s.get('short_name', s.get('name', '')),
                    'total': s['total'],
                    'persentase': round(s.get('percentage', 0), 2)
                }
                for s in analysis['top_sectors'][:5]
            ]
        
        if 'total_usaha' in analysis:
            simplified['hasil_analisis']['total_usaha'] = analysis['total_usaha']
        
        if 'provinsi' in analysis:
            simplified['hasil_analisis']['provinsi'] = analysis['provinsi']
        
        return json.dumps(simplified, indent=2, ensure_ascii=False)
