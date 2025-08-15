#!/usr/bin/env python3
"""
batch_eval_ids.py
-----------------
Evaluate RAG/agent1 on HotpotQA-style grouped multi-doc file.

Input : hotpot_grouped_multidoc.jsonl
         { "query": "...",
           "answer": "...",
           "group": "...",
           "supporting_contexts": [
               {"id": "doc123", "source": "...", "text": "..."},
               ...
           ] }

Output: hotpot_predictions_ids.jsonl
         (adds "prediction_doc_ids" + "hit" boolean to each record)

Metric: hit-rate = share of queries where at least one predicted doc-ID
        overlaps the gold supporting_context IDs.

Author: you
"""

import json, asyncio
from typing import Any
from pathlib import Path

import aiofiles
from tqdm.asyncio import tqdm

# --- import your agent ---------------------------------------------------
# Make sure RAG/ is a package (has __init__.py) or add it to sys.path.
from agent1 import agent_1              # async def agent_1(state) -> dict
from state  import State                # your project’s State TypedDict

# ------------------------------------------------------------------------
IN_PATH   = Path("hotpot_grouped_multidoc.jsonl")
OUT_PATH  = Path("hotpot_predictions_ids.jsonl")
BATCH_SZ  = 8                               # tweak for CPU / I/O limits

GOLD_ID_FIELD  = "id"                       # inside each supporting_context
PRED_ID_FIELD  = "original_id"                       # inside each doc returned by agent_1
# ------------------------------------------------------------------------

async def run_one(line: str, idx: int) -> str:
    """Run agent_1 on a single record and attach prediction IDs + hit flag."""
    rec   = json.loads(line)
    query = rec["query"]

    # -------- gold IDs ---------------------------------------------------
    gold_ids = {ctx[GOLD_ID_FIELD] for ctx in rec["supporting_contexts"]}

    # -------- call agent_1 ----------------------------------------------
    state: State = {"query": query}         # minimal state needed
    try:
        result = await agent_1(state)       # {"response": ["json-string"]}
    except Exception as e:
        print(f"[ERROR {idx}] agent_1 failed → {e}")
        rec["prediction_doc_ids"] = []
        rec["hit"]                = False
        return json.dumps(rec)

    docs      = json.loads(result["response"][0])
    pred_ids  = [d.get(PRED_ID_FIELD) for d in docs]

    # -------- metric & debug --------------------------------------------
    hit = bool(gold_ids.intersection(pred_ids))
    if not hit:
        print(f"[MISS {idx}] {query[:60]}…")
        print(f"    gold={list(gold_ids)[:4]}  pred={pred_ids[:4]}\n")

    # -------- attach + return -------------------------------------------
    rec["prediction_doc_ids"] = pred_ids
    rec["hit"]                = hit
    return json.dumps(rec)

async def main() -> None:
    total, hits = 0, 0
    async with aiofiles.open(IN_PATH,  "r") as fin, \
               aiofiles.open(OUT_PATH, "w") as fout:

        batch: list[tuple[str, int]] = []
        idx = 0

        async for line in fin:
            batch.append((line, idx))
            idx += 1

            if len(batch) == BATCH_SZ:
                for out in await tqdm.gather(
                        *[run_one(l, i) for l, i in batch],
                        desc="eval", leave=False):
                    await fout.write(out + "\n")
                    hits  += json.loads(out)["hit"]
                    total += 1
                batch.clear()

        # flush any remaining records
        if batch:
            for out in await tqdm.gather(
                    *[run_one(l, i) for l, i in batch],
                    desc="eval", leave=False):
                await fout.write(out + "\n")
                hits  += json.loads(out)["hit"]
                total += 1

    print(f"\nHit-rate: {hits}/{total} = {hits/total:.2%}")

if __name__ == "__main__":
    asyncio.run(main())
