from typing import Dict, Any, List
from models import VisualizationConfig
from datetime import datetime
import logging
import uuid # Tambahkan library UUID untuk ID yang benar-benar unik

logger = logging.getLogger(__name__)

# Color palettes for visualizations
COLORS = {
    'primary': ['#e74c3c', '#ff6b35', '#ff8c42', '#ffad73', '#ffd4a3'],
    'gradient': [
        {'offset': 0, 'color': '#e74c3c'},
        {'offset': 1, 'color': '#ff8c42'}
    ],
    'sectors': [
        '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
        '#1abc9c', '#e67e22', '#34495e', '#16a085', '#c0392b',
        '#2980b9', '#27ae60', '#d35400', '#8e44ad', '#17a2b8',
        '#6c757d', '#fd7e14', '#20c997', '#6f42c1', '#dc3545', '#6610f2'
    ]
}

class VisualizationAgent:
    """Agent untuk generate visualisasi data - menghasilkan MULTIPLE visualisasi"""
    
    def __init__(self):
        pass
    
    def _generate_unique_id(self, prefix: str) -> str:
        """Helper untuk generate ID unik agar React me-remount komponen"""
        # Menggunakan UUID hex agar dijamin unik dan tidak bocor state antar chat
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def create_visualizations(
        self, 
        analysis: Dict[str, Any], 
        aggregated_data: Dict[str, Any]
    ) -> List[VisualizationConfig]:
        """Generate MULTIPLE visualizations based on analysis type"""
        
        # Pastikan list baru setiap kali fungsi dipanggil (stateless)
        visualizations = []
        data_type = aggregated_data.get('type', 'unknown')
        
        try:
            if data_type == 'overview':
                visualizations = self._create_overview_viz(analysis, aggregated_data)
            elif data_type == 'ranking':
                visualizations = self._create_ranking_viz(analysis, aggregated_data)
            elif data_type == 'comparison':
                visualizations = self._create_comparison_viz(analysis, aggregated_data)
            elif data_type == 'distribution':
                visualizations = self._create_distribution_viz(analysis, aggregated_data)
            elif data_type == 'province_detail':
                visualizations = self._create_province_detail_viz(analysis, aggregated_data)
            elif data_type == 'sector_analysis':
                visualizations = self._create_sector_analysis_viz(analysis, aggregated_data)
            
            logger.info(f"Created {len(visualizations)} visualizations for type: {data_type}")
        except Exception as e:
            logger.error(f"Error creating visualizations: {e}", exc_info=True)
        
        return visualizations
    
    def _create_overview_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Create comprehensive overview visualizations - 3-4 charts"""
        visualizations = []
        
        # 1. Top 10 Provinces Bar Chart
        top_provinces = analysis.get('top_provinces', [])
        if top_provinces:
            provinces = [p['provinsi'] for p in top_provinces]
            values = [p['total'] for p in top_provinces]
            
            viz1 = VisualizationConfig(
                id=self._generate_unique_id("overview_provinces"),
                type="chart",
                title="Top 10 Provinsi dengan Jumlah Usaha Terbanyak",
                config={
                    "title": {"text": "Top 10 Provinsi dengan Jumlah Usaha Terbanyak", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
                    "xAxis": {"type": "category", "data": provinces, "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 10}},
                    "yAxis": {"type": "value", "axisLabel": {"color": "#666"}},
                    "series": [{"name": "Jumlah Usaha", "type": "bar", "data": values, "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1, "colorStops": COLORS['gradient']}}, "label": {"show": True, "position": "top", "fontSize": 9}}]
                },
                data={"source": "Sensus Ekonomi 2016", "type": "province_ranking"}
            )
            visualizations.append(viz1)
        
        # 2. Sector Distribution Pie Chart
        top_sectors = analysis.get('top_sectors', [])
        if top_sectors:
            pie_data = [{"value": s['total'], "name": s['short_name'], "itemStyle": {"color": COLORS['sectors'][i % len(COLORS['sectors'])]}} for i, s in enumerate(top_sectors[:8])]
            all_sectors = analysis.get('all_sectors', [])
            if len(all_sectors) > 8:
                other_total = sum(s['total'] for s in all_sectors[8:])
                pie_data.append({"value": other_total, "name": "Sektor Lainnya", "itemStyle": {"color": "#95a5a6"}})
            
            viz2 = VisualizationConfig(
                id=self._generate_unique_id("overview_sectors"),
                type="chart",
                title="Distribusi Usaha per Sektor Ekonomi",
                config={
                    "title": {"text": "Distribusi Usaha per Sektor Ekonomi", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
                    "legend": {"orient": "vertical", "left": "left", "top": "middle", "textStyle": {"fontSize": 10}},
                    "series": [{"name": "Jumlah Usaha", "type": "pie", "radius": ["35%", "65%"], "center": ["60%", "50%"], "label": {"show": True, "formatter": "{d}%", "fontSize": 10}, "data": pie_data}]
                },
                data={"source": "Sensus Ekonomi 2016", "type": "sector_distribution"}
            )
            visualizations.append(viz2)
        
        # 3. Horizontal Bar Chart for All Provinces
        all_provinces = analysis.get('all_provinces', [])
        if len(all_provinces) > 10:
            provinces = [p['provinsi'] for p in all_provinces[:20]]
            values = [p['total'] for p in all_provinces[:20]]
            
            viz3 = VisualizationConfig(
                id=self._generate_unique_id("overview_all_provinces"),
                type="chart",
                title="Perbandingan Jumlah Usaha Antar Provinsi (Top 20)",
                config={
                    "title": {"text": "Perbandingan Jumlah Usaha Antar Provinsi (Top 20)", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                    "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                    "grid": {"left": "20%", "right": "10%", "bottom": "5%", "containLabel": True},
                    "xAxis": {"type": "value"},
                    "yAxis": {"type": "category", "data": list(reversed(provinces)), "axisLabel": {"fontSize": 10}},
                    "series": [{"name": "Jumlah Usaha", "type": "bar", "data": list(reversed(values)), "itemStyle": {"color": "#3498db"}, "label": {"show": True, "position": "right", "fontSize": 9}}]
                },
                data={"source": "Sensus Ekonomi 2016", "type": "province_comparison"}
            )
            visualizations.append(viz3)
        
        return visualizations
    
    def _create_ranking_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi ranking provinsi - 2-3 charts"""
        visualizations = []
        ranked_data = data.get('data', [])[:10]
        
        provinces = [item.get('provinsi', '') for item in ranked_data]
        values = [item.get('filtered_total', item.get('total', 0)) for item in ranked_data]
        
        # 1. Vertical Bar Chart
        viz1 = VisualizationConfig(
            id=self._generate_unique_id("ranking_bar"),
            type="chart",
            title="Top 10 Provinsi Berdasarkan Jumlah Usaha",
            config={
                "title": {"text": "Top 10 Provinsi Berdasarkan Jumlah Usaha", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "xAxis": {"type": "category", "data": provinces, "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 11}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#666"}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": values, "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1, "colorStops": COLORS['gradient']}}, "label": {"show": True, "position": "top", "fontSize": 10}}]
            },
            data={"source": "Sensus Ekonomi 2016", "provinces": provinces}
        )
        visualizations.append(viz1)
        
        # 2. Horizontal Bar
        viz2 = VisualizationConfig(
            id=self._generate_unique_id("ranking_hbar"),
            type="chart",
            title="Ranking Provinsi (Horizontal)",
            config={
                "title": {"text": "Ranking Provinsi Berdasarkan Jumlah Usaha", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "20%", "right": "10%", "bottom": "5%", "containLabel": True},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": list(reversed(provinces)), "axisLabel": {"fontSize": 11}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": list(reversed(values)), "itemStyle": {"color": "#3498db"}, "label": {"show": True, "position": "right", "fontSize": 10}}]
            },
            data={"source": "Sensus Ekonomi 2016"}
        )
        visualizations.append(viz2)
        
        # 3. Pie chart showing concentration
        if len(ranked_data) >= 3:
            top3_total = sum(values[:3])
            total_all = analysis.get('total_usaha', sum(values))
            other_total = total_all - top3_total if total_all > top3_total else 0
            
            pie_data = [{"value": values[i], "name": provinces[i], "itemStyle": {"color": COLORS['sectors'][i]}} for i in range(min(3, len(provinces)))]
            if other_total > 0:
                pie_data.append({"value": other_total, "name": "Provinsi Lainnya", "itemStyle": {"color": "#95a5a6"}})
            
            viz3 = VisualizationConfig(
                id=self._generate_unique_id("ranking_pie"),
                type="chart",
                title="Konsentrasi Usaha Top 3 Provinsi",
                config={
                    "title": {"text": "Konsentrasi Usaha: Top 3 vs Lainnya", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                    "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
                    "legend": {"orient": "vertical", "left": "left", "top": "middle"},
                    "series": [{"name": "Jumlah Usaha", "type": "pie", "radius": ["40%", "70%"], "center": ["60%", "50%"], "label": {"show": True, "formatter": "{d}%"}, "data": pie_data}]
                },
                data={"source": "Sensus Ekonomi 2016"}
            )
            visualizations.append(viz3)
        
        return visualizations
    
    def _create_comparison_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi perbandingan provinsi - 2 charts"""
        visualizations = []
        comparison_data = data.get('data', [])
        
        provinces = [item.get('provinsi', '') for item in comparison_data]
        values = [item.get('total', 0) for item in comparison_data]
        
        # 1. Bar Chart
        viz1 = VisualizationConfig(
            id=self._generate_unique_id("comparison_bar"),
            type="chart",
            title="Perbandingan Jumlah Usaha Antar Provinsi",
            config={
                "title": {"text": "Perbandingan Jumlah Usaha Antar Provinsi", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "xAxis": {"type": "category", "data": provinces, "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 10}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#666"}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": [{"value": v, "itemStyle": {"color": COLORS['sectors'][i % len(COLORS['sectors'])]}} for i, v in enumerate(values)], "label": {"show": True, "position": "top", "fontSize": 10}}]
            },
            data={"source": "Sensus Ekonomi 2016"}
        )
        visualizations.append(viz1)
        
        # 2. Line Chart with Area
        viz2 = VisualizationConfig(
            id=self._generate_unique_id("comparison_line"),
            type="chart",
            title="Tren Perbandingan Antar Provinsi",
            config={
                "title": {"text": "Perbandingan Jumlah Usaha", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis"},
                "xAxis": {"type": "category", "data": provinces, "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 10}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#666"}},
                "series": [{"name": "Jumlah Usaha", "type": "line", "data": values, "smooth": True, "itemStyle": {"color": "#e74c3c"}, "areaStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1, "colorStops": [{"offset": 0, "color": "rgba(231, 76, 60, 0.3)"}, {"offset": 1, "color": "rgba(231, 76, 60, 0.05)"}]}}, "label": {"show": True, "position": "top", "fontSize": 9}}]
            },
            data={"source": "Sensus Ekonomi 2016"}
        )
        visualizations.append(viz2)
        
        return visualizations
    
    def _create_distribution_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi distribusi sektor - 2-3 charts"""
        visualizations = []
        distribution_detail = analysis.get('distribution_detail', [])
        
        if not distribution_detail:
            return visualizations
        
        # 1. Pie chart
        pie_data = [{"value": item['total'], "name": item['short_name'], "itemStyle": {"color": COLORS['sectors'][i % len(COLORS['sectors'])]}} for i, item in enumerate(distribution_detail[:10])]
        if len(distribution_detail) > 10:
            other_total = sum(item['total'] for item in distribution_detail[10:])
            pie_data.append({"value": other_total, "name": "Lainnya", "itemStyle": {"color": "#95a5a6"}})
        
        viz1 = VisualizationConfig(
            id=self._generate_unique_id("distribution_pie"),
            type="chart",
            title="Distribusi Usaha Per Sektor",
            config={
                "title": {"text": "Distribusi Usaha Per Sektor", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 18, "fontWeight": "bold"}},
                "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
                "legend": {"orient": "vertical", "left": "left", "top": "middle", "textStyle": {"fontSize": 10}},
                "series": [{"name": "Jumlah Usaha", "type": "pie", "radius": ["40%", "70%"], "avoidLabelOverlap": False, "label": {"show": True, "formatter": "{d}%", "fontSize": 11}, "emphasis": {"label": {"show": True, "fontSize": 14, "fontWeight": "bold"}}, "data": pie_data}]
            },
            data={"source": "Sensus Ekonomi 2016"}
        )
        visualizations.append(viz1)
        
        # 2. Horizontal Bar Chart
        sectors = [item['short_name'] for item in distribution_detail[:15]]
        values = [item['total'] for item in distribution_detail[:15]]
        
        viz2 = VisualizationConfig(
            id=self._generate_unique_id("distribution_bar"),
            type="chart",
            title="Jumlah Usaha per Sektor (Bar Chart)",
            config={
                "title": {"text": "Jumlah Usaha per Sektor", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "25%", "right": "10%", "bottom": "5%", "containLabel": True},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": list(reversed(sectors)), "axisLabel": {"fontSize": 10}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": list(reversed(values)), "itemStyle": {"color": "#3498db"}, "label": {"show": True, "position": "right", "fontSize": 9}}]
            },
            data={"source": "Sensus Ekonomi 2016"}
        )
        visualizations.append(viz2)
        
        return visualizations
    
    def _create_province_detail_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi detail provinsi - 2 charts"""
        visualizations = []
        
        provinsi = analysis.get('provinsi', data.get('provinsi', 'Unknown'))
        all_sectors = analysis.get('all_sectors', [])
        
        if not all_sectors:
            return visualizations
        
        # 1. Pie chart
        pie_data = [{"value": s['total'], "name": s.get('short_name', s.get('name', '')[:15]), "itemStyle": {"color": COLORS['sectors'][i % len(COLORS['sectors'])]}} for i, s in enumerate(all_sectors[:10]) if s['total'] > 0]
        if len(all_sectors) > 10:
            other_total = sum(s['total'] for s in all_sectors[10:] if s['total'] > 0)
            if other_total > 0:
                pie_data.append({"value": other_total, "name": "Lainnya", "itemStyle": {"color": "#95a5a6"}})
        
        viz1 = VisualizationConfig(
            id=self._generate_unique_id("province_pie"),
            type="chart",
            title=f"Distribusi Sektor di {provinsi}",
            config={
                "title": {"text": f"Distribusi Sektor di {provinsi}", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
                "legend": {"orient": "vertical", "left": "left", "top": "middle", "textStyle": {"fontSize": 10}},
                "series": [{"name": "Jumlah Usaha", "type": "pie", "radius": ["35%", "65%"], "center": ["60%", "50%"], "label": {"show": True, "formatter": "{d}%", "fontSize": 10}, "data": pie_data}]
            },
            data={"source": "Sensus Ekonomi 2016", "provinsi": provinsi}
        )
        visualizations.append(viz1)
        
        # 2. Horizontal Bar chart
        sectors = [s.get('short_name', s.get('name', '')[:15]) for s in all_sectors if s['total'] > 0]
        values = [s['total'] for s in all_sectors if s['total'] > 0]
        
        viz2 = VisualizationConfig(
            id=self._generate_unique_id("province_bar"),
            type="chart",
            title=f"Jumlah Usaha per Sektor di {provinsi}",
            config={
                "title": {"text": f"Jumlah Usaha per Sektor di {provinsi}", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "25%", "right": "10%", "bottom": "5%", "containLabel": True},
                "xAxis": {"type": "value"},
                "yAxis": {"type": "category", "data": list(reversed(sectors)), "axisLabel": {"fontSize": 9}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": list(reversed(values)), "itemStyle": {"color": "#3498db"}, "label": {"show": True, "position": "right", "fontSize": 9}}]
            },
            data={"source": "Sensus Ekonomi 2016", "provinsi": provinsi}
        )
        visualizations.append(viz2)
        
        return visualizations
    
    def _create_sector_analysis_viz(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> List[VisualizationConfig]:
        """Visualisasi analisis sektor - 2 charts"""
        visualizations = []
        
        all_provinces = analysis.get('all_provinces', [])
        sector_names = analysis.get('sector_names', [])
        
        if not all_provinces:
            return visualizations
        
        sector_title = ', '.join(sector_names[:2]) if sector_names else 'Sektor'
        
        # 1. Bar chart
        provinces = [p['provinsi'] for p in all_provinces[:15]]
        values = [p['total'] for p in all_provinces[:15]]
        
        viz1 = VisualizationConfig(
            id=self._generate_unique_id("sector_bar"),
            type="chart",
            title=f"Distribusi {sector_title} per Provinsi",
            config={
                "title": {"text": f"Distribusi Sektor {sector_title} per Provinsi", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
                "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
                "xAxis": {"type": "category", "data": provinces, "axisLabel": {"rotate": 45, "color": "#666", "fontSize": 10}},
                "yAxis": {"type": "value", "axisLabel": {"color": "#666"}},
                "series": [{"name": "Jumlah Usaha", "type": "bar", "data": values, "itemStyle": {"color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1, "colorStops": COLORS['gradient']}}, "label": {"show": True, "position": "top", "fontSize": 9}}]
            },
            data={"source": "Sensus Ekonomi 2016", "sectors": sector_names}
        )
        visualizations.append(viz1)
        
        # 2. Pie chart
        pie_data = [{"value": p['total'], "name": p['provinsi'], "itemStyle": {"color": COLORS['sectors'][i % len(COLORS['sectors'])]}} for i, p in enumerate(all_provinces[:8])]
        if len(all_provinces) > 8:
            other_total = sum(p['total'] for p in all_provinces[8:])
            pie_data.append({"value": other_total, "name": "Provinsi Lainnya", "itemStyle": {"color": "#95a5a6"}})
        
        viz2 = VisualizationConfig(
            id=self._generate_unique_id("sector_pie"),
            type="chart",
            title=f"Proporsi {sector_title} Antar Provinsi",
            config={
                "title": {"text": f"Proporsi Sektor {sector_title} Antar Provinsi", "left": "center", "textStyle": {"color": "#e74c3c", "fontSize": 16, "fontWeight": "bold"}},
                "tooltip": {"trigger": "item", "formatter": "{b}: {c:,} ({d}%)"},
                "legend": {"orient": "vertical", "left": "left", "top": "middle", "textStyle": {"fontSize": 10}},
                "series": [{"name": "Jumlah Usaha", "type": "pie", "radius": ["35%", "65%"], "center": ["60%", "50%"], "label": {"show": True, "formatter": "{d}%", "fontSize": 10}, "data": pie_data}]
            },
            data={"source": "Sensus Ekonomi 2016", "sectors": sector_names}
        )
        visualizations.append(viz2)
        
        return visualizations