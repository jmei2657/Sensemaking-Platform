from typing_extensions import TypedDict
from langchain_ollama.llms import OllamaLLM
from typing import Annotated, List
import operator, asyncio


class State(TypedDict):
    query: str
    opt_query: str
    response: Annotated[list, operator.add]
    llm: OllamaLLM
    visited: Annotated[list, operator.add]
    aggregated_response: str
    final_response: str
    ollama_lock: asyncio.locks.Lock
    agents: List
    narrative: str  #hope this doesnt f anything up
    recommendation: str  