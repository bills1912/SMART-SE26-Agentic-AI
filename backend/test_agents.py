import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from data_agent import DataRetrievalAgent, AnalysisAgent
from visualization_agent import VisualizationAgent
from insight_agent import InsightGenerationAgent
import os
import json
from dotenv import load_dotenv
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
# Naik satu level ke root, lalu masuk ke frontend/.env
ENV_PATH = BACKEND_DIR.parent / 'frontend' / '.env'
load_dotenv(ENV_PATH)

async def test_agents():
    # Connect to MongoDB
    mongo_url = os.environ.get('MONGO_URL')
    if not mongo_url:
        print("ERROR: MONGO_URL not set!")
        return
    
    client = AsyncIOMotorClient(mongo_url)
    db = client['policy_db']
    
    # Initialize agents
    data_agent = DataRetrievalAgent(db)
    analysis_agent = AnalysisAgent()
    viz_agent = VisualizationAgent()
    insight_agent = InsightGenerationAgent()
    
    # Test queries
    test_queries = [
        "Berapa jumlah usaha di Jawa Barat?",
        "Bandingkan jumlah usaha antara DKI Jakarta dan Jawa Timur",
        "Provinsi mana yang memiliki usaha terbanyak?",
        "Bagaimana distribusi usaha per sektor di Indonesia?",
        "Berapa banyak usaha sektor perdagangan di Jawa Tengah?",
        "Provinsi mana yang punya industri pengolahan terbanyak?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"QUERY: {query}")
        print(f"{'='*80}\n")
        
        try:
            # Step 1: Understand intent
            intent = await data_agent.understand_query(query)
            print(f"✓ Intent: {intent.intent_type}")
            print(f"  Provinces: {intent.provinces if intent.provinces else 'All'}")
            print(f"  Sectors: {intent.sectors if intent.sectors else 'All'}\n")
            
            # Step 2: Get data
            raw_data = await data_agent.get_data_by_intent(intent)
            print(f"✓ Data fetched: {len(raw_data)} documents\n")
            
            if not raw_data:
                print("❌ No data found for this query!\n")
                continue
            
            # Step 3: Aggregate
            aggregated = await data_agent.aggregate_data(raw_data, intent)
            print(f"✓ Aggregation type: {aggregated.get('type')}\n")
            
            # Step 4: Analyze
            analysis = analysis_agent.analyze(aggregated, intent)
            print(f"✓ Analysis completed:")
            print(f"  {json.dumps(analysis, indent=2, ensure_ascii=False)}\n")
            
            # Step 5: Visualize
            visualizations = viz_agent.create_visualizations(analysis, aggregated)
            print(f"✓ Visualizations created: {len(visualizations)}\n")
            
            # Step 6: Generate insights (only if GEMINI_API_KEY is set)
            if os.environ.get('GEMINI_API_KEY'):
                insights_result = await insight_agent.generate_insights(
                    analysis, aggregated, query, "Indonesian"
                )
                print(f"✓ Insights generated: {len(insights_result.get('insights', []))}")
                print(f"✓ Policies generated: {len(insights_result.get('policies', []))}\n")
                
                # Show first insight
                if insights_result.get('insights'):
                    print(f"  Sample insight: {insights_result['insights'][0][:100]}...\n")
            else:
                print("⚠ GEMINI_API_KEY not set, skipping insights generation\n")
            
        except Exception as e:
            print(f"❌ Error processing query: {e}\n")
            import traceback
            traceback.print_exc()
    
    client.close()
    print("\n" + "="*80)
    print("AGENT TESTING COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(test_agents())