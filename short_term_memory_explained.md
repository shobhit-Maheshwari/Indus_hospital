# Short-Term Memory: MongoDB → Redis Architecture

## Part 1 — How Short-Term Memory Was Stored in MongoDB (Before / Without Redis)

Short-term memory is **NOT** stored by your own code. It is stored automatically by **LangGraph's `AsyncMongoDBSaver` checkpointer**. Every time the LangGraph `graph.ainvoke()` runs, LangGraph serializes the entire `PhilosopherState` and writes it into two MongoDB collections.

### The Two MongoDB Collections

| Collection | Setting Key | Default Name | Purpose |
|---|---|---|---|
| `checkpoints` | `MONGO_STATE_CHECKPOINT_COLLECTION` | `philosopher_state_checkpoints` | Stores the full serialized state after each graph step |
| `writes` | `MONGO_STATE_WRITES_COLLECTION` | `philosopher_state_writes` | Stores pending/intermediate write operations per node |

Configured in [`api.py` (lines 45–50)](file:///c:/Users/BIT/OneDrive/Desktop/a/philoagents-course/philoagents-api/src/philoagents/infrastructure/api.py#L45-L50):
```python
async with AsyncMongoDBSaver.from_conn_string(
    conn_string=settings.MONGO_URI,
    db_name=settings.MONGO_DB_NAME,
    checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
    writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
) as saver:
```

---

### MongoDB Document Structure

#### `philosopher_state_checkpoints` — one document per conversation turn

```json
{
  "_id": ObjectId("..."),
  "thread_id": "aristotle",           // the philosopher_id used as thread key
  "checkpoint_ns": "",
  "checkpoint_id": "1ef8a3b2-...",    // UUID for this specific checkpoint
  "parent_checkpoint_id": "...",      // links to the previous checkpoint
  "type": "empty",
  "checkpoint": {
    "v": 1,
    "ts": "2025-01-01T10:00:00",
    "id": "1ef8a3b2-...",
    "channel_values": {
      "messages": [
        {
          "lc": 1,
          "type": "constructor",
          "id": ["langchain_core", "messages", "HumanMessage"],
          "kwargs": {
            "content": "What do you think about AI?",
            "id": "msg-uuid-1"
          }
        },
        {
          "lc": 1,
          "type": "constructor",
          "id": ["langchain_core", "messages", "AIMessage"],
          "kwargs": {
            "content": "A fascinating question, young one...",
            "id": "msg-uuid-2"
          }
        }
      ],
      "philosopher_name": "Aristotle",
      "philosopher_perspective": "...",
      "philosopher_style": "...",
      "philosopher_era": "Ancient Greece",
      "philosopher_context": "...",
      "summary": ""                    // filled after summarize_conversation_node fires
    },
    "channel_versions": { ... },
    "versions_seen": { ... },
    "pending_sends": []
  },
  "metadata": {
    "source": "loop",
    "step": 4,
    "writes": { ... }
  }
}
```

> Every message exchange **appends** to `channel_values.messages`. The summary field gets populated when `summarize_conversation_node` fires (after `TOTAL_MESSAGES_SUMMARY_TRIGGER = 30` messages).

#### `philosopher_state_writes` — intermediate node output

```json
{
  "_id": ObjectId("..."),
  "thread_id": "aristotle",
  "checkpoint_ns": "",
  "checkpoint_id": "1ef8a3b2-...",
  "task_id": "...",
  "idx": 0,
  "channel": "messages",
  "type": "msgpack",
  "value": "<binary serialized node output>"
}
```

---

### How It Worked Without Redis (Pure MongoDB Flow)

```
User Message
     │
     ▼
get_response() in generate_response.py
     │
     ├── graph.ainvoke(input={..., "summary": ""})
     │       │
     │       ├── LangGraph reads PREVIOUS checkpoint from MongoDB
     │       │   (to restore full conversation state)
     │       │
     │       ├── conversation_node() runs LLM
     │       │
     │       ├── [if > 30 messages] summarize_conversation_node() runs
     │       │
     │       └── LangGraph writes NEW checkpoint to MongoDB
     │
     └── Returns last message
```

**Problem**: Every single request did a MongoDB `find()` (read the full checkpoint with ALL past messages) **before** LLM inference. As conversation grew, the document got larger and this read got slower.

---

## Part 2 — How Redis Saves Time (While MongoDB Still Stores Everything)

Redis acts as an **L1 (Level-1) Cache** in front of MongoDB. Think of it like CPU caches — L1 is fast SRAM, L2 is slower DRAM.

```
Redis (L1)  ←  In-memory, ~0.1ms latency, sliding window of 10 turns
MongoDB (L2) ←  Disk-backed, ~5-50ms latency, complete checkpoint history
```

### The Two Redis Keys Per Session

```
session:{thread_id}:{philosopher_id}:buffer   ← List of last 10 interactions
session:{thread_id}:{philosopher_id}:summary  ← Compressed text summary
```

Example with `philosopher_id = "aristotle"`:
```
session:aristotle:aristotle:buffer   → Redis List (newest first via LPUSH)
session:aristotle:aristotle:summary  → Redis String
```

Both keys have a **TTL of 24 hours** (`SESSION_TTL = 86400`).

---

### Buffer Structure (Redis List)

Each item in the list is a JSON string:
```json
{"human": "What is virtue?", "ai": "Virtue, my friend, is excellence of character..."}
```

Maximum **10 items** enforced by `LTRIM` after every `LPUSH` (sliding window).

---

### The Full Flow With Redis

```
User Message
     │
     ▼
orchestrator.get_agent_state(thread_id, philosopher_id)
     │
     ├── [FAST PATH] Redis pipeline: GET summary + LRANGE buffer
     │       │
     │       ├── Cache HIT? → Return {summary, buffer} in ~0.1ms ✅
     │       │
     │       └── Cache MISS? → Cold-Start from MongoDB
     │               │
     │               └── checkpointer.aget_tuple(config)
     │                       Reads last checkpoint, extracts last 10 messages
     │                       Warms Redis buffer with those messages
     │
     ▼
graph.ainvoke(input={..., "summary": summary_from_redis})
     │   (MongoDB still writes checkpoint here — unchanged)
     │
     ▼
orchestrator.save_interaction(human_msg, ai_msg)
     │
     ├── LPUSH new interaction to Redis buffer
     ├── LTRIM to keep only last 10
     ├── EXPIRE to refresh 24h TTL
     │
     └── [if buffer_length >= 10] → asyncio.create_task(_background_summarize)
             │
             ├── LLM compresses buffer → new summary text
             ├── SET summary key in Redis (ex=24h)
             └── DELETE buffer key (reset sliding window)
```

---

### Where Time Is Saved — The Critical Difference

| Operation | Without Redis | With Redis |
|---|---|---|
| Read conversation history | Full MongoDB document scan (~5–50ms, grows with messages) | Redis pipeline GET+LRANGE (~0.1ms, always fixed size) |
| State passed to LLM | All raw messages (token count grows unbounded) | Compressed summary string (fixed size) |
| Summarization | Blocking — inside `summarize_conversation_node`, delays response | Non-blocking — `asyncio.create_task()` in background, user gets response immediately |
| Session warm-up (cold start) | MongoDB read on every first request | Only on first request; subsequent hits are Redis |

### Concrete Example

**Without Redis (turn 50 of a conversation)**:
1. MongoDB fetches checkpoint → document has 50 serialized LangChain messages → slow
2. All 50 messages sent to LLM prompt → very high token cost
3. If summarization triggers → user WAITS for it to complete

**With Redis (turn 50 of a conversation)**:
1. Redis returns summary string + last 10 messages → ~0.1ms
2. Only summary + 10 messages sent to LLM prompt → low, fixed token cost
3. If summarization triggers → runs in background, user gets response without waiting

---

### MongoDB Is Still the Source of Truth

MongoDB is **never removed** from the picture. It still:
- Stores the **complete checkpoint** after every `graph.ainvoke()` call
- Provides **crash recovery** (if Redis data is lost, `get_agent_state` falls back to MongoDB cold-start)
- Stores the **long-term memory** embeddings in `philosopher_long_term_memory` collection

Redis is purely a **performance layer** — a faster read-path for the most recent conversation context.

---

### Summary Architecture Diagram

```
                    ┌─────────────────────────────────┐
                    │         FastAPI Request          │
                    └─────────────┬───────────────────┘
                                  │
                    ┌─────────────▼───────────────────┐
                    │      MemoryOrchestrator          │
                    │   get_agent_state()              │
                    └──────┬──────────────────────┬───┘
                           │                      │
              ┌────────────▼──────┐    ┌──────────▼──────────┐
              │   Redis (L1)      │    │  MongoDB (L2)        │
              │  ~0.1ms latency   │    │  ~5-50ms latency     │
              │  Buffer: 10 turns │    │  Full checkpoints    │
              │  Summary: string  │    │  All history         │
              │  TTL: 24h         │    │  Permanent           │
              └────────────┬──────┘    └──────────┬──────────┘
                           │    Cache MISS         │
                           └──────────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │    graph.ainvoke()               │
                    │    (LangGraph + MongoDB saver)   │
                    └──────────────┬──────────────────┘
                                   │
                    ┌──────────────▼──────────────────┐
                    │   orchestrator.save_interaction()│
                    │   → Redis write (sync)           │
                    │   → background_summarize (async) │
                    └─────────────────────────────────┘
```
