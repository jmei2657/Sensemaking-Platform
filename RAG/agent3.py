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
    opt_query = state["opt_query"]
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
