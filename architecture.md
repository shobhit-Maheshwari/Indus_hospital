# PhiloAgents — Complete Architecture & Redis Deep Dive

## 1. localhost vs 127.0.0.1 — What's the Difference?

> [!NOTE]
> **They are the same thing.** `localhost` is just a hostname alias that resolves to `127.0.0.1` (IPv4 loopback). Your browser/curl can use either interchangeably. Docker maps `0.0.0.0:8000` inside the container to your host's `127.0.0.1:8000`.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HOST MACHINE (Windows)                           │
│                                                                         │
│  Browser / curl                                                         │
│  http://127.0.0.1:8080  ──►  philoagents-ui  (Vite / Node)            │
│  http://127.0.0.1:8000  ──►  philoagents-api (FastAPI / Python)        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                    Docker Network: philoagents-network            │  │
│  │                                                                   │  │
│  │  ┌───────────────┐   WebSocket/HTTP   ┌────────────────────────┐ │  │
│  │  │  philoagents  │ ◄────────────────► │    philoagents-api     │ │  │
│  │  │      -ui      │                    │  FastAPI  port:8000    │ │  │
│  │  │  port:8080    │                    │                        │ │  │
│  │  └───────────────┘                    │  ┌──────────────────┐  │ │  │
│  │                                       │  │  LangGraph       │  │ │  │
│  │                                       │  │  Workflow Graph  │  │ │  │
│  │                                       │  └────────┬─────────┘  │ │  │
│  │                                       └───────────┼────────────┘ │  │
│  │                                                   │               │  │
│  │              ┌────────────────────────────────────┼─────────────┐│  │
│  │              │                                    │              ││  │
│  │              ▼                                    ▼              ││  │
│  │  ┌─────────────────────┐           ┌─────────────────────────┐  ││  │
│  │  │  philoagents-redis  │           │  philoagents-course-    │  ││  │
│  │  │  Redis 7 Alpine     │           │  local_dev_atlas        │  ││  │
│  │  │  port: 6379         │           │  MongoDB Atlas Local 8  │  ││  │
│  │  │                     │           │  port: 27017            │  ││  │
│  │  │  L1 Fast Cache      │           │                         │  ││  │
│  │  │  (session state)    │           │  L2 Persistent Store    │  ││  │
│  │  └─────────────────────┘           │  • LangGraph checkpts   │  ││  │
│  │                                    │  • Long-term memory     │  ││  │
│  │                                    │  • RAG vector index     │  ││  │
│  │                                    └─────────────────────────┘  ││  │
│  │                                                                  ││  │
│  │  External APIs: Groq (LLM) ──► internet ◄── HuggingFace (embed) ││  │
│  └──────────────────────────────────────────────────────────────────┘│  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Memory Architecture — L1 (Redis) + L2 (MongoDB)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TWO-TIER MEMORY SYSTEM                          │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  L1 CACHE — Redis (Millisecond Access)                       │  │
│  │                                                              │  │
│  │  Key: session:{thread_id}:{philosopher_id}:buffer            │  │
│  │  Type: Redis List (LPUSH → newest at index 0)                │  │
│  │  Value: [{"human": "...", "ai": "..."}, ...]  max 10 items  │  │
│  │  TTL: 24 hours                                               │  │
│  │                                                              │  │
│  │  Key: session:{thread_id}:{philosopher_id}:summary           │  │
│  │  Type: Redis String                                          │  │
│  │  Value: "Compressed conversation summary text..."            │  │
│  │  TTL: 24 hours                                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                    Buffer fills (≥10 items)                         │
│                              │                                      │
│                              ▼ Background Task (asyncio)            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  SUMMARIZATION (Groq llama-3.1-8b-instant)                   │  │
│  │  Compresses buffer → new summary string → write back Redis    │  │
│  │  Buffer is DELeted after summarization                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  L2 STORE — MongoDB (Second-level, persistent)               │  │
│  │                                                              │  │
│  │  Collection: philosopher_state_checkpoints                   │  │
│  │  Collection: philosopher_state_writes                        │  │
│  │  → Managed by LangGraph's AsyncMongoDBSaver                  │  │
│  │  → Contains FULL message history as LangGraph checkpoints    │  │
│  │                                                              │  │
│  │  Collection: philosopher_long_term_memory                    │  │
│  │  → Philosopher knowledge (Wikipedia chunks, vector-indexed)  │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Redis Hit/Miss Sequence Diagram

