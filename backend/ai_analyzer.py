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
            # Check if we have actual data
            if not scraped_data or len(scraped_data) == 0:
                return await self._handle_no_data_scenario(user_message)
            
            # Initialize AI chat
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=self._get_data_driven_analyst_prompt()
            ).with_model("openai", "gpt-4o-mini")

            # Prepare detailed context from real scraped data
            context = self._prepare_detailed_data_context(scraped_data)
            
            # Create strict data-driven analysis prompt
            analysis_prompt = f"""
            STRICT DATA-DRIVEN ANALYSIS REQUIRED:

            USER QUESTION: {user_message}

            AVAILABLE REAL DATA (ONLY USE THIS DATA):
            {context}

            REQUIREMENTS:
            - Only analyze based on the provided real data above
            - If specific data is not available, explicitly state data limitations
            - Generate visualizations ONLY using actual data points from the context
            - All insights must reference specific data from the context
            - Do not create hypothetical scenarios or data
            
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

            # Get AI response
            ai_message = UserMessage(text=analysis_prompt)
            response = await chat.send_message(ai_message)
            
            # Parse AI response
            parsed_response = self._parse_ai_response(response)
            
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
            
        except Exception as e:
            logger.error(f"Error in policy analysis: {e}")
            return await self._handle_error_scenario(user_message, str(e))

    async def _handle_no_data_scenario(self, user_message: str) -> Dict[str, Any]:
        """Handle cases where no real data is available"""
        return {
            'message': f"""I cannot provide a comprehensive analysis for your question about "{user_message}" because no relevant real-time data is currently available in the system. 

To provide accurate policy analysis, I need access to current economic indicators, policy outcome data, and relevant research findings. 

Would you like me to:
1. Suggest what specific data sources would be helpful for this analysis
2. Provide general policy analysis principles that apply to this area
3. Wait while the system attempts to gather more relevant data""",
            'data_availability': 'No relevant data currently available',
            'insights': [
                'Policy analysis requires access to current and historical data',
                'Effective analysis needs multiple data sources for validation',
                'Data availability directly impacts analysis quality and reliability'
            ],
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

    def _get_data_driven_analyst_prompt(self) -> str:
        """System prompt for strictly data-driven policy analysis AI"""
        return """
        You are a DATA-DRIVEN policy analyst who ONLY analyzes based on provided real data.
        
        STRICT REQUIREMENTS:
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
        
        You are honest about limitations rather than providing speculative analysis.
        """

    def _prepare_data_context(self, scraped_data: List[ScrapedData]) -> str:
        """Prepare scraped data context for AI analysis"""
        if not scraped_data:
            return "No recent data available for analysis."
        
        context_parts = []
        
        # Group by category
        by_category = {}
        for data in scraped_data[:50]:  # Limit to prevent token overflow
            category = data.category or 'general'
            if category not in by_category:
                by_category[category] = []
            by_category[category].append(data)
        
        # Create context summary
        for category, items in by_category.items():
            context_parts.append(f"\n{category.upper()} DATA:")
            for item in items[:5]:  # Limit items per category
                context_parts.append(f"- {item.title}: {item.content[:200]}...")
        
        return "\n".join(context_parts)

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