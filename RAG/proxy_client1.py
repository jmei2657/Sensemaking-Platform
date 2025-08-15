# from fastmcp import Client
import psycopg2
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama.llms import OllamaLLM
from state import State
from concurrent.futures import ThreadPoolExecutor
import agent1, agent2, asyncio, summarizationagent, agent3, proxy_agent1
import narrativeagent
from langgraph.graph import StateGraph, START, END
from langgraph.constants import Send
from langchain_community.chat_models import ChatOllama
import os
import sys, json
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Database'))
from db_connection import get_secret
langsmith_dict = get_secret("LangSmith")
os.environ['LANGSMITH_TRACING'] = langsmith_dict['LANGSMITH_TRACING']
os.environ['LANGSMITH_ENDPOINT'] = langsmith_dict['LANGSMITH_ENDPOINT']
os.environ['LANGSMITH_API_KEY'] = langsmith_dict['LANGSMITH_API_KEY']
os.environ['LANGSMITH_PROJECT'] = langsmith_dict['LANGSMITH_PROJECT']

app = FastAPI()


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)


connected_users = {}
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # can alter with time
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def proxy_agent2(state: State):
    temp = "\n".join(state["response"])
    return {"aggregated_response": temp}


def dummy(state: State):
    return {}


def route(state: State):
    if len(state["response"]) == len(state["agents"]):
        return "proxy_agent2"
    else:
        return "dummy"


def assign_workers(state: State):
    """Assign a worker to each section in the plan"""
    calls = []
    for s in state["agents"]:
        if s not in state["visited"]:
            calls.append(s)
            state["visited"].append(s)
    # Kick off section writing in parallel via Send() API
    return [Send(s, state) for s in calls]


orchestrator_worker_builder = StateGraph(State)
orchestrator_worker_builder.add_node("proxy_agent1", proxy_agent1.proxy_agent1)
orchestrator_worker_builder.add_node("community_engagement_agent", agent1.agent_1)
orchestrator_worker_builder.add_node("news_agent", agent2.agent_2)
orchestrator_worker_builder.add_node("music_industry_agent", agent3.agent_3)
orchestrator_worker_builder.add_node("proxy_agent2", proxy_agent2)
orchestrator_worker_builder.add_node("summarization_agent", summarizationagent.summarization_agent)
orchestrator_worker_builder.add_node("narrative_agent", narrativeagent.narrative_agent) #added 
orchestrator_worker_builder.add_node("dummy", dummy)

orchestrator_worker_builder.add_edge(START, "proxy_agent1")
orchestrator_worker_builder.add_conditional_edges(
    "proxy_agent1", assign_workers, ["community_engagement_agent", "news_agent", "music_industry_agent"]
)
orchestrator_worker_builder.add_conditional_edges(
    "proxy_agent1", route, ["proxy_agent2", "dummy"])
orchestrator_worker_builder.add_edge("community_engagement_agent", "proxy_agent1")
orchestrator_worker_builder.add_edge("news_agent", "proxy_agent1")
orchestrator_worker_builder.add_edge("music_industry_agent", "proxy_agent1")
orchestrator_worker_builder.add_edge("proxy_agent2", "summarization_agent")
orchestrator_worker_builder.add_edge("summarization_agent", "narrative_agent")
orchestrator_worker_builder.add_edge("narrative_agent", END)

orchestrator_worker = orchestrator_worker_builder.compile()
# display(Image(orchestrator_worker.get_graph().draw_mermaid_png()))

#keep alive=0 removes the cache 
#can we do an if statement, connect to streamlit to toggle this?
#keep_alive = true, 

#llm = OllamaLLM(model="deepseek-r1:latest",api_base="https:/localhost:11434",keep_alive=-1)


#llm = OllamaLLM(model="deepseek-r1:latest",api_base="https:/localhost:11434",keep_alive=0)


def create_llm(mode):
    if mode == "cache":
        #keep alive -1 retains
        print("cache")
        return OllamaLLM(model="deepseek-r1:latest", api_base="http://localhost:11434", keep_alive=-1)
    else:
        print("not cache")
        return OllamaLLM(model="deepseek-r1:latest", api_base="http://localhost:11434", keep_alive=0)

