from __future__ import annotations
from typing import Dict, List
from langchain_ollama.llms import OllamaLLM
from state import State

async def narrative_agent(state: State) -> Dict[str, str]:
    """
    Takes the summary output from the summarization agent and generates:
    - a narrative (story-like synthesis)
    - a prediction or recommended action
    """
    # Try to get the summary from state
    summary = state.get("final_response") or state.get("summary") or ""
    print("summary ", summary)
    query = state.get("query", "")
    print("query ", query)

    # The Narrative Prompt, version 4.4 by Team ahhhhh-gpu
    prompt = f"""
You are a narrative strategist. Given the following summary of insights, write:
1. A compelling narrative that weaves together the key points, trends, sentiment spikes, and notable people or events from the summary specifically in relation to {query}.
- The narrative should extrapolate plot points that are based off the summary points.
- If there is any spike or change in sentiment, reference any/all specific events (by name) that are associated with it, and create a sub-plot (ex. What happened at the tour? What were people thinking? Why was it successful or not?)
- The narrative should briefly explain a likely outcome based on the summary. 
2. A prediction or recommended action for the user, based on the summary and your analysis.
- This should be at least 7 sentences.
- You must **always** make a determination about whether a lawsuit should be filed against the relevant artist. If the narrative and sentiment paint a negative picture of the artist — especially if there's evidence of misconduct, controversy, or harm — say that a lawsuit **should be considered**. If the overall picture is positive or inconclusive, say "No lawsuit recommended."

- Include a section discussing related names and associated places with the query.

User query: {query}

Summary:
{summary}

Respond in this format:
Narrative: <your narrative>
Recommendation: <your prediction or recommended action>
Your response should not contain bullet points.
If you cannot create a narrative, try again by rephrasing the summary.
Do not repeat the example.

Your response should look something like this:

"""
    llm = state["llm"]
    lock = state["ollama_lock"]
    print("[narrative_agent] Invoking LLM for narrative and recommendation...")
    result = await llm.ainvoke(prompt)
    print("[narrative_agent] LLM call complete")

    
    # Try to parse the result into narrative and recommendation
    narrative, recommendation = "", ""
    if "Narrative:" in result and "Recommendation:" in result:
        parts = result.split("Recommendation:", 1)
        narrative = parts[0].replace("Narrative:", "").strip()
        recommendation = parts[1].strip()
    # If not actionable content, at least try and offer some sort of narrative
    else:
        narrative = result.strip()
        recommendation = "(No explicit recommendation found.)"

    print(f"\n[NARRATIVE AGENT OUTPUT]\nNarrative: {narrative}\nRecommendation: {recommendation}\n")

    return {
        "narrative": narrative,
        "recommendation": recommendation
    }
