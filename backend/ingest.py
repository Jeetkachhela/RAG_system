import os
import pandas as pd
from pymongo import MongoClient
import logging
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

load_dotenv()

EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "../K Apply - Accounts Dump - 18.03.2026 (1).xlsx")
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = os.getenv("MONGODB_DB_NAME", "kanan_rag")
COLLECTION_NAME = "kanan_agents"
COMPANY_COLLECTION_NAME = "company_info"

def _norm_value(key: str, val: str) -> str:
    v = (val or "").strip()
    if not v or v.lower() in {"nan", "n/a"}:
        return "Unknown"
    if key == "zone":
        return v.upper()
    if key == "active":
        vv = v.strip().lower()
        if vv in {"yes", "y", "true", "1"}:
            return "Yes"
        if vv in {"no", "n", "false", "0"}:
            return "No"
        return v.title()
    if key in {"rank", "city", "state", "category", "bdm", "team"}:
        return v.title()
    return v

def _norm_keyed_metadata(metadata: dict) -> dict:
    return {k: _norm_value(k, str(v)) for k, v in metadata.items()}


def parse_and_ingest():
    """Read Excel and text files, embed texts, and ingest into MongoDB Atlas."""
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable is not set.")
        
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]
    
    # 1. Ingest Company Info
    company_info_path = os.path.join(os.path.dirname(__file__), "company_info.txt")
    if os.path.exists(company_info_path):
        company_collection = db[COMPANY_COLLECTION_NAME]
        with open(company_info_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        company_collection.delete_many({}) # Clear existing
        company_collection.insert_one({"type": "company_profile", "content": content})
        print("Ingested company_info.txt")

    # 2. Ingest Excel Agents
    if not os.path.exists(EXCEL_FILE_PATH):
        raise FileNotFoundError(f"Excel file not found at {EXCEL_FILE_PATH}")

    print(f"Loading data from {EXCEL_FILE_PATH}...")
    df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='All Agents')
    
    # Pre-processing
    df.columns = [col.strip() for col in df.columns]
    df = df.astype(object).fillna("")
    
    collection = db[COLLECTION_NAME]
    
    try:
        collection.delete_many({})
        print("Dropped existing agent collection contents for fresh ingestion.")
    except Exception as e:
        print(f"Error clearing collection: {e}")

    # Load embedder locally for generating vectors
    print("Loading embedding model...")
    embedder = SentenceTransformer("all-MiniLM-L6-v2")

    documents = []

    print(f"Processing {len(df)} records...")
    for idx, row in df.iterrows():
        doc_parts = []
        metadata = {}
        
        filter_map = {
            "account_name": "K-Apply Account Name",
            "rank": "Rank",
            "city": "City",
            "state": "State",
            "zone": "Zone",
            "category": "Category Type",
            "active": "Active",
            "bdm": "BDM",
            "team": "Team"
        }
        
        for meta_key, col_name in filter_map.items():
            val = str(row.get(col_name, "")).strip()
            metadata[meta_key] = val
        metadata = _norm_keyed_metadata(metadata)

        for col in df.columns:
            val = str(row[col]).strip()
            if val and val.lower() not in ["", "nan", "n/a"]:
                doc_parts.append(f"{col}: {val}")

        doc_text = " || ".join(doc_parts)
        
        documents.append({
            "text": doc_text,
            **metadata
        })

    # Generate Embeddings in batches and insert
    batch_size = 200
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        texts = [doc["text"] for doc in batch]
        print(f"  Generating embeddings for batch {i}-{i+len(batch)}...")
        embeddings = embedder.encode(texts, convert_to_numpy=True).tolist()
        
        for j, doc in enumerate(batch):
            doc["embedding"] = embeddings[j]
            
        print(f"  Inserting batch {i}-{i+len(batch)} into MongoDB...")
        collection.insert_many(batch)

    print(f"Ingestion complete! {len(documents)} records indexed in MongoDB.")
    return len(documents)

if __name__ == "__main__":
    parse_and_ingest()