def log_prompt_to_db(session_id, user_query, prompt, response, context):
    s_dict = get_secret("DB")
    user, password, host, port, dbname = s_dict['user'], s_dict[
        'password'], s_dict['host'], s_dict['port'], s_dict['dbname']
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    print("Connected to db.")
    cur = conn.cursor()
    # Create table if it doesn't exist
    cur.execute('''
        CREATE TABLE IF NOT EXISTS prompts (
            id SERIAL PRIMARY KEY,
            session_id TEXT,
            user_query TEXT,
            prompt TEXT,
            response TEXT,
            context TEXT,
            timestamp TIMESTAMPTZ DEFAULT NOW()
        );
    ''')
    # Insert the prompt/response
    cur.execute('''
        INSERT INTO prompts (session_id, user_query, prompt, response, context, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s);
    ''', (session_id, user_query, prompt, response, context, datetime.now()))
    conn.commit()
    print(" Prompt and response inserted into database.")
    # print(response)
    cur.close()
    conn.close()

recent_queries = {} 

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(user_id: str, websocket: WebSocket):
    await websocket.accept()

    # Store the WebSocket connection in the dictionary
    connected_users[user_id] = websocket

    

    try:
        while True:
            try:
                # Wait for data with a timeout



                data = await asyncio.wait_for(websocket.receive_text(), timeout=None)
                print(f"Message received: {data}")
                print("type" , type(data))



                b = json.loads(data)

                

                print("type", type(b))
                
                mode = b["mode"] 
                query = b["query"]
                llm = create_llm(mode)  


                if user_id not in recent_queries:
                    recent_queries[user_id] = []
                recent_queries[user_id].append(query)
            
                recent_queries[user_id] = recent_queries[user_id][-3:] #last 3 


                if mode == "cache":
                    prompt = "recent queries:\n"
                    print(prompt)
                    for pq in recent_queries[user_id][:-1]:  
                        prompt += f"- {pq}\n"
                    prompt += f"Current query: {query}"
                    print(prompt)
                else:
                    prompt = query

                print("invoke")
                # Call the orchestrator
                #"query": prompt
                state = await orchestrator_worker.ainvoke({"query": prompt, "session_id": user_id, "llm" : llm, "ollama_lock": asyncio.Lock(), "agents": None})
                summary = state.get("final_response", "")
                narrative = state.get("narrative", "")
                recommendation = state.get("recommendation", "")
                responses = state.get("response", "")
                # If the narrative or recommendation is missing, try to extract from the LLM output (handle 'Action:' as well)
                if not narrative or not recommendation:
                    # Try to extract from the summary if present
                    if "Narrative:" in summary and ("Recommendation:" in summary or "Action:" in summary):
                        parts = summary.split("Narrative:", 1)
                        if len(parts) > 1:
                            after_narr = parts[1]
                            if "Recommendation:" in after_narr:
                                n, r = after_narr.split("Recommendation:", 1)
                                narrative = n.strip()
                                recommendation = r.strip()
                            elif "Action:" in after_narr:
                                n, r = after_narr.split("Action:", 1)
                                narrative = n.strip()
                                recommendation = r.strip()

                # Display both narrative and recommendation/action clearly
                # response = f"{summary}\n\nNARRATIVE:\n{narrative}\n\nRECOMMENDATION / ACTION:\n{recommendation}"
                # print(f"\n=== NARRATIVE ===\n{narrative}\n\n=== RECOMMENDATION ===\n{recommendation}\n")
                dict = {"summary" : summary, "narrative/recommendation" : f"{narrative}\n{recommendation}", "response": responses}
                response = json.dumps(dict)
                # Log prompt/response to DB
                try:
                    prompt = state.get("prompt", [""])[
                        0] if "prompt" in state else ""
                    context = state.get("context", "")
                    log_prompt_to_db(user_id, query, prompt, response, context)
                except Exception as e:
                    print(f"[DB LOGGING ERROR] {e}")

                await websocket.send_text(response)

            except asyncio.TimeoutError:
                print(f"No message. Keeping connection alive.")
                # Optionally send a ping or heartbeat here
            # async def call_llm_async(data):
            #     loop = asyncio.get_running_loop()
            #     return await loop.run_in_executor(executor, llm.invoke, data)
            # response = await call_llm_async(data)

            # send query + RAG response to DB

            # Send the received data to the other user
    except Exception as e:
        print(f"Disconnected user: {repr(e)}")
    finally:
        # Always clean up
        connected_users.pop(user_id, None)

# def synthesizer(state: State):
#     resps = state["response"]

#     # Format completed section to str to use as context for final sections
#     final_rep = "\n".join(resps)

#     return {"final_response": final_rep}
