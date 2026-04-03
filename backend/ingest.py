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
    df.fillna("N/A", inplace=True)

    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

    # Drop existing collection for a clean re-ingest (safe for ~2500 rows)
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print("Dropped existing collection for fresh ingestion.")
    except Exception:
        pass

    # Use ChromaDB's default embedding function (ONNX MiniLM-L6-v2, no PyTorch needed)
    collection = client.create_collection(name=COLLECTION_NAME)

    documents = []
    ids = []
    metadatas = []

    print(f"Processing {len(df)} records...")
    for idx, row in df.iterrows():
        doc_parts = []
        for col in df.columns:
            val = str(row[col]).strip()
            if val and val.upper() != "N/A" and val.lower() != "nan":
                doc_parts.append(f"{col}: {val}")

        doc_text = " || ".join(doc_parts)

        metadata = {
            "account_name": str(row.get('K-Apply Account Name', 'N/A')),
            "rank": str(row.get('Rank', 'N/A')),
            "city": str(row.get('City', 'N/A')),
            "state": str(row.get('State', 'N/A')),
            "zone": str(row.get('Zone', 'N/A')),
            "category": str(row.get('Category Type', 'N/A')),
            "active": str(row.get('Active', 'N/A')),
        }

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

    print(f"Ingestion complete! {len(documents)} records indexed.")
    return len(documents)


if __name__ == "__main__":
    parse_and_ingest()
