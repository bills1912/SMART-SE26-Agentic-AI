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
        """Comprehensive policy analysis using AI"""
        try:
            # Initialize AI chat
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=self._get_policy_analyst_prompt()
            ).with_model("openai", "gpt-4o-mini")

            # Prepare context from scraped data
            context = self._prepare_data_context(scraped_data) if scraped_data else ""
            
            # Create analysis prompt
            analysis_prompt = f"""
            Analyze the following policy question and provide comprehensive insights:

            USER QUESTION: {user_message}

            AVAILABLE DATA CONTEXT:
            {context}

            Please provide your response in the following JSON structure:
            {{
                "main_response": "Your main analysis response",
                "insights": ["insight 1", "insight 2", "insight 3"],
                "policy_recommendations": [
                    {{
                        "title": "Recommendation Title",
                        "description": "Description",
                        "priority": "high|medium|low",
                        "category": "economic|social|environmental|healthcare|education|security|technology",
                        "impact": "Expected impact description",
                        "implementation_steps": ["step 1", "step 2", "step 3"]
                    }}
                ],
                "visualizations": [
                    {{
                        "type": "chart|graph|map|table",
                        "title": "Visualization Title",
                        "data_type": "economic|social|environmental|comparative",
                        "description": "What this visualization shows"
                    }}
                ]
            }}
            """

            # Get AI response
            ai_message = UserMessage(text=analysis_prompt)
            response = await chat.send_message(ai_message)
            
            # Parse AI response
            parsed_response = self._parse_ai_response(response)
            
            # Generate visualizations
            visualizations = await self._generate_visualizations(
                parsed_response.get('visualizations', []),
                user_message
            )
            
            # Create policy recommendations
            recommendations = self._create_policy_recommendations(
                parsed_response.get('policy_recommendations', [])
            )
            
            return {
                'message': parsed_response.get('main_response', response),
                'insights': parsed_response.get('insights', []),
                'policies': recommendations,
                'visualizations': visualizations,
                'supporting_data_count': len(scraped_data) if scraped_data else 0
            }
            
        except Exception as e:
            logger.error(f"Error in policy analysis: {e}")
            return {
                'message': f"I apologize, but I encountered an error while analyzing your policy question. However, I can still provide some general insights based on policy analysis principles.",
                'insights': [
                    "Policy analysis requires comprehensive data from multiple sources",
                    "Effective policies should consider economic, social, and environmental impacts",
                    "Stakeholder engagement is crucial for successful policy implementation"
                ],
                'policies': [],
                'visualizations': [],
                'supporting_data_count': 0
            }

    def _get_policy_analyst_prompt(self) -> str:
        """System prompt for policy analysis AI"""
        return """
        You are an expert policy analyst with deep knowledge of:
        - Economic policy and its impacts on growth, employment, and inflation
        - Social policy including healthcare, education, and welfare systems
        - Environmental policy and sustainability initiatives
        - Comparative policy analysis across different regions and time periods
        - Policy implementation strategies and stakeholder analysis
        
        Your role is to:
        1. Analyze policy scenarios with supporting data
        2. Generate actionable insights based on evidence
        3. Provide practical policy recommendations
        4. Suggest relevant data visualizations
        5. Consider multiple perspectives and potential outcomes
        
        Always provide evidence-based analysis and acknowledge uncertainties when data is limited.
        Focus on practical, implementable solutions.
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