import os
import json
import logging
import chromadb
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
COLLECTION_NAME = "kanan_agents"


def get_chroma_collection():
    """Get the ChromaDB collection using the default ONNX embedding function."""
    if not os.path.exists(CHROMA_DB_DIR):
        return None
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        collection = client.get_collection(name=COLLECTION_NAME)
        return collection
    except Exception as e:
        logger.error(f"Error connecting to ChromaDB: {e}")
        return None

def rewrite_query(query: str, chat_history: list = None) -> tuple[str, dict]:
    """Uses Groq to extract a semantic query and a metadata filters dictionary."""
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    history_text = ""
    if chat_history:
        for msg in chat_history[-6:]:  # Keep last 6 messages
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"{role}: {msg.get('content')}\n"
        
    prompt = f"""Given the following conversation history and latest query, extract:
1. `search_query`: A string for semantic search (names, general topics).
2. `keyword`: IF the user mentions a specific proper noun, company name, or agent name (e.g., 'A P Consultants', 'Star Education', 'Manish Shah'), extract ONLY that exact name here. If none found, leave as empty string.
3. `filters`: A dictionary of exact match filters. Valid keys: "rank", "city", "state", "zone", "category", "active".

Valid values to choose from for filters:
- rank: 'Bronze', 'Diamond', 'Gold', 'Platinum', 'Silver'
- zone: 'WEST', 'NORTH', 'SOUTH', 'EAST'
- active: 'Yes', 'No'
- category: 'SubAgent', 'Prepcom', 'SubAgent+Prepcom', 'HO', 'Franchise', 'Preferred Partner'

Return ONLY a valid JSON object with the keys 'search_query', 'keyword', and 'filters'. No markdown formatting or extra text.

Conversation History:
{history_text}
Latest Query: {query}
"""

    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a JSON query extractor. Return ONLY valid JSON."}, 
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        
        search_query = data.get("search_query", query)
        if not search_query or not search_query.strip():
            search_query = query
            
        keyword = data.get("keyword", "")
            
        filters = data.get("filters", {})
        # Clean dict of empty/bad values
        clean_filters = {}
        for k, v in filters.items():
            if v and isinstance(v, str):
                # Title case specific fields to match ChromaDB's case-sensitivity
                if k in ["state", "city", "category"]:
                    clean_filters[k] = v.title()
                elif k == "zone":
                    clean_filters[k] = v.upper()
                else:
                    clean_filters[k] = v

        logger.info(f"[RAG] Rewritten Query: '{search_query}'")
        logger.info(f"[RAG] Extracted Keyword: '{keyword}'")
        logger.info(f"[RAG] Filters Applied: {clean_filters}")
        return search_query, keyword, clean_filters
    except Exception as e:
        logger.error(f"[RAG] Query rewrite failed: {e}")
        return query, "", {}

def retrieve_from_pandas(search_query: str, keyword: str, filters: dict, max_results: int = 15) -> list:
    excel_path = os.getenv("EXCEL_FILE_PATH", "./K Apply - Accounts Dump - 18.03.2026 (1).xlsx")
    if not os.path.exists(excel_path):
        excel_path = os.getenv("EXCEL_FILE_PATH", "../K Apply - Accounts Dump - 18.03.2026 (1).xlsx")
    if not os.path.exists(excel_path):
        return []
        
    try:
        df = pd.read_excel(excel_path, sheet_name='All Agents')
        df.fillna("N/A", inplace=True)
        
        # Apply exact filters first
        if filters:
            for k, v in filters.items():
                col_map = {
                    "rank": "Rank", "city": "City", "state": "State", 
                    "zone": "Zone", "category": "Category Type", "active": "Active"
                }
                if k in col_map and col_map[k] in df.columns:
                    df = df[df[col_map[k]].astype(str).str.lower() == str(v).lower()]
                    
        # Apply keyword search
        if keyword:
            mask = df.apply(lambda row: row.astype(str).str.contains(keyword, case=False, na=False).any(), axis=1)
            df = df[mask]
        elif search_query:
            # Fallback for semantic broad searches if no exact keyword
            # We don't apply search_query heavily as it might contain broad noisy text
            pass
            
        results = []
        for _, row in df.head(max_results).iterrows():
            doc_parts = []
            for col in df.columns:
                val = str(row[col]).strip()
                if val and val.upper() != "N/A" and val.lower() != "nan":
                    doc_parts.append(f"{col}: {val}")
            doc_text = " || ".join(doc_parts)
            results.append(doc_text)
            
        logger.info(f"[RAG] Pandas retrieved {len(results)} exact matches.")
        return results
    except Exception as e:
        logger.error(f"[RAG] Pandas retrieval failed: {e}")
        return []

def retrieve_context(query: str, chat_history: list = None, n_results: int = 40) -> str:
    """
    Dual-Engine Search: Vector Search (Chroma) + Keyword Search (Pandas).
    """
    collection = get_chroma_collection()
    if not collection:
        return "Knowledge base not initialized. Please click 'Update Knowledge' first."

    # Build an enriched query using LLM
    enriched_query, keyword, filters = rewrite_query(query, chat_history)

    kwargs = {
        "query_texts": [enriched_query],
        "n_results": n_results,
    }
    
    if filters:
        if len(filters) > 1:
            kwargs["where"] = {"$and": [{k: v} for k, v in filters.items()]}
        else:
            kwargs["where"] = filters

    # Engine 1: ChromaDB (Semantic)
    chroma_docs = []
    try:
        results = collection.query(**kwargs)
        if results and results["documents"] and results["documents"][0]:
            chroma_docs = results["documents"][0]
            logger.info(f"[RAG] ChromaDB retrieved {len(chroma_docs)} semantic matches.")
    except Exception as e:
        logger.error(f"[RAG] ChromaDB search failed: {e}")
        
    # Engine 2: Pandas (BM25 / Keyword)
    pandas_docs = retrieve_from_pandas(enriched_query, keyword, filters)
    
    # Combine (remove duplicates while preserving order: Exact matches first, then semantic)
    all_results = list(dict.fromkeys(pandas_docs + chroma_docs))
    
    if not all_results:
        return "No relevant agents found for this query."

    formatted = "\n---\n".join(all_results[:n_results])
    return formatted


if __name__ == "__main__":
    print(retrieve_context("Show me agents in Ahmedabad"))
