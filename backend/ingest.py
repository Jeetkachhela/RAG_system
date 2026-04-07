import os
import pandas as pd
from pymongo import MongoClient
import logging
from dotenv import load_dotenv

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
    return _ingest_dataframe(df, db)


def parse_and_ingest_from_bytes(file_bytes: bytes, filename: str = "upload.xlsx"):
    """Accept uploaded Excel file bytes, replace old data, and ingest new data."""
    import io
    if not MONGODB_URI:
        raise ValueError("MONGODB_URI environment variable is not set.")

    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    logger.info(f"Processing uploaded file: {filename} ({len(file_bytes)} bytes)")
    
    # Try to detect sheet name
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    sheet_name = 'All Agents' if 'All Agents' in xls.sheet_names else xls.sheet_names[0]
    logger.info(f"Using sheet: '{sheet_name}' from {xls.sheet_names}")
    
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
    return _ingest_dataframe(df, db)


def _ingest_dataframe(df, db):
    """Common ingestion logic for both file-based and upload-based ingestion."""
    # Pre-processing
    df.columns = [col.strip() for col in df.columns]
    df = df.astype(object).fillna("")
    
    collection = db[COLLECTION_NAME]
    
    try:
        # CRITICAL: Always wipe before replace for daily updates
        res = collection.delete_many({})
        logger.info(f"Dropped {res.deleted_count} existing agent records for fresh ingestion.")
    except Exception as e:
        logger.error(f"Error clearing collection: {e}")

    # Import HF embedder helper locally to avoid top-level issues
    from retriever import get_hf_embeddings

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
    batch_size = 50 # HF API likes smaller batches or single calls
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i+batch_size]
        print(f"  Generating embeddings for batch {i}-{i+len(batch)} via HF API...")
        
        for j, doc in enumerate(batch):
            # HF API feature extraction can handle lists, but for MiniLM we do one by one for reliability
            vec = get_hf_embeddings(doc["text"])
            if vec:
                doc["embedding"] = vec
            else:
                logger.warning(f"Failed to get embedding for record {i+j}")
            
        print(f"  Inserting batch {i}-{i+len(batch)} into MongoDB...")
        # Only insert records that have embeddings
        valid_batch = [d for d in batch if "embedding" in d]
        if valid_batch:
            collection.insert_many(valid_batch)

    print(f"Ingestion complete! Successfully indexed {len(documents)} records in MongoDB Atlas.")
    return len(documents)

if __name__ == "__main__":
    parse_and_ingest()
