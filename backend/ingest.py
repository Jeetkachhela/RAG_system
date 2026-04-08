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

def _norm_value(val: str) -> str:
    v = (val or "").strip()
    if not v or v.lower() in {"nan", "n/a", "none", "unknown"}:
        return "Unknown"
    return v


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
    df.columns = [str(col).strip() for col in df.columns]
    df = df.astype(object).fillna("")
    
    collection = db[COLLECTION_NAME]
    schema_collection = db["kanan_schema"]
    
    try:
        # CRITICAL: Always wipe before replace for daily updates
        res = collection.delete_many({})
        schema_res = schema_collection.delete_many({})
        logger.info(f"Dropped {res.deleted_count} agent records and {schema_res.deleted_count} schemas for fresh ingestion.")
    except Exception as e:
        logger.error(f"Error clearing collection: {e}")

    # --- DYNAMIC SCHEMA DETECTION ---
    categorical_fields = {}
    bad_schema_keywords = {"name", "date", "id", "no.", "number", "email", "phone", "code"}
    for col in df.columns:
        col_lower = col.lower()
        if any(bad_word in col_lower for bad_word in bad_schema_keywords):
            continue
            
        unique_vals = set()
        for idx, row in df.iterrows():
            val = str(row[col]).strip()
            if val and val.lower() not in {"nan", "n/a", "none"}:
                unique_vals.add(val)
        # Limit expanded to 35 for elements like 'Team' while excluding IDs
        if 0 < len(unique_vals) <= 35:
            categorical_fields[col] = sorted(list(unique_vals))

    # Save schema profile
    schema_collection.insert_one({
        "type": "schema_profile",
        "categorical_fields": categorical_fields,
        "all_columns": list(df.columns)
    })
    logger.info(f"Generated dynamic schema profile. Categorical fields: {list(categorical_fields.keys())}")

    # Import HF embedder helper locally to avoid top-level issues
    from retriever import get_hf_embeddings

    documents = []

    print(f"Processing and inserting {len(df)} records dynamically into MongoDB native index...")
    for idx, row in df.iterrows():
        doc_parts = []
        metadata = {}
        
        for col in df.columns:
            val = _norm_value(str(row[col]))
            
            # If it's a known categorical field, inject it into exact metadata
            if col in categorical_fields:
                metadata[col] = val
                
            if val != "Unknown":
                doc_parts.append(f"{col}: {val}")

        doc_text = " || ".join(doc_parts)
        
        documents.append({
            "text": doc_text,
            **metadata
        })

    # Massive speedup: Insert standard JSON without computing machine-learning density vectors
    if documents:
        # We can insert chunks of 500 to alleviate rapid Atlas connection loads
        batch_size = 500
        for i in range(0, len(documents), batch_size):
            collection.insert_many(documents[i:i+batch_size])

    print(f"Ingestion complete! Successfully natively indexed {len(documents)} records in MongoDB Atlas.")
    return len(documents)

if __name__ == "__main__":
    parse_and_ingest()
