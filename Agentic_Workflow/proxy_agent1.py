import json
from ollama import chat
from pydantic import BaseModel
from state import State


class Agents(BaseModel):
    reasoning: dict[str, str]
    agents: list[str]


def proxy_agent1(state: State):
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
        return {"agents": result.agents}
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
