import os
import asyncio
from typing import List, Dict, Any, Optional
from emergentintegrations.llm.chat import LlmChat, UserMessage
from models import (
    ScrapedData, PolicyInsight, PolicyRecommendation, 
    VisualizationConfig, PolicyCategory, ChatMessage
)
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class PolicyAIAnalyzer:
    def __init__(self):
        self.api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not self.api_key:
            raise ValueError("EMERGENT_LLM_KEY not found in environment variables")

    async def analyze_policy_query(
        self, 
        user_message: str,
        session_id: str,
        scraped_data: List[ScrapedData] = None
    ) -> Dict[str, Any]:
        """Data-driven policy analysis using AI - only use available real data"""
        try:
            # Detect user input language
            user_language = self._detect_language(user_message)
            
            # Check if we have actual data
            if not scraped_data or len(scraped_data) == 0:
                return await self._handle_no_data_scenario(user_message, user_language)
            
            # Initialize AI chat with language-aware prompt
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=self._get_data_driven_analyst_prompt(user_language)
            ).with_model("openai", "gpt-4o-mini")

            # Prepare detailed context from real scraped data
            context = self._prepare_detailed_data_context(scraped_data)
            
            # Check if the query is analysis-related
            is_analysis_query = self._is_analysis_related_query(user_message)
            
            # Create context-aware analysis prompt
            if is_analysis_query:
                analysis_prompt = f"""
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
                analysis_prompt = f"""
                CONVERSATIONAL RESPONSE REQUIRED:
                Language: Respond in {user_language}

                USER QUESTION: {user_message}

                This question is not related to data analysis, policy analysis, statistics, or visualization.
                Provide a helpful conversational response without generating analysis outputs.

                REQUIREMENTS:
                - Respond conversationally and helpfully in {user_language}
                - Do NOT generate visualizations, insights, or policy recommendations
                - If the user asks about general topics, provide informative chat responses
                - If the user asks how you can help, explain your policy analysis capabilities
                - Keep the response focused and relevant to their question

                Provide response in JSON format:
                {{
                    "main_response": "Conversational response in {user_language}",
                    "is_analysis": false
                }}
                """

            # Get AI response
            ai_message = UserMessage(text=analysis_prompt)
            response = await chat.send_message(ai_message)
            
            # Parse AI response
            parsed_response = self._parse_ai_response(response)
            
            # Check if this is an analysis query
            if is_analysis_query and parsed_response.get('is_analysis', True):
                # Generate data-driven visualizations
                visualizations = await self._generate_data_driven_visualizations(
                    scraped_data, 
                    user_message,
                    parsed_response.get('visualizations', [])
                )
                
                # Create evidence-based policy recommendations
                recommendations = self._create_evidence_based_recommendations(
                    parsed_response.get('policy_recommendations', [])
                )
                
                return {
                    'message': parsed_response.get('main_response', response),
                    'data_availability': parsed_response.get('data_availability', 'Limited data available'),
                    'insights': parsed_response.get('insights', []),
                    'policies': recommendations,
                    'visualizations': visualizations,
                    'supporting_data_count': len(scraped_data)
                }
            else:
                # For non-analysis queries, return only chat response
                return {
                    'message': parsed_response.get('main_response', response),
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
        
        # Multilingual responses based on detected language
        responses = {
            "Spanish": {
                'message': f"""No puedo proporcionar un análisis completo para su pregunta sobre "{user_message}" porque actualmente no hay datos relevantes en tiempo real disponibles en el sistema.

Para proporcionar un análisis de políticas preciso, necesito acceso a indicadores económicos actuales, datos de resultados de políticas y hallazgos de investigación relevantes.

¿Le gustaría que:
1. Sugiera qué fuentes de datos específicas serían útiles para este análisis
2. Proporcione principios generales de análisis de políticas que se aplican a esta área
3. Espere mientras el sistema intenta recopilar más datos relevantes""",
                'insights': [
                    'El análisis de políticas requiere acceso a datos actuales e históricos',
                    'Un análisis efectivo necesita múltiples fuentes de datos para validación',
                    'La disponibilidad de datos impacta directamente la calidad y confiabilidad del análisis'
                ]
            },
            "French": {
                'message': f"""Je ne peux pas fournir une analyse complète de votre question sur "{user_message}" car aucune donnée pertinente en temps réel n'est actuellement disponible dans le système.

Pour fournir une analyse politique précise, j'ai besoin d'accès aux indicateurs économiques actuels, aux données de résultats politiques et aux résultats de recherche pertinents.

