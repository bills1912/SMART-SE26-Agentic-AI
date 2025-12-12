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

# Short names for visualization labels
KBLI_SHORT_NAMES = {
    'A': 'Pertanian',
    'B': 'Pertambangan',
    'C': 'Industri Pengolahan',
    'D': 'Listrik & Gas',
    'E': 'Pengelolaan Air',
    'F': 'Konstruksi',
    'G': 'Perdagangan',
    'H': 'Transportasi',
    'I': 'Akomodasi & Makan Minum',
    'J': 'Informasi & Komunikasi',
    'K': 'Keuangan & Asuransi',
    'L': 'Real Estat',
    'M': 'Jasa Profesional',
    'N': 'Jasa Persewaan',
    'O': 'Administrasi Pemerintahan',
    'P': 'Pendidikan',
    'Q': 'Kesehatan',
    'R': 'Hiburan & Rekreasi',
    'S': 'Jasa Lainnya',
    'T': 'Jasa Rumah Tangga',
    'U': 'Badan Internasional'
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
                values = list(sector_obj.values())
                return int(values[0]) if values else 0
            elif isinstance(sector_obj, (int, float)):
                # Fallback jika format lama (langsung integer)
                return int(sector_obj)
            else:
                return 0
        except (KeyError, IndexError, TypeError, ValueError) as e:
            logger.debug(f"Error getting sector {sector_code} value: {e}")
            return 0
    
    def _get_sector_name_from_doc(self, doc: Dict[str, Any], sector_code: str) -> str:
        """Get sector name from document structure"""
        try:
            sector_obj = doc.get(sector_code)
            if isinstance(sector_obj, dict):
                keys = list(sector_obj.keys())
                return keys[0] if keys else KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}')
            return KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}')
        except:
            return KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}')
    
    def _calculate_province_total(self, doc: Dict[str, Any]) -> int:
        """Calculate total usaha for a province by summing all sectors"""
        # First check if 'total' field exists
        if 'total' in doc and doc['total']:
            return int(doc['total'])
        
        # Otherwise calculate from all sectors
        total = 0
        for sector_code in KBLI_MAPPING.keys():
            total += self._get_sector_value(doc, sector_code)
        return total
    
    async def understand_query(self, query: str) -> QueryIntent:
        """Enhanced query understanding with better intent detection"""
        query_lower = query.lower()
        
        intent = QueryIntent(intent_type='distribution')
        
        # Enhanced intent detection - check for overview/analysis first
        if any(word in query_lower for word in ['analisis', 'analyze', 'analisa', 'overview', 'keseluruhan', 'semua', 'lengkap', 'detail', 'mendetail', 'gambaran']):
            intent.intent_type = 'overview'
        # Check for comparison
        elif any(word in query_lower for word in ['bandingkan', 'compare', 'versus', 'vs', 'perbandingan', 'beda', 'dibanding']):
            intent.intent_type = 'comparison'
        # Check for ranking
        elif any(word in query_lower for word in ['ranking', 'urut', 'tertinggi', 'terendah', 'terbanyak', 'terbesar', 'top', 'paling', 'mana yang', 'terkecil', 'tersedikit']):
            intent.intent_type = 'ranking'
        # Check for trend
        elif any(word in query_lower for word in ['tren', 'trend', 'perkembangan', 'perubahan']):
            intent.intent_type = 'trend'
        # Check for distribution
        elif any(word in query_lower for word in ['distribusi', 'sebaran', 'persebaran', 'komposisi', 'bagaimana', 'proporsi']):
            intent.intent_type = 'distribution'
        
        # ENHANCED: Detect if asking for specific value (e.g., "berapa jumlah")
        if any(word in query_lower for word in ['berapa', 'jumlah', 'total', 'banyak']):
            # If asking about specific province + sector → comparison
            provinces = self._extract_provinces(query)
            sectors = self._extract_sectors(query)
            
            if provinces and len(provinces) == 1 and sectors:
                intent.intent_type = 'province_detail'  # Single province with sector analysis
            elif provinces and len(provinces) == 1:
                intent.intent_type = 'province_detail'  # Province overview
            elif provinces and len(provinces) > 1:
                intent.intent_type = 'comparison'  # Multiple provinces
            elif sectors and not provinces:
                intent.intent_type = 'sector_analysis'  # Sector analysis across all provinces
        
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
            'kepulauan bangka belitung': 'KEP. BANGKA BELITUNG',
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
            'di yogyakarta': 'DI YOGYAKARTA',
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
            'papua barat': 'PAPUA BARAT',
            'papua barat daya': 'PAPUA BARAT DAYA',
            'papua selatan': 'PAPUA SELATAN',
            'papua tengah': 'PAPUA TENGAH',
            'papua pegunungan': 'PAPUA PEGUNUNGAN'
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
            'pertanian': 'A', 'kehutanan': 'A', 'perikanan': 'A', 'perkebunan': 'A', 'tani': 'A',
            'pertambangan': 'B', 'tambang': 'B', 'galian': 'B', 'penggalian': 'B', 'mining': 'B',
            'industri': 'C', 'manufaktur': 'C', 'pengolahan': 'C', 'pabrik': 'C', 'manufacturing': 'C',
            'listrik': 'D', 'gas': 'D', 'energi': 'D', 'tenaga': 'D', 'electricity': 'D',
            'air': 'E', 'limbah': 'E', 'sampah': 'E', 'sanitasi': 'E', 'daur ulang': 'E',
            'konstruksi': 'F', 'bangunan': 'F', 'kontraktor': 'F', 'pembangunan': 'F',
            'perdagangan': 'G', 'retail': 'G', 'eceran': 'G', 'grosir': 'G', 'toko': 'G', 'dagang': 'G', 'reparasi': 'G',
            'transportasi': 'H', 'logistik': 'H', 'pergudangan': 'H', 'angkutan': 'H', 'transport': 'H',
            'hotel': 'I', 'restoran': 'I', 'akomodasi': 'I', 'kuliner': 'I', 'penginapan': 'I', 'makanan': 'I', 'minum': 'I', 'cafe': 'I', 'katering': 'I',
            'informasi': 'J', 'komunikasi': 'J', 'telekomunikasi': 'J', 'it': 'J', 'teknologi informasi': 'J', 'media': 'J',
            'keuangan': 'K', 'bank': 'K', 'asuransi': 'K', 'finance': 'K', 'perbankan': 'K',
            'real estat': 'L', 'properti': 'L', 'tanah': 'L', 'real estate': 'L',
            'profesional': 'M', 'konsultan': 'M', 'teknis': 'M', 'jasa profesional': 'M', 'ilmiah': 'M',
            'persewaan': 'N', 'tenaga kerja': 'N', 'agen perjalanan': 'N', 'travel': 'N', 'rental': 'N',
            'pemerintah': 'O', 'administrasi': 'O', 'pertahanan': 'O', 'pemerintahan': 'O',
            'pendidikan': 'P', 'sekolah': 'P', 'universitas': 'P', 'kampus': 'P', 'kursus': 'P', 'bimbel': 'P',
            'kesehatan': 'Q', 'rumah sakit': 'Q', 'klinik': 'Q', 'medis': 'Q', 'apotek': 'Q', 'farmasi': 'Q',
            'seni': 'R', 'hiburan': 'R', 'rekreasi': 'R', 'entertainment': 'R', 'olahraga': 'R', 'wisata': 'R',
            'jasa lainnya': 'S', 'salon': 'S', 'laundry': 'S', 'bengkel': 'S'
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
            
            # Calculate total for each document if not present
            for doc in data:
                if 'total' not in doc or not doc['total']:
                    doc['total'] = self._calculate_province_total(doc)
            
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
        
        if intent.intent_type == 'overview':
            return self._aggregate_overview(data, intent)
        elif intent.intent_type == 'ranking':
            return self._aggregate_ranking(data, intent)
        elif intent.intent_type == 'comparison':
            return self._aggregate_comparison(data, intent)
        elif intent.intent_type == 'distribution':
            return self._aggregate_distribution(data, intent)
        elif intent.intent_type == 'province_detail':
            return self._aggregate_province_detail(data, intent)
        elif intent.intent_type == 'sector_analysis':
            return self._aggregate_sector_analysis(data, intent)
        elif intent.intent_type == 'trend':
            return self._aggregate_trend(data, intent)
        
        return {'type': 'raw', 'raw_data': data}
    
    def _aggregate_overview(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Agregasi untuk overview/analisis keseluruhan"""
        # Calculate totals per province
        provinces_data = []
        for doc in data:
            total = doc.get('filtered_total', doc.get('total', self._calculate_province_total(doc)))
            provinces_data.append({
                'provinsi': doc.get('provinsi', ''),
                'total': total
            })
        
        # Sort by total descending
        provinces_data.sort(key=lambda x: x['total'], reverse=True)
        
        # Calculate sector totals across all provinces
        sector_totals = {}
        for sector_code in KBLI_MAPPING.keys():
            total = sum(self._get_sector_value(doc, sector_code) for doc in data)
            if total > 0:
                sector_totals[sector_code] = {
                    'total': total,
                    'name': KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}'),
                    'short_name': KBLI_SHORT_NAMES.get(sector_code, sector_code)
                }
        
        grand_total = sum(p['total'] for p in provinces_data)
        
        return {
            'type': 'overview',
            'data': provinces_data,
            'sectors': sector_totals,
            'grand_total': grand_total,
            'provinces_count': len(provinces_data),
            'sectors_count': len(sector_totals)
        }
    
    def _aggregate_ranking(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Ranking berdasarkan total usaha"""
        if intent.sectors:
            # Ranking berdasarkan sektor tertentu
            ranked = sorted(data, key=lambda x: x.get('filtered_total', 0), reverse=True)
        else:
            # Ranking berdasarkan total semua sektor
            ranked = sorted(data, key=lambda x: x.get('total', self._calculate_province_total(x)), reverse=True)
        
        return {
            'type': 'ranking',
            'data': ranked[:10],  # Top 10
            'all_data': ranked,  # All data for analysis
            'sectors': intent.sectors if intent.sectors else 'all'
        }
    
    def _aggregate_comparison(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Perbandingan antar provinsi/sektor"""
        comparison_data = []
        
        for doc in data:
            total = doc.get('filtered_total', doc.get('total', self._calculate_province_total(doc)))
            entry = {
                'provinsi': doc.get('provinsi', ''),
                'total': total
            }
            
            # Breakdown per sektor jika ada
            if intent.sectors:
                entry['breakdown'] = {
                    sector: self._get_sector_value(doc, sector)
                    for sector in intent.sectors
                }
            else:
                # Include all sectors breakdown
                entry['breakdown'] = {
                    code: self._get_sector_value(doc, code)
                    for code in KBLI_MAPPING.keys()
                    if self._get_sector_value(doc, code) > 0
                }
            
            comparison_data.append(entry)
        
        # Sort by total
        comparison_data.sort(key=lambda x: x['total'], reverse=True)
        
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
                    'name': KBLI_MAPPING.get(sector, f'Sektor {sector}'),
                    'short_name': KBLI_SHORT_NAMES.get(sector, sector)
                }
        else:
            # Distribusi semua sektor
            distribution = {}
            for sector_code in KBLI_MAPPING.keys():
                total = sum(self._get_sector_value(doc, sector_code) for doc in data)
                if total > 0:
                    distribution[sector_code] = {
                        'total': total,
                        'name': KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}'),
                        'short_name': KBLI_SHORT_NAMES.get(sector_code, sector_code)
                    }
        
        return {
            'type': 'distribution',
            'data': distribution,
            'provinces': intent.provinces if intent.provinces else 'all'
        }
    
    def _aggregate_province_detail(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Detail analisis untuk satu provinsi"""
        if not data:
            return {'type': 'province_detail', 'data': None}
        
        doc = data[0]  # Single province
        provinsi = doc.get('provinsi', '')
        
        # Get all sectors for this province
        sectors = []
        for sector_code in KBLI_MAPPING.keys():
            value = self._get_sector_value(doc, sector_code)
            if value > 0:
                sectors.append({
                    'code': sector_code,
                    'name': KBLI_MAPPING.get(sector_code, f'Sektor {sector_code}'),
                    'short_name': KBLI_SHORT_NAMES.get(sector_code, sector_code),
                    'total': value
                })
        
        # Sort by total descending
        sectors.sort(key=lambda x: x['total'], reverse=True)
        
        total = sum(s['total'] for s in sectors)
        
        return {
            'type': 'province_detail',
            'data': doc,
            'provinsi': provinsi,
            'sectors': sectors,
            'total': total
        }
    
    def _aggregate_sector_analysis(self, data: List[Dict[str, Any]], intent: QueryIntent) -> Dict[str, Any]:
        """Analisis sektor tertentu di semua provinsi"""
        sector_codes = intent.sectors if intent.sectors else list(KBLI_MAPPING.keys())
        
        # Get data per province for the sectors
        province_data = []
        for doc in data:
            total = sum(self._get_sector_value(doc, code) for code in sector_codes)
            if total > 0:
                province_data.append({
                    'provinsi': doc.get('provinsi', ''),
                    'total': total,
                    'breakdown': {
                        code: self._get_sector_value(doc, code)
                        for code in sector_codes
                    }
                })
        
        # Sort by total
        province_data.sort(key=lambda x: x['total'], reverse=True)
        
        sector_names = [KBLI_SHORT_NAMES.get(code, code) for code in sector_codes]
        grand_total = sum(p['total'] for p in province_data)
        
        return {
            'type': 'sector_analysis',
            'data': province_data,
            'sectors': sector_codes,
            'sector_names': sector_names,
            'total': grand_total
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
        
        if data_type == 'overview':
            return self._analyze_overview(aggregated_data)
        elif data_type == 'ranking':
            return self._analyze_ranking(aggregated_data)
        elif data_type == 'comparison':
            return self._analyze_comparison(aggregated_data)
        elif data_type == 'distribution':
            return self._analyze_distribution(aggregated_data)
        elif data_type == 'province_detail':
            return self._analyze_province_detail(aggregated_data)
        elif data_type == 'sector_analysis':
            return self._analyze_sector_analysis(aggregated_data)
        
        return {'analysis': 'No analysis available'}
    
    def _analyze_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis overview keseluruhan"""
        provinces = data.get('data', [])
        sectors = data.get('sectors', {})
        grand_total = data.get('grand_total', 0)
        
        if not provinces:
            return {'message': 'No data to analyze'}
        
        # Top provinces
        top_provinces = [
            {
                'provinsi': p['provinsi'],
                'total': p['total'],
                'percentage': (p['total'] / grand_total * 100) if grand_total > 0 else 0
            }
            for p in provinces[:10]
        ]
        
        # Top sectors
        sorted_sectors = sorted(sectors.items(), key=lambda x: x[1]['total'], reverse=True)
        top_sectors = [
            {
                'code': code,
                'name': info['name'],
                'short_name': info.get('short_name', info['name'][:20]),
                'total': info['total'],
                'percentage': (info['total'] / grand_total * 100) if grand_total > 0 else 0
            }
            for code, info in sorted_sectors[:10]
        ]
        
        # Concentration metrics
        top3_province_concentration = sum(p['total'] for p in provinces[:3]) / grand_total * 100 if grand_total > 0 else 0
        top3_sector_concentration = sum(s[1]['total'] for s in sorted_sectors[:3]) / grand_total * 100 if grand_total > 0 else 0
        
        return {
            'total_usaha': grand_total,
            'total_provinces': len(provinces),
            'total_sectors': len(sectors),
            'top_provinces': top_provinces,
            'top_sectors': top_sectors,
            'all_provinces': [
                {
                    'provinsi': p['provinsi'],
                    'total': p['total'],
                    'percentage': (p['total'] / grand_total * 100) if grand_total > 0 else 0
                }
                for p in provinces
            ],
            'all_sectors': [
                {
                    'code': code,
                    'name': info['name'],
                    'short_name': info.get('short_name', info['name'][:20]),
                    'total': info['total'],
                    'percentage': (info['total'] / grand_total * 100) if grand_total > 0 else 0
                }
                for code, info in sorted_sectors
            ],
            'province_concentration_top3': top3_province_concentration,
            'sector_concentration_top3': top3_sector_concentration,
            'average_per_province': grand_total / len(provinces) if provinces else 0,
            'max_province': provinces[0] if provinces else None,
            'min_province': provinces[-1] if provinces else None
        }
    
    def _analyze_ranking(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis ranking"""
        ranked_data = data.get('data', [])
        all_data = data.get('all_data', ranked_data)
        
        if not ranked_data:
            return {'message': 'No data to analyze'}
        
        total_all = sum(item.get('filtered_total', item.get('total', 0)) for item in all_data)
        
        top_3 = ranked_data[:3]
        
        analysis = {
            'top_provinces': [
                {
                    'provinsi': item.get('provinsi'),
                    'total': item.get('filtered_total', item.get('total', 0)),
                    'percentage': (item.get('filtered_total', item.get('total', 0)) / total_all * 100) if total_all > 0 else 0
                }
                for item in top_3
            ],
            'all_ranked': [
                {
                    'rank': i + 1,
                    'provinsi': item.get('provinsi'),
                    'total': item.get('filtered_total', item.get('total', 0)),
                    'percentage': (item.get('filtered_total', item.get('total', 0)) / total_all * 100) if total_all > 0 else 0
                }
                for i, item in enumerate(all_data)
            ],
            'total_provinces': len(all_data),
            'total_usaha': total_all,
            'concentration': (sum(item.get('filtered_total', item.get('total', 0)) for item in top_3) / total_all * 100) if total_all > 0 else 0,
            'average': total_all / len(all_data) if all_data else 0
        }
        
        return analysis
    
    def _analyze_comparison(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis perbandingan"""
        comparison_data = data.get('data', [])
        
        if not comparison_data:
            return {'message': 'No data to compare'}
        
        totals = [item.get('total', 0) for item in comparison_data]
        total_sum = sum(totals)
        
        analysis = {
            'max_province': comparison_data[0] if comparison_data else None,
            'min_province': comparison_data[-1] if comparison_data else None,
            'average': total_sum / len(totals) if totals else 0,
            'total': total_sum,
            'provinces_count': len(comparison_data),
            'comparison_data': [
                {
                    **item,
                    'percentage': (item['total'] / total_sum * 100) if total_sum > 0 else 0
                }
                for item in comparison_data
            ]
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
                    'short_name': info.get('short_name', info['name'][:20]),
                    'total': info['total'],
                    'percentage': (info['total'] / total * 100) if total > 0 else 0
                }
                for code, info in sorted_sectors
            ]
        }
        
        return analysis
    
    def _analyze_province_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis detail provinsi"""
        if data.get('data') is None:
            return {'message': 'No province data'}
        
        sectors = data.get('sectors', [])
        total = data.get('total', 0)
        provinsi = data.get('provinsi', '')
        
        return {
            'provinsi': provinsi,
            'total_usaha': total,
            'total_sectors': len(sectors),
            'top_sectors': [
                {
                    **s,
                    'percentage': (s['total'] / total * 100) if total > 0 else 0
                }
                for s in sectors[:5]
            ],
            'all_sectors': [
                {
                    **s,
                    'percentage': (s['total'] / total * 100) if total > 0 else 0
                }
                for s in sectors
            ],
            'sector_concentration_top3': sum(s['total'] for s in sectors[:3]) / total * 100 if total > 0 and len(sectors) >= 3 else 0
        }
    
    def _analyze_sector_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analisis sektor"""
        province_data = data.get('data', [])
        total = data.get('total', 0)
        
        return {
            'sectors': data.get('sectors', []),
            'sector_names': data.get('sector_names', []),
            'total_usaha': total,
            'total_provinces': len(province_data),
            'top_provinces': [
                {
                    **p,
                    'percentage': (p['total'] / total * 100) if total > 0 else 0
                }
                for p in province_data[:10]
            ],
            'all_provinces': [
                {
                    **p,
                    'percentage': (p['total'] / total * 100) if total > 0 else 0
                }
                for p in province_data
            ],
            'average_per_province': total / len(province_data) if province_data else 0
        }