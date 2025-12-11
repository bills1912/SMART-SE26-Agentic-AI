import google.generativeai as genai
import os
import json
from typing import Dict, Any, List
from models import PolicyRecommendation, PolicyCategory
import logging

logger = logging.getLogger(__name__)

class InsightGenerationAgent:
    """Agent untuk generate insights dan policy recommendations"""
    
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.model_name = "gemini-2.0-flash-exp"
    
    async def generate_insights(
        self, 
        analysis: Dict[str, Any], 
        aggregated_data: Dict[str, Any],
        user_query: str,
        language: str = "Indonesian"
    ) -> Dict[str, Any]:
        """Generate insights dari hasil analisis"""
        
        if not self.api_key:
            return self._fallback_insights(analysis, aggregated_data)
        
        # Prepare context for Gemini
        context = self._prepare_context(analysis, aggregated_data, user_query)
        
        system_prompt = f"""Anda adalah ahli analisis ekonomi dan kebijakan publik yang fokus pada data Sensus Ekonomi Indonesia.
        
Tugas Anda:
1. Berikan 3-5 insight mendalam berdasarkan data yang diberikan
2. Generate 2-3 rekomendasi kebijakan yang actionable
3. Semua jawaban harus dalam bahasa {language}
4. Gunakan data statistik yang konkret
5. Fokus pada implikasi ekonomi dan sosial

Format output JSON:
{{
    "insights": ["insight 1", "insight 2", ...],
    "policy_recommendations": [
        {{
            "title": "Judul Rekomendasi",
            "description": "Deskripsi detail",
            "priority": "high|medium|low",
            "category": "economic|social|infrastructure",
            "impact": "Expected impact",
            "implementation_steps": ["step 1", "step 2", ...]
        }}
    ]
}}"""
        
        try:
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            response = await model.generate_content_async(context)
            result = json.loads(response.text)
            
            # Convert to PolicyRecommendation objects
            recommendations = []
            for rec in result.get('policy_recommendations', []):
                try:
                    category_str = rec.get('category', 'economic').lower()
                    category_map = {
                        'economic': PolicyCategory.ECONOMIC,
                        'social': PolicyCategory.SOCIAL,
                        'infrastructure': PolicyCategory.TECHNOLOGY,
                        'environmental': PolicyCategory.ENVIRONMENTAL,
                        'healthcare': PolicyCategory.HEALTHCARE,
                        'education': PolicyCategory.EDUCATION
                    }
                    category = category_map.get(category_str, PolicyCategory.ECONOMIC)
                    
                    recommendations.append(PolicyRecommendation(
                        title=rec.get('title', ''),
                        description=rec.get('description', ''),
                        priority=rec.get('priority', 'medium'),
                        category=category,
                        impact=rec.get('impact', ''),
                        implementation_steps=rec.get('implementation_steps', [])
                    ))
                except Exception as e:
                    logger.error(f"Error creating recommendation: {e}")
            
            return {
                'insights': result.get('insights', []),
                'policies': recommendations
            }
            
        except Exception as e:
            logger.error(f"Error generating insights with Gemini: {e}")
            return self._fallback_insights(analysis, aggregated_data)
    
    def _prepare_context(self, analysis: Dict[str, Any], data: Dict[str, Any], query: str) -> str:
        """Prepare context for Gemini"""
        
        data_type = data.get('type', 'unknown')
        
        context = f"User Query: {query}\n\n"
        context += f"Data Type: {data_type}\n\n"
        context += "Analysis Results:\n"
        context += json.dumps(analysis, indent=2, ensure_ascii=False)
        context += "\n\nBerikan insights dan rekomendasi kebijakan berdasarkan analisis di atas."
        
        return context
    
    def _fallback_insights(self, analysis: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback insights jika Gemini tidak tersedia"""
        
        data_type = data.get('type', 'unknown')
        insights = []
        
        if data_type == 'ranking':
            top_provinces = analysis.get('top_provinces', [])
            if top_provinces:
                top = top_provinces[0]
                insights.append(
                    f"{top['provinsi']} menempati posisi teratas dengan {top['total']:,} usaha "
                    f"atau {top['percentage']:.1f}% dari total."
                )
                
                concentration = analysis.get('concentration', 0)
                insights.append(
                    f"3 provinsi teratas menguasai {concentration:.1f}% dari total usaha, "
                    f"menunjukkan konsentrasi ekonomi yang cukup tinggi."
                )
        
        elif data_type == 'distribution':
            top_sector = analysis.get('top_sector')
            if top_sector:
                code, info = top_sector
                insights.append(
                    f"Sektor {info['name']} mendominasi dengan {info['total']:,} usaha."
                )
        
        # Default recommendation
        default_policy = PolicyRecommendation(
            title="Pemerataan Pembangunan Ekonomi",
            description="Mendorong pemerataan distribusi usaha di seluruh provinsi melalui insentif fiskal dan kemudahan perizinan.",
            priority="high",
            category=PolicyCategory.ECONOMIC,
            impact="Meningkatkan pertumbuhan ekonomi inklusif dan mengurangi kesenjangan antar wilayah.",
            implementation_steps=[
                "Identifikasi provinsi dengan jumlah usaha rendah",
                "Buat program insentif pajak untuk daerah tertinggal",
                "Sederhanakan prosedur perizinan usaha",
                "Tingkatkan infrastruktur pendukung"
            ]
        )
        
        return {
            'insights': insights if insights else ["Data menunjukkan variasi signifikan dalam distribusi usaha."],
            'policies': [default_policy]
        }