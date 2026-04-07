import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

import asyncio
from retriever import retrieve_context

async def test_retrieval():
    query = "Latest Canada Study Permit updates"
    print(f"Testing Query: {query}")
    context = retrieve_context(query)
    
    if "Source: http" in context:
        print("✅ SUCCESS: Web search was triggered and results returned.")
    else:
        print("❌ FAILURE: Web search was NOT triggered or failed.")
        
    # Test DB match but still trigger web
    query_2 = "Canada student visa news"
    print(f"\nTesting Query 2: {query_2}")
    context_2 = retrieve_context(query_2)
    if "Source: http" in context_2:
        print("✅ SUCCESS: Web search was triggered for priority keyword.")
    else:
        print("❌ FAILURE: Web search was NOT triggered for priority keyword.")

if __name__ == "__main__":
    asyncio.run(test_retrieval())