```
Client                  FastAPI              MemoryOrchestrator        Redis              MongoDB
  │                        │                         │                    │                   │
  │  POST /chat            │                         │                    │                   │
  │  {"message":"...",     │                         │                    │                   │
  │   "philosopher_id":    │                         │                    │                   │
  │   "turing"}            │                         │                    │                   │
  │ ──────────────────────►│                         │                    │                   │
  │                        │  get_agent_state(       │                    │                   │
  │                        │    thread_id,           │                    │                   │
  │                        │    philosopher_id)      │                    │                   │
  │                        │ ───────────────────────►│                    │                   │
  │                        │                         │  PIPELINE GET      │                   │
  │                        │                         │  GET summary_key   │                   │
  │                        │                         │  LRANGE buffer_key │                   │
  │                        │                         │ ──────────────────►│                   │
  │                        │                         │                    │                   │
  │                        │                    ╔════╪════════════════════╪═══════════════╗   │
  │                        │                    ║    │  CACHE HIT?         │               ║   │
  │                        │                    ╚════╪════════════════════╪═══════════════╝   │
  │                        │                         │                    │                   │
  │                    ┌───┤  [HIT] summary/buffer found in Redis         │                   │
  │                    │   │                         │◄──────────────────┤                   │
  │                    │   │                         │ Returns summary+   │                   │
  │                    │   │                         │ buffer in ~1ms     │                   │
  │                    │   │                         │                    │                   │
  │                    └───┤  [MISS] nothing in Redis                     │                   │
  │                        │                         │   nil, []          │                   │
  │                        │                         │◄──────────────────┤                   │
  │                        │                         │                    │                   │
  │                        │                         │  Cold-start:       │                   │
  │                        │                         │  aget_tuple(config)│                   │
  │                        │                         │ ──────────────────────────────────────►│
  │                        │                         │                    │                   │
  │                        │                         │◄──────────────────────────────────────┤
  │                        │                         │  checkpoint_tuple  │                   │
  │                        │                         │  (full history)    │                   │
  │                        │                         │                    │                   │
  │                        │                         │  Warm Redis cache  │                   │
  │                        │                         │  RPUSH buffer_key  │                   │
  │                        │                         │  EXPIRE buffer_key │                   │
  │                        │                         │ ──────────────────►│                   │
  │                        │                         │                    │                   │
  │                        │ {summary, buffer}       │                    │                   │
  │                        │◄────────────────────────│                    │                   │
  │                        │                         │                    │                   │
  │                        │  LangGraph.ainvoke(...)  [Groq LLM API call] │                   │
  │                        │ ─────────────────────────────────────────────────────────────►[Groq]
  │                        │◄─────────────────────────────────────────────────────────────[Groq]
  │                        │  AI Response            │                    │                   │
  │                        │                         │                    │                   │
  │                        │  save_interaction(...)  │                    │                   │
  │                        │ ───────────────────────►│                    │                   │
  │                        │                         │  LPUSH buffer_key  │                   │
  │                        │                         │  LTRIM (max 10)    │                   │
  │                        │                         │  EXPIRE (24h TTL)  │                   │
  │                        │                         │  LLEN buffer_key   │                   │
  │                        │                         │ ──────────────────►│                   │
  │                        │                         │◄──────────────────┤                   │
  │                        │                         │  buffer_length     │                   │
  │                        │                         │                    │                   │
  │                        │              ╔═══════════╪════════════════════╪══════════════╗   │
  │                        │              ║  buffer_length >= 10?          │               ║   │
  │                        │              ╚═══════════╪════════════════════╪══════════════╝   │
  │                        │                         │                    │                   │
  │                        │           [YES] asyncio.create_task(         │                   │
  │                        │                _background_summarize)        │                   │
  │                        │           [Non-blocking background task]     │                   │
  │                        │                         │                    │                   │
  │  {"response":"..."}    │                         │                    │                   │
  │◄───────────────────────│                         │                    │                   │
```

