import os
import logging
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
import google.generativeai as genai
from data_agent import DataRetrievalAgent, AnalysisAgent, KBLI_SHORT_NAMES, KBLI_MAPPING
from visualization_agent import VisualizationAgent
from insight_agent import InsightGenerationAgent
from models import QueryIntent
import json
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# --- 1. KONFIGURASI ENV ---
BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

class PolicyAIAnalyzer:
    """
    Enhanced Policy Analyzer with detailed intent detection, 
    advanced analytics enrichment (LQ, Heatmap), and robust fallback mechanisms.
    """
    
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
        Deteksi apakah query memerlukan pengambilan data/analisis.
        Menggunakan daftar keyword yang lengkap untuk akurasi tinggi.
        """
        query_lower = query.lower()
        
        # 1. Keywords Indikator Pertanyaan Data
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
            
            # Kata kunci analisis & visualisasi
            'analisis', 'analyze', 'analisa', 'tren', 'trend', 'perkembangan', 'data', 'statistik',
            'insight', 'laporan', 'report', 'overview', 'gambaran', 'detail', 'lengkap',
            'heatmap', 'peta', 'treemap', 'radar', 'grafik', 'chart'
        ]
        
        # 2. Keywords Percakapan Biasa (Non-Data)
        conversational_only = [
            'halo', 'hello', 'hi', 'hai', 'terima kasih', 'thank you', 'thanks',
            'siapa kamu', 'who are you', 'apa itu', 'what is', 'tolong jelaskan',
            'selamat pagi', 'selamat siang', 'selamat malam', 'assalamualaikum'
        ]
        
        # 3. Entity Mentions: Provinces
        has_province = any(prov in query_lower for prov in [
            'aceh', 'sumut', 'sumbar', 'riau', 'jambi', 'sumsel', 'bengkulu', 'lampung',
            'jakarta', 'jabar', 'jateng', 'jatim', 'yogya', 'banten', 'bali',
            'kalimantan', 'sulawesi', 'papua', 'maluku', 'nusa tenggara',
            'sumatera', 'jawa', 'gorontalo'
        ])
        
        # 4. Entity Mentions: Sectors
        has_sector = any(sector in query_lower for sector in [
            'pertanian', 'pertambangan', 'industri', 'listrik', 'konstruksi',
            'perdagangan', 'transportasi', 'hotel', 'restoran', 'akomodasi',
            'informasi', 'keuangan', 'real estat', 'properti', 'pendidikan',
            'kesehatan', 'sektor', 'lapangan usaha', 'kbli', 'usaha', 'bisnis'
        ])
        
        has_data_keyword = any(keyword in query_lower for keyword in data_keywords)
        is_conversational = any(keyword in query_lower for keyword in conversational_only)
        
        # Logic Keputusan
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
        Main analysis pipeline:
        Intent -> Data -> Aggregation -> Analysis -> Enrichment -> Viz -> Insight -> Narrative
        """
        try:
            logger.info(f"Analyzing query: {query}")
            
            # Check if this is a data query
            is_data_query = self._is_data_query(query)
            logger.info(f"Query classification: {'DATA_QUERY' if is_data_query else 'CONVERSATIONAL'}")
            
            if not is_data_query:
                return await self._handle_conversational_query(query, language)
            
            # --- START DATA PIPELINE ---
            try:
                # Step 1: Understand intent
                intent = await self.data_agent.understand_query(query)
                logger.info(f"Intent detected: {intent.intent_type}, provinces={intent.provinces}, sectors={intent.sectors}")
                
                # Step 2: Get data
                raw_data = await self.data_agent.get_data_by_intent(intent)
                
                # Fallback Logic: Try broader search if no data found
                if not raw_data:
                    logger.warning("No data found, attempting broader search...")
                    
                    # FALLBACK A: Try without province filter
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
                    
                    # FALLBACK B: Try overview if still no data
                    if not raw_data:
                        logger.info("Fallback: Switching to overview")
                        intent = QueryIntent(intent_type='overview')
                        raw_data = await self.data_agent.get_data_by_intent(intent)
                
                if not raw_data:
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
                
                # Step 4: Analyze (Basic Statistics)
                analysis = self.analysis_agent.analyze(aggregated, intent)
                logger.info(f"Analysis completed, total_usaha={analysis.get('total_usaha', 0)}")
                
                # --- STEP 4.5: ENRICHMENT FOR ADVANCED VISUALIZATIONS (NEW) ---
                # Menambahkan perhitungan LQ dan Heatmap Matrix secara on-the-fly
                analysis = await self._enrich_analysis_with_advanced_metrics(analysis, aggregated, raw_data, intent)

                # Step 5: Create Visualizations (Now includes Radar, Heatmap, Treemap from analysis data)
                visualizations = self.viz_agent.create_visualizations(analysis, aggregated)
                logger.info(f"Created {len(visualizations)} visualizations")
                
                # Step 6: Generate insights (Gemini)
                insights_result = await self.insight_agent.generate_insights(
                    analysis, aggregated, query, language
                )
                
                # Step 7: Generate main response narrative (Gemini)
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

    async def _enrich_analysis_with_advanced_metrics(self, analysis: Dict[str, Any], aggregated: Dict[str, Any], raw_data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """
        Menghitung metrik tambahan untuk mendukung visualisasi advanced (Heatmap & Radar).
        Dilakukan di sini agar VisualizationAgent tetap stateless dan hanya menerima data jadi.
        """
        try:
            # A. Prepare Heatmap Matrix Data (Top 10 Prov x Top 8 Sectors)
            # Digunakan saat intent Overview atau Comparison
            if aggregated.get('type') in ['overview', 'comparison']:
                # Sort provinces by total descending
                provinces = sorted(raw_data, key=lambda x: x.get('total', 0), reverse=True)[:10]
                prov_names = [p.get('provinsi', p.get('Nama Provinsi')) for p in provinces]
                
                # Top sectors (codes) - ambil 8 sektor utama
                top_sector_codes = list(KBLI_SHORT_NAMES.keys())[:8] 
                sector_names = [KBLI_SHORT_NAMES[c] for c in top_sector_codes]
                
                matrix_values = []
                for p_idx, prov in enumerate(provinces):
                    for s_idx, code in enumerate(top_sector_codes):
                        # Get value safely
                        val = 0
                        sector_obj = prov.get(code)
                        if isinstance(sector_obj, dict): 
                            val = int(list(sector_obj.values())[0])
                        elif isinstance(sector_obj, (int, float)): 
                            val = int(sector_obj)
                        
                        # Heatmap ECharts format: [x_index, y_index, value]
                        matrix_values.append([s_idx, p_idx, val])
                
                analysis['matrix_data'] = {
                    'provinces': prov_names,
                    'sectors': sector_names,
                    'values': matrix_values
                }

            # B. Prepare Location Quotient (LQ) for Radar Chart
            # Digunakan saat intent Province Detail
            # LQ mengukur spesialisasi relatif sektor di suatu daerah dibanding nasional.
            if aggregated.get('type') == 'province_detail':
                prov_total = analysis.get('total_usaha', 1)
                lq_data = []
                all_sectors = analysis.get('all_sectors', [])
                
                for sector in all_sectors:
                    sect_val = sector['total']
                    # Share sektor di provinsi tersebut
                    sect_share_prov = sect_val / prov_total if prov_total > 0 else 0
                    
                    # Benchmark Nasional (Simplified / Approximated)
                    # Idealnya ini query agregat nasional dari DB. 
                    # Untuk performa, kita gunakan baseline 5% (asumsi 20 sektor terdistribusi merata 1/20)
                    # atau logic bisnis: jika share provinsi > 5%, anggap spesialisasi.
                    national_share_approx = 0.05 
                    
                    lq = sect_share_prov / national_share_approx if national_share_approx > 0 else 0
                    
                    lq_data.append({
                        'code': sector['code'],
                        'short_name': sector['short_name'],
                        'lq': lq
                    })
                
                # Simpan data LQ untuk divisualisasikan oleh VisualizationAgent
                analysis['lq_data'] = lq_data

        except Exception as e:
            logger.warning(f"Failed to calculate advanced metrics: {e}")
            # Lanjut tanpa metric tambahan, tidak perlu crash
        
        return analysis
    
    async def _generate_main_response(
        self,
        query: str,
        analysis: Dict[str, Any],
        aggregated: Dict[str, Any],
        insights: Dict[str, Any],
        language: str
    ) -> str:
        """
        Generate narasi utama menggunakan Gemini dengan System Prompt yang SANGAT DETAIL.
        """
        
        if not self.model:
            logger.warning("No Gemini model available, using fallback")
            return self._generate_fallback_response(analysis, aggregated)
        
        try:
            # Prepare structured context
            context_str = self._prepare_context_for_prompt({
                'query': query,
                'analysis': analysis,
                'data_type': aggregated.get('type', 'unknown'),
                'insights': insights.get('insights', [])
            })
            
            # --- DETAILED SYSTEM PROMPT ---
            prompt = f"""Kamu adalah asisten analisis data Sensus Ekonomi Indonesia yang profesional, akurat, dan berwawasan luas.

Pertanyaan User: "{query}"

DATA ANALISIS YANG TERSEDIA:
{context_str}

INSTRUKSI PENJAWABAN:
1. **Gunakan Data Konkret**: Setiap klaim harus didukung oleh angka dari data yang disediakan di atas. Jangan mengarang angka.
2. **Struktur Jawaban**:
   - **Paragraf 1 (Headline)**: Jawab pertanyaan secara langsung. Sebutkan angka total, nama provinsi/sektor tertinggi, atau poin utama.
   - **Paragraf 2 (Deep Dive)**: Berikan perbandingan, persentase, atau detail menarik. Contoh: "Provinsi X mendominasi 40% dari total..." atau "Sektor A dua kali lebih besar dari Sektor B...".
   - **Paragraf 3 (Insight/Implikasi)**: Jelaskan apa arti data ini secara singkat. (Misal: Konsentrasi tinggi di Jawa menunjukkan...)
3. **Tone**: Profesional, Objektif, Informatif. Hindari bahasa yang terlalu kaku tapi tetap formal.
4. **Visualisasi**: Jika ada data kompleks (seperti matriks atau hierarki), sebutkan secara implisit "Seperti terlihat pada visualisasi..." untuk mengarahkan user melihat grafik.
5. **Keterbatasan**: Jangan berulang kali meminta maaf atau menyebutkan keterbatasan AI. Fokus pada apa yang bisa dijawab.

PANJANG RESPON: 3-5 kalimat per paragraf (Concise namun padat).
BAHASA: {language}
"""
            
            response = self.model.generate_content(prompt)
            generated_text = response.text.strip()
            
            logger.info(f"Generated response length: {len(generated_text)} chars")
            return generated_text
            
        except Exception as e:
            logger.error(f"Error generating main response with Gemini: {e}", exc_info=True)
            return self._generate_fallback_response(analysis, aggregated)
    
    def _prepare_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """
        Memformat data analisis mentah menjadi string JSON bersih yang mudah dibaca LLM.
        """
        
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
            try:
                # Handle tuple unpacking safely if structure varies
                if isinstance(analysis['top_sector'], (list, tuple)) and len(analysis['top_sector']) >= 2:
                    sector_code, sector_info = analysis['top_sector']
                    simplified['hasil_analisis']['sektor_tertinggi'] = {
                        'kode': sector_code,
                        'nama': sector_info['name'],
                        'total': sector_info['total']
                    }
                else:
                     simplified['hasil_analisis']['sektor_tertinggi'] = str(analysis['top_sector'])
            except:
                pass
        
        if 'total_usaha' in analysis:
            simplified['hasil_analisis']['total_usaha'] = analysis['total_usaha']
        
        if 'average' in analysis:
            simplified['hasil_analisis']['rata_rata'] = round(analysis['average'], 2)
        
        if 'concentration' in analysis:
            simplified['hasil_analisis']['konsentrasi_top3'] = round(analysis['concentration'], 2)
        
        # Province detail specific
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
        """
        Generate response without LLM (Rule-based).
        Ini sangat penting jika API Gemini down, agar user tetap mendapat penjelasan data.
        """
        
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
                    
                    response = f"Analisis distribusi menunjukkan bahwa sektor {top_sector.get('short_name', top_sector.get('name'))} mendominasi dengan total {top_sector['total']:,} unit usaha ({top_sector.get('percentage', 0):.1f}% dari total). "
                    
                    # Add top 3 sectors
                    if len(dist_detail) >= 3:
                        top3_sectors = ', '.join([s.get('short_name', s.get('name')) for s in dist_detail[:3]])
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
        """Handle non-data queries conversationally with persona"""
        
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
   - Menampilkan Heatmap, Treemap, dan Radar Chart
   - Insight dan rekomendasi kebijakan
3. Jika user menyapa, balas dengan ramah dan tawarkan bantuan spesifik

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