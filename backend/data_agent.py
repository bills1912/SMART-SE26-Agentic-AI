from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Optional
import logging
from models import QueryIntent
import re

logger = logging.getLogger(__name__)

# Mapping KBLI ke nama sektor (dari KBLI 2020)
KBLI_MAPPING = {
    'A': 'Pertanian, Kehutanan, dan Perikanan',
    'B': 'Pertambangan dan Penggalian',
    'C': 'Industri Pengolahan',
    'D': 'Pengadaan Listrik, Gas, Uap/Air Panas dan Udara Dingin',
    'E': 'Pengelolaan Air, Pengelolaan Air Limbah, Pengelolaan dan Daur Ulang Sampah',
    'F': 'Konstruksi',
    'G': 'Perdagangan Besar dan Eceran; Reparasi dan Perawatan Mobil dan Sepeda Motor',
    'H': 'Transportasi dan Pergudangan',
    'I': 'Penyediaan Akomodasi dan Penyediaan Makan Minum',
    'J': 'Informasi dan Komunikasi',
    'K': 'Jasa Keuangan dan Asuransi',
    'L': 'Real Estat',
    'M': 'Jasa Profesional, Ilmiah dan Teknis',
    'N': 'Jasa Persewaan, Ketenagakerjaan, Agen Perjalanan dan Penunjang Usaha Lainnya',
    'O': 'Administrasi Pemerintahan, Pertahanan dan Jaminan Sosial Wajib',
    'P': 'Jasa Pendidikan',
    'Q': 'Jasa Kesehatan dan Kegiatan Sosial',
    'R': 'Kesenian, Hiburan dan Rekreasi',
    'S': 'Kegiatan Jasa Lainnya',
    'T': 'Jasa Perorangan yang Melayani Rumah Tangga',
    'U': 'Kegiatan Badan Internasional dan Badan Ekstra Internasional Lainnya'
}

