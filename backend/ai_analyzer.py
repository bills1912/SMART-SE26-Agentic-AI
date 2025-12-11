import os
import asyncio
from typing import List, Dict, Any, Optional
# GANTI: Menggunakan library Google Generative AI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from models import (
    ScrapedData, PolicyInsight, PolicyRecommendation, 
    VisualizationConfig, PolicyCategory, ChatMessage, QueryIntent
)
from motor.motor_asyncio import AsyncIOMotorDatabase
from data_agent import DataRetrievalAgent, AnalysisAgent
from visualization_agent import VisualizationAgent
from insight_agent import InsightGenerationAgent
import json
import logging
from datetime import datetime
from langdetect import detect, DetectorFactory

# Set seed for consistent language detection results
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

class PolicyAnalyzer:
    """Enhanced Policy Analyzer with better intent detection"""
    
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
            'bandingkan', 'compare', 'versus', 'vs', 'perbandingan', 'lebih besar', 'lebih kecil',
            
            # Pertanyaan ranking
            'terbanyak', 'tertinggi', 'terendah', 'terbesar', 'terkecil', 'top', 'ranking', 
            'urutan', 'urut', 'paling', 'most', 'least', 'highest', 'lowest',
            
            # Pertanyaan distribusi
            'distribusi', 'sebaran', 'persebaran', 'komposisi', 'proporsi', 'persentase',
            'bagaimana', 'how', 'distribution',
            
            # Pertanyaan spesifik
            'provinsi mana', 'sektor apa', 'wilayah mana', 'daerah mana', 'which province',
            'which sector', 'what sector', 'where',
            
            # Kata kunci analisis
            'analisis', 'analyze', 'tren', 'trend', 'perkembangan', 'data', 'statistik',
            'insight', 'laporan', 'report'
        ]
        
        # Check if query contains any data keywords
        has_data_keyword = any(keyword in query_lower for keyword in data_keywords)
        
        # Exclude conversational queries
        conversational_only = [
            'halo', 'hello', 'hi', 'hai', 'terima kasih', 'thank you', 'thanks',
            'siapa kamu', 'who are you', 'apa itu', 'what is', 'tolong jelaskan'
        ]
        
        is_conversational = any(keyword in query_lower for keyword in conversational_only)
        
        # Entity mentions (provinces, sectors)
        has_province = any(prov in query_lower for prov in [
            'aceh', 'sumut', 'sumbar', 'riau', 'jambi', 'sumsel', 'bengkulu', 'lampung',
            'jakarta', 'jabar', 'jateng', 'jatim', 'yogya', 'banten', 'bali',
            'kalimantan', 'sulawesi', 'papua', 'maluku', 'nusa tenggara'
        ])
        
        has_sector = any(sector in query_lower for sector in [
            'pertanian', 'pertambangan', 'industri', 'listrik', 'konstruksi',
            'perdagangan', 'transportasi', 'hotel', 'restoran', 'akomodasi',
            'informasi', 'keuangan', 'real estat', 'properti', 'pendidikan',
            'kesehatan', 'sektor', 'lapangan usaha', 'kbli'
        ])
        
        # Decision logic
        if is_conversational and not (has_province or has_sector):
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
        Main analysis method with enhanced intent detection
        """
        try:
            logger.info(f"Analyzing query: {query}")
            
            # Check if this is a data query
            is_data_query = self._is_data_query(query)
            
            logger.info(f"Query classification: {'DATA_QUERY' if is_data_query else 'CONVERSATIONAL'}")
            
            if not is_data_query:
                # Handle conversational queries
                return await self._handle_conversational_query(query, language)
            
            # ENHANCED: Try to process as data query
            try:
                # Step 1: Understand intent
                intent = await self.data_agent.understand_query(query)
                logger.info(f"Intent detected: {intent.intent_type}, provinces={intent.provinces}, sectors={intent.sectors}")
                
                # Step 2: Get data
                raw_data = await self.data_agent.get_data_by_intent(intent)
                
                if not raw_data:
                    logger.warning("No data found, but attempting broader search...")
                    
                    # FALLBACK 1: Try without province filter
                    if intent.provinces:
                        intent.provinces = []
                        raw_data = await self.data_agent.get_data_by_intent(intent)
                    
                    # FALLBACK 2: Try without sector filter
                    if not raw_data and intent.sectors:
                        intent.sectors = []
                        raw_data = await self.data_agent.get_data_by_intent(intent)
                    
                    if not raw_data:
                        # Last resort: Get all data
                        logger.info("Fetching all data as last resort")
                        intent = QueryIntent(intent_type='distribution')
                        raw_data = await self.data_agent.get_data_by_intent(intent)
                
                if not raw_data:
                    return {
                        'message': 'Maaf, tidak ada data yang ditemukan untuk pertanyaan Anda. Silakan coba pertanyaan lain.',
                        'visualizations': [],
                        'insights': [],
                        'policies': [],
                        'supporting_data_count': 0
                    }
                
                logger.info(f"Retrieved {len(raw_data)} documents")
                
                # Step 3: Aggregate data
                aggregated = await self.data_agent.aggregate_data(raw_data, intent)
                
                # Step 4: Analyze
                analysis = self.analysis_agent.analyze(aggregated, intent)
                
                # Step 5: Create visualizations
                visualizations = self.viz_agent.create_visualizations(analysis, aggregated)
                
                # Step 6: Generate insights
                insights_result = await self.insight_agent.generate_insights(
                    analysis, aggregated, query, language
                )
                
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
            logger.error(f"Error in analyze_policy_query: {e}", exc_info=True)
            return {
                'message': f"Maaf, terjadi kesalahan: {str(e)}",
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
            return self._generate_fallback_response(analysis, aggregated)
        
        try:
            # Prepare context
            context = {
                'query': query,
                'analysis': analysis,
                'data_type': aggregated.get('type', 'unknown'),
                'insights': insights.get('insights', [])
            }
            
            # Enhanced prompt
            prompt = f"""Kamu adalah asisten analisis data Sensus Ekonomi Indonesia yang profesional.