---

## 5. Complete Chat Request Flow — Sequence Diagram

```
Browser/curl            UI (8080)         API (8000)       LangGraph       Groq LLM       MongoDB        Redis
     │                     │                  │                │               │               │             │
     │  WebSocket connect  │                  │                │               │               │             │
     │────────────────────►│                  │                │               │               │             │
     │                     │  /ws/chat        │                │               │               │             │
     │                     │─────────────────►│                │               │               │             │
     │                     │                  │                │               │               │             │
     │  {message,          │                  │                │               │               │             │
     │   philosopher_id}   │                  │                │               │               │             │
     │────────────────────►│─────────────────►│                │               │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │ 1. get_agent_  │               │               │             │
     │                     │                  │    state()     │               │               │             │
     │                     │                  │────────────────────────────────────────────────────────────►│
     │                     │                  │                │               │               │  GET/LRANGE │
     │                     │                  │◄───────────────────────────────────────────────────────────┤
     │                     │                  │  {summary,buf} │               │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │ 2. compile_    │               │               │             │
     │                     │                  │    graph()     │               │               │             │
     │                     │                  │───────────────►│               │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │ 3. astream()   │               │               │             │
     │                     │                  │───────────────►│               │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │                │ conversation_ │               │             │
     │                     │                  │                │ node()        │               │             │
     │                     │                  │                │──────────────►│               │             │
     │                     │                  │                │               │ [Groq API]    │             │
     │                     │                  │                │◄──────────────│               │             │
     │                     │                  │                │  AI chunks    │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │  4. Tool call? │               │               │             │
     │                     │                  │                │ retrieve_     │               │             │
     │                     │                  │                │ philosopher_  │               │             │
     │                     │                  │                │ context()     │               │             │
     │                     │                  │                │──────────────────────────────►│             │
     │                     │                  │                │               │  MongoDB      │             │
     │                     │                  │                │               │  Vector Search│             │
     │                     │                  │                │◄──────────────────────────────│             │
     │                     │                  │                │  RAG context  │               │             │
     │                     │                  │                │──────────────►│               │             │
     │                     │                  │                │               │ [Groq + RAG]  │             │
     │                     │                  │                │◄──────────────│               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │  5. Checkpoint │               │               │             │
     │                     │                  │     saved      │               │               │             │
     │                     │                  │                │──────────────────────────────►│             │
     │                     │                  │                │               │  MongoDB write│             │
     │                     │                  │                │               │               │             │
     │  {"chunk":"..."}    │                  │                │               │               │             │
     │◄────────────────────│◄─────────────────│                │               │               │             │
     │  (streaming)        │  chunk stream    │                │               │               │             │
     │                     │                  │                │               │               │             │
     │                     │                  │ 6. save_       │               │               │             │
     │                     │                  │    interaction │               │               │             │
     │                     │                  │────────────────────────────────────────────────────────────►│
     │                     │                  │                │               │               │  LPUSH/TRIM │
     │                     │                  │◄───────────────────────────────────────────────────────────┤
     │                     │                  │                │               │               │             │
     │  {response,         │                  │                │               │               │             │
     │   streaming:false}  │                  │                │               │               │             │
     │◄────────────────────│◄─────────────────│                │               │               │             │
```

---

## 6. LangGraph Workflow — Internal Node Flow

```
START
  │
  ▼
┌─────────────────┐
│ conversation_   │  Uses Groq llama-3.3-70b-versatile
│ node()          │  Receives: messages, summary, philosopher context
│                 │  May call tools → goes to retriever
└────────┬────────┘
         │
    tools_condition
   /              \
  /                \
 ▼                  ▼
┌──────────────┐  ┌──────────────────┐
│ retrieve_    │  │  connector_node  │  (passthrough)
│ philosopher  │  │                  │
│ _context     │  └────────┬─────────┘
│ (ToolNode)   │           │
└──────┬───────┘           │  should_summarize_conversation()
       │                   │
       ▼                   ├── len(messages) > 30? ──► summarize_conversation_node
┌──────────────────┐       │
│ summarize_       │       └── else ──► END
│ context_node()   │
│                  │  summarize_conversation_node
│ Condenses RAG    │  ┌─────────────────────────────┐
│ results into     │  │ Uses llama-3.1-8b-instant    │
│ brief context    │  │ Creates summary, trims old   │
└──────┬───────────┘  │ messages to last 5           │
       │              └──────────────┬───────────────┘
       └──► back to                  │
            conversation_node        ▼
                                    END
```

