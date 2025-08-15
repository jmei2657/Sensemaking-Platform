import streamlit as st
import websocket, random, json
import requests



# def clear_ollama_model_cache(model_name="deepseek-r1:latest"):
#     try:
#         response = requests.delete(f"http://localhost:11434/api/models/{model_name}")
#         if response.status_code == 200:
#             st.success(f"cleared: {model_name}")
#         else:
#             st.error(f"didn't clear cache: {response.text}")
#     except Exception as e:
#         st.error(f"Error clearing model cache: {e}")



# App title
st.title("Ask Me About Noteable People ✅ 🚀")

# UI subheader
st.subheader("Noteable Person Analayzer 🎤💃💫")
# images = ["./Kansas-City-Chiefs-Logo-1972-present.png", "./blue-broncos-logo.jpg"]
# st.image(images[int(random.random() * len(images))], width=300)

st.button("button text", type="primary")

if st.button("Clear Model Cache"):
    #clear_ollama_model_cache()
    print("button press")

box = st.empty()






cache_mode = st.radio("LLM Cache Mode", ["Use Cache", "Don't Use Cache"], index=0)

#set cache

if "ws" not in st.session_state:
    try:
        st.session_state.ws = websocket.create_connection("ws://localhost:8003/ws/user1")
    except Exception as e:
        st.error(f"WebSocket connection failed: {e}")
        #st.stop()
        st.session_state.ws = None 

if "input" not in st.session_state:
    st.session_state.input = False
def send_query(query):
    st.session_state.input = True
    try:

        mode = "cache" if cache_mode == "Use Cache" else "no_cache"
        #payload = json.dumps({"query": query, "mode": mode})
        #st.session_state.ws.send(payload)
        


        st.session_state.ws.send(query)
        response = st.session_state.ws.recv()
        responses = json.loads(response)
        tab1, tab2 = st.tabs(["Summary", "Narrative/Recommendation"])
        with tab1:
            raw1 = responses["summary"]
            start = raw1.find("</think>")
            if start == -1:
                raise ValueError(f"No JSON found in LLM output: {raw1!r}")
            tab1.write(raw1[start + 8:])
        with tab2:
            raw2 = responses["narrative/recommendation"]
            start = raw2.find("</think>")
            if start == -1:
                raise ValueError(f"No JSON found in LLM output: {raw2!r}")
            tab2.write(raw2[start + 8:])
    except Exception:
        st.session_state.ws = websocket.create_connection("ws://localhost:8003/ws/user1")
        send_query(query)
    finally:
        st.session_state.input = False



query=box.text_input('Enter some text', disabled=st.session_state.input, key="query_box")
if query and not st.session_state.input:
    send_query(query)


