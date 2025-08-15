# agent3.py – Music Industry Agent (no-LLM)
# -----------------------------------------
# Router still does:  state["response"] += agent_2(state)["response"]

from __future__ import annotations
import os
import json
import requests
import asyncio
from typing import Dict, Any, List, TypedDict
from state import State
from langchain_ollama.llms import OllamaLLM

# ── Llama‑3.2‑1B set‑up ────────────────────────────────────────────


# Optimized, token-lean prompt for llama3.2:1b-instruct-q4_0
SYSTEM_PROMPT = (
    "Music industry Query Rewriter\n"
    "Convert the user question: about a public figure into ONE plain search sentence relating to the music industry.\n"
    "Rules for the rewritten prompt (goes in the “rewritten” field):\n"
    "  • Begin with the person’s full name in double quotes.\n"
    "  • Add 2–4 meaning-bearing words from the question; drop filler words.\n"
    "  • Use spaces only—no punctuation, Boolean words, or extra text.\n"
    "Output format (as valid JSON):\n"
    "  {"
    "    \"reasoning\": \"<your chain of thought here>\","
    "    \"rewritten\": \"<the one-sentence search prompt here>\""
    "  }"
    "Reply with exactly that JSON object and nothing else."
)


async def optimize_query_for_news(user_query: str, state: State) -> str:
    """Rewrite *user_query* into a precise search string for Music RAG."""
    full_prompt = (
        f"<s>[INST] {SYSTEM_PROMPT}\nUser question: {user_query}\n[/INST]"
    )
    # llm = OllamaLLM(model="deepseek-r1:latest")
    llm = state["llm"]
    lock = state["ollama_lock"]
    async with lock:
        raw = await llm.ainvoke(full_prompt)
    start = raw.find("</think>")
    if start == -1:
        raise ValueError(f"No JSON found in LLM output: {raw!r}")

    # decode just the first JSON object
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(raw[start + raw[start:].find("{"):])
    # data is now a dict with 'reasoning' and 'rewritten'
    return data["rewritten"]
# ── MCP helper -----------------------------------------------------
MCP_BASE = os.getenv("MCP_BASE_URL", "http://localhost:8002")
MCP_API = os.getenv("MCP_API_KEY")


def _post(path: str, payload: Dict[str, Any], timeout: float = 100.0) -> Any:
    url, hdrs = f"{MCP_BASE}{path}", {"Content-Type": "application/json"}
    if MCP_API:
        hdrs["Authorization"] = f"Bearer {MCP_API}"
    resp = requests.post(url, headers=hdrs, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


# ── Collections to search -----------------------------------------
MUSIC_COLLECTIONS = [
    
    "taylornme_embeddings",
    "billboard_embeddings",
    "szanme_embeddings",
    "blackpink_tours_embeddings",
    "sza_tours_embeddings",
    "taylornme_embeddings",
    "ticketmaster_beyonce_events_embeddings",
    "straykids_tours_embeddings",
    "apify_youtube_events_embeddings"
    # "apify_youtube_embeddings"
]

# ── Main agent -----------------------------------------------------


async def agent_3(state: State) -> Dict[str, List[str]]:
    """Return music docs (with sentiment + segment tag) — no LLM."""
    query = state["query"]
    try:
        opt_query = await optimize_query_for_news(query, state)
        print(f"[agent3] Raw query: {query}")
        print(f"[agent3] Optimized query: {opt_query}")
    except Exception as e:
        # Fallback to raw query if LLM fails
        print("LLM rewrite failed:", e)
        opt_query = query

    # 1. Vector search over news collections
    rag_resp = _post("/rag", {
        "query":       opt_query,
        "collections": MUSIC_COLLECTIONS,
        "top_k":       6
    })
    docs = rag_resp.get("results", [])
    # Ensure each doc has a top-level 'id' for evaluation
    for d in docs:
        if "id" not in d:
            meta_id = d.get("metadata", {}).get("id")
            if meta_id:
                d["id"] = meta_id
            d["segment"] = "music"
    doc_ids = [d["id"] for d in docs if "id" in d]

    if not docs:
        return {"response": ["[]"], "prompt": []}
    # 4. Return to proxy
    return {
        "response": [json.dumps(docs)]
    }
