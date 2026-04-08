import os
import requests
import json
from groq import AsyncGroq
from dotenv import load_dotenv
from typing import List, Dict
from connectivity import get_current_mode

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = AsyncGroq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = """You are Kanan — a warm, sharp, and genuinely helpful AI consultant who manages Kanan International's agent network data.

Think of yourself as a friendly colleague sitting across the desk, not a search engine. You have personality. You're enthusiastic about helping, you crack the occasional light remark, and you genuinely care about giving the user exactly what they need.

{company_profile_block}

YOUR PERSONALITY & STYLE:
- Speak like a real human consultant would in a casual workplace chat. Use natural phrasing: "Oh absolutely!", "Great question!", "Hmm, let me dig into that...", "Here's what I found 👇"
- NEVER start with "Based on the provided context" or "According to the database". Just answer naturally, like you already know the data.
- Use emojis sparingly but effectively (📊 🏆 ✅ 🔍 💡) to make responses feel alive.
- When listing agents, use clean Markdown tables with bold headers — they look great.
- For analytical questions (zones, rankings, counts), lead with the key insight FIRST, then show the supporting data. Don't just dump raw lists.
- If you genuinely can't find something, be honest and warm: "I couldn't spot that in our current records — want me to try a different angle?"
- Remember past messages in the conversation. Reference them naturally: "Following up on those Gujarat agents you asked about earlier..."
- Keep responses concise but complete. No walls of text. Break things into digestible chunks.

ANALYSIS GUIDELINES:
- When asked about trends or patterns, provide actual insights, not just data. Say "East Zone is dominating with 45% of all Platinum agents" instead of just listing numbers.
- Compare and contrast when relevant: "While Gujarat leads in volume, Maharashtra agents have a higher active rate."
- Suggest follow-up questions the user might find useful: "Want me to break this down by city?"

{context_block}
"""


def _get_company_profile():
    # Helper to avoid blocking the async event loop during connection setup
    profile = ""
    try:
        from pymongo import MongoClient
        mongodb_uri = os.getenv("MONGODB_URI")
        if mongodb_uri:
            # Fix: Native resource cleanup prevents Unclosed Socket leakages spamming the event loop!
            with MongoClient(mongodb_uri, serverSelectionTimeoutMS=2000) as client_mongo:
                db = client_mongo[os.getenv("MONGODB_DB_NAME", "kanan_rag")]
                company_doc = db["company_info"].find_one({"type": "company_profile"})
                if company_doc and "content" in company_doc:
                    profile = f"============= COMPANY PROFILE =============\n{company_doc['content']}\n==========================================="
    except Exception as e:
        print(f"Error loading company profile from MongoDB: {e}")
    return profile

async def generate_chat_stream(messages: List[Dict[str, str]], retrieved_context: str):
    """
    messages: A list of dicts [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    retrieved_context: String chunk retrieved from Vector DB or Static KB.
    """
    # ONLINE PATH (Default): Use Groq (Cloud)
    if not os.getenv("GROQ_API_KEY"):
        yield "Error: GROQ_API_KEY is not set."
        return


    # Load company info from MongoDB asynchronously-safe wrapper
    company_profile = _get_company_profile()

    # Construct the system instruction dynamically
    context_block = f"============= DATABASE CONTEXT =============\n{retrieved_context}\n============================================"
    final_system_prompt = SYSTEM_PROMPT.replace("{context_block}", context_block).replace("{company_profile_block}", company_profile)
    
    # Prepend system prompt to the messages list
    api_messages = [{"role": "system", "content": final_system_prompt}]
    
    # Add the user's conversation history
    for msg in messages:
        # Standardize roles just to be safe
        role = msg.get("role", "user")
        if role not in ["user", "assistant", "system"]:
            role = "user"
            
        # Ensure content is string, handles empty content gracefully
        content = msg.get("content", "")
        if not isinstance(content, str):
            content = str(content)
            
        api_messages.append({"role": role, "content": content})
    
    try:
        stream = await client.chat.completions.create(
            messages=api_messages,
            model="llama-3.3-70b-versatile",
            temperature=0.3,
            max_tokens=800,
            stream=True,
        )
        async for chunk in stream:
            token = chunk.choices[0].delta.content
            if token:
                yield token
    except Exception as e:
        yield f"Error communicating with LLM: {str(e)}"
