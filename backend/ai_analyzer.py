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
        scraped_data: List[ScrapedData] = None
    ) -> Dict[str, Any]:
        """Data-driven policy analysis using Gemini AI"""
        try:
            if not self.api_key:
                return await self._handle_error_scenario(user_message, "API Key missing")

            # Detect user input language
            user_language = self._detect_language(user_message)
            
            # Check if we have actual data
            if not scraped_data or len(scraped_data) == 0:
                return await self._handle_no_data_scenario(user_message, user_language)
            
            # Prepare detailed context from real scraped data
            context = self._prepare_detailed_data_context(scraped_data)
            
            # Check if the query is analysis-related
            is_analysis_query = self._is_analysis_related_query(user_message)
            
            # Dapatkan System Prompt
            system_instruction = self._get_data_driven_analyst_prompt(user_language)
            
            # Buat Prompt User
            if is_analysis_query:
                user_prompt = f"""
                STRICT DATA-DRIVEN ANALYSIS REQUIRED:
                Language: Respond in {user_language}

                USER QUESTION: {user_message}

                AVAILABLE REAL DATA (ONLY USE THIS DATA):
                {context}

                REQUIREMENTS:
                - Only analyze based on the provided real data above
                - If specific data is not available, explicitly state data limitations
                - Generate visualizations ONLY using actual data points from the context
                - All insights must reference specific data from the context
                - Do not create hypothetical scenarios or data
                - Respond in {user_language} language
                
                Provide response in JSON format:
                {{
                    "main_response": "Analysis based strictly on available data (mention data limitations)",
                    "data_availability": "Available: [list data types], Missing: [list missing data]",
                    "insights": ["insight based on real data point", "another data-driven insight"],
                    "policy_recommendations": [
                        {{
                            "title": "Evidence-based recommendation title",
                            "description": "Based on specific data from context",
                            "priority": "high|medium|low", 
                            "category": "economic|social|environmental|healthcare|education|security|technology",
                            "impact": "Expected impact based on similar real examples from data",
                            "implementation_steps": ["step based on real examples"],
                            "supporting_evidence": "Specific data reference from context"
                        }}
                    ],
                    "visualizations": [
                        {{
                            "type": "chart",
                            "title": "Chart title based on real data",
                            "data_source": "Specific data reference",
                            "real_data_points": true
                        }}
                    ]
                }}
                """
            else:
                user_prompt = f"""
                CONVERSATIONAL RESPONSE REQUIRED:
                Language: Respond in {user_language}

                USER QUESTION: {user_message}

                This question is not related to data analysis, policy analysis, statistics, or visualization.
                Provide a helpful conversational response without generating analysis outputs.

                REQUIREMENTS:
                - Respond conversationally and helpfully in {user_language}
                - Do NOT generate visualizations, insights, or policy recommendations
                - Keep the response focused and relevant to their question

                Provide response in JSON format:
                {{
                    "main_response": "Conversational response in {user_language}",
                    "is_analysis": false
                }}
                """

            # --- INISIALISASI MODEL GEMINI KHUSUS REQUEST INI ---
            # Kita inisialisasi per request agar System Instruction bisa dinamis sesuai bahasa
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config={"response_mime_type": "application/json"}, # Memaksa output JSON
                safety_settings=self.safety_settings
            )

            # --- PANGGIL API GEMINI (ASYNC) ---
            response = await model.generate_content_async(user_prompt)
            
            # Ambil text response
            ai_response_text = response.text

            # Parse AI response
            parsed_response = self._parse_ai_response(ai_response_text)
            
            # Check if this is an analysis query
            if is_analysis_query and parsed_response.get('is_analysis', True):
                # Generate data-driven visualizations
                visualizations = await self._generate_data_driven_visualizations(
                    scraped_data, 
                    user_message,
                    parsed_response.get('visualizations', [])
                )
                
                # Jika tidak ada visualisasi data riil, coba generate visualisasi simulasi
                if not visualizations:
                     visualizations = await self._generate_visualizations(
                        parsed_response.get('visualizations', []),
                        user_message
                    )

                # Create evidence-based policy recommendations
                recommendations = self._create_evidence_based_recommendations(
                    parsed_response.get('policy_recommendations', [])
                )
                
                return {
                    'message': parsed_response.get('main_response', ai_response_text),
                    'data_availability': parsed_response.get('data_availability', 'Limited data available'),
                    'insights': parsed_response.get('insights', []),
                    'policies': recommendations,
                    'visualizations': visualizations,
                    'supporting_data_count': len(scraped_data)
                }
            else:
                # For non-analysis queries
                return {
                    'message': parsed_response.get('main_response', ai_response_text),
                    'data_availability': 'Not applicable for general conversation',
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