import os
import logging
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from data_agent import DataRetrievalAgent, AnalysisAgent, KBLI_SHORT_NAMES
from visualization_agent import VisualizationAgent
from insight_agent import InsightGenerationAgent
from models import QueryIntent
import json
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# --- 1. KONFIGURASI ENV (FIXED) ---
# Mengambil path folder backend saat ini
BACKEND_DIR = Path(__file__).resolve().parent
# Naik satu level ke root, lalu masuk ke frontend/.env
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

class PolicyAIAnalyzer:
    """Enhanced Policy Analyzer with better intent detection and multi-visualization support"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        
        # Initialize Gemini
        api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if api_key:
            genai.configure(api_key=api_key)
            model_name = os.environ.get('LLM_MODEL', 'gemini-2.0-flash-exp')
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Gemini initialized with model: {model_name}")
        else:
            logger.warning("No Gemini API key found")
            self.model = None
        
        # Initialize agents
        self.data_agent = DataRetrievalAgent(db)
        self.analysis_agent = AnalysisAgent()
        self.viz_agent = VisualizationAgent()
        self.insight_agent = InsightGenerationAgent()
    
    def _is_data_query(self, query: str) -> bool:
        """
        Enhanced detection for data analysis queries
        Returns True if query is asking for data/analysis
        """
        query_lower = query.lower()
        
        # Data query indicators (expanded)
        data_keywords = [
            # Pertanyaan jumlah
            'berapa', 'jumlah', 'total', 'banyak', 'many', 'how much', 'how many',
            
            # Pertanyaan perbandingan
            'bandingkan', 'compare', 'versus', 'vs', 'perbandingan', 'lebih besar', 'lebih kecil', 'dibanding',
            
            # Pertanyaan ranking
            'terbanyak', 'tertinggi', 'terendah', 'terbesar', 'terkecil', 'top', 'ranking', 
            'urutan', 'urut', 'paling', 'most', 'least', 'highest', 'lowest', 'tersedikit',
            
            # Pertanyaan distribusi
            'distribusi', 'sebaran', 'persebaran', 'komposisi', 'proporsi', 'persentase',
            'bagaimana', 'how', 'distribution',
            
            # Pertanyaan spesifik
            'provinsi mana', 'sektor apa', 'wilayah mana', 'daerah mana', 'which province',
            'which sector', 'what sector', 'where',
            
            # Kata kunci analisis
            'analisis', 'analyze', 'analisa', 'tren', 'trend', 'perkembangan', 'data', 'statistik',
            'insight', 'laporan', 'report', 'overview', 'gambaran', 'detail', 'lengkap'
        ]
        
        # Check if query contains any data keywords
        has_data_keyword = any(keyword in query_lower for keyword in data_keywords)
        
        # Exclude conversational queries
        conversational_only = [
            'halo', 'hello', 'hi', 'hai', 'terima kasih', 'thank you', 'thanks',
            'siapa kamu', 'who are you', 'apa itu', 'what is', 'tolong jelaskan',
            'selamat pagi', 'selamat siang', 'selamat malam'
        ]
        
        is_conversational = any(keyword in query_lower for keyword in conversational_only)
        
        # Entity mentions (provinces, sectors)
        has_province = any(prov in query_lower for prov in [
            'aceh', 'sumut', 'sumbar', 'riau', 'jambi', 'sumsel', 'bengkulu', 'lampung',
            'jakarta', 'jabar', 'jateng', 'jatim', 'yogya', 'banten', 'bali',
            'kalimantan', 'sulawesi', 'papua', 'maluku', 'nusa tenggara',
            'sumatera', 'jawa', 'gorontalo'
        ])
        
        has_sector = any(sector in query_lower for sector in [
            'pertanian', 'pertambangan', 'industri', 'listrik', 'konstruksi',
            'perdagangan', 'transportasi', 'hotel', 'restoran', 'akomodasi',
            'informasi', 'keuangan', 'real estat', 'properti', 'pendidikan',
            'kesehatan', 'sektor', 'lapangan usaha', 'kbli', 'usaha', 'bisnis'
        ])
        
        # Decision logic
        if is_conversational and not (has_province or has_sector or has_data_keyword):
            return False
        
        if has_data_keyword or has_province or has_sector:
            return True
        
        return False
    
    async def analyze_policy_query(
        self,
        query: str,
        language: str = "Indonesian",
        scraped_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main analysis method with enhanced intent detection and MULTIPLE visualizations
        """
        try:
            logger.info(f"Analyzing query: {query}")
            
            # Check if this is a data query
            is_data_query = self._is_data_query(query)
            
            logger.info(f"Query classification: {'DATA_QUERY' if is_data_query else 'CONVERSATIONAL'}")
            
            if not is_data_query:
                # Handle conversational queries
                return await self._handle_conversational_query(query, language)
            
            # ENHANCED: Process as data query with multiple visualizations
            try:
                # Step 1: Understand intent
                intent = await self.data_agent.understand_query(query)
                logger.info(f"Intent detected: {intent.intent_type}, provinces={intent.provinces}, sectors={intent.sectors}")
                
                # Step 2: Get data
                raw_data = await self.data_agent.get_data_by_intent(intent)
                
                if not raw_data:
                    logger.warning("No data found, attempting broader search...")
                    
                    # FALLBACK 1: Try without province filter
                    if intent.provinces:
                        logger.info("Fallback: Removing province filter")
                        fallback_intent = QueryIntent(
                            intent_type=intent.intent_type,
                            provinces=[],
                            sectors=intent.sectors
                        )
                        raw_data = await self.data_agent.get_data_by_intent(fallback_intent)
                        if raw_data:
                            intent = fallback_intent
                    
                    # FALLBACK 2: Try overview if still no data
                    if not raw_data:
                        logger.info("Fallback: Switching to overview")
                        intent = QueryIntent(intent_type='overview')
                        raw_data = await self.data_agent.get_data_by_intent(intent)
                
                if not raw_data:
                    logger.error("No data found even after fallbacks")
                    return {
                        'message': 'Maaf, tidak ada data yang ditemukan untuk pertanyaan Anda. Data Sensus Ekonomi mungkin tidak tersedia untuk kriteria yang Anda minta.',
                        'visualizations': [],
                        'insights': [],
                        'policies': [],
                        'supporting_data_count': 0
                    }
                
                logger.info(f"Retrieved {len(raw_data)} documents")
                
                # Step 3: Aggregate data
                aggregated = await self.data_agent.aggregate_data(raw_data, intent)
                logger.info(f"Data aggregated: type={aggregated.get('type')}")
                
                # Step 4: Analyze
                analysis = self.analysis_agent.analyze(aggregated, intent)
                logger.info(f"Analysis completed, total_usaha={analysis.get('total_usaha', 0)}")
                
                # Step 5: Create MULTIPLE visualizations
                visualizations = self.viz_agent.create_visualizations(analysis, aggregated)
                logger.info(f"Created {len(visualizations)} visualizations")
                
                # Step 6: Generate insights
                insights_result = await self.insight_agent.generate_insights(
                    analysis, aggregated, query, language
                )
                logger.info(f"Generated {len(insights_result.get('insights', []))} insights")
                
                # Step 7: Generate main response narrative
                main_message = await self._generate_main_response(
                    query, analysis, aggregated, insights_result, language
                )
                
                return {
                    'message': main_message,
                    'visualizations': [viz.dict() for viz in visualizations],
                    'insights': insights_result.get('insights', []),
                    'policies': insights_result.get('policies', []),
                    'supporting_data_count': len(raw_data)
                }
                
            except Exception as e:
                logger.error(f"Error in data analysis pipeline: {e}", exc_info=True)
                # Don't give up - try conversational fallback
                return await self._handle_conversational_query(query, language)
        
        except Exception as e:
            logger.error(f"Critical error in analyze_policy_query: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan sistem. Silakan coba lagi. Error: {str(e)}",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
    
    async def _generate_main_response(
        self,
        query: str,
        analysis: Dict[str, Any],
        aggregated: Dict[str, Any],
        insights: Dict[str, Any],
        language: str
    ) -> str:
        """Generate main narrative response using Gemini"""
        
        if not self.model:
            logger.warning("No Gemini model available, using fallback")
            return self._generate_fallback_response(analysis, aggregated)
        
        try:
            # Prepare context
            context = {
                'query': query,
                'analysis': analysis,
                'data_type': aggregated.get('type', 'unknown'),
                'insights': insights.get('insights', [])
            }
            
            # Enhanced prompt for better responses
            prompt = f"""Kamu adalah asisten analisis data Sensus Ekonomi Indonesia yang profesional dan tepat.

Pertanyaan user: "{query}"

Data yang tersedia:
{self._prepare_context_for_prompt(context)}

TUGAS KAMU:
1. Jawab pertanyaan user secara LANGSUNG dan SPESIFIK dengan data yang ada
2. Berikan angka-angka konkret (jumlah usaha, persentase, ranking)
3. Highlight insight penting dalam 2-3 kalimat
4. JANGAN sebutkan keterbatasan data atau menyuruh user ke BPS/sumber lain
5. Gunakan bahasa yang mudah dipahami dan profesional

FORMAT JAWABAN:
- Paragraf pembuka: Jawaban langsung dengan angka spesifik
- Paragraf analisis: Insight dan perbandingan penting
- Paragraf penutup: Kesimpulan singkat (opsional jika sudah jelas)

PANJANG: 3-5 kalimat maksimal (concise tapi informatif)
BAHASA: {language}
TONE: Profesional, informatif, langsung ke point

PENTING: Berikan jawaban yang PASTI berdasarkan data yang ada. Jangan spekulatif.
"""
            
            response = self.model.generate_content(prompt)
            generated_text = response.text.strip()
            
            logger.info(f"Generated response length: {len(generated_text)} chars")
            
            return generated_text
            
        except Exception as e:
            logger.error(f"Error generating main response with Gemini: {e}", exc_info=True)
            return self._generate_fallback_response(analysis, aggregated)
    
    def _prepare_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context for LLM prompt"""
        
        # Simplified context for better LLM comprehension
        simplified = {
            'tipe_analisis': context.get('data_type', 'unknown'),
            'hasil_analisis': {}
        }
        
        analysis = context.get('analysis', {})
        
        # Add relevant analysis results based on type
        if 'top_provinces' in analysis:
            simplified['hasil_analisis']['provinsi_teratas'] = [
                {
                    'provinsi': prov['provinsi'],
                    'total_usaha': prov['total'],
                    'persentase': round(prov.get('percentage', 0), 2)
                }
                for prov in analysis['top_provinces'][:5]
            ]
        
        if 'max_province' in analysis and analysis['max_province']:
            simplified['hasil_analisis']['provinsi_tertinggi'] = {
                'provinsi': analysis['max_province'].get('provinsi'),
                'total': analysis['max_province'].get('total')
            }
        
        if 'min_province' in analysis and analysis['min_province']:
            simplified['hasil_analisis']['provinsi_terendah'] = {
                'provinsi': analysis['min_province'].get('provinsi'),
                'total': analysis['min_province'].get('total')
            }
        
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
        
        if 'distribution_detail' in analysis:
            # Top 5 sectors only
            simplified['hasil_analisis']['distribusi_sektor'] = [
                {
                    'kode': detail['sector_code'],
                    'nama': detail.get('short_name', detail['sector_name']),
                    'total': detail['total'],
                    'persentase': round(detail['percentage'], 2)
                }
                for detail in analysis['distribution_detail'][:5]
            ]
        
        if 'top_sector' in analysis and analysis['top_sector']:
            sector_code, sector_info = analysis['top_sector']
            simplified['hasil_analisis']['sektor_tertinggi'] = {
                'kode': sector_code,
                'nama': sector_info['name'],
                'total': sector_info['total']
            }
        
        if 'total_usaha' in analysis:
            simplified['hasil_analisis']['total_usaha'] = analysis['total_usaha']
        
        if 'average' in analysis:
            simplified['hasil_analisis']['rata_rata'] = round(analysis['average'], 2)
        
        if 'concentration' in analysis:
            simplified['hasil_analisis']['konsentrasi_top3'] = round(analysis['concentration'], 2)
        
        if 'province_concentration_top3' in analysis:
            simplified['hasil_analisis']['konsentrasi_provinsi_top3'] = round(analysis['province_concentration_top3'], 2)
        
        if 'sector_concentration_top3' in analysis:
            simplified['hasil_analisis']['konsentrasi_sektor_top3'] = round(analysis['sector_concentration_top3'], 2)
        
        # Province detail
        if 'provinsi' in analysis:
            simplified['hasil_analisis']['provinsi'] = analysis['provinsi']
        
        if 'all_sectors' in analysis and context.get('data_type') == 'province_detail':
            simplified['hasil_analisis']['sektor_di_provinsi'] = [
                {
                    'nama': s.get('short_name', s.get('name', '')),
                    'total': s['total'],
                    'persentase': round(s.get('percentage', 0), 2)
                }
                for s in analysis['all_sectors'][:5]
            ]
        
        return json.dumps(simplified, indent=2, ensure_ascii=False)
    
    def _generate_fallback_response(self, analysis: Dict[str, Any], aggregated: Dict[str, Any]) -> str:
        """Generate response without LLM (rule-based)"""
        
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
                    total_national = analysis.get('total_usaha', 0)
                    
                    response = f"Berdasarkan data Sensus Ekonomi 2016, {top['provinsi']} memiliki jumlah usaha terbanyak dengan total {top['total']:,} unit usaha"
                    
                    if top.get('percentage', 0) > 0:
                        response += f" ({top['percentage']:.1f}% dari total nasional)"
                    
                    response += ". "
                    
                    # Add top 3 if available
                    if len(top_provinces) >= 3:
                        top3_names = ', '.join([p['provinsi'] for p in top_provinces[:3]])
                        concentration = analysis.get('concentration', 0)
                        response += f"Tiga provinsi teratas ({top3_names}) menguasai {concentration:.1f}% dari total usaha nasional."
                    
                    return response
            
            elif data_type == 'distribution':
                dist_detail = analysis.get('distribution_detail', [])
                if dist_detail:
                    top_sector = dist_detail[0]
                    total_usaha = analysis.get('total_usaha', 0)
                    
                    response = f"Analisis distribusi menunjukkan bahwa sektor {top_sector.get('short_name', top_sector['sector_name'])} mendominasi dengan total {top_sector['total']:,} unit usaha ({top_sector['percentage']:.1f}% dari total). "
                    
                    # Add top 3 sectors
                    if len(dist_detail) >= 3:
                        top3_sectors = ', '.join([s.get('short_name', s['sector_name']) for s in dist_detail[:3]])
                        response += f"Tiga sektor teratas adalah {top3_sectors}."
                    
                    return response
            
            elif data_type == 'comparison':
                max_prov = analysis.get('max_province', {})
                min_prov = analysis.get('min_province', {})
                average = analysis.get('average', 0)
                
                if max_prov:
                    response = f"Dari perbandingan data, {max_prov.get('provinsi', 'provinsi tertentu')} memiliki jumlah usaha tertinggi dengan {max_prov.get('total', 0):,} unit usaha"
                    
                    if min_prov:
                        response += f", sementara {min_prov.get('provinsi', 'provinsi lain')} memiliki {min_prov.get('total', 0):,} unit usaha"
                    
                    if average > 0:
                        response += f". Rata-rata jumlah usaha per provinsi adalah {average:,.0f} unit."
                    else:
                        response += "."
                    
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
            
            elif data_type == 'sector_analysis':
                sector_names = analysis.get('sector_names', [])
                total_usaha = analysis.get('total_usaha', 0)
                top_provinces = analysis.get('top_provinces', [])
                
                sector_str = ', '.join(sector_names[:2]) if sector_names else 'sektor tersebut'
                response = f"Sektor {sector_str} memiliki total {total_usaha:,} unit usaha di seluruh Indonesia. "
                
                if top_provinces:
                    top = top_provinces[0]
                    response += f"{top['provinsi']} memiliki jumlah terbanyak dengan {top['total']:,} usaha ({top.get('percentage', 0):.1f}%)."
                
                return response
            
            # Generic fallback
            total_usaha = analysis.get('total_usaha', 0)
            if total_usaha > 0:
                return f"Data telah berhasil dianalisis dengan total {total_usaha:,} unit usaha. Silakan lihat visualisasi dan insight untuk informasi lebih detail."
            else:
                return "Data telah berhasil dianalisis. Silakan lihat visualisasi dan insight untuk informasi lebih detail."
        
        except Exception as e:
            logger.error(f"Error in fallback response generation: {e}", exc_info=True)
            return "Data telah berhasil dianalisis. Silakan lihat visualisasi dan insight untuk informasi lebih detail."
    
    async def _handle_conversational_query(self, query: str, language: str) -> Dict[str, Any]:
        """Handle non-data queries conversationally"""
        
        if not self.model:
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
   - Ranking dan statistik ekonomi
   - Insight dan rekomendasi kebijakan
3. Jika user menyapa, balas dengan ramah dan tawarkan bantuan spesifik
4. Jangan buat asumsi tentang data yang tidak ada

Bahasa: {language}
Panjang: 2-3 kalimat maksimal.
Tone: Ramah, helpful, profesional.
"""
            
            response = self.model.generate_content(prompt)
            return {
                'message': response.text.strip(),
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }
            
        except Exception as e:
            logger.error(f"Error in conversational handler: {e}", exc_info=True)
            return {
                'message': "Halo! Ada yang bisa saya bantu terkait data Sensus Ekonomi Indonesia? Saya bisa menganalisis jumlah usaha per provinsi, perbandingan antar wilayah, distribusi sektor, dan memberikan insight kebijakan.",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }