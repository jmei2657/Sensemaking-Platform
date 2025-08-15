from fastapi import FastAPI, Request
from pydantic import BaseModel
import requests
from test_chromd import setup_chroma

from collections import Counter
from transformers import pipeline
from geopy.geocoders import Nominatim
import spacy
import time
import json
from bertopic import BERTopic

# Load spaCy model for NER
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("spaCy model not found. Please run: python -m spacy download en_core_web_sm")
    nlp = None

MCP_URL = "http://localhost:8002/query"

app = FastAPI()
chroma_client = setup_chroma()

# List of all available collections
ALL_COLLECTIONS = [
    "newsapi_embeddings",
    "reddit_embeddings",
    "tmz_embeddings",
#    "guardian_embeddings",
    "sza_tours_embeddings",
    "szanme_embeddings",
    "taylornme_embeddings"
]
COMMUNITY_COLLECTIONS = [
    "reddit_embeddings",
    "reddit_billie_embeddings",
    "reddit_blackpink_embeddings",
    "reddit_straykids_embeddings",
    "reddit_sza_embeddings"
]
class RAGRequest(BaseModel):
    query: str
    collections: list[str] | None = None   # falls back to ALL_COLLECTIONS
    top_k: int = 5 #not used but dont take out

#also just dont take out
def _rag(query: str, collections: list[str], top_k: int):
    """Run a vector search on the given collections and hit MCP."""
    all_results = []
    for name in collections:
        coll = chroma_client.get_collection(name)
        res  = coll.query(query_texts=[query], n_results=top_k)
        for doc, meta, dist in zip(res["documents"][0],
                                   res["metadatas"][0],
                                   res["distances"][0]):
            all_results.append({
                "source":   name,
                "document": doc,
                "metadata": meta,
                "distance": dist,
            })

    #get closest to now 
    
    # def recency_weighted_score(result):
    #     alpha = 0.5
    #     recency = get_date_score(result["metadata"])
    #     return result["distance"] - alpha * recency
    # all_results.sort(key=recency_weighted_score)
    all_results.sort(key=lambda r: r["distance"])
    top = all_results[:top_k]
    context = "\n".join(r["document"] for r in top)

    mcp_resp = requests.post(
        MCP_URL, json={"query": query, "context": context}
    ).json()

    return {"mcp_result": mcp_resp, "rag_context": context, "results": top}

@app.get("/collections")
def list_collections():
    return {"collections": ALL_COLLECTIONS}

@app.post("/rag")
def rag_endpoint(req: RAGRequest):
    chosen = req.collections or ALL_COLLECTIONS
    return _rag(req.query, chosen, req.top_k)
#hello
#most used words, maybe change this to do something more useful
def trend_tool(collection_name: str):
    collection = chroma_client.get_collection(collection_name)
    all_docs = collection.get()["documents"]
    # BERTopic expects a list of documents (strings)
    topic_model = BERTopic()
    topics, _ = topic_model.fit_transform(all_docs)
    topic_info = topic_model.get_topic_info()
    # Return the top_n topics (excluding -1, which is usually 'outliers')
    topic_info = topic_info[topic_info.Topic != -1].head(top_n)
    return topic_info.to_dict(orient='records')

#sentiment tool 
# Initialize the sentiment analysis pipeline once
transformer_sentiment_analyzer = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

def sentiment_tool(docs: list):
    documents = []
    for doc in docs:
        print(doc)
        print(type(doc))
        collection = chroma_client.get_collection(doc.get("source"))
        res = collection.get(where={'original_id': doc.get("metadata").get("original_id")})
        documents.extend(res.get("documents", []))
    print(documents)
    results = transformer_sentiment_analyzer(documents)
    # Return the positive class probability as the sentiment score
    return [r["score"] if r["label"] == "POSITIVE" else -r["score"] for r in results]

# NER tool for notable persons
from collections import Counter
class NERRequest(BaseModel):
    docs: list
    # top_k: int = 10

# Load once at the top of your file
ner_pipe = pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