Souhaitez-vous que je:
1. Suggère quelles sources de données spécifiques seraient utiles pour cette analyse
2. Fournisse des principes généraux d'analyse politique qui s'appliquent à ce domaine
3. Attende pendant que le système tente de rassembler plus de données pertinentes""",
                'insights': [
                    'L\'analyse politique nécessite l\'accès aux données actuelles et historiques',
                    'Une analyse efficace nécessite plusieurs sources de données pour la validation',
                    'La disponibilité des données impacte directement la qualité et la fiabilité de l\'analyse'
                ]
            },
            "English": {
                'message': f"""I cannot provide a comprehensive analysis for your question about "{user_message}" because no relevant real-time data is currently available in the system.

To provide accurate policy analysis, I need access to current economic indicators, policy outcome data, and relevant research findings.

Would you like me to:
1. Suggest what specific data sources would be helpful for this analysis
2. Provide general policy analysis principles that apply to this area
3. Wait while the system attempts to gather more relevant data""",
                'insights': [
                    'Policy analysis requires access to current and historical data',
                    'Effective analysis needs multiple data sources for validation',
                    'Data availability directly impacts analysis quality and reliability'
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
        """System prompt for strictly data-driven policy analysis AI"""
        return f"""
        You are a DATA-DRIVEN multilingual policy analyst who ONLY analyzes based on provided real data.
        
        LANGUAGE REQUIREMENT:
        - ALWAYS respond in the same language as the user's input: {user_language}
        - If the user writes in Spanish, respond in Spanish
        - If the user writes in French, respond in French
        - If the user writes in Chinese, respond in Chinese
        - Maintain professional policy analysis terminology in the target language
        
        STRICT DATA REQUIREMENTS:
        - Only use data explicitly provided in the context
        - Never generate hypothetical numbers or scenarios
        - If specific data is missing, clearly state this limitation
        - All insights must reference specific data points
        - Visualizations must use only real data from the context
        - Be transparent about data limitations and gaps
        
        Your expertise areas (only when data is available):
        - Economic indicators and policy outcomes
        - Evidence-based policy recommendations
        - Data-driven comparative analysis
        - Real case studies and implementation results
        
        Always:
        1. State what data is available vs. what's missing
        2. Base ALL analysis on provided evidence
        3. Acknowledge when analysis is limited by data availability
        4. Never extrapolate beyond available data
        5. Provide specific data references for each insight
        6. Respond in {user_language} language throughout
        
        You are honest about limitations rather than providing speculative analysis.
        """

    def _detect_language(self, text: str) -> str:
        """Detect the language of user input"""
        # Simple language detection based on common words and patterns
        text_lower = text.lower()
        
        # Spanish indicators
        spanish_words = ['que', 'del', 'los', 'las', 'una', 'para', 'con', 'por', 'como', 'cual', 'donde', 'cuando', 'porque', 'economia', 'politica', 'datos']
        if any(word in text_lower for word in spanish_words):
            return "Spanish"
        
        # French indicators
        french_words = ['que', 'des', 'les', 'une', 'pour', 'avec', 'par', 'comme', 'quel', 'ou', 'quand', 'pourquoi', 'économie', 'politique', 'données']
        if any(word in text_lower for word in french_words):
            return "French"
        
        # German indicators
        german_words = ['das', 'der', 'die', 'und', 'mit', 'für', 'von', 'wie', 'wo', 'wann', 'warum', 'wirtschaft', 'politik', 'daten']
        if any(word in text_lower for word in german_words):
            return "German"
        
        # Italian indicators
        italian_words = ['che', 'del', 'gli', 'una', 'per', 'con', 'come', 'dove', 'quando', 'perché', 'economia', 'politica', 'dati']
        if any(word in text_lower for word in italian_words):
            return "Italian"
        
        # Portuguese indicators
        portuguese_words = ['que', 'dos', 'uma', 'para', 'com', 'por', 'como', 'onde', 'quando', 'porque', 'economia', 'política', 'dados']
        if any(word in text_lower for word in portuguese_words):
            return "Portuguese"
        
        # Chinese indicators (simplified)
        chinese_chars = ['的', '和', '在', '是', '有', '了', '不', '经济', '政策', '数据']
        if any(char in text for char in chinese_chars):
            return "Chinese"
        
        # Default to English
        return "English"

    def _is_analysis_related_query(self, user_message: str) -> bool:
        """Determine if the user query is related to analysis, data, policy, etc."""
        message_lower = user_message.lower()
        
        # Analysis-related keywords
        analysis_keywords = [
            # English
            'analyze', 'analysis', 'compare', 'comparison', 'data', 'statistics', 'chart', 'graph', 
            'visualization', 'policy', 'economic', 'gdp', 'growth', 'inflation', 'unemployment',
            'impact', 'effect', 'trend', 'insight', 'recommendation', 'study', 'research',
            'evaluate', 'assessment', 'measure', 'metric', 'indicator', 'performance',
            'forecast', 'prediction', 'model', 'correlation', 'pattern', 'distribution',
            
            # Spanish
            'analizar', 'análisis', 'comparar', 'comparación', 'datos', 'estadísticas',
            'gráfico', 'visualización', 'política', 'económico', 'crecimiento', 'inflación',
            'desempleo', 'impacto', 'efecto', 'tendencia', 'recomendación', 'estudio',
            
            # French  
            'analyser', 'analyse', 'comparer', 'comparaison', 'données', 'statistiques',
            'graphique', 'visualisation', 'politique', 'économique', 'croissance', 'inflation',
            'chômage', 'impact', 'effet', 'tendance', 'recommandation', 'étude',
            
            # German
            'analysieren', 'analyse', 'vergleichen', 'vergleich', 'daten', 'statistiken',
            'grafik', 'visualisierung', 'politik', 'wirtschaft', 'wachstum', 'inflation',
            'arbeitslosigkeit', 'auswirkung', 'effekt', 'trend', 'empfehlung', 'studie'
        ]
        
        # Non-analysis keywords (general chat)
        chat_keywords = [
            'hello', 'hi', 'how are you', 'what is your name', 'who are you',
            'thank you', 'thanks', 'goodbye', 'bye', 'help', 'what can you do',
            'how do you work', 'tell me about', 'explain', 'define', 'meaning',
            'weather', 'time', 'date', 'joke', 'story', 'news', 'latest',
            'hola', 'gracias', 'adiós', 'ayuda', 'qué puedes hacer',
            'bonjour', 'merci', 'au revoir', 'aide', 'que peux-tu faire',
            'hallo', 'danke', 'auf wiedersehen', 'hilfe', 'was kannst du'
        ]
        
        # Check for analysis keywords
        analysis_score = sum(1 for keyword in analysis_keywords if keyword in message_lower)
        
        # Check for chat-only keywords
        chat_score = sum(1 for keyword in chat_keywords if keyword in message_lower)
        
        # If there are analysis keywords and no pure chat keywords, it's analysis
        if analysis_score > 0 and chat_score == 0:
            return True
            
        # If there are more analysis keywords than chat keywords
        if analysis_score > chat_score:
            return True
            
        # If asking specifically about capabilities or help
        if any(phrase in message_lower for phrase in ['what can you', 'how can you help', 'what do you do', 'capabilities']):
            return False  # This is a general question, not analysis
            
        # Default: if uncertain and contains some analysis terms, treat as analysis
        return analysis_score > 0

    def _prepare_detailed_data_context(self, scraped_data: List[ScrapedData]) -> str:
        """Prepare detailed, structured data context for AI analysis"""
        if not scraped_data:
            return "No data available for analysis."
        
        context_parts = ["AVAILABLE REAL DATA:\n"]
        
        # Group by category and source
        by_category = {}
        for data in scraped_data:
            category = data.category or 'general'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(data)
        
        # Create detailed context with all data points
        for category, items in by_category.items():
            context_parts.append(f"\n{category.upper()} DATA:")
            
            for i, item in enumerate(items[:10]):  # Limit per category
                context_parts.append(f"\n[{category}_{i+1}] {item.title}")
                context_parts.append(f"Source: {item.source.value}")
                context_parts.append(f"Content: {item.content}")
                
                # Include structured metadata if available
                if item.metadata:
                    context_parts.append("Metadata:")
                    for key, value in item.metadata.items():
                        context_parts.append(f"  - {key}: {value}")
                
                context_parts.append(f"Scraped: {item.scraped_at}\n")
        
        context_parts.append(f"\nTOTAL DATA POINTS: {len(scraped_data)}")
        context_parts.append(f"DATA SOURCES: {', '.join(set([d.source.value for d in scraped_data]))}")
        
        return "\n".join(context_parts)

    async def _generate_data_driven_visualizations(
        self, 
        scraped_data: List[ScrapedData],
        query: str,
        viz_requests: List[Dict]
    ) -> List[VisualizationConfig]:
        """Generate visualizations using only real data points"""
        visualizations = []
        
        # Extract data points that can be visualized
        economic_data = []
        for data in scraped_data:
            if data.category == PolicyCategory.ECONOMIC and data.metadata:
                if 'data_points' in data.metadata:
                    economic_data.extend(data.metadata['data_points'])
                elif any(key in data.metadata for key in ['gdp_growth', 'investment_amount', 'jobs_created']):
                    economic_data.append(data.metadata)
        
        if economic_data:
            # Create real data visualization
            viz_config = self._create_real_data_chart(economic_data, query)
            if viz_config:
                visualizations.append(viz_config)
        else:
            # Create a simple data availability chart
            availability_chart = self._create_data_availability_chart(scraped_data)
            visualizations.append(availability_chart)
        
        return visualizations

    def _create_real_data_chart(self, data_points: List[Dict], query: str) -> Optional[VisualizationConfig]:
        """Create chart using actual data points"""
        try:
            # Organize data by year if available
            yearly_data = {}
            categories = set()
            
            for point in data_points[:20]:  # Limit data points
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
                        "name": category,
                        "type": "line",
                        "data": values,
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
                    "legend": {
                        "data": categories,
                        "bottom": 10,
                        "textStyle": {"color": "#333"}
                    },
                    "xAxis": {
                        "type": "category",
                        "data": years,
                        "axisLabel": {"color": "#666"}
                    },
                    "yAxis": {
                        "type": "value",
                        "axisLabel": {"color": "#666", "formatter": "{value}%"}
                    },
                    "series": series_data
                }
                
                return VisualizationConfig(
                    id=f"real_data_{int(datetime.utcnow().timestamp())}",
                    type="chart",
                    title="Real Economic Data Analysis",
                    config=config,
                    data={"source": "Real data points", "count": len(data_points)}
                )
                
        except Exception as e:
            logger.error(f"Error creating real data chart: {e}")
        
        return None

    def _create_data_availability_chart(self, scraped_data: List[ScrapedData]) -> VisualizationConfig:
        """Create chart showing what data is actually available"""
        
        # Count data by category and source
        category_counts = {}
        source_counts = {}
        
        for data in scraped_data:
            cat = data.category.value if data.category else 'unknown'
            src = data.source.value if data.source else 'unknown'
            
            category_counts[cat] = category_counts.get(cat, 0) + 1
            source_counts[src] = source_counts.get(src, 0) + 1
        
        # Create pie chart of available data
        pie_data = []
        colors = ['#e74c3c', '#ff6b35', '#ff8c42', '#ffad73', '#ffd4a3']
        
        for i, (category, count) in enumerate(category_counts.items()):
            pie_data.append({
                "value": count,
                "name": f"{category.title()} ({count} items)",
                "itemStyle": {"color": colors[i % len(colors)]}
            })
        
        config = {
            "title": {
                "text": "Available Data Sources",
                "subtext": f"Total: {len(scraped_data)} data points",
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 16}
            },
            "tooltip": {
                "trigger": "item",
                "formatter": "{a} <br/>{b}: {c} ({d}%)"
            },
            "series": [{
                "name": "Data Availability",
                "type": "pie",
                "radius": "50%",
                "data": pie_data,
                "emphasis": {
                    "itemStyle": {
                        "shadowBlur": 10,
                        "shadowOffsetX": 0,
                        "shadowColor": "rgba(0, 0, 0, 0.5)"
                    }
                }
            }]
        }
        
        return VisualizationConfig(
            id=f"data_availability_{int(datetime.utcnow().timestamp())}",
            type="chart", 
            title="Available Data Sources",
            config=config,
            data={"categories": category_counts, "sources": source_counts}
        )

    def _create_evidence_based_recommendations(
        self, 
        recommendations_data: List[Dict]
    ) -> List[PolicyRecommendation]:
        """Create policy recommendations that reference real evidence"""
        recommendations = []
        
        for rec_data in recommendations_data:
            try:
                category_str = rec_data.get('category', 'economic').lower()
                category = PolicyCategory(category_str) if category_str in PolicyCategory.__members__.values() else PolicyCategory.ECONOMIC
                
                # Ensure supporting evidence is included
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
        """Parse AI JSON response safely"""
        try:
            # Try to extract JSON from the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)
            else:
                # Fallback parsing
                return {'main_response': response}
                
        except Exception as e:
            logger.error(f"Error parsing AI response: {e}")
            return {'main_response': response}

    async def _generate_visualizations(
        self, 
        viz_requests: List[Dict], 
        query: str
    ) -> List[VisualizationConfig]:
        """Generate ECharts visualizations based on AI suggestions"""
        visualizations = []
        
        for i, viz_request in enumerate(viz_requests[:3]):  # Limit to 3 visualizations
            try:
                viz_config = await self._create_visualization_config(viz_request, query, i)
                if viz_config:
                    visualizations.append(viz_config)
            except Exception as e:
                logger.error(f"Error creating visualization {i}: {e}")
        
        return visualizations

    async def _create_visualization_config(
        self, 
        viz_request: Dict, 
        query: str, 
        index: int
    ) -> Optional[VisualizationConfig]:
        """Create specific visualization configuration"""
        viz_type = viz_request.get('type', 'chart')
        title = viz_request.get('title', f'Policy Analysis Chart {index + 1}')
        
        # Generate sample data based on query and type
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
            type=viz_type,
            title=title,
            config=config,
            data={}
        )

    def _create_economic_chart_config(self, title: str) -> Dict[str, Any]:
        """Create economic impact chart configuration"""
        return {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "axis"},
            "legend": {
                "data": ["GDP Growth", "Employment Rate", "Inflation Rate"],
                "bottom": 10,
                "textStyle": {"color": "#333"}
            },
            "xAxis": {
                "type": "category",
                "data": ["2020", "2021", "2022", "2023", "2024"],
                "axisLabel": {"color": "#666"}
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {"color": "#666"}
            },
            "series": [
                {
                    "name": "GDP Growth",
                    "type": "line",
                    "data": [-3.4, 5.7, 2.1, 2.4, 2.8],
                    "itemStyle": {"color": "#e74c3c"}
                },
                {
                    "name": "Employment Rate",
                    "type": "line",
                    "data": [59.2, 58.4, 60.1, 62.3, 63.1],
                    "itemStyle": {"color": "#ff6b35"}
                },
                {
                    "name": "Inflation Rate",
                    "type": "line",
                    "data": [1.2, 4.7, 8.0, 4.1, 3.2],
                    "itemStyle": {"color": "#ff8c42"}
                }
            ]
        }

    def _create_social_chart_config(self, title: str) -> Dict[str, Any]:
        """Create social impact chart configuration"""
        return {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "item"},
            "series": [
                {
                    "name": "Social Impact",
                    "type": "pie",
                    "radius": "50%",
                    "data": [
                        {"value": 35, "name": "Healthcare Access", "itemStyle": {"color": "#e74c3c"}},
                        {"value": 25, "name": "Education Quality", "itemStyle": {"color": "#ff6b35"}},
                        {"value": 20, "name": "Social Welfare", "itemStyle": {"color": "#ff8c42"}},
                        {"value": 15, "name": "Housing Affordability", "itemStyle": {"color": "#ffad73"}},
                        {"value": 5, "name": "Other Services", "itemStyle": {"color": "#ffd4a3"}}
                    ],
                    "emphasis": {
                        "itemStyle": {
                            "shadowBlur": 10,
                            "shadowOffsetX": 0,
                            "shadowColor": "rgba(0, 0, 0, 0.5)"
                        }
                    }
                }
            ]
        }

    def _create_network_graph_config(self, title: str) -> Dict[str, Any]:
        """Create network graph configuration"""
        return {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {},
            "series": [
                {
                    "type": "graph",
                    "layout": "force",
                    "symbolSize": 50,
                    "roam": True,
                    "label": {"show": True},
                    "edgeSymbol": ["circle", "arrow"],
                    "edgeSymbolSize": [4, 10],
                    "data": [
                        {"name": "Policy", "x": 300, "y": 300, "itemStyle": {"color": "#e74c3c"}},
                        {"name": "Economy", "x": 800, "y": 300, "itemStyle": {"color": "#ff6b35"}},
                        {"name": "Society", "x": 550, "y": 100, "itemStyle": {"color": "#ff8c42"}},
                        {"name": "Environment", "x": 550, "y": 500, "itemStyle": {"color": "#ffad73"}}
                    ],
                    "links": [
                        {"source": 0, "target": 1},
                        {"source": 0, "target": 2},
                        {"source": 0, "target": 3},
                        {"source": 1, "target": 2}
                    ]
                }
            ]
        }

    def _create_default_chart_config(self, title: str) -> Dict[str, Any]:
        """Create default chart configuration"""
        return {
            "title": {
                "text": title,
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": ["Q1", "Q2", "Q3", "Q4"],
                "axisLabel": {"color": "#666"}
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {"color": "#666"}
            },
            "series": [
                {
                    "name": "Policy Impact",
                    "type": "bar",
                    "data": [85, 92, 78, 95],
                    "itemStyle": {"color": "#e74c3c"}
                }
            ]
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