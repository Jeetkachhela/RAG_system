import os
import pandas as pd
import chromadb
from dotenv import load_dotenv

load_dotenv()

EXCEL_FILE_PATH = os.getenv("EXCEL_FILE_PATH", "../K Apply - Accounts Dump - 18.03.2026 (1).xlsx")
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "./chroma_db")
COLLECTION_NAME = "kanan_agents"


def parse_and_ingest():
    """Read the Excel file and ingest all rows into ChromaDB using its default ONNX embedding."""
    if not os.path.exists(EXCEL_FILE_PATH):
        raise FileNotFoundError(f"Excel file not found at {EXCEL_FILE_PATH}")

    print(f"Loading data from {EXCEL_FILE_PATH}...")
    df = pd.read_excel(EXCEL_FILE_PATH, sheet_name='All Agents')
    
    # Pre-processing: Strip all column names and string values
    df.columns = [col.strip() for col in df.columns]
    
    # Fill NA with empty string for normalization, then handle specifics
    df = df.astype(object).fillna("")
    
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

    # Drop existing collection for a clean re-ingest
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print("Dropped existing collection for fresh ingestion.")
    except Exception:
        pass

    collection = client.create_collection(name=COLLECTION_NAME)

    documents = []
    ids = []
    metadatas = []

    print(f"Processing {len(df)} records...")
    for idx, row in df.iterrows():
        doc_parts = []
        metadata = {}
        
        # Mapping specific columns for structured filtering
        # Note: We use .get() to be safe against column name changes
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
            if not val or val.lower() == "nan" or val.lower() == "n/a":
                val = "Unknown"
            metadata[meta_key] = val

        # Build full text for semantic search
        for col in df.columns:
            val = str(row[col]).strip()
            if val and val.lower() not in ["", "nan", "n/a"]:
                doc_parts.append(f"{col}: {val}")

        doc_text = " || ".join(doc_parts)

        documents.append(doc_text)
        metadatas.append(metadata)
        ids.append(f"doc_{idx}")

    # Batch insert into ChromaDB
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        end = min(i + batch_size, len(documents))
        print(f"  Adding batch {i}-{end}...")
        collection.add(
            documents=documents[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end],
        )

    print(f"Ingestion complete! {len(documents)} records indexed with normalization.")
    return len(documents)


if __name__ == "__main__":
    parse_and_ingest()
