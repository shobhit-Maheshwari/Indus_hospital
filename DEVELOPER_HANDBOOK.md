# Philoagents-API: Complete Developer Handbook
> A beginner-friendly, line-by-line explanation of every file in the project.
> Save this file and open it in VS Code anytime to revise.

---

## Table of Contents

1. [Project Architecture Overview](#1-project-architecture-overview)
2. [Technology Glossary](#2-technology-glossary)
3. [config.py](#3-configpy)
4. [domain/philosopher.py](#4-domainphilosopherpy)
5. [domain/prompts.py](#5-domainpromptspy)
6. [infrastructure/api.py](#6-infrastructureapipy)
7. [infrastructure/memory_orchestrator.py](#7-infrastructurememory_orchestratorpy)
8. [rag/retrievers.py](#8-ragretrievers-py)
9. [workflow/state.py](#9-workflowstatepy)
10. [workflow/tools.py](#10-workflowtoolspy)
11. [workflow/chains.py](#11-workflowchainspy)
12. [workflow/nodes.py](#12-workflownodespy)
13. [workflow/edges.py](#13-workflowedgespy)
14. [workflow/graph.py](#14-workflowgraphpy)
15. [generate_response.py](#15-generate_responsepy)
16. [reset_conversation.py](#16-reset_conversationpy)
17. [Complete Request Flow Diagram](#17-complete-request-flow-diagram)

---

## 1. Project Architecture Overview

Think of the system like a TV show production:
- **FastAPI (api.py)** = The TV Studio (receives audience calls/requests)
- **MemoryOrchestrator (Redis)** = The prompter backstage (whispers recent dialogue to actors)
- **LangGraph (graph.py)** = The script director (manages who speaks, in what order)
- **LLM (Groq/Llama)** = The actor (generates the actual dialogue)
- **MongoDB** = The permanent archive (stores all scripts/episodes forever)
- **MongoDB Vector Search** = The research library (finds relevant reference material instantly)

```
User → api.py → get_response() → LangGraph Graph → LLM → Response
                     ↑                   ↑
               Redis (fast cache)   MongoDB (permanent + RAG)
```

The project has 3 memory layers:
- **L1 (Redis)**: Ultra-fast, temporary. Stores the last 10 messages + summary per session.
- **L2 (MongoDB Checkpoints)**: Permanent. Full LangGraph state saved after every step.
- **L3 (MongoDB Vector Store)**: Static knowledge base (philosopher books/essays). Never changes during chat.

---

## 2. Technology Glossary

| Term | What it is | Simple Analogy |
|------|-----------|----------------|
| **FastAPI** | Python web framework that handles HTTP requests | A telephone switchboard operator |
| **Pydantic** | Library that validates data types automatically | A form validation checklist |
| **LangGraph** | Library to build AI workflows as state machines (nodes + edges) | A flowchart where each box is an AI action |
| **LangChain** | Toolkit for building LLM apps (prompts, message types, chains) | A LEGO kit for AI |
| **Groq** | AI hardware company. Their API runs Llama models very fast | A super-fast chef that cooks answers |
| **Redis** | In-memory database. Stores data in RAM, not disk. Extremely fast | A sticky note on your desk |
| **MongoDB** | Document database that stores data on disk permanently | A filing cabinet |
| **Vector Search** | Finding documents by meaning/concept instead of exact words | Searching by concept, not exact words |
| **HuggingFace Embeddings** | A model that converts text into a list of numbers (a vector) | Translating text to GPS coordinates |
| **RAG** | Find relevant documents first, then generate an answer using them | Open-book exam instead of from memory |
| **Opik** | LLM observability platform. Logs and monitors every LLM call | A CCTV system for your AI |
| **asyncio** | Python framework for running multiple things at once | A chef juggling multiple dishes |
| **Pipeline (Redis)** | Batch of Redis commands sent all at once | A shopping list vs. one item at a time |
| **Checkpointer** | LangGraph saves full workflow state after each node | A save-game slot in a video game |
| **TypedDict** | A Python dictionary with declared field names and types | A form with labeled fields |
| **BM25** | Keyword-based search algorithm | Google search for exact words |
| **Dot Product** | Math formula to compare two vectors for similarity | Measuring how "close" two GPS points are |
| **RRF** | Reciprocal Rank Fusion. Merges results from two search methods fairly | Averaging two judges' scores |
| **LPUSH** | Redis command: push item to the LEFT (front) of a list | Put a new paper on TOP of a stack |
| **LTRIM** | Redis command: keep only a range of items in a list | Shredding old papers to keep only the last 10 |
| **EXPIRE** | Redis command: set an auto-delete timer on a key | A sticky note that self-destructs after 24h |
| **TTL** | Time-to-Live. How many seconds before a Redis key auto-deletes | Expiry date on food |

---

## 3. `config.py`

**File:** `src/philoagents/config.py`
**Purpose:** Centralizes ALL configuration values. Any setting that might change lives here.
**Technology:** `pydantic-settings` — reads values from `.env` file automatically.

```python
from pathlib import Path
# Path is Python's built-in tool to represent file paths.
# Works the same on Windows, Linux, and Mac.

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
# BaseSettings: A special class that reads values from environment variables or .env files.
# Field: Adds extra info to a setting like description or default value.


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",           # Read from the .env file
        extra="ignore",            # If .env has unknown keys, ignore them (don't crash)
        env_file_encoding="utf-8"  # Read the file as UTF-8 text
    )

    # --- GROQ (The LLM Provider) ---
    GROQ_API_KEY: str
    # Required field. No default value.
    # If this is missing from .env, the app crashes at startup. Good — it forces you to set it.

    GROQ_LLM_MODEL: str = "llama-3.3-70b-versatile"
    # The main conversation model. 70b = 70 billion parameters = large, smart, slower.

    GROQ_LLM_MODEL_SUMMARY: str = "llama-3.1-8b-instant"
    # A smaller, faster model (8b = 8 billion params).
    # Used for background summarization to save cost and time.

    GROQ_LLM_MODEL_CONTEXT_SUMMARY: str = "llama-3.1-8b-instant"
    # Used to compress long RAG results into short summaries.

    GROQ_LLM_MODEL_JUDGE: str = "llama-3.3-70b-versatile"
    # Used as an AI judge in evaluation (Opik evaluation tasks).

    # --- MongoDB ---
    MONGO_URI: str = Field(
        default="mongodb://philoagents:philoagents@local_dev_atlas:27017/?directConnection=true",
        description="Connection URI for the local MongoDB Atlas instance."
    )
    # The connection string to MongoDB. Format: mongodb://username:password@host:port/

    MONGO_DB_NAME: str = "philoagents"
    # The database name inside MongoDB. Like a folder that contains all our tables.

    MONGO_STATE_CHECKPOINT_COLLECTION: str = "philosopher_state_checkpoints"
    # Collection (like a SQL table) where LangGraph saves full workflow state snapshots.

    MONGO_STATE_WRITES_COLLECTION: str = "philosopher_state_writes"
    # Collection where LangGraph saves individual state change records (diffs between steps).

    MONGO_LONG_TERM_MEMORY_COLLECTION: str = "philosopher_long_term_memory"
    # Collection where philosopher knowledge base (books, essays, quotes) is stored.
    # This is the RAG knowledge base. Searched during conversations.

    # --- Redis ---
    REDIS_URI: str = Field(default="redis://localhost:6379/0")
    # Connection string to Redis. /0 refers to Redis database number 0.
    # Redis supports 16 databases numbered 0-15.

    # --- Opik (Observability) ---
    COMET_API_KEY: str | None = None
    # API key for Opik/CometML. Optional — if missing, Opik logging is disabled.

    COMET_PROJECT: str = "philoagents_course"
    # Project name in Opik dashboard. All traces are grouped under this name.

    # --- Agent Conversation Settings ---
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 30
    # When the LangGraph message list reaches 30 messages, trigger graph-level summarization.

    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5
    # After graph-level summarization, keep only the last 5 messages.
    # The rest are deleted from LangGraph's state to reduce token usage.

    # --- RAG Settings ---
    RAG_TEXT_EMBEDDING_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    # HuggingFace embedding model. Converts text into 384-dimensional vectors.
    # "all-MiniLM-L6-v2" is small, fast, and accurate enough for this use case.

    RAG_TEXT_EMBEDDING_MODEL_DIM: int = 384
    # The number of dimensions in the embedding vector. Must match MongoDB vector index config.

    RAG_TOP_K: int = 3
    # When searching the knowledge base, return the top 3 most relevant document chunks.

    RAG_DEVICE: str = "cpu"
    # Device to run the embedding model on. "cpu" works always. "cuda" = GPU (faster if available).

    RAG_CHUNK_SIZE: int = 256
    # When splitting philosopher texts into chunks, each chunk is 256 words/tokens.


settings = Settings()
# Create ONE global settings object.
# Pydantic reads the .env file HERE and fills all values.
# Every other file does: from philoagents.config import settings
# This is the Singleton pattern — one shared instance across the entire app.
```

---

## 4. `domain/philosopher.py`

**File:** `src/philoagents/domain/philosopher.py`
**Purpose:** Defines the data shape of what a "Philosopher" is in this system.
**Technology:** `Pydantic BaseModel` — auto-validates that data matches declared types.

```python
import json
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field


class PhilosopherExtract(BaseModel):
    """
    Used during data scraping/ingestion phase.
    Represents raw philosopher data before it is enriched.
    """
    id: str    # Unique identifier, e.g., "turing", "socrates"
    urls: List[str]  # List of Wikipedia or other URLs to scrape info from

    @classmethod
    def from_json(cls, metadata_file: Path) -> list["PhilosopherExtract"]:
        # classmethod = can be called on the CLASS itself, not an instance.
        # from_json(Path("data/philosophers.json")) returns a list of PhilosopherExtract objects.
        with open(metadata_file, "r") as f:
            philosophers_data = json.load(f)   # Read JSON file into Python list
        return [cls(**philosopher) for philosopher in philosophers_data]
        # cls(**philosopher) = create a PhilosopherExtract object from each dict in the list


class Philosopher(BaseModel):
    """
    The main philosopher model used during actual conversations.
    """
    id: str
    # Unique key used as the identifier in API requests.
    # e.g., "turing" (used in POST /chat body as philosopher_id)

    name: str
    # Display name used inside LLM prompts.
    # e.g., "Alan Turing"

    perspective: str
    # A paragraph describing the philosopher's theoretical views about AI.
    # Injected into the system prompt so the LLM knows how to argue.
    # e.g., "Alan Turing is a brilliant and pragmatic thinker who challenges you..."

    style: str
    # How the philosopher talks.
    # e.g., "Turing analyzes ideas with a puzzle-solver's delight..."
    # Injected into the system prompt to shape LLM tone.

    era: str
    # The historical time period the philosopher lived in.
    # e.g., "Early-to-mid 20th century England (1912-1954 AD)"
    # VERY IMPORTANT: Used as a guardrail in the system prompt.
    # The LLM is told: "You have no knowledge of anything after 1954."
    # This prevents Turing from knowing about ChatGPT, the internet, etc.

    def __str__(self) -> str:
        # Called when you do str(philosopher) or print(philosopher)
        return f"Philosopher(id={self.id}, name={self.name}, ...)"
```

---

## 5. `domain/prompts.py`

**File:** `src/philoagents/domain/prompts.py`
**Purpose:** Stores ALL text prompts sent to the LLM. Prompts are versioned using Opik.
**Technology:** `opik` for prompt versioning, `loguru` for logging.

### Why version prompts?
When you change a prompt, Opik stores the old version. If your AI starts behaving differently, you can see exactly which prompt version caused the change. Like Git version control, but for AI prompts.

```python
class Prompt:
    def __init__(self, name: str, prompt: str):
        self.name = name
        self._raw_prompt = prompt   # Store the plain text as backup

        try:
            client = opik.Opik()
            # create_prompt: Saves this prompt to Opik. If it already exists,
            # creates a new version. If Opik is unavailable, uses plain text.
            self.__opik_prompt = client.create_prompt(name=name, prompt=prompt)
        except Exception:
            # If Opik credentials are missing or wrong → log a warning, don't crash.
            logger.warning("Can't use Opik... Falling back to local prompt.")

    @property
    def prompt(self) -> str:
        # When you access prompt.prompt, return Opik version if available.
        if self.__opik_prompt is not None:
            return self.__opik_prompt.prompt
        return self._raw_prompt    # Fallback: return plain text
```

### The Prompts:

**PHILOSOPHER_CHARACTER_CARD** — The main system prompt (the "character sheet" for the LLM):
```
Let's roleplay. You're {{philosopher_name}} - a real person...

Person name: {{philosopher_name}}
Person perspective: {{philosopher_perspective}}
Person talking style: {{philosopher_style}}
Person era: {{philosopher_era}}

ERA GUARDRAIL: If the user asks about any event, person, invention, or concept
that came AFTER your era, decline to answer those specific aspects while staying
fully in character.

Summary of conversation earlier:
{{summary}}         ← This is filled from Redis! The LLM "remembers" past chats.
```
- `{{variable}}` = Jinja2 template syntax. These are replaced with real values at runtime.
- The ERA GUARDRAIL rule prevents Turing from knowing about modern technology.
- `{{summary}}` injects the Redis conversation summary so the LLM has long-term memory.

**SUMMARY_PROMPT** — Used by `summarize_conversation_node`:
```
Create a summary of the conversation between {{philosopher_name}} and the user.
Capture all the relevant information shared...
```

**EXTEND_SUMMARY_PROMPT** — Used when a summary already exists:
```
This is a summary of the conversation to date:
{{summary}}

Extend the summary by taking into account the new messages above:
```

**CONTEXT_SUMMARY_PROMPT** — Used after RAG retrieval to compress long documents:
```
Summarize the following information into less than 50 words:
{{context}}
```

---

## 6. `infrastructure/api.py`

**File:** `src/philoagents/infrastructure/api.py`
**Purpose:** The entry point of the app. Starts the web server, manages database connections, defines HTTP and WebSocket endpoints.
**Technology:** FastAPI, asynccontextmanager, Pydantic, Opik.

### Section 1: Imports
```python
from contextlib import asynccontextmanager
# asynccontextmanager: Turns an async function into a "setup + teardown" manager.
# Used to run startup code before the app starts serving requests.

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
# FastAPI: The web application class.
# HTTPException: Raise this to return an error response (e.g., 500 error).
# WebSocket: Handles a persistent two-way connection (for streaming responses).
# WebSocketDisconnect: Exception raised when the browser disconnects.
# Depends: FastAPI's dependency injection. Shares objects between routes cleanly.

from fastapi.middleware.cors import CORSMiddleware
# CORS = Cross-Origin Resource Sharing.
# Browsers BLOCK requests from a different port/domain by default.
# This middleware tells the browser: "It's OK to call this API from the frontend (port 8080)."
```

### Section 2: Global Variables
```python
_orchestrator: MemoryOrchestrator = None
_mongodb_saver: AsyncMongoDBSaver = None
# These hold the database connections.
# They are initialized ONCE at startup and reused for ALL requests.
# The underscore prefix (_) means "private to this module".

async def get_orchestrator() -> MemoryOrchestrator:
    return _orchestrator

async def get_mongodb_saver() -> AsyncMongoDBSaver:
    return _mongodb_saver
# These are "dependency provider" functions.
# FastAPI's Depends() calls them automatically and injects the result into routes.
```

### Section 3: Lifespan (Startup & Shutdown)
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Everything before yield = startup. Everything after yield = shutdown."""
    global _orchestrator, _mongodb_saver
    # global keyword: We're modifying the global variables defined above.

    async with AsyncMongoDBSaver.from_conn_string(
        conn_string=settings.MONGO_URI,
        db_name=settings.MONGO_DB_NAME,
        checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
        writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
    ) as saver:
        # async with: Opens a MongoDB connection.
        # Everything inside this block runs WITH the connection open.
        # When the block ends (shutdown), the connection closes automatically.

        _mongodb_saver = saver
        # Save the MongoDB saver to our global variable for use by routes.

        llm = ChatGroq(
            model=settings.GROQ_LLM_MODEL_SUMMARY,
            temperature=0.0,
            # temperature=0.0 = completely deterministic.
            # Used for summarization (we want consistent, factual summaries, not creative ones).
        )

        _orchestrator = MemoryOrchestrator(
            redis_url=settings.REDIS_URI,
            llm_client=llm,
            mongodb_saver=_mongodb_saver,
        )
        # Initialize the Redis cache manager with:
        # - Redis connection (for fast L1 cache)
        # - LLM (for background summarization)
        # - MongoDB saver (for cold-start fallback)

        yield
        # ← FastAPI PAUSES HERE and starts serving requests.
        # All code BEFORE yield = startup.
        # All code AFTER yield = shutdown.

    opik_tracer = OpikTracer()
    opik_tracer.flush()
    # On shutdown, force Opik to send any buffered log data to the cloud.
    # The MongoDB connection closes automatically when the "async with" block exits.
```

### Section 4: App Creation
```python
app = FastAPI(lifespan=lifespan)
# Create the FastAPI app and tell it to use our lifespan manager.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Allow requests from ANY domain
    allow_credentials=True,     # Allow cookies/auth headers
    allow_methods=["*"],        # Allow GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],        # Allow any request headers
)
```

### Section 5: /chat Route
```python
class ChatMessage(BaseModel):
    message: str
    philosopher_id: str
# Pydantic model. FastAPI auto-parses the JSON request body into this object.
# If the body is missing "message" or "philosopher_id", FastAPI returns 422 automatically.

@app.post("/chat")
async def chat(
    chat_message: ChatMessage,
    orch: MemoryOrchestrator = Depends(get_orchestrator),   # Injected automatically
    saver: AsyncMongoDBSaver = Depends(get_mongodb_saver),  # Injected automatically
):
    try:
        philosopher_factory = PhilosopherFactory()
        philosopher = philosopher_factory.get_philosopher(chat_message.philosopher_id)
        # PhilosopherFactory: A lookup service. Given "turing", returns the full Philosopher object.

        response, _ = await get_response(
            messages=chat_message.message,
            philosopher_id=chat_message.philosopher_id,
            philosopher_name=philosopher.name,      # "Alan Turing"
            philosopher_perspective=philosopher.perspective,
            philosopher_style=philosopher.style,
            philosopher_era=philosopher.era,
            philosopher_context="",     # Empty initially; filled by RAG retrieval inside the graph
            orchestrator=orch,
            mongodb_saver=saver,
        )
        return {"response": response}
        # Returns JSON: {"response": "My Turing Test is..."}

    except Exception as e:
        opik_tracer = OpikTracer()
        opik_tracer.flush()   # Save Opik logs even on error
        raise HTTPException(status_code=500, detail=str(e))
        # HTTPException: FastAPI converts this into a 500 error response.
```

### Section 6: /ws/chat WebSocket Route
```python
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, ...):
    await websocket.accept()
    # Accept the connection. Without this, the WebSocket is rejected.

    try:
        while True:
            # Infinite loop: keep listening for new messages.
            data = await websocket.receive_json()
            # Wait until the client sends a JSON message. Then parse it.

            # Get streaming response (word by word)
            response_stream = get_streaming_response(messages=data["message"], ...)

            await websocket.send_json({"streaming": True})
            # Tell the frontend "I'm starting to stream now."

            full_response = ""
            async for chunk in response_stream:
                # chunk = one word or phrase at a time (like ChatGPT typing effect)
                full_response += chunk
                await websocket.send_json({"chunk": chunk})
                # Send each word to the frontend immediately.

            await websocket.send_json({"response": full_response, "streaming": False})
            # Send the complete response when done.

            await orch.save_interaction(...)
            # Save the full conversation turn to Redis.

    except WebSocketDisconnect:
        pass
        # When the user closes the browser tab, this exception is raised.
        # "pass" = do nothing, just exit the loop cleanly.
```

### Section 7: /reset-memory Route
```python
@app.post("/reset-memory")
async def reset_conversation(orch: MemoryOrchestrator = Depends(get_orchestrator)):
    result = await reset_conversation_state(orch)
    # Wipes ALL Redis keys AND drops MongoDB checkpoint collections.
    return result
```

---

## 7. `infrastructure/memory_orchestrator.py`

**File:** `src/philoagents/infrastructure/memory_orchestrator.py`
**Purpose:** The Redis L1 cache manager. Handles fast reads/writes of conversation state.
**Technology:** `redis.asyncio` (async Redis client), `asyncio` (background tasks).

### Constants
```python
BUFFER_LIMIT = 10
# Maximum number of raw conversation turns kept in Redis.
# When this is reached, the 10 messages are compressed into a summary.

SESSION_TTL = 86400
# 86400 seconds = 24 hours.
# Every Redis key auto-deletes after 24 hours of inactivity.
# This keeps Redis memory clean — inactive sessions are automatically removed.
```

### `__init__`
```python
def __init__(self, redis_url: str, llm_client: Any, mongodb_saver: AsyncMongoDBSaver):
    self.redis = redis.from_url(redis_url, decode_responses=True)
    # redis.from_url(): Creates a connection pool to Redis.
    # decode_responses=True: Redis returns Python strings (not raw bytes).
    # A "connection pool" means Redis reuses connections instead of creating a new one each time.

    self.llm = llm_client
    # The LLM used for background summarization.

    self.checkpointer = mongodb_saver
    # The MongoDB saver used as fallback when Redis has no data (cache miss).
```

### Key Name Helpers
```python
def _get_summary_key(self, thread_id, philosopher_id) -> str:
    return f"session:{thread_id}:{philosopher_id}:summary"

def _get_buffer_key(self, thread_id, philosopher_id) -> str:
    return f"session:{thread_id}:{philosopher_id}:buffer"

# Example keys in Redis:
# session:turing:turing:buffer  → List of last 10 message turns
# session:turing:turing:summary → Compressed summary of older messages

# Why this format?
# - "session:" prefix: All keys are grouped. Wildcard flush: redis.scan_iter("session:*")
# - thread_id: Isolates different conversation threads
# - philosopher_id: Isolates different philosophers
# - buffer/summary: Separates the two types of data
```

### `flush_all_sessions`
```python
async def flush_all_sessions(self) -> int:
    keys_to_delete = []
    async for key in self.redis.scan_iter("session:*"):
        # scan_iter: Iterates through all Redis keys matching "session:*"
        # Uses SCAN internally (not KEYS) to avoid blocking Redis on large databases.
        # KEYS command blocks Redis while it searches all keys. SCAN does it in small batches.
        keys_to_delete.append(key)

    if keys_to_delete:
        deleted = await self.redis.delete(*keys_to_delete)
        # *keys_to_delete: The * unpacks the list as individual arguments.
        # delete("key1", "key2", "key3") deletes all 3 in one command.
        return deleted

    return 0
```

### `get_agent_state` (The Read Function)
```python
async def get_agent_state(self, thread_id: str, philosopher_id: str):
    summary_key = self._get_summary_key(thread_id, philosopher_id)
    buffer_key = self._get_buffer_key(thread_id, philosopher_id)

    # Step 1: Try Redis first (L1 Cache)
    async with self.redis.pipeline() as pipe:
        pipe.get(summary_key)          # Get the summary string
        pipe.lrange(buffer_key, 0, -1) # Get ALL items in the buffer list (0=first, -1=last)
        summary, buffer_items = await pipe.execute()
        # Pipeline: Both commands are sent to Redis in ONE network trip.
        # Without pipeline: 2 separate network trips (slower).

    # Step 2: Cache Hit Check
    if summary is not None or len(buffer_items) > 0:
        # Either the summary exists OR the buffer has items → Cache HIT
        return {
            "summary": summary or "",   # If summary is None, return ""
            "buffer": [json.loads(item) for item in buffer_items],
            # json.loads(): Convert each JSON string back to a Python dict
        }

    # Step 3: Cache Miss → Fall back to MongoDB
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint_tuple = await self.checkpointer.aget_tuple(config)
    # aget_tuple(): LangGraph's async method to retrieve the checkpoint state from MongoDB.
    # Returns a CheckpointTuple object (or None if no checkpoint exists).

    if checkpoint_tuple and checkpoint_tuple.checkpoint:
        # checkpoint_tuple.checkpoint["channel_values"]["messages"] = list of all messages
        state_messages = checkpoint_tuple.checkpoint["channel_values"].get("messages", [])
        last_messages = state_messages[-BUFFER_LIMIT:]
        # Take only the last 10 messages (to warm up the Redis buffer)

        formatted_buffer = []
        async with self.redis.pipeline() as pipe:
            for i in range(0, len(last_messages) - 1, 2):
                # Step through messages 2 at a time (human, then AI)
                human_msg = last_messages[i]
                ai_msg = last_messages[i + 1] if i + 1 < len(last_messages) else None
                if ai_msg is None:
                    break
                item_json = json.dumps({"human": human_msg.content, "ai": ai_msg.content})
                # json.dumps(): Convert Python dict to JSON string for Redis storage
                formatted_buffer.append(item_json)
                pipe.rpush(buffer_key, item_json)
                # rpush: Push to the RIGHT (oldest at index 0).
                # During warmup we use rpush to preserve chronological order.

            if formatted_buffer:
                pipe.expire(buffer_key, SESSION_TTL)
                # Set the 24-hour expiration on the newly populated key
                await pipe.execute()

        return {"summary": "", "buffer": [json.loads(item) for item in formatted_buffer]}

    # Total cold start: New thread with no history anywhere
    return {"summary": "", "buffer": []}
```

### `save_interaction` (The Write Function)
```python
async def save_interaction(self, thread_id, philosopher_id, human_msg, ai_msg):
    buffer_key = self._get_buffer_key(thread_id, philosopher_id)

    interaction = json.dumps({"human": human_msg, "ai": ai_msg})
    # Convert dict to JSON string. Redis stores strings, not Python dicts.

    async with self.redis.pipeline() as pipe:
        pipe.lpush(buffer_key, interaction)
        # LPUSH: Push to the LEFT (front) of the list.
        # Index 0 = NEWEST message. Index 9 = OLDEST message.
        # The list grows from the left side.

        pipe.ltrim(buffer_key, 0, BUFFER_LIMIT - 1)
        # LTRIM: Keep only indices 0 to 9 (10 items total).
        # If there were 11 items, the item at index 10 (oldest) is automatically deleted.

        pipe.expire(buffer_key, SESSION_TTL)
        # EXPIRE: Reset the 24-hour timer.
        # If this is called on an existing key, the timer RESTARTS from now.
        # So active conversations never expire mid-chat.

        pipe.llen(buffer_key)
        # LLEN: Get the current length of the list AFTER trimming.

        results = await pipe.execute()
        buffer_length = results[-1]   # results = [lpush_result, ltrim_result, expire_result, llen_result]

    if buffer_length >= BUFFER_LIMIT:
        # Buffer is full (10 messages). Trigger compression.
        asyncio.create_task(self._background_summarize(thread_id, philosopher_id))
        # create_task(): Spawns a SEPARATE background task.
        # The current request does NOT wait for this to finish.
        # The user gets their response immediately while summarization runs in background.
```

### `_background_summarize` (The Compressor)
```python
async def _background_summarize(self, thread_id, philosopher_id):
    # Step 1: Get current state from Redis
    async with self.redis.pipeline() as pipe:
        pipe.get(summary_key)
        pipe.lrange(buffer_key, 0, -1)
        results = await pipe.execute()

    current_summary = results[0] or ""   # Existing summary (may be empty)
    buffer_items = results[1]            # The 10 raw message turns

    # Step 2: Format messages into text for the LLM
    interactions = [json.loads(item) for item in reversed(buffer_items)]
    # reversed(): Buffer was stored newest-first (LPUSH). Reverse for chronological order.

    history_text = "\n".join([f"Human: {i['human']}\nAI: {i['ai']}" for i in interactions])

    prompt = (
        f"You are a state manager for the AI philosopher: {philosopher_id}.\n"
        f"Compress the following interaction history into a concise, updated summary.\n\n"
        f"CURRENT SUMMARY:\n{current_summary}\n\n"
        f"NEW INTERACTIONS:\n{history_text}\n\n"
        f"Return ONLY the updated summary text."
    )

    # Step 3: Call the LLM
    response = await self.llm.ainvoke([HumanMessage(content=prompt)])
    new_summary = response.content

    # Step 4: Atomically update Redis
    async with self.redis.pipeline() as pipe:
        pipe.set(summary_key, new_summary, ex=SESSION_TTL)
        # set() with ex=: Sets the value AND the TTL in one command.

        pipe.delete(buffer_key)
        # Delete the raw buffer. It resets to 0 items.
        # The next 10 messages will start accumulating fresh.

        await pipe.execute()
```

---

## 8. `rag/retrievers.py`

**File:** `src/philoagents/application/rag/retrievers.py`
**Purpose:** Builds the hybrid search retriever that finds relevant philosopher knowledge from MongoDB.
**Technology:** HuggingFaceEmbeddings, MongoDBAtlasVectorSearch, MongoDBAtlasHybridSearchRetriever.

```python
def get_retriever(embedding_model_id, k=3, device="cpu"):
    embedding_model = get_embedding_model(embedding_model_id, device)
    # get_embedding_model(): Loads the HuggingFace embedding model from disk/cache.
    # "all-MiniLM-L6-v2": A pre-trained model that converts text into 384-dim vectors.
    # These vectors represent the "meaning" of the text as numbers.

    return get_hybrid_search_retriever(embedding_model, k)


def get_hybrid_search_retriever(embedding_model, k):
    vectorstore = MongoDBAtlasVectorSearch.from_connection_string(
        connection_string=settings.MONGO_URI,
        embedding=embedding_model,
        # embedding: The model used to convert query text into a vector for searching.

        namespace=f"{settings.MONGO_DB_NAME}.{settings.MONGO_LONG_TERM_MEMORY_COLLECTION}",
        # namespace: "philoagents.philosopher_long_term_memory"
        # This is the MongoDB collection that holds all philosopher knowledge chunks.

        text_key="chunk",
        # In MongoDB documents, the field named "chunk" contains the original text.

        embedding_key="embedding",
        # In MongoDB documents, the field named "embedding" contains the pre-computed vector.

        relevance_score_fn="dotProduct",
        # dotProduct: Mathematical formula to compare two vectors.
        # Higher dot product = more similar = more relevant.
    )

    retriever = MongoDBAtlasHybridSearchRetriever(
        vectorstore=vectorstore,
        search_index_name="hybrid_search_index",
        # The name of the MongoDB Atlas Search index configured in MongoDB Atlas UI.

        top_k=k,
        # Return the top 3 most relevant document chunks.

        vector_penalty=50,
        fulltext_penalty=50,
        # Reciprocal Rank Fusion (RRF) penalties.
        # Both are equal → 50% weight to vector search + 50% weight to keyword search.
        # Lower penalty = higher weight (counterintuitive but that's how RRF works).
    )
    return retriever

# HOW HYBRID SEARCH WORKS:
# 1. Vector Search: Convert query to vector → find chunks with similar vectors (semantic meaning)
#    Example: "thinking machine" matches chunks about "artificial intelligence"
# 2. BM25 Keyword Search: Find chunks containing the exact query words
#    Example: "Turing" matches chunks containing the exact word "Turing"
# 3. RRF Merging: Combine both result lists fairly using math formula
# 4. Return top 3 combined results
```

---

## 9. `workflow/state.py`

**File:** `src/philoagents/application/conversation_service/workflow/state.py`
**Purpose:** Defines the data that flows between all nodes in the LangGraph workflow.
**Think of it as:** A shared whiteboard every node can read from and write to.

```python
from langgraph.graph import MessagesState

class PhilosopherState(MessagesState):
    # MessagesState: A LangGraph built-in that includes a "messages" field.
    # messages = Annotated[list, add_messages]
    # The add_messages reducer means: APPEND new messages instead of replacing all messages.
    # So if you return {"messages": [new_message]}, it's ADDED to the existing list.

    philosopher_context: str
    # The RAG search results. After the retriever runs, the found document chunks are stored here.
    # Injected into the LLM prompt as reference material.

    philosopher_name: str
    # e.g., "Alan Turing"

    philosopher_perspective: str
    # How the philosopher views AI. Used in the system prompt.

    philosopher_style: str
    # How the philosopher talks. Used in the system prompt.

    philosopher_era: str
    # Time period guardrail. e.g., "1912-1954 AD"

    summary: str
    # The running conversation summary.
    # Comes from Redis (via get_agent_state) → passed into graph input → injected into prompt.
    # Updated by summarize_conversation_node when messages exceed 30.
```

---

## 10. `workflow/tools.py`

**File:** `src/philoagents/application/conversation_service/workflow/tools.py`
**Purpose:** Defines the tools the LLM can choose to call (function calling).

```python
# What is an LLM Tool?
# Modern LLMs can decide to "call a function" instead of directly answering.
# The LLM says "I need to look something up" and the system executes the function.
# The result is returned to the LLM, which then generates its final answer.

retriever = get_retriever(
    embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
    k=settings.RAG_TOP_K,
    device=settings.RAG_DEVICE
)
# Build the hybrid search retriever (reads from MongoDB).

retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_philosopher_context",
    # This is the TOOL NAME. The LLM uses this name to call it.

    "Search and return information about a specific philosopher. Always use this tool when "
    "the user asks you about a philosopher, their works, ideas or historical context."
    # This is the TOOL DESCRIPTION. The LLM reads this to decide WHEN to use the tool.
    # If the user asks about philosophy → LLM decides to call this tool.
    # If the user says "hello" → LLM decides to answer directly without calling any tool.
)

tools = [retriever_tool]
# List of all available tools. Passed to the LLM via model.bind_tools(tools).
```

---

## 11. `workflow/chains.py`

**File:** `src/philoagents/application/conversation_service/workflow/chains.py`
**Purpose:** Assembles LLM prompt templates + model calls into executable "chains".

```python
# What is a Chain?
# A chain is created using the | operator (pipe).
# prompt | model means:
# 1. Take the input data
# 2. Run it through "prompt" to create a formatted message
# 3. Pass that to "model" to generate a response

def get_chat_model(temperature=0.7, model_name=settings.GROQ_LLM_MODEL):
    return ChatGroq(
        api_key=settings.GROQ_API_KEY,
        model_name=model_name,
        temperature=temperature,
        # temperature=0.7: Slightly creative responses.
        # 0.0 = always the same answer (deterministic)
        # 1.0 = very random/creative
    )


def get_philosopher_response_chain():
    model = get_chat_model()
    model = model.bind_tools(tools)
    # bind_tools(): Attaches the retriever tool to the LLM.
    # Now the LLM can either answer directly OR call retrieve_philosopher_context.

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_message.prompt),
            # The PHILOSOPHER_CHARACTER_CARD goes here.
            # This is what makes the LLM act like Turing, Socrates, etc.

            MessagesPlaceholder(variable_name="messages"),
            # A slot filled at runtime with the actual conversation history.
            # e.g., [HumanMessage("what is turing test"), AIMessage("A test to...")]
        ],
        template_format="jinja2",
        # Use Jinja2 syntax: {{variable}} instead of {variable}
    )
    return prompt | model   # Chain: format prompt → call LLM → return response


def get_conversation_summary_chain(summary: str = ""):
    model = get_chat_model(model_name=settings.GROQ_LLM_MODEL_SUMMARY)
    # Uses the smaller, faster 8b model for summarization.

    summary_message = EXTEND_SUMMARY_PROMPT if summary else SUMMARY_PROMPT
    # If a summary already exists → extend it.
    # If no summary yet → create one from scratch.

    return prompt | model


def get_context_summary_chain():
    model = get_chat_model(model_name=settings.GROQ_LLM_MODEL_CONTEXT_SUMMARY)
    # Compresses RAG results into under 50 words.
    # Saves tokens in the main conversation prompt.
    return prompt | model
```

---

## 12. `workflow/nodes.py`

**File:** `src/philoagents/application/conversation_service/workflow/nodes.py`
**Purpose:** Python functions registered as nodes in the LangGraph state machine.
**Each node:** Reads from state → does work → returns state updates.

```python
retriever_node = ToolNode(tools)
# ToolNode: A LangGraph built-in node.
# When the conversation_node LLM returns a tool call (instead of text),
# ToolNode intercepts it, runs the retriever, and puts results back into the message state.


async def conversation_node(state: PhilosopherState, config: RunnableConfig):
    summary = state.get("summary", "")
    # Get the conversation summary from state (originally from Redis).

    conversation_chain = get_philosopher_response_chain()
    # Build the prompt + model chain.

    response = await conversation_chain.ainvoke(
        {
            "messages": state["messages"],              # Full conversation history
            "philosopher_context": state["philosopher_context"],  # RAG results
            "philosopher_name": state["philosopher_name"],
            "philosopher_perspective": state["philosopher_perspective"],
            "philosopher_style": state["philosopher_style"],
            "philosopher_era": state["philosopher_era"],
            "summary": summary,                          # Redis summary (long-term memory)
        },
        config,  # Passes callbacks (like OpikTracer) to the LLM call
    )
    return {"messages": response}
    # Return the AI's response as a message.
    # LangGraph's add_messages reducer APPENDS this to the existing messages list.


async def summarize_conversation_node(state: PhilosopherState):
    # Called when messages > 30 (TOTAL_MESSAGES_SUMMARY_TRIGGER).
    summary_chain = get_conversation_summary_chain(state.get("summary", ""))
    response = await summary_chain.ainvoke({"messages": state["messages"], ...})

    delete_messages = [
        RemoveMessage(id=m.id)
        for m in state["messages"][:-settings.TOTAL_MESSAGES_AFTER_SUMMARY]
    ]
    # Create RemoveMessage objects for ALL messages EXCEPT the last 5.
    # state["messages"][:-5] = all messages except the last 5
    # LangGraph processes RemoveMessage objects and deletes those messages from state.

    return {"summary": response.content, "messages": delete_messages}
    # Return: new summary text + instructions to delete old messages.


async def summarize_context_node(state: PhilosopherState):
    # Called AFTER the retriever returns RAG results.
    # Compresses the long retrieved text into < 50 words.
    context_summary_chain = get_context_summary_chain()
    response = await context_summary_chain.ainvoke(
        {"context": state["messages"][-1].content}
        # state["messages"][-1] = the last message = the tool result from the retriever
    )
    state["messages"][-1].content = response.content
    # Replace the long RAG text with the compressed summary IN PLACE.
    return {}   # Return empty dict (state was modified directly)


async def connector_node(state: PhilosopherState):
    return {}
    # A pass-through node. Does nothing.
    # Used as a routing junction in the graph.
    # After conversation_node gives a final answer → go to connector_node
    # → connector_node sends to should_summarize_conversation edge.
```

---

## 13. `workflow/edges.py`

**File:** `src/philoagents/application/conversation_service/workflow/edges.py`
**Purpose:** Functions that make routing decisions in the LangGraph graph.

```python
def should_summarize_conversation(
    state: PhilosopherState,
) -> Literal["summarize_conversation_node", "__end__"]:
    # Literal["...", "..."]: The return type is restricted to EXACTLY these two values.
    # Python errors if you return anything else.

    messages = state["messages"]

    if len(messages) > settings.TOTAL_MESSAGES_SUMMARY_TRIGGER:  # > 30
        return "summarize_conversation_node"
        # Tell LangGraph: "Go to the summarize_conversation_node next."

    return END
    # END = "__end__" = Stop the graph execution here.

# SIMPLE LOGIC: "Are there more than 30 messages? If yes → summarize. Otherwise → end."
# NOTE: This is the LANGGRAPH-level summarization (at 30 messages).
# There is also a REDIS-level summarization (at 10 turns) in memory_orchestrator.py.
# They are TWO separate systems serving different purposes.
```

---

## 14. `workflow/graph.py`

**File:** `src/philoagents/application/conversation_service/workflow/graph.py`
**Purpose:** Assembles all nodes, edges, and tools into a complete executable LangGraph state machine.

```python
from functools import lru_cache

@lru_cache(maxsize=1)
def create_workflow_graph():
    # @lru_cache(maxsize=1): Cache the result of this function.
    # The graph is expensive to build (loads embedding models, etc.).
    # maxsize=1: Store exactly 1 cached result.
    # The SAME graph object is reused for EVERY request (built only once).

    graph_builder = StateGraph(PhilosopherState)
    # StateGraph: LangGraph's main class for building state machines.
    # PhilosopherState: The data schema that flows through all nodes.

    # --- ADD NODES ---
    graph_builder.add_node("conversation_node", conversation_node)
    graph_builder.add_node("retrieve_philosopher_context", retriever_node)
    graph_builder.add_node("summarize_conversation_node", summarize_conversation_node)
    graph_builder.add_node("summarize_context_node", summarize_context_node)
    graph_builder.add_node("connector_node", connector_node)
    # add_node(name, function): Register a function as a node with a given name.

    # --- DEFINE EDGES (The Flow) ---

    graph_builder.add_edge(START, "conversation_node")
    # The graph ALWAYS starts at conversation_node.

    graph_builder.add_conditional_edges(
        "conversation_node",      # FROM this node
        tools_condition,          # Use this function to decide where to go
        {
            "tools": "retrieve_philosopher_context",  # If LLM called a tool → go here
            END: "connector_node"                     # If LLM gave final answer → go here
        }
    )
    # tools_condition: A LangGraph built-in function.
    # It checks: "Did the last AI message contain a tool call?"
    # Yes → return "tools"
    # No  → return END

    graph_builder.add_edge("retrieve_philosopher_context", "summarize_context_node")
    # After RAG retrieval → compress the results.

    graph_builder.add_edge("summarize_context_node", "conversation_node")
    # After compression → go BACK to conversation_node.
    # Now the LLM has the RAG results and can generate a proper answer.

    graph_builder.add_conditional_edges("connector_node", should_summarize_conversation)
    # After conversation ends at connector_node → check if we need to summarize.

    graph_builder.add_edge("summarize_conversation_node", END)
    # After summarizing → always end.

    return graph_builder


# COMPLETE FLOW DIAGRAM:
#
#  START
#    ↓
#  conversation_node  ←──────────────────────────┐
#    ↓                                            │
#    ├── (LLM called a tool?) ──→ retrieve_philosopher_context
#    │                                    ↓
#    │                            summarize_context_node ──┘
#    │
#    └── (LLM gave final answer?) ──→ connector_node
#                                          ↓
#                              (messages > 30?) ──→ summarize_conversation_node → END
#                                          ↓ (≤30)
#                                         END
```

---

## 15. `generate_response.py`

**File:** `src/philoagents/application/conversation_service/generate_response.py`
**Purpose:** Bridges the API layer and LangGraph graph. Runs the full workflow and returns the AI response.

```python
async def get_response(
    messages,         # The user's current message
    philosopher_id,   # e.g., "turing"
    philosopher_name, # e.g., "Alan Turing"
    ...
    orchestrator,     # The MemoryOrchestrator (Redis)
    mongodb_saver,    # The MongoDB checkpointer
):
    graph_builder = create_workflow_graph()
    # Get the cached graph builder (built only once, reused forever).

    graph = graph_builder.compile(checkpointer=mongodb_saver)
    # compile(): Finalizes the graph and makes it executable.
    # checkpointer=mongodb_saver: Attach MongoDB. LangGraph will auto-save state
    # after EVERY node execution to MongoDB.

    opik_tracer = OpikTracer(graph=graph.get_graph(xray=True))
    # Create Opik tracer with xray=True (sees inside the graph structure).
    # This creates the detailed traces you saw in Opik showing all messages.

    thread_id = philosopher_id if not new_thread else f"{philosopher_id}-{uuid.uuid4()}"
    # thread_id: Groups all messages of the same conversation together.
    # new_thread=False (default): All chats with "turing" share thread_id = "turing".
    # new_thread=True: Creates a unique ID per session (used in evaluation).

    fast_state = await orchestrator.get_agent_state(thread_id, philosopher_id)
    # Check Redis first. Returns {summary, buffer} or empty dicts if cache miss.

    summary = fast_state.get("summary") or ""
    # Guard: If Redis returns None, use "" instead.
    # Without this guard, LangGraph would crash trying to process None as a string.

    config = {
        "configurable": {"thread_id": thread_id},
        # thread_id tells MongoDB which conversation to load/save checkpoints for.

        "callbacks": [opik_tracer],
        # Registers Opik to intercept all LLM calls in this graph execution.
    }

    output_state = await graph.ainvoke(
        input={
            "messages": __format_messages(messages),
            # __format_messages(): Converts string input to [HumanMessage("...")] list.

            "philosopher_name": philosopher_name,
            "philosopher_perspective": philosopher_perspective,
            "philosopher_style": philosopher_style,
            "philosopher_era": philosopher_era,
            "philosopher_context": philosopher_context,  # Empty initially; filled by RAG node
            "summary": summary,                          # From Redis
        },
        config=config,
    )
    # ainvoke(): Runs the ENTIRE LangGraph workflow asynchronously.
    # Internally: START → conversation_node → (maybe retrieval) → END
    # MongoDB saves checkpoint after each node.

    last_message = output_state["messages"][-1]
    # After the graph finishes, the LAST message in the state is the AI's response.

    await orchestrator.save_interaction(
        thread_id=thread_id,
        philosopher_id=philosopher_id,
        human_msg=human_msg,          # The user's original question
        ai_msg=last_message.content   # The AI's response
    )
    # Save this turn to Redis for the next message.

    return last_message.content, PhilosopherState(**output_state)
    # Return: the response text + the final state object.
```

---

## 16. `reset_conversation.py`

**File:** `src/philoagents/application/conversation_service/reset_conversation.py`
**Purpose:** Wipes ALL conversation state from both Redis and MongoDB.

```python
async def reset_conversation_state(orchestrator: "MemoryOrchestrator") -> dict:
    # Step 1: Flush Redis L1 Cache
    redis_keys_deleted = await orchestrator.flush_all_sessions()
    # Deletes ALL "session:*" keys from Redis.
    # After this, Redis has zero conversation data.

    # Step 2: Drop MongoDB checkpoint collections
    client = MongoClient(settings.MONGO_URI)
    # MongoClient: Synchronous MongoDB client.
    # For a one-time admin operation (dropping collections), sync is fine.
    # The async client (AsyncMongoDBSaver) is used for high-frequency chat operations.

    db = client[settings.MONGO_DB_NAME]
    # Access the "philoagents" database.

    if settings.MONGO_STATE_CHECKPOINT_COLLECTION in db.list_collection_names():
        db.drop_collection(settings.MONGO_STATE_CHECKPOINT_COLLECTION)
        # drop_collection(): Completely removes the collection. ALL data is permanently deleted.
        # This collection holds LangGraph's full state snapshots.

    if settings.MONGO_STATE_WRITES_COLLECTION in db.list_collection_names():
        db.drop_collection(settings.MONGO_STATE_WRITES_COLLECTION)
        # This collection holds LangGraph's state change records.
        # Both collections must be dropped to fully reset LangGraph's memory.

    client.close()
    # Always close the connection when done.

    return {"status": "success", "message": f"Flushed {redis_keys_deleted} Redis keys."}

# WHY NOT drop "philosopher_long_term_memory"?
# That collection holds the philosopher knowledge base (books, essays).
# It should NEVER be deleted during a reset — that would erase the RAG data!
# Only the CONVERSATION state (checkpoints + writes) is reset.
```

---

## 17. Complete Request Flow Diagram

When you send: `POST /chat {"message": "What is the Turing test?", "philosopher_id": "turing"}`

```
USER
  │
  │ HTTP POST /chat
  ▼
api.py
  ├── Parse ChatMessage(message="What is the Turing test?", philosopher_id="turing")
  ├── PhilosopherFactory.get_philosopher("turing")
  │     → Returns Philosopher(name="Alan Turing", era="1912-1954", style="...")
  │
  ├── get_response(message, philosopher_id, philosopher_name, ...)
  │
  ▼
generate_response.py
  │
  ├── create_workflow_graph() → get cached graph
  ├── graph.compile(checkpointer=mongodb_saver)
  │
  ├── orchestrator.get_agent_state("turing", "turing")
  │   │
  │   ├── Redis pipeline: GET summary_key + LRANGE buffer_key
  │   ├── CACHE HIT → return {summary: "...", buffer: [...]}
  │   └── CACHE MISS → MongoDB.aget_tuple() → warm Redis → return state
  │
  ├── graph.ainvoke({messages: [HumanMessage("What is the Turing test?")], summary: "...", ...})
  │
  ▼
LANGGRAPH EXECUTION:
  │
  ├── [Node: conversation_node]
  │     LLM reads: system_prompt (with era guardrail + summary) + messages
  │     LLM decides: "I should look up info about the Turing test"
  │     LLM returns: ToolCall(name="retrieve_philosopher_context")
  │
  ├── [Conditional Edge: tools_condition → "tools"]
  │
  ├── [Node: retrieve_philosopher_context]
  │     MongoDB Hybrid Search:
  │       Vector Search → finds semantically similar text chunks
  │       BM25 Search   → finds chunks with exact keywords
  │       RRF merges    → returns top 3 document chunks
  │     Result stored as ToolMessage in messages list
  │
  ├── [Node: summarize_context_node]
  │     Compresses the 3 RAG chunks into < 50 words
  │
  ├── [Edge: back to conversation_node]
  │
  ├── [Node: conversation_node] (2nd time)
  │     LLM now has: persona + history + compressed RAG context
  │     LLM generates: "My Turing Test is a way to see if a machine can think..."
  │     LLM returns: AIMessage (no tool call)
  │
  ├── [Conditional Edge: tools_condition → connector_node]
  │
  ├── [Node: connector_node] → pass-through (does nothing)
  │
  └── [Conditional Edge: should_summarize_conversation]
        len(messages) = 3, which is < 30 → return END
  │
  ▼
Back in generate_response.py:
  │
  ├── last_message = output_state["messages"][-1]
  │     = AIMessage("My Turing Test is a way to see...")
  │
  ├── orchestrator.save_interaction("turing", "turing", "What is...", "My Turing Test...")
  │     Redis Pipeline:
  │       LPUSH session:turing:turing:buffer '{"human":"...","ai":"..."}'
  │       LTRIM session:turing:turing:buffer 0 9
  │       EXPIRE session:turing:turing:buffer 86400
  │       LLEN → returns 1 (< 10, no summarization triggered)
  │
  └── return "My Turing Test is a way to see..."
  │
  ▼
api.py:
  │
  └── return {"response": "My Turing Test is a way to see if a machine can think like a human..."}
  │
  ▼
USER receives the response ✓
```

---

## Key Takeaways

| Concept | How it works in this project |
|---------|------------------------------|
| **Why Redis?** | Avoids reading MongoDB on every message. Active chats are served from RAM (< 1ms). |
| **Why 2 summarizations?** | Redis summarizes at 10 turns (fast, per-session). LangGraph summarizes at 30 messages (full graph-level). |
| **Why MongoDB?** | Permanent backup. Redis data disappears after 24h or container restart. MongoDB never loses data. |
| **Why Hybrid Search?** | Keyword search finds exact names/terms. Vector search finds related concepts. Together they cover both cases. |
| **Why LangGraph?** | Manages the complex multi-step flow: respond → maybe retrieve → maybe summarize. Handles state, checkpoints, and tool calls. |
| **Why Opik?** | Logs every LLM call. If the AI behaves unexpectedly, you can trace exactly what prompt + context it received. |