class DataRetrievalAgent:
    """Agent untuk mengambil dan memproses data dari MongoDB"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.initial_data
    
    def _get_sector_value(self, doc: Dict[str, Any], sector_code: str) -> int:
        """
        Helper function to safely get sector value from nested object structure
        
        Structure: doc[sector_code] = {"Nama Sektor": value}
        Example: doc["C"] = {"Industri Pengolahan": 86987}
        """
        try:
            sector_obj = doc.get(sector_code)
            if isinstance(sector_obj, dict):
                # Get the first (and should be only) value in the dict
                return list(sector_obj.values())[0] if sector_obj else 0
            elif isinstance(sector_obj, (int, float)):
                # Fallback jika format lama (langsung integer)
                return int(sector_obj)
            else:
                return 0
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.debug(f"Error getting sector {sector_code} value: {e}")
            return 0
    
    async def understand_query(self, query: str) -> QueryIntent:
        """Enhanced query understanding with better intent detection"""
        query_lower = query.lower()
        
        intent = QueryIntent(intent_type='distribution')
        
        # Enhanced intent detection
        if any(word in query_lower for word in ['bandingkan', 'compare', 'versus', 'vs', 'perbandingan', 'beda']):
            intent.intent_type = 'comparison'
        elif any(word in query_lower for word in ['ranking', 'urut', 'tertinggi', 'terendah', 'terbanyak', 'terbesar', 'top', 'paling', 'mana yang']):
            intent.intent_type = 'ranking'
        elif any(word in query_lower for word in ['tren', 'trend', 'perkembangan', 'perubahan']):
            intent.intent_type = 'trend'
        elif any(word in query_lower for word in ['distribusi', 'sebaran', 'persebaran', 'komposisi', 'bagaimana', 'proporsi']):
            intent.intent_type = 'distribution'
        
        # ENHANCED: Detect if asking for specific value (e.g., "berapa jumlah")
        if any(word in query_lower for word in ['berapa', 'jumlah', 'total', 'banyak']):
            # If asking about specific province + sector → comparison
            provinces = self._extract_provinces(query)
            sectors = self._extract_sectors(query)
            
            if provinces and len(provinces) == 1 and sectors:
                intent.intent_type = 'comparison'  # Single province analysis
            elif provinces and len(provinces) == 1:
                intent.intent_type = 'comparison'  # Province overview
            elif sectors and not provinces:
                intent.intent_type = 'distribution'  # Sector analysis across all provinces
        
        # Extract entities
        intent.provinces = self._extract_provinces(query)
        intent.sectors = self._extract_sectors(query)
        
        # ENHANCEMENT: If asking "mana yang..." without provinces → ranking
        if 'mana yang' in query_lower and not intent.provinces:
            intent.intent_type = 'ranking'
        
        logger.info(f"Enhanced intent: type={intent.intent_type}, provinces={intent.provinces}, sectors={intent.sectors}")
        
        return intent
    
    def _extract_provinces(self, query: str) -> List[str]:
        """Extract nama provinsi dari query"""
        # Daftar provinsi Indonesia dengan berbagai variasi nama
        provinces_map = {
            'aceh': 'ACEH',
            'sumut': 'SUMATERA UTARA', 
            'sumatera utara': 'SUMATERA UTARA',
            'sumatra utara': 'SUMATERA UTARA',
            'sumbar': 'SUMATERA BARAT', 
            'sumatera barat': 'SUMATERA BARAT',
            'sumatra barat': 'SUMATERA BARAT',
            'riau': 'RIAU', 
            'jambi': 'JAMBI', 
            'sumsel': 'SUMATERA SELATAN',
            'sumatera selatan': 'SUMATERA SELATAN',
            'sumatra selatan': 'SUMATERA SELATAN',
            'bengkulu': 'BENGKULU',
            'lampung': 'LAMPUNG', 
            'babel': 'KEP. BANGKA BELITUNG',
            'bangka belitung': 'KEP. BANGKA BELITUNG',
            'kepri': 'KEPULAUAN RIAU', 
            'kepulauan riau': 'KEPULAUAN RIAU',
            'dki': 'DKI JAKARTA', 
            'jakarta': 'DKI JAKARTA',
            'dki jakarta': 'DKI JAKARTA',
            'jabar': 'JAWA BARAT', 
            'jawa barat': 'JAWA BARAT',
            'jateng': 'JAWA TENGAH', 
            'jawa tengah': 'JAWA TENGAH',
            'yogya': 'DI YOGYAKARTA', 
            'yogyakarta': 'DI YOGYAKARTA',
            'diy': 'DI YOGYAKARTA',
            'jatim': 'JAWA TIMUR', 
            'jawa timur': 'JAWA TIMUR',
            'banten': 'BANTEN', 
            'bali': 'BALI',
            'ntb': 'NUSA TENGGARA BARAT',
            'nusa tenggara barat': 'NUSA TENGGARA BARAT',
            'ntt': 'NUSA TENGGARA TIMUR',
            'nusa tenggara timur': 'NUSA TENGGARA TIMUR',
            'kalbar': 'KALIMANTAN BARAT',
            'kalimantan barat': 'KALIMANTAN BARAT',
            'kalteng': 'KALIMANTAN TENGAH',
            'kalimantan tengah': 'KALIMANTAN TENGAH',
            'kalsel': 'KALIMANTAN SELATAN',
            'kalimantan selatan': 'KALIMANTAN SELATAN',
            'kaltim': 'KALIMANTAN TIMUR',
            'kalimantan timur': 'KALIMANTAN TIMUR',
            'kaltara': 'KALIMANTAN UTARA',
            'kalimantan utara': 'KALIMANTAN UTARA',
            'sulut': 'SULAWESI UTARA',
            'sulawesi utara': 'SULAWESI UTARA',
            'sulteng': 'SULAWESI TENGAH',
            'sulawesi tengah': 'SULAWESI TENGAH',
            'sulsel': 'SULAWESI SELATAN',
            'sulawesi selatan': 'SULAWESI SELATAN',
            'sultra': 'SULAWESI TENGGARA',
            'sulawesi tenggara': 'SULAWESI TENGGARA',
            'gorontalo': 'GORONTALO',
            'sulbar': 'SULAWESI BARAT',
            'sulawesi barat': 'SULAWESI BARAT',
            'maluku': 'MALUKU', 
            'malut': 'MALUKU UTARA',
            'maluku utara': 'MALUKU UTARA',
            'papua': 'PAPUA', 
            'papua barat': 'PAPUA BARAT'
        }
        
        query_lower = query.lower()
        found_provinces = []
        
        # Sort by length descending to match longer names first
        sorted_keys = sorted(provinces_map.keys(), key=len, reverse=True)
        
        for key in sorted_keys:
            if key in query_lower:
                value = provinces_map[key]
                if value not in found_provinces:
                    found_provinces.append(value)
        
        return found_provinces
    
    def _extract_sectors(self, query: str) -> List[str]:
        """Extract sektor KBLI dari query"""
        query_lower = query.lower()
        found_sectors = []
        
        # Map kata kunci ke kode KBLI
        sector_keywords = {
            'pertanian': 'A', 'kehutanan': 'A', 'perikanan': 'A', 'perkebunan': 'A',
            'pertambangan': 'B', 'tambang': 'B', 'galian': 'B', 'penggalian': 'B',
            'industri': 'C', 'manufaktur': 'C', 'pengolahan': 'C', 'pabrik': 'C',
            'listrik': 'D', 'gas': 'D', 'energi': 'D', 'tenaga': 'D',
            'air': 'E', 'limbah': 'E', 'sampah': 'E', 'sanitasi': 'E',
            'konstruksi': 'F', 'bangunan': 'F', 'kontraktor': 'F',
            'perdagangan': 'G', 'retail': 'G', 'eceran': 'G', 'grosir': 'G', 'toko': 'G', 'dagang': 'G',
            'transportasi': 'H', 'logistik': 'H', 'pergudangan': 'H', 'angkutan': 'H',
            'hotel': 'I', 'restoran': 'I', 'akomodasi': 'I', 'kuliner': 'I', 'penginapan': 'I', 'makanan': 'I', 'minum': 'I',
            'informasi': 'J', 'komunikasi': 'J', 'telekomunikasi': 'J', 'it': 'J', 'teknologi informasi': 'J',
            'keuangan': 'K', 'bank': 'K', 'asuransi': 'K', 'finance': 'K',
            'real estat': 'L', 'properti': 'L', 'tanah': 'L',
            'profesional': 'M', 'konsultan': 'M', 'teknis': 'M', 'jasa profesional': 'M',
            'persewaan': 'N', 'tenaga kerja': 'N', 'agen perjalanan': 'N',
            'pemerintah': 'O', 'administrasi': 'O', 'pertahanan': 'O',
            'pendidikan': 'P', 'sekolah': 'P', 'universitas': 'P', 'kampus': 'P',
            'kesehatan': 'Q', 'rumah sakit': 'Q', 'klinik': 'Q', 'medis': 'Q',
            'seni': 'R', 'hiburan': 'R', 'rekreasi': 'R', 'entertainment': 'R',
            'jasa lainnya': 'S', 'salon': 'S', 'laundry': 'S'
        }
        
        for keyword, code in sector_keywords.items():
            if keyword in query_lower and code not in found_sectors:
                found_sectors.append(code)
        
        return found_sectors
    
    async def get_data_by_intent(self, intent: QueryIntent) -> List[Dict[str, Any]]:
        """Mengambil data berdasarkan intent dengan error handling"""
        try:
            query_filter = {}
            
            # Filter by provinces if specified
            if intent.provinces:
                query_filter['provinsi'] = {'$in': intent.provinces}
            
            logger.info(f"MongoDB query filter: {query_filter}")
            
            # Fetch data
            cursor = self.collection.find(query_filter, {'_id': 0})
            data = await cursor.to_list(length=None)
            
            if not data:
                logger.warning(f"No data found for filter: {query_filter}")
                return []
            
            logger.info(f"Fetched {len(data)} documents from MongoDB")
            
            # Filter by sectors if specified
            if intent.sectors:
                filtered_data = []
                for doc in data:
                    # Hitung total untuk sektor yang diminta menggunakan helper function
                    sector_total = sum(
                        self._get_sector_value(doc, sector) 
                        for sector in intent.sectors
                    )
                    
                    if sector_total > 0:
                        filtered_data.append({
                            **doc,
                            'filtered_total': sector_total,
                            'filtered_sectors': intent.sectors
                        })
                
                if not filtered_data:
                    logger.warning(f"No data found for sectors: {intent.sectors}")
                else:
                    logger.info(f"Filtered to {len(filtered_data)} documents with specified sectors")
                
                return filtered_data
            
            return data
        
        except Exception as e:
            logger.error(f"Error fetching data from MongoDB: {e}", exc_info=True)
            return []
    
    async def aggregate_data(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Agregasi data sesuai intent"""
        
        if intent.intent_type == 'ranking':
            return self._aggregate_ranking(data, intent)
        elif intent.intent_type == 'comparison':
            return self._aggregate_comparison(data, intent)
        elif intent.intent_type == 'distribution':
            return self._aggregate_distribution(data, intent)
        elif intent.intent_type == 'trend':
            return self._aggregate_trend(data, intent)
        
        return {'raw_data': data}
    
    def _aggregate_ranking(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Ranking berdasarkan total usaha"""
        if intent.sectors:
            # Ranking berdasarkan sektor tertentu
            ranked = sorted(data, key=lambda x: x.get('filtered_total', 0), reverse=True)
        else:
            # Ranking berdasarkan total semua sektor
            ranked = sorted(data, key=lambda x: x.get('total', 0), reverse=True)
        
        return {
            'type': 'ranking',
            'data': ranked[:10],  # Top 10
            'sectors': intent.sectors if intent.sectors else 'all'
        }
    
    def _aggregate_comparison(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Perbandingan antar provinsi/sektor"""
        comparison_data = []
        
        for doc in data:
            entry = {
                'provinsi': doc.get('provinsi', ''),
                'total': doc.get('filtered_total', doc.get('total', 0))
            }
            
            # Breakdown per sektor jika ada
            if intent.sectors:
                entry['breakdown'] = {
                    sector: self._get_sector_value(doc, sector)
                    for sector in intent.sectors
                }
            
            comparison_data.append(entry)
        
        return {
            'type': 'comparison',
            'data': comparison_data,
            'sectors': intent.sectors if intent.sectors else 'all'
        }
    
    def _aggregate_distribution(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Distribusi usaha per sektor/provinsi"""
        
        if intent.sectors:
            # Distribusi per sektor yang diminta
            distribution = {}
            for sector in intent.sectors:
                total = sum(self._get_sector_value(doc, sector) for doc in data)
                distribution[sector] = {
                    'total': total,
                    'name': KBLI_MAPPING.get(sector, f'Sektor {sector}')
                }
        else:
            # Distribusi semua sektor
            distribution = {}
            for sector_code in KBLI_MAPPING.keys():
                total = sum(self._get_sector_value(doc, sector_code) for doc in data)
                if total > 0:
                    distribution[sector_code] = {
                        'total': total,
                        'name': KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}')
                    }
        
        return {
            'type': 'distribution',
            'data': distribution,
            'provinces': intent.provinces if intent.provinces else 'all'
        }
    
    def _aggregate_trend(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Untuk data trend (saat ini single year, nanti bisa multi-year)"""
        # Saat ini hanya 2016, tapi struktur siap untuk multi-year
        return {
            'type': 'trend',
            'message': 'Data trend memerlukan data multi-tahun. Saat ini hanya tersedia data 2016.',
            'data': data
        }


class AnalysisAgent:
    """Agent untuk melakukan analisis statistik"""
    
    def __init__(self):
        pass
    
    def analyze(self, aggregated_data: Dict[str, Any], intent: QueryIntent) -> Dict[str, Any]:
        """Melakukan analisis statistik"""
        
        data_type = aggregated_data.get('type', 'unknown')
        
        if data_type == 'ranking':
            return self._analyze_ranking(aggregated_data)
        elif data_type == 'comparison':
            return self._analyze_comparison(aggregated_data)
        elif data_type == 'distribution':
            return self._analyze_distribution(aggregated_data)
        
        return {'analysis': 'No analysis available'}
    
    def _analyze_ranking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis ranking"""
        ranked_data = data.get('data', [])
        
        if not ranked_data:
            return {'message': 'No data to analyze'}
        
        top_3 = ranked_data[:3]
        total_all = sum(item.get('filtered_total', item.get('total', 0)) for item in ranked_data)
        
        analysis = {
            'top_provinces': [
                {
                    'provinsi': item.get('provinsi'),
                    'total': item.get('filtered_total', item.get('total', 0)),
                    'percentage': (item.get('filtered_total', item.get('total', 0)) / total_all * 100) if total_all > 0 else 0
                }
                for item in top_3
            ],
            'total_provinces': len(ranked_data),
            'total_usaha': total_all,
            'concentration': (sum(item.get('filtered_total', item.get('total', 0)) for item in top_3) / total_all * 100) if total_all > 0 else 0
        }
        
        return analysis
    
    def _analyze_comparison(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis perbandingan"""
        comparison_data = data.get('data', [])
        
        if not comparison_data:
            return {'message': 'No data to compare'}
        
        totals = [item.get('total', 0) for item in comparison_data]
        
        analysis = {
            'max_province': max(comparison_data, key=lambda x: x.get('total', 0)) if comparison_data else None,
            'min_province': min(comparison_data, key=lambda x: x.get('total', 0)) if comparison_data else None,
            'average': sum(totals) / len(totals) if totals else 0,
            'total': sum(totals),
            'provinces_count': len(comparison_data)
        }
        
        return analysis
    
    def _analyze_distribution(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis distribusi"""
        distribution = data.get('data', {})
        
        if not distribution:
            return {'message': 'No distribution data'}
        
        total = sum(item['total'] for item in distribution.values())
        
        # Sortir berdasarkan total (descending)
        sorted_sectors = sorted(
            distribution.items(),
            key=lambda x: x[1]['total'],
            reverse=True
        )
        
        analysis = {
            'top_sector': sorted_sectors[0] if sorted_sectors else None,
            'total_sectors': len(distribution),
            'total_usaha': total,
            'distribution_detail': [
                {
                    'sector_code': code,
                    'sector_name': info['name'],
                    'total': info['total'],
                    'percentage': (info['total'] / total * 100) if total > 0 else 0
                }
                for code, info in sorted_sectors
            ]
        }
        
        return analysis