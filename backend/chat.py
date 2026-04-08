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

SYSTEM_PROMPT = """You are Kanan, an intelligent, helpful, and conversational AI assistant for managing Kanan's Agent data and providing general information about Kanan International.
You have access to a large context block retrieved from the database of Kanan Agents.
Use the provided `DATABASE CONTEXT` to answer the user's questions specifically and accurately.

{company_profile_block}

CRITICAL INSTRUCTIONS:
1. Rely primarily on the provided context. If asked to summarize or aggregate (e.g., "what are the zones?"), confidently extract the unique patterns you see in the provided agents rather than requiring an explicit master list to exist.
2. The context contains up to 40 agents retrieved via our Dual-Engine system. Scan them carefully.
3. If asked to list agents, provide a well-formatted Markdown table or bulleted list.
4. If the entity requested categorically does not exist in the context, politely state that you cannot find this information in the current database subset.
5. You must remember the conversation history so you can properly answer follow-up queries.
6. ADOPT A HUMAN-LIKE, WARM TONE. Act like a helpful human consultant, not a stiff robotic machine. Be conversational, empathetic, and chatty while still delivering precise data. You can express enthusiasm or ask friendly clarifying questions.

{context_block}
"""

def _get_company_profile():
    # Helper to avoid blocking the async event loop during connection setup
    profile = ""
    try:
        from pymongo import MongoClient
        mongodb_uri = os.getenv("MONGODB_URI")
        if mongodb_uri:
            client_mongo = MongoClient(mongodb_uri, serverSelectionTimeoutMS=2000)
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