---

## 7. How to Monitor Redis Hit/Miss in Real-Time

### Option A — Redis CLI Stats (Server-side)
```bash
# Watch live keyspace hits/misses every 1 second
docker exec philoagents-redis redis-cli info stats | grep keyspace

# Current result after your curl test:
# keyspace_hits: 3   ← Redis cache hits
# keyspace_misses: 3 ← Redis cache misses (cold starts)
```

### Option B — View Actual Redis Keys & Buffer Contents
```bash
# List all session keys
docker exec philoagents-redis redis-cli keys "session:*"

# Read the buffer for turing (your test philosopher)
docker exec philoagents-redis redis-cli lrange "session:turing:turing:buffer" 0 -1

# Read the summary (populated after 10+ interactions)
docker exec philoagents-redis redis-cli get "session:turing:turing:summary"

# Get buffer length
docker exec philoagents-redis redis-cli llen "session:turing:turing:buffer"

# Check TTL remaining (in seconds)
docker exec philoagents-redis redis-cli ttl "session:turing:turing:buffer"
```

### Option C — Watch API Logs for Cache Hit/MISS Messages
```bash
docker compose logs api -f
# Look for lines like:
# "L1 Cache HIT for thread turing"    ← Redis served the state
# "L1 Cache MISS for thread turing"   ← Had to go to MongoDB
```

### Option D — Redis Monitor (Live command stream)
```bash
# See every Redis command in real-time
docker exec philoagents-redis redis-cli monitor
# Then fire another curl request to see the GET/LPUSH/LRANGE commands live
```

---

## 8. Current Redis State (After Your Test)

```
Redis db0:
  keys=1, expires=1, avg_ttl=84294s (~23.4 hours remaining)

  session:turing:turing:buffer  (Redis List, 7 items)
  ├── [0] {"human": "what you think about machines can think?", "ai": "..."}  ← newest
  ├── [1] {"human": "can machine think?",                       "ai": "..."}
  ├── [2] {"human": "what you think about machines?",           "ai": "..."}
  ├── [3] {"human": "hii who are you?",                         "ai": "..."}
  ├── [4] {"human": "hii",                                      "ai": "..."}
  ├── [5] {"human": "what is turing test",                      "ai": "..."}
  └── [6] {"human": "what is turing test",                      "ai": "..."}  ← oldest

  keyspace_hits:   3  (subsequent requests served from Redis)
  keyspace_misses: 3  (first request, went to MongoDB cold-start)
```

> [!TIP]
> When the buffer reaches **10 items**, the `_background_summarize()` task fires automatically (non-blocking). It calls Groq to compress the buffer into a summary string, stores it as `session:turing:turing:summary`, and **deletes** the buffer key to reset the sliding window.

---

## 9. Component Responsibility Summary

| Component | Technology | Role |
|-----------|-----------|------|
| **philoagents-ui** | Vite + Node 18 | Frontend chat interface on port 8080 |
| **philoagents-api** | FastAPI + Python 3.11 | REST + WebSocket API on port 8000 |
| **MemoryOrchestrator** | Custom class | Manages Redis L1 cache + background summarization |
| **LangGraph** | StateGraph | Orchestrates conversation workflow (nodes, edges) |
| **AsyncMongoDBSaver** | LangGraph checkpoint | Persists full message history to MongoDB |
| **ChatGroq** | Groq API | LLM inference (llama-3.3-70b for chat, llama-3.1-8b for summary) |
| **HuggingFace Embeddings** | sentence-transformers | Embeds text for RAG vector search |
| **philoagents-redis** | Redis 7 Alpine | L1 fast cache — session buffer + summary (24h TTL) |
| **MongoDB Atlas Local** | MongoDB 8.0 | L2 persistent — LangGraph state + RAG vector index |

