from typing import Dict, Any, List
from models import VisualizationConfig
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class VisualizationAgent:
    """Agent untuk generate visualisasi data"""
    
    def __init__(self):
        pass
    
    def create_visualizations(
        self, 
        analysis: Dict[str, Any], 
        aggregated_data: Dict[str, Any]
    ) -> List[VisualizationConfig]:
        """Generate visualizations based on analysis"""
        
        data_type = aggregated_data.get('type', 'unknown')
        
        if data_type == 'ranking':
            return self._create_ranking_viz(analysis, aggregated_data)
        elif data_type == 'comparison':
            return self._create_comparison_viz(analysis, aggregated_data)
        elif data_type == 'distribution':
            return self._create_distribution_viz(analysis, aggregated_data)
        
        return []
    
    def _create_ranking_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi ranking provinsi"""
        ranked_data = data.get('data', [])[:10]  # Top 10
        
        provinces = [item.get('provinsi', '') for item in ranked_data]
        values = [item.get('filtered_total', item.get('total', 0)) for item in ranked_data]
        
        config = {
            "title": {
                "text": "Top 10 Provinsi Berdasarkan Jumlah Usaha",
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
            "xAxis": {
                "type": "category",
                "data": provinces,
                "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 11}
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {"color": "#666", "formatter": "{value}"}
            },
            "series": [{
                "name": "Jumlah Usaha",
                "type": "bar",
                "data": values,
                "itemStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "#e74c3c"},
                            {"offset": 1, "color": "#ff8c42"}
                        ]
                    }
                },
                "label": {
                    "show": True,
                    "position": "top",
                    "formatter": "{c}",
                    "fontSize": 10
                }
            }]
        }
        
        return [VisualizationConfig(
            id=f"ranking_{int(datetime.utcnow().timestamp())}",
            type="chart",
            title="Ranking Provinsi Berdasarkan Jumlah Usaha",
            config=config,
            data={"source": "Sensus Ekonomi 2016", "provinces": provinces}
        )]
    
    def _create_comparison_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi perbandingan provinsi"""
        comparison_data = data.get('data', [])
        
        provinces = [item.get('provinsi', '') for item in comparison_data]
        values = [item.get('total', 0) for item in comparison_data]
        
        config = {
            "title": {
                "text": "Perbandingan Jumlah Usaha Antar Provinsi",
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "axis"},
            "xAxis": {
                "type": "category",
                "data": provinces,
                "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 10}
            },
            "yAxis": {
                "type": "value",
                "axisLabel": {"color": "#666"}
            },
            "series": [{
                "name": "Jumlah Usaha",
                "type": "line",
                "data": values,
                "smooth": True,
                "itemStyle": {"color": "#e74c3c"},
                "areaStyle": {
                    "color": {
                        "type": "linear",
                        "x": 0, "y": 0, "x2": 0, "y2": 1,
                        "colorStops": [
                            {"offset": 0, "color": "rgba(231, 76, 60, 0.3)"},
                            {"offset": 1, "color": "rgba(231, 76, 60, 0.05)"}
                        ]
                    }
                }
            }]
        }
        
        return [VisualizationConfig(
            id=f"comparison_{int(datetime.utcnow().timestamp())}",
            type="chart",
            title="Perbandingan Jumlah Usaha",
            config=config,
            data={"source": "Sensus Ekonomi 2016"}
        )]
    
    def _create_distribution_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi distribusi sektor"""
        distribution_detail = analysis.get('distribution_detail', [])
        
        # Pie chart untuk distribusi
        pie_data = [
            {
                "value": item['total'],
                "name": f"{item['sector_name']} ({item['percentage']:.1f}%)"
            }
            for item in distribution_detail[:10]  # Top 10 sectors
        ]
        
        config = {
            "title": {
                "text": "Distribusi Usaha Per Sektor",
                "left": "center",
                "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}
            },
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {
                "orient": "vertical",
                "left": "left",
                "top": "middle",
                "textStyle": {"fontSize": 10}
            },
            "series": [{
                "name": "Jumlah Usaha",
                "type": "pie",
                "radius": ["40%", "70%"],
                "avoidLabelOverlap": False,
                "label": {
                    "show": True,
                    "formatter": "{d}%",
                    "fontSize": 11
                },
                "emphasis": {
                    "label": {"show": True, "fontSize": 14, "fontWeight": "bold"}
                },
                "data": pie_data
            }]
        }
        
        return [VisualizationConfig(
            id=f"distribution_{int(datetime.utcnow().timestamp())}",
            type="chart",
            title="Distribusi Usaha Per Sektor",
            config=config,
            data={"source": "Sensus Ekonomi 2016"}
        )]