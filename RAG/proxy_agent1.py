import json
from ollama import chat
from pydantic import BaseModel
from state import State


class Agents(BaseModel):
    reasoning: dict[str, str]
    agents: list[str]

# SYSTEM_PROMPT = (
#     "Query Rewriter\n"
#     "Convert the user question: about a public figure into ONE plain search sentence.\n"
#     "Rules for the rewritten prompt (goes in the “rewritten” field):\n"
#     "  • Begin with the person’s full name in double quotes. This is incredibly important, include their name first\n"
#     "  • Add 2–4 meaning-bearing words from the question; drop filler words.\n"
#     "  • Use spaces only—no punctuation, Boolean words, or extra text.\n"
#     "Output format (as valid JSON):\n"
#     "  {"
#     "    \"reasoning\": \"<your chain of thought here>\","
#     "    \"rewritten\": \"<the one-sentence search prompt here>\""
#     "  }"
#     "Reply with exactly that JSON object and nothing else."
# )

SYSTEM_PROMPT = (
    "Query Rewriter\n"
    "You are provided with the user's current question *and* their previous queries. "
    "Your task is to convert the new user question about a public figure into ONE plain search sentence.\n"
    "Rules for the rewritten prompt (goes in the 'rewritten' field):\n"
    "  • Begin with the person’s full name in double quotes. This is incredibly important, include their name first\n"
    "  • Add 2–4 meaning-bearing words from the question and, if relevant, incorporate keywords or context from the previous queries. Drop filler words.\n"
    "  • Use spaces only—no punctuation, Boolean words, or extra text.\n"
    "If the new question is similar to recent queries, make the rewritten prompt more specific to avoid redundancy.\n"
    "You will be given the previous queries as a list, and the current question.\n"
    "Output format (as valid JSON):\n"
    "{"
    "  \"reasoning\": \"<your chain of thought here, including how you used previous queries if you did>\","
    "  \"rewritten\": \"<the one-sentence search prompt here>\""
    "}\n"
    "Reply with exactly that JSON object and nothing else."
)


async def optimize_query(user_query: str, state: State) -> str:
    """Rewrite *user_query* into a precise search string for community RAG."""
    full_prompt = f"<s>[INST] {SYSTEM_PROMPT}\nUser question: {user_query}\n[/INST]"

    # llm = OllamaLLM(model="deepseek-r1:latest")
    llm = state["llm"]
    # 1. Invoke the LLM
    raw = await llm.ainvoke(full_prompt)

    start = raw.find("</think>")
    if start == -1:
        raise ValueError(f"No JSON found in LLM output: {raw!r}")

    # decode just the first JSON object
    decoder = json.JSONDecoder()
    data, end = decoder.raw_decode(raw[start + raw[start:].find("{"):])
    # data is now a dict with 'reasoning' and 'rewritten'
    print("Proxy Agent 1 optimized query: " + data["rewritten"])
    return data["rewritten"]

async def proxy_agent1(state: State):
    if not state["agents"]:
        response = chat(
            messages=[
                {
                    "role": "system",
                    "content": """
                        You are an agent classification assistant.
                        Your job is to identify all agents that may help answer a user query, even if only partially.
                        Be inclusive. Select liberally. Do not omit an agent unless it's clearly irrelevant.
                        """,
                },
                {
                    "role": "user",
                    "content": f"""
                    Think step by step.

                    You can choose from 3 agents, each with broad capabilities:

                    1. "community_engagement_agent": Handles anything that might appear on fan sites, forums, social media platforms, or online communities. Use this agent if the topic is likely discussed by fans or the public in informal or interactive settings.

                    2. "news_agent": Handles anything that might be reported, analyzed, or discussed on news sites, blogs, or official media channels. Use this agent for any topic that could be featured in editorial or media coverage.

                    3. "music_industry_agent": Handles the professional and operational side of music, including artists, releases, tours, bookings, production, schedules, and business logistics.

                    Your task:
                    Given the user query below, return only a JSON object with:

                    - "reasoning": a dictionary with keys as the agent names and values as short explanations of why each was or wasn't selected.
                    - "agents": a list of the agents that may help answer the query. Choose agents generously — if there's any chance the agent could provide useful insight or context, include it.

                    Only pick from: ["community_engagement_agent", "news_agent", "music_industry_agent"]

                    If no agent is useful, return an empty list for "agents".

                    Do NOT explain anything else. Do NOT include any text outside the JSON object.

                    Query: {state['query']}
                    """,
                },
            ],
            model="deepseek-r1:latest",
            format=Agents.model_json_schema(),
        )
        result = Agents.model_validate_json(response.message.content)
        print(result)
        opt_query = await optimize_query(state["query"], state)
        return {"agents": result.agents, "opt_query" : opt_query}
    else:
        return {}

# res = []
# with open('test_queries.json') as json_data:
#     d = json.load(json_data)
#     for i in range(0, len(d)):
#         response = getAgents(d[i]["query"])
#         result = Agents.model_validate_json(response.message.content)
#         # print(result)
#         print(f"Ran query #{i + 1}")
#         res.append(
#             {"query": d[i]["query"], "reasoning": result.reasoning, "choices": result.agents})
#     json_data.close()

# with open("results.json", 'w') as json_file:
#     json_file.write(json.dumps(res, indent=4))
