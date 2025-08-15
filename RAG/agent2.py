from __future__ import annotations

"""
agent2.py – Community‑Engagement Agent, now with **local** Llama‑3.2‑1B prompt‑optimizer
-------------------------------------------------------------------------------
Changes vs. the original no‑LLM version
• Adds a *tiny* local‑LLM rewrite step that converts the user’s raw query into a retrieval‑friendly one.
• Keeps everything else (RAG collections, sentiment tagger, return format) **unchanged**.

Assumptions
• You have llama‑cpp‑python installed and a quantised model file named
  `llama3.2:1b-instruct-q4_0.gguf` (or point LLAMA_MODEL_PATH env‑var to it).
• The model accepts plain text and returns a single best completion.
"""

import os
import json
import requests
import asyncio
from typing import Dict, Any, List
from state import State
from langchain_ollama.llms import OllamaLLM

# ── Llama‑3.2‑1B set‑up ────────────────────────────────────────────


# ── MCP helper ─────────────────────────────────────────────────────
MCP_BASE = os.getenv("MCP_BASE_URL", "http://localhost:8002")
MCP_API = os.getenv("MCP_API_KEY")


def _post(path: str, payload: Dict[str, Any], timeout: float = 15.0) -> Any:
    url = f"{MCP_BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if MCP_API:
        headers["Authorization"] = f"Bearer {MCP_API}"
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

# ── Main agent entry point ─────────────────────────────────────────


async def agent_2(state: State) -> Dict[str, List[str]]:
    """Return news RAG docs with sentiment tags — now using optimized query."""
    opt_query: str = state["opt_query"]

    # 1. Community‑only vector search
    rag_resp = _post("/rag", {
        "query": opt_query,
        "collections": [
            "newsapi_embeddings",
            "vulturetaylor_embeddings",
            "guardian_beyonce_embeddings",
            "news_beyonce_embeddings",
            "newsapi_embeddings",
            "tmz_embeddings",
            "tmz_billie_embeddings",
            "tmz_sza_embeddings",
            "newsapi_straykids_embeddings",
           "dc_straykids_embeddings", 
           "dc_straykids_embeddings2",
            
            # "change_petitions_embeddings",
            "nbc_straykids_embeddings",
            

        ],
        "top_k": 6,
    })
    docs = rag_resp.get("results", [])
    # Ensure each doc has a top-level 'id' for evaluation
    for d in docs:
        if "id" not in d:
            meta_id = d.get("metadata", {}).get("id")
            if meta_id:
                d["id"] = meta_id
            d["segment"] = "news"
    doc_ids = [d["id"] for d in docs if "id" in d]

    if not docs:
        return {"response": ["[]"], "prompt": []}


    # 3. Serialize for router
    return {"response": [json.dumps(docs)]}