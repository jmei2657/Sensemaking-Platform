from __future__ import annotations

import json
import textwrap
from typing import Any, Dict, List

import requests
from langchain_ollama.llms import OllamaLLM
from dateutil import parser as date_parser
from state import State
import numpy as np

# ── Config ──────────────────────────────────────────────────────────
MAX_SNIPPETS = 3  # per segment
MAX_PROMPT_TOK = 1500  # rough whitespace-token safeguard
TOOL_API_URL = "http://localhost:8002"


def get_date_after_cutoff(meta):
    cutoff = date_parser.parse("2024-06-07")
    date_str = meta.get("date") if meta else None
    if date_str:
        try:
            dt = date_parser.parse(date_str)
            # more recent, higher score
            return dt if dt > cutoff else None
        except Exception:
            return None
    return None


# -------------------------------------------------------------------
# Helper: pick representative snippets
# -------------------------------------------------------------------
def pick_snippets(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Select most representative docs by |sentiment.score| then distance."""

    def score(doc: Dict[str, Any]):
        sent = doc.get("sentiment", {})
        mag = abs(sent.get("score", 0))
        dist = doc.get("distance", 1.0)
        # larger magnitude first, smaller dist
        return (-mag, dist)

    return sorted(docs, key=score)[:MAX_SNIPPETS]


# -------------------------------------------------------------------
# Helper: render snippet block (Community / News / Music)
# NOTE: No instructions here; pure data so we don't repeat in the main prompt.
# -------------------------------------------------------------------
def make_prompt(
    query: str,
    community: List[Dict[str, Any]],
    news: List[Dict[str, Any]],
    music: List[Dict[str, Any]],
) -> str:
    def section(title: str, items: List[Dict[str, Any]]) -> str:
        if not items:
            return f"### {title} (0 docs)\nNone."
        lines = [f"### {title} ({len(items)} docs)"]
        for idx, doc in enumerate(items, start=1):
            sent_label = doc.get("sentiment", {}).get("label", "UNK")
            meta = doc.get("metadata", {}) or {}
            title_txt = meta.get("title") or "Untitled"
            snippet = (doc.get("document", "") or "").strip().replace("\n", " ")
            if len(snippet) > 250:
                snippet = snippet[:250] + "…"
            lines.append(f"{idx}. ({sent_label}) {title_txt} – {snippet}")
        return "\n".join(lines)

    block = "\n\n".join(
        [
            f"USER_QUERY: {query}",
            section("Community View", community),
            section("News View", news),
            section("Music View", music),
        ]
    )

    # Hard cut if somehow exceeds limit (approx by whitespace tokens)
    if len(block.split()) > MAX_PROMPT_TOK:
        block = " ".join(block.split()[:MAX_PROMPT_TOK]) + " …"
    return block


# -------------------------------------------------------------------
# Helper: ask LLM which extra tools to call
# -------------------------------------------------------------------
async def llm_decide_tools(
    llm, query: str, segment: str, docs: List[Dict[str, Any]]
) -> List[str]:
    """Use LLM to decide which tools to call for a segment."""
    doc_titles = [d.get("metadata", {}).get("title", "Untitled") for d in docs[:3]]
    doc_snippets = [d.get("document", "")[:100] for d in docs[:3]]
    context = "\n".join(f"- {t}: {s}" for t, s in zip(doc_titles, doc_snippets))
    tool_list = ["geolocation", "sentiment", "ner"]
    tool_str = ", ".join(tool_list)

    prompt = (
        f"You are a tool selector for an agent.\n"
        f"User query: {query}\n"
        f"Segment: {segment}\n"
        f"Here are some relevant documents (title: snippet):\n{context}\n"
        f"Available tools: {tool_str}.\n"
        "Which tools should be called to best answer the query? "
        "geolocation identifies places; "
        "sentiment detects polarity; "
        "ner extracts notable persons.\n"
        "Reply with a comma-separated list of tool names (from the available tools) only."
    )

    resp = await llm.ainvoke(prompt)
    tools = [t.strip() for t in resp.lower().split(",") if t.strip() in tool_list]

    # dedupe preserving order
    out, seen = [], set()
    for t in tools:
        if t not in seen:
            out.append(t)
            seen.add(t)

    if "sentiment" not in seen: # or "ner" not in seen:
        out.append("sentiment")
       # out.append("ner")  # take out after testing

    return out


# -------------------------------------------------------------------
# Helper: call external analytics tools
# -------------------------------------------------------------------
# def call_tool(tool: str, collection: str, docs, top_k: int = 5):
def call_tool(tool: str, collection: str, docs, top_k=None):
    """Call local HTTP tool endpoints and return parsed list (or [])."""
    url = TOOL_API_URL

    try:
        # if tool == "trend":
        #     payload = {"collection": collection}
        #     print(f"[summarization_agent] [TOOL CALL] trend_tool payload: {payload}")
        #     resp = requests.post(f"{url}/trend_tool", json=payload)
        #     resp.raise_for_status()
        #     data = resp.json()
        #     print(f"[summarization_agent] [TOOL RESPONSE] trend_tool: {data}")
        #     return data.get("trends", [])

        if tool == "geolocation":
            payload = {"docs": docs}
            print(
                f"[summarization_agent] [TOOL CALL] geolocation_tool payload: {payload}"
            )
            resp = requests.post(f"{url}/geolocation_tool", json=payload)
            resp.raise_for_status()
            data = resp.json()
            print(f"[summarization_agent] [TOOL RESPONSE] geolocation_tool: {data}")
            return data.get("locations", [])

        if tool == "sentiment":
            # payload = {"docs": docs, "top_k": top_k}
            payload = {"docs": docs}
            print(
                f"[summarization_agent] [TOOL CALL] sentiment_tool payload: {payload}"
            )
            resp = requests.post(f"{url}/sentiment_tool", json=payload)
            resp.raise_for_status()
            data = resp.json()
            print(data)
            print(f"[summarization_agent] [TOOL RESPONSE] sentiment_tool: {data}")
            return data.get("sentiments", [])

        if tool == "ner":
            payload = {"docs": docs}
            print(
                f"[summarization_agent] [TOOL CALL] ner_person_tool payload: {payload}"
            )
            resp = requests.post(f"{url}/ner_person_tool", json=payload)
            resp.raise_for_status()
            data = resp.json()
            print(f"[summarization_agent] [TOOL RESPONSE] ner_person_tool: {data}")
            return data.get("persons", [])

    except Exception as e:
        print(f"[summarization_agent] [TOOL ERROR] {tool} ({docs}): {e}")

    return []  # fallthrough


# -------------------------------------------------------------------
# Main summarization agent
# -------------------------------------------------------------------
async def summarization_agent(state: State) -> Dict[str, List[str]]:
    """
    Aggregate RAG payloads, call analytic tools, and summarize via DeepSeek R1.
    Returns state update: {"final_response": summary_text}.
    """
    query = state["query"]
    payloads = state["response"]
    print("[summarization_agent] received", len(payloads), "payload strings")

    # 1. Parse payloads into segment buckets -----------------------------------
    comm_docs: List[Dict[str, Any]] = []
    news_docs: List[Dict[str, Any]] = []
    music_docs: List[Dict[str, Any]] = []

    for idx, p in enumerate(payloads, 1):
        try:
            docs = json.loads(p)
            print(f"[summarization_agent] payload {idx} → {len(docs)} docs")
        except Exception as e:
            print("[summarization_agent] JSON parse error:", e)
            continue

        for d in docs:
            seg = d.get("segment", "unknown")
            if seg == "community":
                comm_docs.append(d)
            elif seg == "news":
                news_docs.append(d)
            elif seg == "music":
                music_docs.append(d)

    print(
        "[summarization_agent] totals | community:",
        len(comm_docs),
        "| news:",
        len(news_docs),
        "| music:",
        len(music_docs),
    )

    if not (comm_docs or news_docs or music_docs):
        return {"final_response": "No data to summarize."}

    # After comm_docs, news_docs, music_docs are populated

    # print("ahh doc source", docs[0].get("source"))

    # 2. Decide which analytic tools to call (community + news only) -----------
    llm: OllamaLLM = state["llm"]

    tool_results: Dict[str, Dict[str, List]] = {}
    for segment, docs in [
        ("community", comm_docs),
        ("news", news_docs),
        ("music", music_docs),
    ]:
        if not docs:
            continue

        collections = list({d.get("source") for d in docs if d.get("source")})

        print(collections)

        tools = await llm_decide_tools(llm, query, segment, docs)

        print("ahhhh segment ", segment)

        print(f"[summarization_agent] LLM selected tools for {segment}: {tools}")
        print(docs)
        seg_results: Dict[str, List] = {}
        for tool in tools:
            seg_results[tool] = []
            if tool == "sentiment" or tool == "ner" or tool == "geolocation":
                print(
                    f"[summarization_agent] Calling tool '{tool}' for "
                    f"segment '{segment}'"
                )
                # seg_results[tool].extend(call_tool(tool, None, docs, top_k=12)) #test for now
                seg_results[tool].extend(call_tool(tool, None, docs))  # test for now
            # probably taking this out
            else:
                for collection in collections:
                    print("formatting issue if thsi is called")
                    print(
                        f"[summarization_agent] Calling tool '{tool}' for "
                        f"segment '{segment}'"
                    )
                    seg_results[tool].extend(call_tool(tool, collection, docs=None))

        tool_results[segment] = seg_results
    updated_docs = []
    for segment, docs in [
        ("community", comm_docs),
        ("news", news_docs),
        ("music", music_docs),
    ]:
        if not docs:
            continue

        print(f"[debug] segment = {segment}")
        print(f"[debug] len(docs) = {len(docs)}")
        # print(f"[debug] len(dates) = {len(dates)}")
        print(f"[debug] len(sentiment) = {len(tool_results[segment]['sentiment'])}")
        print(f"sentiment {tool_results[segment]['sentiment']} ")

        dates = [get_date_after_cutoff(doc.get("metadata")) for doc in docs]

        # we are going to need to take out top k everywhere

        if len(docs) != len(tool_results[segment]["sentiment"]):
            print("thats fine ig")
            # print("that's probably an issue")

        updated_docs.extend(zip(docs, dates, tool_results[segment]["sentiment"]))
    print("updated docs")
    print(updated_docs)
    cleaned_docs = [doc for doc in updated_docs if doc[1] is not None]
    cleaned_docs.sort(key=lambda x: x[1])
    print(cleaned_docs)

    # Bin cleaned_docs into two-week periods from cutoff date
    from datetime import timedelta, datetime

    cutoff = date_parser.parse("2024-06-07")
    if cleaned_docs:
        last_date = cleaned_docs[-1][1]
    else:
        last_date = cutoff
    bin_size = timedelta(days=14)
    # Calculate number of bins needed
    num_bins = ((last_date - cutoff).days // 14) + 1
    bins = {i: [] for i in range(num_bins)}

    for doc_tuple in cleaned_docs:
        date = doc_tuple[1]
        if date >= cutoff:
            bin_index = (date - cutoff).days // 14
            bins[bin_index].append(doc_tuple)
    # Optionally, label bins with date ranges
    bin_labels = {}
    for i in range(num_bins):
        start = cutoff + i * bin_size
        end = start + bin_size - timedelta(days=1)

        doc_tuples = bins[i]

        for doc in doc_tuples:
            print("sentiment field", doc[2])
        # if doc_tuples:
        sentiment_scores = [
            doc[2] for doc in doc_tuples if isinstance(doc[2], (int, float))
        ]

        print("sentiment scores, ", sentiment_scores)

        # if sentiment_scores:
        #     mean_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        #     print("mean_sentiment ", mean_sentiment)

        # else:
        #     mean_sentiment = 0 #idk if empty

        if not sentiment_scores:
            continue  # do not include if empty

        mean_sentiment = sum(sentiment_scores) / len(sentiment_scores)
        print(f"[BIN {i}] mean_sentiment = {mean_sentiment:.3f}")

        bin_labels[f"{start.date()} to {end.date()}"] = {
            "docs": doc_tuples,
            "mean_sentiment": mean_sentiment,
        }

        # bin_labels[f"{start.date()} to {end.date()}"] = bins[i]
    print("bin labels")
    print(bin_labels)
    print(type(bin_labels))

    all_mean_sentiments = [data["mean_sentiment"] for data in bin_labels.values()]
    mean_sent = np.mean(all_mean_sentiments)
    std_sent = np.std(all_mean_sentiments)

    threshold = mean_sent + 2 * std_sent  # maybe increase from 2
    print(
        f"\n[spike detection] Mean: {mean_sent:.4f}, Std: {std_sent:.4f}, Threshold: {threshold:.4f}"
    )
    # pos

    # sentiment_spikes = []
    # for label, data in bin_labels.items():
    #     if data["mean_sentiment"] > threshold:
    #         print(data["docs"])
    #         sentiment_spikes.append((label, data["mean_sentiment"]))
    sentiment_spikes = []
    for label, data in bin_labels.items():
        if data["mean_sentiment"] > threshold:
            print(f"\n[SPIKE] {label} — mean sentiment: {data['mean_sentiment']:.3f}")
            print("Top documents in this bin:")
            doc_list = []
            for i, doc_tuple in enumerate(data["docs"]):
                doc = doc_tuple[0]
                text = doc.get("document", "[no text]")
                doc_list.append(
                    f"Doc {i+1}: {text[:300]}{'...' if len(text) > 300 else ''}"
                )
                # print(f"  Doc {i+1}: {text[:300]}{'...' if len(text) > 300 else ''}")  # limit to 300 chars
            # sentiment_spikes.append((label, data["mean_sentiment"]))

            sentiment_spikes.append(
                {
                    "range": label,
                    "mean_sentiment": data["mean_sentiment"],
                    "docs": "\n".join(doc_list),
                }
            )

    print("\n[Sentiment Spikes Detected]")
    for label, score in sentiment_spikes:
        print(f" {label} — mean sentiment: {score:.3f}")

    #     print("Top documents:")
    # for i, doc_tuple in enumerate(data["docs"][:5]):  # adjust the slice to show more/less
    #     doc_text = doc_tuple[0].get("document") or "[no text]"
    #     print(f"  Doc {i+1}: {doc_text[:200]}{'...' if len(doc_text) > 200 else ''}")

    # 3. Representative snippet selection --------------------------------------
    comm_sel = pick_snippets(comm_docs)
    news_sel = pick_snippets(news_docs)
    music_sel = pick_snippets(music_docs)
    print(
        "[summarization_agent] selected",
        len(comm_sel),
        "community snippets &",
        len(news_sel),
        "news snippets &",
        len(music_sel),
        "music snippets",
    )

    # 4. Format tool results ----------------------------------------------------
    # (token-lean summary of tool results)
    tool_results_lines = ["TOOL RESULTS"]
    for segment, results in tool_results.items():
        tool_results_lines.append(f"\n{segment.title()} tools:")
        for tool, res in results.items():
            if tool == "geolocation" and res:
                max_count = max(loc.get("count", 0) for loc in res)
                top_locs = [loc for loc in res if loc.get("count", 0) == max_count]
                for loc in top_locs:
                    tool_results_lines.append(
                        f"- {tool}: {loc.get('location')} "
                        f"(count: {loc.get('count')}, ex: {loc.get('examples')})"
                    )
            elif tool == "ner" and res:
                names = [p["name"] for p in res if isinstance(p, dict) and "name" in p]
                tool_results_lines.append(
                    f"- {tool}: {', '.join(names) if names else res}"
                )
            else:
                tool_results_lines.append(f"- {tool}: {res}")

    sentiment_analysis = []
    if "sentiment_spikes" in tool_results and tool_results["sentiment_spikes"]:
        sentiment_analysis.append("Sentiment Spikes:")
        for spike in tool_results["sentiment_spikes"]:
            tool_results_lines.append(
                f"- Range: {spike['range']}, Mean Sentiment: {spike['mean_sentiment']:.3f}, Related Docs: {spike["docs"]}"
            )

    tool_results_str = "\n".join(tool_results_lines)
    sentiment_analysis_str = "\n".join(sentiment_analysis)
    # 5. Build snippet data block ----------------------------------------------
    snippet_block = make_prompt(query, comm_sel, news_sel, music_sel)

    # 6. Build full LLM prompt --------------------------------------------------
    # Concise, single-instruction block tuned for DeepSeek-R1
    instructions = textwrap.dedent(
        """
    INSTRUCTIONS:
    You are InsightSynth. Use only the context above.

    STRICT OUTPUT FORMAT (plain text, no bullet characters):
    Takeaway: <4‑5 sentences – headline facts + spike highlight.>
    Spike: <5‑8 sentences – who‑did‑what‑where‑when, sentiment ↑/↓ value, ≥1 concrete event(s) causing the spike, audience reaction.>
    Community: <5‑8 sentences – top themes, quoted phrases (≤8 words in “quotes”), metrics (~ if approx.), notable names, disagreements.>
    News: <5‑8 sentences – media framing, key details, numeric impacts, stakeholders quoted.>
    Music: <5‑8 sentences – releases, business moves, management context, chart/stream numbers.>
    WatchNext: <2‑3 sentences – forward‑looking signal or risk.>

    WRITING RULES
    1. Name the event up front: first clause says WHO did WHAT, WHERE, WHEN (YYYY‑MM‑DD).
    2. Quote vivid doc wording sparingly (“…”); otherwise paraphrase.
    3. When a number appears in any doc, keep it and prefix with “~” if approximate.
    4. Summarise disagreements clearly (e.g., “Some fans praised… while others called it tone‑deaf.”).
    5. If details truly absent, write “Details unclear” rather than guessing.
    6. Sentiment‑spike section must reference the exact bin date/time and link it to specific event(s) from the docs.
    7. Think silently; do NOT output <think> or chain‑of‑thought.
    8. No bullet characters (‘-’, ‘*’, ‘•’) anywhere.
    """
    ).strip()


    prompt = (
        "ROLE: InsightSynth – integrate tool signals + doc snippets to answer the user query.\n"
        f"USER_QUERY: {query}\n\n"
        "=== TOOL SIGNALS ===\n"
        f"{tool_results_str}\n\n"
        "=== DOC SNIPPETS ===\n"
        f"{snippet_block}\n\n"              # this apparently contains the prompt?? 
        "=== SENTIMENT SPIKES AND RELATED DOCUMENTS ===\n"
        f"{sentiment_analysis_str}\n\n"     # this has bins w/ sentiment spike (there might not be a sentiment spike!)
        f"{instructions}\n"
    )

    # Prompt length safeguard (approx)
    if len(prompt.split()) > MAX_PROMPT_TOK:
        prompt = " ".join(prompt.split()[:MAX_PROMPT_TOK]) + " …"

    print("[summarization_agent] prompt token count:", len(prompt.split()))

    # 7. LLM call ---------------------------------------------------------------
    print("[summarization_agent] invoking DeepSeek R1 model …")
    summary = await llm.ainvoke(prompt)
    print("[summarization_agent] LLM call complete")

    # 8. Assemble final response ------------------------------------------------
    # Downstream narrative_agent expects 'final_response' to hold summary text.
    # (We intentionally do NOT prepend tool_results_str here to reduce redundancy.)
    final_response = summary.strip()

    return {"final_response": final_response}
