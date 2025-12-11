import os
import asyncio
from typing import List, Dict, Any, Optional
# GANTI: Menggunakan library Google Generative AI
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from models import (
    ScrapedData, PolicyInsight, PolicyRecommendation, 
    VisualizationConfig, PolicyCategory, ChatMessage
)
import json
import logging
from datetime import datetime
from langdetect import detect, DetectorFactory

# Set seed for consistent language detection results
DetectorFactory.seed = 0

logger = logging.getLogger(__name__)

class PolicyAIAnalyzer:
    def __init__(self):
        # Ambil API Key Gemini dari Environment
        self.api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not found in environment variables")
        else:
            # Konfigurasi Gemini
            genai.configure(api_key=self.api_key)
            
        # Konfigurasi Model
        # Menggunakan Gemini 1.5 Flash yang cepat dan efisien
        self.model_name = os.environ.get('LLM_MODEL') or "gemini-2.5-flash"
        
        # Konfigurasi Safety (agar tidak terlalu restriktif untuk analisis kebijakan)
        self.safety_settings = {
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

    async def analyze_policy_query(
        self, 
        user_message: str,
        session_id: str,
        scraped_data: List[ScrapedData] = None  # Parameter ini sekarang diabaikan
    ) -> Dict[str, Any]:
        """Data-driven policy analysis using multi-agent system with real Sensus data"""
        try:
            # Import agents - MUST BE INSIDE METHOD to avoid circular imports
            from data_agent import DataRetrievalAgent, AnalysisAgent
            from visualization_agent import VisualizationAgent
            from insight_agent import InsightGenerationAgent
            from database import get_database
            
            if not self.api_key:
                return await self._handle_error_scenario(user_message, "API Key missing")
            
            # Detect language
            user_language = self._detect_language(user_message)
            
            # Check if analysis-related
            is_analysis_query = self._is_analysis_related_query(user_message)
            
            if not is_analysis_query:
                # Handle conversational query
                return await self._handle_conversational_query(user_message, user_language)
            
            # Initialize agents
            db = await get_database()
            data_agent = DataRetrievalAgent(db)
            analysis_agent = AnalysisAgent()
            viz_agent = VisualizationAgent()
            insight_agent = InsightGenerationAgent()
            
            # AGENT 1: Understand query intent
            intent = await data_agent.understand_query(user_message)
            logger.info(f"Query intent: {intent.intent_type}, provinces: {intent.provinces}, sectors: {intent.sectors}")
            
            # AGENT 2: Retrieve data based on intent from initial_data collection
            raw_data = await data_agent.get_data_by_intent(intent)
            
            if not raw_data:
                return {
                    'message': f'Maaf, tidak ditemukan data yang sesuai dengan pertanyaan Anda tentang "{user_message}". Silakan coba pertanyaan lain atau spesifikkan provinsi/sektor yang ingin dianalisis.',
                    'data_availability': 'No matching data found in Sensus Ekonomi 2016',
                    'insights': [
                        'Coba spesifikkan nama provinsi (contoh: Jawa Barat, DKI Jakarta)',
                        'Atau sebutkan sektor usaha tertentu (contoh: perdagangan, industri, konstruksi)'
                    ],
                    'policies': [],
                    'visualizations': [],
                    'supporting_data_count': 0
                }
            
            # AGENT 3: Aggregate data
            aggregated_data = await data_agent.aggregate_data(raw_data, intent)
            logger.info(f"Aggregated data type: {aggregated_data.get('type')}")
            
            # AGENT 4: Analyze data
            analysis = analysis_agent.analyze(aggregated_data, intent)
            logger.info(f"Analysis completed with {len(analysis)} metrics")
            
            # AGENT 5: Create visualizations
            visualizations = viz_agent.create_visualizations(analysis, aggregated_data)
            logger.info(f"Generated {len(visualizations)} visualizations")
            
            # AGENT 6: Generate insights & policy recommendations using Gemini
            insights_result = await insight_agent.generate_insights(
                analysis, 
                aggregated_data,
                user_message,
                user_language
            )
            logger.info(f"Generated {len(insights_result.get('insights', []))} insights and {len(insights_result.get('policies', []))} policies")
            
            # Generate main narrative response using Gemini
            main_response = await self._generate_main_response(
                user_message,
                analysis,
                aggregated_data,
                insights_result,
                user_language
            )
            
            return {
                'message': main_response,
                'data_availability': f'Data dari Sensus Ekonomi 2016: {len(raw_data)} provinsi',
                'insights': insights_result.get('insights', []),
                'policies': insights_result.get('policies', []),
                'visualizations': visualizations,
                'supporting_data_count': len(raw_data)
            }
            
        except Exception as e:
            logger.error(f"Error in policy analysis: {e}", exc_info=True)
            return await self._handle_error_scenario(user_message, str(e))


    async def _generate_main_response(
        self,
        user_query: str,
        analysis: Dict[str, Any],
        aggregated_data: Dict[str, Any],
        insights_result: Dict[str, Any],
        language: str
    ) -> str:
        """Generate main narrative response using Gemini"""
        
        if not self.api_key:
            return self._generate_fallback_response(analysis, aggregated_data)
        
        # Prepare comprehensive context
        context = f"""
    PERTANYAAN PENGGUNA: {user_query}

    TIPE ANALISIS: {aggregated_data.get('type', 'unknown').upper()}

    DATA STATISTIK:
    {json.dumps(analysis, indent=2, ensure_ascii=False)}

    INSIGHTS YANG DIHASILKAN:
    {json.dumps(insights_result.get('insights', []), indent=2, ensure_ascii=False)}

    TUGAS ANDA:
    1. Buat narasi analisis yang komprehensif dan mudah dipahami dalam bahasa {language}
    2. Gunakan angka statistik yang konkret dari data di atas
    3. Jelaskan implikasi dan konteks ekonomi dari temuan
    4. Berikan penjelasan yang actionable dan relevan
    5. Jangan membuat data fiktif - hanya gunakan data yang disediakan
    """
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=f"""Anda adalah ahli analisis data Sensus Ekonomi Indonesia dengan keahlian dalam:
    - Interpretasi data statistik ekonomi
    - Analisis pola ekonomi regional
    - Memberikan konteks kebijakan ekonomi

    Berikan penjelasan yang:
    - Jelas dan profesional dalam bahasa {language}
    - Menggunakan data konkret dari analisis
    - Mudah dipahami oleh pembuat kebijakan dan publik umum
    - Menghubungkan data dengan implikasi praktis"""
            )
            
            response = await model.generate_content_async(context)
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating main response with Gemini: {e}")
            return self._generate_fallback_response(analysis, aggregated_data)


    def _generate_fallback_response(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> str:
        """Fallback response if Gemini fails"""
        data_type = data.get('type', 'unknown')
        
        if data_type == 'ranking':
            top_provinces = analysis.get('top_provinces', [])
            if top_provinces and len(top_provinces) > 0:
                top = top_provinces[0]
                response = f"Berdasarkan data Sensus Ekonomi 2016, **{top['provinsi']}** menempati posisi teratas dengan **{top['total']:,} usaha** atau **{top['percentage']:.1f}%** dari total.\n\n"
                
                if len(top_provinces) > 1:
                    response += "**Top 3 Provinsi:**\n"
                    for i, prov in enumerate(top_provinces[:3], 1):
                        response += f"{i}. {prov['provinsi']}: {prov['total']:,} usaha ({prov['percentage']:.1f}%)\n"
                
                concentration = analysis.get('concentration', 0)
                response += f"\nKonsentrasi ekonomi cukup tinggi dengan 3 provinsi teratas menguasai **{concentration:.1f}%** dari total usaha."
                
                return response
        
        elif data_type == 'comparison':
            max_prov = analysis.get('max_province')
            min_prov = analysis.get('min_province')
            avg = analysis.get('average', 0)
            
            if max_prov and min_prov:
                response = f"**Perbandingan Jumlah Usaha:**\n\n"
                response += f"- Tertinggi: **{max_prov.get('provinsi')}** dengan {max_prov.get('total', 0):,} usaha\n"
                response += f"- Terendah: **{min_prov.get('provinsi')}** dengan {min_prov.get('total', 0):,} usaha\n"
                response += f"- Rata-rata: **{avg:,.0f} usaha** per provinsi\n"
                
                gap = max_prov.get('total', 0) - min_prov.get('total', 0)
                response += f"\nKesenjangan: **{gap:,} usaha** antara provinsi tertinggi dan terendah."
                
                return response
        
        elif data_type == 'distribution':
            top_sector = analysis.get('top_sector')
            total = analysis.get('total_usaha', 0)
            
            if top_sector:
                code, info = top_sector
                response = f"**Distribusi Usaha Per Sektor (Sensus Ekonomi 2016):**\n\n"
                response += f"Sektor dominan: **{info['name']}** dengan {info['total']:,} usaha.\n\n"
                response += f"Total usaha yang dianalisis: **{total:,}**\n"
                
                distribution_detail = analysis.get('distribution_detail', [])
                if len(distribution_detail) > 1:
                    response += f"\n**Top 5 Sektor:**\n"
                    for i, sector in enumerate(distribution_detail[:5], 1):
                        response += f"{i}. {sector['sector_name']}: {sector['total']:,} ({sector['percentage']:.1f}%)\n"
                
                return response
        
        return "Analisis data telah selesai berdasarkan Sensus Ekonomi 2016. Silakan lihat visualisasi dan insight untuk detail lebih lanjut."


    async def _handle_conversational_query(self, user_message: str, language: str) -> Dict[str, Any]:
        """Handle non-analysis conversational queries"""
        
        if not self.api_key:
            return {
                'message': "Halo! Saya adalah asisten analisis Sensus Ekonomi Indonesia. Apa yang bisa saya bantu?",
                'data_availability': 'Not applicable for general conversation',
                'insights': [],
                'policies': [],
                'visualizations': [],
                'supporting_data_count': 0
            }
        
        system_prompt = f"""Anda adalah asisten ramah untuk Sensus Ekonomi Indonesia.

    Tugas Anda:
    - Jawab pertanyaan umum dengan ramah dalam bahasa {language}
    - Jika pengguna bertanya tentang data atau analisis, arahkan mereka untuk bertanya spesifik
    - Jangan generate visualisasi, insights, atau rekomendasi kebijakan untuk chat biasa

    Contoh pertanyaan yang BUKAN analisis data:
    - "Halo", "Apa kabar", "Terima kasih"
    - "Apa itu sensus ekonomi?"
    - "Bagaimana cara menggunakan aplikasi ini?"
    """
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt
            )
            
            response = await model.generate_content_async(user_message)
            
            return {
                'message': response.text,
                'data_availability': 'Not applicable for general conversation',
                'insights': [],
                'policies': [],
                'visualizations': [],
                'supporting_data_count': 0
            }
            
        except Exception as e:
            logger.error(f"Error in conversational response: {e}")
            return {
                'message': "Maaf, saya mengalami kendala teknis. Silakan coba lagi atau ajukan pertanyaan analisis data.",
                'data_availability': 'Error',
                'insights': [],
                'policies': [],
                'visualizations': [],
                'supporting_data_count': 0
            }
            
        except Exception as e:
            logger.error(f"Error in policy analysis: {e}")
            return await self._handle_error_scenario(user_message, str(e))

    async def _handle_no_data_scenario(self, user_message: str, user_language: str = "English") -> Dict[str, Any]:
        """Handle cases where no real data is available"""
        
        responses = {
            "Spanish": {
                'message': f"""No puedo proporcionar un análisis completo para su pregunta sobre "{user_message}" porque actualmente no hay datos relevantes en tiempo real disponibles en el sistema.""",
                'insights': ['El análisis de políticas requiere acceso a datos actuales e históricos']
            },
            "English": {
                'message': f"""I cannot provide a comprehensive analysis for your question about "{user_message}" because no relevant real-time data is currently available in the system.""",
                'insights': ['Policy analysis requires access to current and historical data']
            },
            "Indonesian": {
                'message': f"""Saya tidak dapat memberikan analisis komprehensif untuk pertanyaan Anda tentang "{user_message}" karena saat ini tidak ada data real-time yang relevan tersedia di sistem.

Untuk memberikan analisis kebijakan yang akurat, saya memerlukan akses ke indikator ekonomi terkini, data hasil kebijakan, dan temuan penelitian yang relevan.""",
                'insights': [
                    'Analisis kebijakan memerlukan akses ke data terkini dan historis',
                    'Analisis yang efektif membutuhkan berbagai sumber data untuk validasi',
                    'Ketersediaan data berdampak langsung pada kualitas dan keandalan analisis'
                ]
            }
        }
        
        response = responses.get(user_language, responses["English"])
        
        return {
            'message': response['message'],
            'data_availability': 'No relevant data currently available',
            'insights': response['insights'],
            'policies': [],
            'visualizations': [],
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