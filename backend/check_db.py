from pymongo import MongoClient
import os
from dotenv import load_dotenv
load_dotenv()
uri = os.getenv("MONGODB_URI")
client = MongoClient(uri, serverSelectionTimeoutMS=5000)
db = client[os.getenv("MONGODB_DB_NAME", "kanan_rag")]

print("=== Collections ===")
print(db.list_collection_names())
print()
print("=== Agent count ===")
print(db["kanan_agents"].count_documents({}))
print()
print("=== Schema profile ===")
schema = db["kanan_schema"].find_one({"type": "schema_profile"})
if schema:
    cats = schema.get("categorical_fields", {})
    print(f"Categorical fields: {list(cats.keys())}")
    print(f"All columns: {schema.get('all_columns', [])}")
else:
    print("NO SCHEMA PROFILE FOUND!")

client.close()
