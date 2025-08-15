from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class MCPRequest(BaseModel):
    query: str
    context: str = None  

@app.post("/query")
def mcp_query(req: MCPRequest):
   
    response = {
        "received_query": req.query,
        "received_context": req.context,
        "mcp_answer": f"Processed: {req.query} (context length: {len(req.context) if req.context else 0})"
    }
    return response



# uvicorn mcp_api:app --reload --port 8001

