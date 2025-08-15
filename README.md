# AI Sense-making Platform

## Project Description
This project leverages a multi-agent, Retrieval-Augmented Generation (RAG) architecture to simulate next-generation sensemaking capabilities in support of open-source narrative intelligence. It focuses specifically on contextualizing capabilities, actions, and intentions involving both US and South Korean celebrities including Beyonce, SZA, Taylor Swift, Blackpink, and Stray Kids. The system uses publicly available data (OSINT)—including social media activity, news reporting, and open-source metadata to analyze artist behavior and use sentiment around public events to build a narrative around. This information is crucial for providing insights to prominent figures, supporting operations, and advancing goals globally. By combining semantic retrieval, LLM-based analysis, and multi-agent collaboration, the platform provides crucial context to support analyst decision-making, surfacing relationships, sentiment trends, and thematic narratives. This is done by leveraging open-source media, and metadata sources such as:

- Social media sentiment
- Open-source media reporting


## Instance Setup 

1. Go into the [Install_Script](/Install_Script) folder

2. Transfer over the  ``` manually_installed.txt ```  and the ``` run.sh ``` file on the instance to install basic dependenciwa

3. Make the script executable: ``` chmod +x run.sh ``` 

4. Run the script: ``` ./run.sh ``` 

5. The script will print Done! when completed 

6. Follow the Install VSCode documentation inside of the [Documentation](/Documentation) folder

7. You will need to setup the VSCode ssh extension locally. 


## Installation Instructions: 
To set up this project, follow these steps:

- Create a python venv: ``` python3 -m venv [name_of_venv] ```

- Activate the python venv: ``` source name_of_venv/bin/activate ``` (ensure venv is activated in every terminal)

- Run: ``` pip install -r requirements.txt ```

- Open a new terminal:

    - cd into RAG directory: ``` cd RAG ```

    - Build the vector db:  ``` python test_chromd.py ```

    - Pull the deepseek model: ``` ollama pull deepseek-r1:latest ``` 

    - Run the rag mcp: ``` python -m uvicorn rag_mcp_api:app --reload --port 8002 ```

- Open a new terminal:

    - cd into RAG directory: ``` cd RAG ```

    - Run the proxy client: ``` python -m uvicorn proxy_client1:app --reload --port 8003 ``` 

- Open a new terminal:

    - cd into RAG directory: ``` cd RAG ```

    - Run the streamlit UI: ``` streamlit run streamlit_app.py ```
  

## Project Structure

- **Data_Ingestion/**  
  Script to add a new table to the database with default fields.

- **Database/**  
  Script to connect to and query the database.

- **Documentation/**  
  Guides for AWS resource setup, database setup, LLM/RAG overview & comparison, chosen RAG components, and vector store selection.

- **Install_Script/**  
  Scripts to install basic dependencies on a fresh instance.

- **Agentic_Workflow/**  
  All agents (subagents, proxy, summarizer, narrative), MCP Server, Streamlit UI, chunking configs per source, and the ChromaDB vector‑build file.

- **Data_Collection/**  
  Scripts for gathering data via scraping, free APIs, and Apify.

- **(root)**  
  `README.md` and `requirements.txt`  


## Features
- Granular multi-agent architecture with tool-using agents (NER, sentiment analysis, and geolocation) with LLM-guided query routing, RAG query optimization, dynamic tool selection
- End-to-end Retrieval-Augmented Generation (RAG) pipeline for natural language querying over OSINT data
- Semantic search and vectorized retrieval using Chroma and SentenceTransformers
- Batch ingestion of open-source data (social media, news articles)
- Modular and cloud-portable design (no reliance on AWS-native services) for secure and flexible deployment
- UI that displays summary of retrieved documents and generated narrative


## Technologies Used
The following technologies are used in this project:
- ChromaDB
- PostgreSQL
- LangGraph
- MCP
- LangSmith
- Locally hosted Deepseek R1
- Sentence Transformers


## Contributing
We welcome contributions to this project! To contribute, please follow these guidelines:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes and push your branch to your fork.
4. Submit a pull request with a detailed description of your changes.


## License
This project is licensed under the MIT License.

## Authors and Acknowledgments
This project was developed by the intern team at Everwatch Corporation:

- Myra Cropper
- Jonathan Mei
- Sachin Ashok
- Kyle Simon
- Matthew Lessler
- Izaiah Davis
- Quinn Dunnigan
- Julia Calvert
- Julie Ochs
- Alyssa Miller
- Bentley Cech

Mentored by David Culver.


## Contact Information
For questions or issues, please open an issue in the repository or contact the authors.
