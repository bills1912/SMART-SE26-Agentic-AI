import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from pathlib import Path
from dotenv import load_dotenv
import json

BACKEND_DIR = Path(__file__).resolve().parent
# Naik satu level ke root, lalu masuk ke frontend/.env
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

async def verify_initial_data():
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        print("ERROR: MONGO_URL environment variable not set!")
        return
    
    client = AsyncIOMotorClient(mongo_url)
    db = client['policy_db']
    
    print("="*80)
    print("VERIFYING INITIAL_DATA COLLECTION")
    print("="*80)
    
    # Check collection exists
    collections = await db.list_collection_names()
    print(f"\n✓ Available collections: {collections}")
    
    if 'initial_data' not in collections:
        print("\n❌ ERROR: initial_data collection not found!")
        client.close()
        return
    
    # Check document count
    count = await db.initial_data.count_documents({})
    print(f"✓ Total documents in initial_data: {count}")
    
    if count == 0:
        print("\n❌ ERROR: No documents found in initial_data!")
        client.close()
        return
    
    # Check sample document
    print("\n" + "="*80)
    print("SAMPLE DOCUMENT STRUCTURE")
    print("="*80)
    
    sample = await db.initial_data.find_one()
    if sample:
        print(f"\nProvinsi: {sample.get('provinsi')}")
        print(f"Kode Provinsi: {sample.get('kode_provinsi')}")
        print(f"Total: {sample.get('total', 0):,}")
        
        print("\nAvailable KBLI Sectors:")
        sector_keys = [k for k in sample.keys() if k not in ['_id', 'provinsi', 'kode_provinsi', 'total']]
        
        for sector_code in sorted(sector_keys)[:5]:  # Show first 5
            sector_data = sample.get(sector_code)
            if isinstance(sector_data, dict):
                sector_name = list(sector_data.keys())[0] if sector_data else 'Unknown'
                sector_value = list(sector_data.values())[0] if sector_data else 0
                print(f"  {sector_code}: {sector_name} = {sector_value:,}")
            else:
                print(f"  {sector_code}: {sector_data}")
        
        if len(sector_keys) > 5:
            print(f"  ... and {len(sector_keys) - 5} more sectors")
    
    # Test specific queries
    print("\n" + "="*80)
    print("TESTING SPECIFIC QUERIES")
    print("="*80)
    
    # Test 1: Query by province
    print("\n1. Testing query for 'JAWA BARAT'...")
    jabar = await db.initial_data.find_one({'provinsi': 'JAWA BARAT'})
    if jabar:
        print(f"   ✓ Found JAWA BARAT")
        print(f"   Total usaha: {jabar.get('total', 0):,}")
        
        # Test nested structure for sector C
        sector_c = jabar.get('C')
        if isinstance(sector_c, dict):
            sector_name = list(sector_c.keys())[0]
            sector_value = list(sector_c.values())[0]
            print(f"   Sektor C ({sector_name}): {sector_value:,} usaha")
        
        # Test nested structure for sector G
        sector_g = jabar.get('G')
        if isinstance(sector_g, dict):
            sector_name = list(sector_g.keys())[0]
            sector_value = list(sector_g.values())[0]
            print(f"   Sektor G ({sector_name}): {sector_value:,} usaha")
    else:
        print("   ❌ JAWA BARAT not found!")
    
    # Test 2: Query all provinces
    print("\n2. Testing query for all provinces...")
    all_provinces = await db.initial_data.find({}, {'provinsi': 1, 'total': 1, '_id': 0}).to_list(length=None)
    print(f"   ✓ Found {len(all_provinces)} provinces")
    print("\n   Top 5 provinces by total:")
    sorted_provinces = sorted(all_provinces, key=lambda x: x.get('total', 0), reverse=True)[:5]
    for i, prov in enumerate(sorted_provinces, 1):
        print(f"   {i}. {prov.get('provinsi')}: {prov.get('total', 0):,} usaha")
    
    # Test 3: Aggregation test
    print("\n3. Testing aggregation for sector C across all provinces...")
    all_docs = await db.initial_data.find({}).to_list(length=None)
    total_sector_c = 0
    for doc in all_docs:
        sector_c = doc.get('C')
        if isinstance(sector_c, dict):
            total_sector_c += list(sector_c.values())[0]
    print(f"   ✓ Total Industri Pengolahan (C): {total_sector_c:,} usaha")
    
    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)
    
    client.close()

if __name__ == "__main__":
    asyncio.run(verify_initial_data())