Pertanyaan user: "{query}"

Data yang tersedia:
{self._prepare_context_for_prompt(context)}

Tugas kamu:
1. Jawab pertanyaan user secara LANGSUNG dan SPESIFIK dengan data yang ada
2. Berikan angka-angka konkret (jumlah usaha, persentase, ranking)
3. Highlight insight penting dalam 2-3 kalimat
4. Jangan sebutkan keterbatasan data atau menyuruh user ke BPS
5. Gunakan bahasa yang mudah dipahami

Format jawaban:
- Paragraf pembuka: Jawaban langsung dengan angka
- Paragraf analisis: Insight dan perbandingan
- Paragraf penutup: Kesimpulan singkat

Panjang: 3-5 kalimat maksimal.
Bahasa: {language}
"""
            
            response = self.model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Error generating main response: {e}")
            return self._generate_fallback_response(analysis, aggregated)
    
    def _prepare_context_for_prompt(self, context: Dict[str, Any]) -> str:
        """Format context for LLM prompt"""
        import json
        
        # Simplified context for better LLM comprehension
        simplified = {
            'tipe_analisis': context.get('data_type', 'unknown'),
            'hasil_analisis': {}
        }
        
        analysis = context.get('analysis', {})
        
        if 'top_provinces' in analysis:
            simplified['hasil_analisis']['provinsi_teratas'] = analysis['top_provinces']
        
        if 'max_province' in analysis:
            simplified['hasil_analisis']['provinsi_tertinggi'] = analysis['max_province']
        
        if 'distribution_detail' in analysis:
            simplified['hasil_analisis']['distribusi_sektor'] = analysis['distribution_detail'][:5]  # Top 5
        
        if 'top_sector' in analysis:
            simplified['hasil_analisis']['sektor_tertinggi'] = analysis['top_sector']
        
        return json.dumps(simplified, indent=2, ensure_ascii=False)
    
    def _generate_fallback_response(self, analysis: Dict[str, Any], aggregated: Dict[str, Any]) -> str:
        """Generate response without LLM"""
        
        data_type = aggregated.get('type', 'unknown')
        
        if data_type == 'ranking':
            top_provinces = analysis.get('top_provinces', [])
            if top_provinces:
                top = top_provinces[0]
                return f"Berdasarkan data Sensus Ekonomi 2016, {top['provinsi']} memiliki jumlah usaha terbanyak dengan total {top['total']:,} unit usaha ({top['percentage']:.1f}% dari total nasional). Provinsi ini mendominasi perekonomian nasional di sektor yang dianalisis."
        
        elif data_type == 'distribution':
            dist_detail = analysis.get('distribution_detail', [])
            if dist_detail:
                top_sector = dist_detail[0]
                return f"Analisis distribusi menunjukkan bahwa sektor {top_sector['sector_name']} mendominasi dengan total {top_sector['total']:,} unit usaha ({top_sector['percentage']:.1f}% dari total). Sektor ini merupakan tulang punggung ekonomi Indonesia."
        
        elif data_type == 'comparison':
            max_prov = analysis.get('max_province', {})
            if max_prov:
                return f"Dari perbandingan data, {max_prov.get('provinsi', 'provinsi tertentu')} memiliki jumlah usaha tertinggi dengan {max_prov.get('total', 0):,} unit usaha. Data ini menunjukkan konsentrasi ekonomi yang signifikan di wilayah tersebut."
        
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
   - Analisis jumlah usaha per provinsi
   - Perbandingan antar wilayah
   - Distribusi per sektor KBLI
   - Ranking dan statistik ekonomi
3. Jika user menyapa, balas dengan ramah dan tawarkan bantuan
4. Jangan buat asumsi tentang data yang tidak ada

Bahasa: {language}
Panjang: 2-3 kalimat.
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
            logger.error(f"Error in conversational handler: {e}")
            return {
                'message': "Halo! Ada yang bisa saya bantu terkait data Sensus Ekonomi Indonesia?",
                'visualizations': [],
                'insights': [],
                'policies': [],
                'supporting_data_count': 0
            }

    async def _handle_error_scenario(self, user_message: str, error: str) -> Dict[str, Any]:
        """Handle error scenarios transparently"""
        return {
            'message': f'I encountered a technical error while analyzing your policy question: "{user_message}". Error details: {error}. Please try rephrasing your question or try again later.',
            'data_availability': 'Error accessing data',
            'insights': ['Technical issues can affect analysis quality'],
            'policies': [],
            'visualizations': [],
            'supporting_data_count': 0
        }

    def _get_data_driven_analyst_prompt(self, user_language: str = "English") -> str:
        """Generate system prompt for data-driven policy analysis with language support"""
        return f"""
        You are an AI Policy and Economic Analysis Assistant specializing in Indonesian Economic Census (Sensus Ekonomi Indonesia).
        
        YOUR PRIMARY SCOPE:
        1. Sensus Ekonomi Indonesia
        2. Perekonomian Indonesia
        3. Kegiatan Sensus
        4. Metodologi Sensus
        5. Diseminasi dan Publikasi
        
        MULTILINGUAL SUPPORT:
        - Always respond in the SAME language as the user's question ({user_language})
        
        STRICT DATA REQUIREMENTS:
        - Only use data explicitly provided in the context
        - Never generate hypothetical numbers or scenarios
        
        You are helpful and informative about Indonesian Economic Census while being honest about data limitations.
        """

    def _detect_language(self, text: str) -> str:
        try:
            detected_code = detect(text)
            language_map = {
                'en': 'English', 'es': 'Spanish', 'fr': 'French', 
                'id': 'Indonesian', 'ms': 'Malay', 'de': 'German'
            }
            return language_map.get(detected_code, 'English')
        except Exception:
            return "English"

    def _is_analysis_related_query(self, user_message: str) -> bool:
        message_lower = user_message.lower()
        analysis_keywords = [
            'analyze', 'analysis', 'compare', 'data', 'statistics', 'chart', 'graph', 
            'visualization', 'policy', 'economic', 'gdp', 'growth', 'inflation', 
            'analisis', 'bandingkan', 'statistik', 'visualisasi', 'kebijakan', 
            'ekonomi', 'pertumbuhan', 'inflasi', 'sensus', 'census'
        ]
        chat_keywords = ['hello', 'hi', 'halo', 'apa kabar', 'thank you', 'terima kasih']
        
        analysis_score = sum(1 for keyword in analysis_keywords if keyword in message_lower)
        chat_score = sum(1 for keyword in chat_keywords if keyword in message_lower)
        
        if analysis_score > 0 and chat_score == 0:
            return True
        if analysis_score > chat_score:
            return True
        return False

    def _prepare_detailed_data_context(self, scraped_data: List[ScrapedData]) -> str:
        if not scraped_data:
            return "No data available for analysis."
        
        context_parts = ["AVAILABLE REAL DATA:\n"]
        by_category = {}
        for data in scraped_data:
            category = data.category or 'general'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(data)
        
        for category, items in by_category.items():
            context_parts.append(f"\n{category.upper()} DATA:")
            for i, item in enumerate(items[:10]):
                context_parts.append(f"\n[{category}_{i+1}] {item.title}")
                context_parts.append(f"Source: {item.source.value}")
                context_parts.append(f"Content: {item.content}")
                if item.metadata:
                    context_parts.append("Metadata:")
                    for key, value in item.metadata.items():
                        context_parts.append(f"  - {key}: {value}")
        
        return "\n".join(context_parts)

    async def _generate_data_driven_visualizations(
        self, 
        scraped_data: List[ScrapedData],
        query: str,
        viz_requests: List[Dict]
    ) -> List[VisualizationConfig]:
        visualizations = []
        economic_data = []
        for data in scraped_data:
            if data.category == PolicyCategory.ECONOMIC and data.metadata:
                if 'data_points' in data.metadata:
                    economic_data.extend(data.metadata['data_points'])
                elif any(key in data.metadata for key in ['gdp_growth', 'investment_amount', 'jobs_created']):
                    economic_data.append(data.metadata)
        
        if economic_data:
            viz_config = self._create_real_data_chart(economic_data, query)
            if viz_config:
                visualizations.append(viz_config)
        else:
            availability_chart = self._create_data_availability_chart(scraped_data)
            visualizations.append(availability_chart)
        
        return visualizations

    def _create_real_data_chart(self, data_points: List[Dict], query: str) -> Optional[VisualizationConfig]:
        try:
            yearly_data = {}
            categories = set()
            for point in data_points[:20]:
                if 'year' in point and 'value' in point:
                    year = str(point['year'])
                    if year not in yearly_data:
                        yearly_data[year] = {}
                    country = point.get('country', 'Data')
                    categories.add(country)
                    yearly_data[year][country] = point['value']
            
            if yearly_data:
                years = sorted(yearly_data.keys())
                categories = sorted(list(categories))
                series_data = []
                colors = ['#e74c3c', '#ff6b35', '#ff8c42', '#ffad73']
                for i, category in enumerate(categories):
                    values = []
                    for year in years:
                        values.append(yearly_data[year].get(category, None))
                    series_data.append({
                        "name": category, "type": "line", "data": values,
                        "itemStyle": {"color": colors[i % len(colors)]}
                    })
                
                config = {
                    "title": {
                        "text": f"Real Economic Data Analysis",
                        "subtext": f"Based on {len(data_points)} actual data points",
                        "left": "center",
                        "textStyle": {"color": "#e74c3c", "fontSize": 16}
                    },
                    "tooltip": {"trigger": "axis"},
                    "legend": {"data": categories, "bottom": 10},
                    "xAxis": {"type": "category", "data": years},
                    "yAxis": {"type": "value", "axisLabel": {"formatter": "{value}%"}},
                    "series": series_data
                }
                return VisualizationConfig(
                    id=f"real_data_{int(datetime.utcnow().timestamp())}",
                    type="chart", title="Real Economic Data Analysis",
                    config=config, data={"source": "Real data points", "count": len(data_points)}
                )
        except Exception as e:
            logger.error(f"Error creating real data chart: {e}")
        return None

    def _create_data_availability_chart(self, scraped_data: List[ScrapedData]) -> VisualizationConfig:
        category_counts = {}
        source_counts = {}
        for data in scraped_data:
            cat = data.category.value if data.category else 'unknown'
            src = data.source.value if data.source else 'unknown'
            category_counts[cat] = category_counts.get(cat, 0) + 1
            source_counts[src] = source_counts.get(src, 0) + 1
        
        pie_data = []
        colors = ['#e74c3c', '#ff6b35', '#ff8c42', '#ffad73', '#ffd4a3']
        for i, (category, count) in enumerate(category_counts.items()):
            pie_data.append({
                "value": count, "name": f"{category.title()} ({count} items)",
                "itemStyle": {"color": colors[i % len(colors)]}
            })
        
        config = {
            "title": {
                "text": "Available Data Sources",
                "subtext": f"Total: {len(scraped_data)} data points",
                "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16}
            },
            "tooltip": {"trigger": "item"},
            "series": [{
                "name": "Data Availability", "type": "pie", "radius": "50%",
                "data": pie_data, "emphasis": {"itemStyle": {"shadowBlur": 10}}
            }]
        }
        return VisualizationConfig(
            id=f"data_availability_{int(datetime.utcnow().timestamp())}",
            type="chart", title="Available Data Sources",
            config=config, data={"categories": category_counts, "sources": source_counts}
        )

    def _create_evidence_based_recommendations(self, recommendations_data: List[Dict]) -> List[PolicyRecommendation]:
        recommendations = []
        for rec_data in recommendations_data:
            try:
                category_str = rec_data.get('category', 'economic').lower()
                category = PolicyCategory(category_str) if category_str in PolicyCategory.__members__.values() else PolicyCategory.ECONOMIC
                supporting_evidence = rec_data.get('supporting_evidence', 'Based on available data analysis')
                recommendation = PolicyRecommendation(
                    title=rec_data.get('title', 'Evidence-Based Policy Recommendation'),
                    description=f"{rec_data.get('description', '')} | Evidence: {supporting_evidence}",
                    priority=rec_data.get('priority', 'medium'),
                    category=category,
                    impact=rec_data.get('impact', 'Impact assessment requires more specific data'),
                    implementation_steps=rec_data.get('implementation_steps', ['Gather more specific implementation data']),
                    supporting_insights=[supporting_evidence]
                )
                recommendations.append(recommendation)
            except Exception as e:
                logger.error(f"Error creating evidence-based recommendation: {e}")
        return recommendations

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        try:
            # Clean markdown code blocks if present
            cleaned_response = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned_response)
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return {'main_response': response}

    async def _generate_visualizations(self, viz_requests: List[Dict], query: str) -> List[VisualizationConfig]:
        visualizations = []
        for i, viz_request in enumerate(viz_requests[:3]):
            try:
                viz_config = await self._create_visualization_config(viz_request, query, i)
                if viz_config:
                    visualizations.append(viz_config)
            except Exception as e:
                logger.error(f"Error creating visualization {i}: {e}")
        return visualizations

    async def _create_visualization_config(self, viz_request: Dict, query: str, index: int) -> Optional[VisualizationConfig]:
        viz_type = viz_request.get('type', 'chart')
        title = viz_request.get('title', f'Policy Analysis Chart {index + 1}')
        if viz_type == 'chart' and 'economic' in query.lower():
            config = self._create_economic_chart_config(title)
        elif viz_type == 'chart' and ('social' in query.lower() or 'demographic' in query.lower()):
            config = self._create_social_chart_config(title)
        elif viz_type == 'graph':
            config = self._create_network_graph_config(title)
        else:
            config = self._create_default_chart_config(title)
        return VisualizationConfig(
            id=f"viz_{index}_{int(datetime.utcnow().timestamp())}",
            type=viz_type, title=title, config=config, data={}
        )

    def _create_economic_chart_config(self, title: str) -> Dict[str, Any]:
        return {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
            "tooltip": {"trigger": "axis"},
            "legend": {"data": ["GDP Growth", "Employment Rate", "Inflation Rate"], "bottom": 10},
            "xAxis": {"type": "category", "data": ["2020", "2021", "2022", "2023", "2024"]},
            "yAxis": {"type": "value"},
            "series": [
                {"name": "GDP Growth", "type": "line", "data": [-3.4, 5.7, 2.1, 2.4, 2.8], "itemStyle": {"color": "#e74c3c"}},
                {"name": "Employment Rate", "type": "line", "data": [59.2, 58.4, 60.1, 62.3, 63.1], "itemStyle": {"color": "#ff6b35"}},
                {"name": "Inflation Rate", "type": "line", "data": [1.2, 4.7, 8.0, 4.1, 3.2], "itemStyle": {"color": "#ff8c42"}}
            ]
        }

    def _create_social_chart_config(self, title: str) -> Dict[str, Any]:
        return {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
            "tooltip": {"trigger": "item"},
            "series": [{
                "name": "Social Impact", "type": "pie", "radius": "50%",
                "data": [
                    {"value": 35, "name": "Healthcare Access", "itemStyle": {"color": "#e74c3c"}},
                    {"value": 25, "name": "Education Quality", "itemStyle": {"color": "#ff6b35"}},
                    {"value": 20, "name": "Social Welfare", "itemStyle": {"color": "#ff8c42"}},
                    {"value": 15, "name": "Housing Affordability", "itemStyle": {"color": "#ffad73"}},
                    {"value": 5, "name": "Other Services", "itemStyle": {"color": "#ffd4a3"}}
                ]
            }]
        }

    def _create_network_graph_config(self, title: str) -> Dict[str, Any]:
        return {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
            "tooltip": {},
            "series": [{
                "type": "graph", "layout": "force", "symbolSize": 50, "roam": True, "label": {"show": True},
                "data": [{"name": "Policy", "x": 300, "y": 300}, {"name": "Economy", "x": 800, "y": 300}, {"name": "Society", "x": 550, "y": 100}, {"name": "Environment", "x": 550, "y": 500}],
                "links": [{"source": 0, "target": 1}, {"source": 0, "target": 2}, {"source": 0, "target": 3}, {"source": 1, "target": 2}]
            }]
        }

    def _create_default_chart_config(self, title: str) -> Dict[str, Any]:
        return {
            "title": {"text": title, "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
            "tooltip": {"trigger": "axis"},
            "xAxis": {"type": "category", "data": ["Q1", "Q2", "Q3", "Q4"]},
            "yAxis": {"type": "value"},
            "series": [{"name": "Policy Impact", "type": "bar", "data": [85, 92, 78, 95], "itemStyle": {"color": "#e74c3c"}}]
        }

    def _create_policy_recommendations(
        self, 
        recommendations_data: List[Dict]
    ) -> List[PolicyRecommendation]:
        """Create policy recommendation objects"""
        recommendations = []
        
        for rec_data in recommendations_data:
            try:
                category_str = rec_data.get('category', 'economic').lower()
                category = PolicyCategory(category_str) if category_str in PolicyCategory.__members__.values() else PolicyCategory.ECONOMIC
                
                recommendation = PolicyRecommendation(
                    title=rec_data.get('title', 'Policy Recommendation'),
                    description=rec_data.get('description', ''),
                    priority=rec_data.get('priority', 'medium'),
                    category=category,
                    impact=rec_data.get('impact', ''),
                    implementation_steps=rec_data.get('implementation_steps', [])
                )
                recommendations.append(recommendation)
                
            except Exception as e:
                logger.error(f"Error creating policy recommendation: {e}")
        
        return recommendations