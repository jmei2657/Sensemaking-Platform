from __future__ import annotations

"""
agent1.py – Community‑Engagement Agent, now with **local** Llama‑3.2‑1B prompt‑optimizer
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
import re
from typing import Dict, Any, List
from state import State
from langchain_ollama.llms import OllamaLLM

# ── Llama‑3.2‑1B set‑up ────────────────────────────────────────────


# Optimized, token-lean prompt for llama3.2:1b-instruct-q4_0
SYSTEM_PROMPT = (
    "Community Query Rewriter\n"
    "Convert the user question: about a public figure into ONE plain search sentence.\n"
    "Rules for the rewritten prompt (goes in the “rewritten” field):\n"
    "  • Begin with the person’s full name in double quotes. This is incredibly important, include their name first\n"
    "  • Add 2–4 meaning-bearing words from the question; drop filler words.\n"
    "  • Use spaces only—no punctuation, Boolean words, or extra text.\n"
    "Output format (as valid JSON):\n"
    "  {"
    "    \"reasoning\": \"<your chain of thought here>\","
    "    \"rewritten\": \"<the one-sentence search prompt here>\""
    "  }"
    "Reply with exactly that JSON object and nothing else."
)


async def optimize_query_for_community(user_query: str, state: State) -> str:
    """Rewrite *user_query* into a precise search string for community RAG."""
    full_prompt = f"<s>[INST] {SYSTEM_PROMPT}\nUser question: {user_query}\n[/INST]"

    # llm = OllamaLLM(model="deepseek-r1:latest")
    llm = state["llm"]
    lock = state["ollama_lock"]
    # 1. Invoke the LLM
    async with lock:
        raw = await llm.ainvoke(full_prompt)

    start = raw.find("</think>")
    if start == -1:
        raise ValueError(f"No JSON found in LLM output: {raw!r}")

    # decode just the first JSON object
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(raw[start + raw[start:].find("{"):])
    # data is now a dict with 'reasoning' and 'rewritten'
    print("Agent 1 optimized query: " + data["rewritten"])
    return data["rewritten"]


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


async def agent_1(state: State) -> Dict[str, List[str]]:
    """Return community‑only RAG docs with sentiment tags — now using optimized query."""
    raw_query: str = state["query"]
    try:
        opt_query = await optimize_query_for_community(raw_query, state)
        print(f"[agent1] Raw query: {raw_query}")
        print(f"[agent1] Optimized query: {opt_query}")
    except Exception as e:
        # Fallback to raw query if LLM fails
        print("[agent1] LLM rewrite failed:", e)
        opt_query = raw_query

    # 1. Community‑only vector search
    rag_resp = _post("/rag", {
        "query": opt_query,
        "collections": [
            "reddit_embeddings",
            "reddit_billie_embeddings",
            "reddit_blackpink_embeddings",
            "reddit_straykids_embeddings",
            "reddit_sza_embeddings",
            "popculture_reddit_taylor_embeddings",
            "kpop_reddit_blackpink_embeddings",
            "kpop_reddit_straykids_embeddings",
            "popculture_reddit_billie_embeddings",
            "popculture_reddit_blackpink_embeddings",
            "popculture_reddit_straykids_embeddings",
            "popculture_reddit_sza_embeddings",
            "beyonce_tmz_embeddings",
            "twitter_embeddings",
            "guardian_beyonce_embeddings",
            "popculture_reddit_beyonce_embeddings",
            "reddit_beyonce_embeddings",
            "kpopnoir_reddit_straykids_embeddings"
        ],
        "top_k": 6,
    })
    docs = rag_resp.get("results", [])
    # print("[agent1] Retrieved docs from RAG:", json.dumps(docs))
    # Ensure each doc has a top-level 'id' for evaluation
    for d in docs:
        if "id" not in d:
            meta_id = d.get("metadata", {}).get("id")
            if meta_id:
                d["id"] = meta_id
            d["segment"] = "community"
    doc_ids = [d["id"] for d in docs if "id" in d]

    if not docs:
        return {"response": ["[]"], "prompt": []}


    # 3. Serialize for router
    return {"response": [json.dumps(docs)]}