def ner_person_tool(docs):
    person_counter = Counter()
    person_examples = {}

    # Retrieve full documents using source + original_id
    full_docs = []
    for doc in docs:
        collection = chroma_client.get_collection(doc.get("source"))
        res = collection.get(where={'original_id': doc.get("metadata", {}).get("original_id")})
        full_docs.extend(res.get("documents", []))

    for text in full_docs:
        results = ner_pipe(text)
        merged_persons = []
        current_person = ""
        for ent in results:
            if ent['entity_group'] == 'PER':
                word = ent['word'].strip()
                if word.startswith("##"):
                    word = word[2:]
                if ent.get('start', 0) > 0 and text[ent['start'] - 1] != ' ':
                    current_person += word
                else:
                    if current_person:
                        merged_persons.append(current_person.strip())
                    current_person = word
            else:
                if current_person:
                    merged_persons.append(current_person.strip())
                    current_person = ""
        if current_person:
            merged_persons.append(current_person.strip())

        for name in merged_persons:
            if (
                "http" in name or ".com" in name or ".org" in name or ".net" in name
                or len(name) > 40 or any(char.isdigit() for char in name)
                or name.lower() == name or name.upper() == name
            ):
                continue
            person_counter[name] += 1
            if name not in person_examples:
                person_examples[name] = text

    return [
        {"name": name, "count": count, "examples": [person_examples[name]]}
        for name, count in person_counter.most_common()
    ]

@app.post("/ner_person_tool")
def ner_person_tool_endpoint(req: NERRequest):
    return {"persons": ner_person_tool(req.docs)}

#geolocation tool 
#thinks that Kelce is a place apparently 
def geolocation_tool(docs, query: str = None):
    if nlp is None:
        return {"error": "spaCy model not loaded."}

    full_docs = []
    for doc in docs:
        collection = chroma_client.get_collection(doc.get("source"))
        res = collection.get(where={'original_id': doc.get("metadata", {}).get("original_id")})
        full_docs.extend(res.get("documents", []))

    location_contexts = {}
    for text in full_docs:
        spacy_doc = nlp(text)
        for sent in spacy_doc.sents:
            for ent in sent.ents:
                if ent.label_ == "GPE":
                    name = ent.text.strip()
                    name_lower = name.lower()
                    if name_lower in {"kelce", "us", "spotify", "cardigan", "debut", "swifties", "tiktok", "youtube", "album", "era", "apple", "music"}:
                        continue
                    if len(name) < 2 or name.islower():
                        continue
                    if query and query.lower() not in sent.text.lower():
                        continue
                    if name not in location_contexts:
                        location_contexts[name] = {"count": 0, "examples": []}
                    location_contexts[name]["count"] += 1
                    if len(location_contexts[name]["examples"]) < 2:
                        location_contexts[name]["examples"].append(sent.text)

    results = []
    geolocator = Nominatim(user_agent="rag_geolocator")
    for name, info in sorted(location_contexts.items(), key=lambda x: -x[1]["count"]):
        try:
            geo = geolocator.geocode(name, timeout=2)
            lat, lon = (geo.latitude, geo.longitude) if geo else (None, None)
        except Exception:
            lat, lon = (None, None)
        results.append({
            "location": name,
            "count": info["count"],
            "examples": info["examples"],
            "lat": lat,
            "lon": lon
        })
    return results

def resolve_location(name):
    geolocator = Nominatim(user_agent="rag_geolocator")
    location = geolocator.geocode(name)
    if location:
        return {"name": name, "lat": location.latitude, "lon": location.longitude}
    return {"name": name, "lat": None, "lon": None}
 

# Remove or guard these print statements to avoid errors at import time
# print(trend_tool("news_embeddings", top_n=10))
# print(sentiment_tool("news_embeddings", top_k=5))

class TrendRequest(BaseModel):
    docs: list
    # top_n: int = 10

@app.post("/trend_tool")
def trend_tool_endpoint(req: TrendRequest):
    return {"trends": trend_tool(req.collection)}

class SentimentRequest(BaseModel):
    docs: list
    # top_k: int = 10

@app.post("/sentiment_tool")
def sentiment_tool_endpoint(req: SentimentRequest):
    return {"sentiments": sentiment_tool(req.docs)}

class GeoRequest(BaseModel):
    docs: list
    # top_k: int = 10

@app.post("/geolocation_tool")
def geolocation_tool_endpoint(req: GeoRequest):
    #locations = geolocation_tool(req.collection)
    # Optionally resolve to coordinates:
    # locations = [resolve_location(name) for name, _ in locations]
    return {"locations": geolocation_tool(req.docs)}

class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    return {"received_query": req.query}

#uvicorn rag_mcp_api:app --reload --port 8002

#trend: curl -X POST "http://localhost:8002/trend_tool" \
#   -H "Content-Type: application/json" \
#   -d '{"collection": "news_embeddings", "top_n": 10}'

# curl -X POST "http://localhost:8002/sentiment_tool" \
#     -H "Content-Type: application/json" \
#    -d '{"collection": "news_embeddings", "top_k": 5}'