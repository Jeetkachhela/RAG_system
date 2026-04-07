import os
from pymongo import MongoClient


def main():
    uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGODB_DB_NAME", "kanan_rag")
    collection_name = os.getenv("AGENTS_COLLECTION_NAME", "kanan_agents")

    if not uri:
        raise SystemExit("MONGODB_URI is required.")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    db = client[db_name]
    col = db[collection_name]

    # Create text indexes that help fallback queries / filters
    col.create_index("account_name")
    col.create_index("rank")
    col.create_index("city")
    col.create_index("state")
    col.create_index("zone")
    col.create_index("category")
    col.create_index("active")
    col.create_index("bdm")
    col.create_index("team")

    # Atlas Vector Search uses an Atlas Search index (not a normal MongoDB index).
    # This command works on Atlas clusters that support Search indexes.
    try:
        db.command(
            {
                "createSearchIndex": collection_name,
                "name": "vector_index",
                "definition": {
                    "mappings": {
                        "dynamic": False,
                        "fields": {
                            "embedding": {
                                "type": "vector",
                                "dimensions": 384,
                                "similarity": "cosine",
                            },
                            "text": {"type": "string"},
                            "account_name": {"type": "string"},
                            "rank": {"type": "string"},
                            "city": {"type": "string"},
                            "state": {"type": "string"},
                            "zone": {"type": "string"},
                            "category": {"type": "string"},
                            "active": {"type": "string"},
                            "bdm": {"type": "string"},
                            "team": {"type": "string"},
                        },
                    }
                },
            }
        )
        print("Requested creation of Atlas Search vector index: vector_index")
    except Exception as e:
        print(f"Could not create Atlas Search index via command: {e}")
        print("Create it in Atlas UI instead (Search Indexes) with name 'vector_index' on field 'embedding'.")

    print("Done.")


if __name__ == "__main__":
    main()

