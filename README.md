# Kanan RAG System

## Quick start

### Backend
1. Create `backend/.env` based on `backend/.env.example`
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Run API:

```bash
uvicorn main:app --reload --port 8001
```

### Frontend
1. Create `frontend/.env` based on `frontend/.env.example` (set `VITE_API_BASE`)
2. Install and run:

```bash
cd frontend
npm install
npm run dev
```

## Authentication
- First ever `POST /api/auth/register` user becomes **admin** (bootstrap).
- After that, registration is **admin-only** (use an admin token).

## MongoDB Atlas Vector Search

This project uses an Atlas Search vector index named **`vector_index`** on field **`embedding`** (dimensions **384**, cosine similarity).

### Create indexes (script)

```bash
cd backend
python scripts/create_atlas_indexes.py
```

If index creation via command is not permitted on your Atlas tier, create the Search Index in the Atlas UI with the same settings.

## Security notes (public deployment)
- Set `ENV=production` and provide a strong `JWT_SECRET` (backend will refuse to start without it).
- Set `CORS_ORIGINS` to your real frontend domains.

