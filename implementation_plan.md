# Implement Hybrid Async-Writebehind Redis System

This document outlines the proposed architectural changes to implement the `MemoryOrchestrator` with Redis and LangGraph.

## User Review Required

> [!IMPORTANT]
> The current LangGraph workflow (`nodes.py`, `edges.py`) already has a `summarize_conversation_node` that runs when messages exceed 30.
> The new `MemoryOrchestrator` runs its own background summarization every 10 messages and caches it in Redis.
> **Decision**: I propose we *keep* the LangGraph summarization for L2 (MongoDB) to prevent unbounded growth in MongoDB, while `MemoryOrchestrator` provides high-speed L1 caching and summarization. Does this sound correct?

> [!WARNING]
> This requires adding a new `redis` service to `docker-compose.yml` and a new dependency `redis` in `pyproject.toml`.

## Open Questions

- Should we inject `MemoryOrchestrator` into the FastAPI endpoints via `Depends()` and manage the orchestrator lifecycle globally (e.g. initialize it on app startup)?
- Do you want me to also add the background LLM summarization call inside `MemoryOrchestrator` using the existing LLM config (e.g. `GROQ_LLM_MODEL_SUMMARY`), or keep it as a simulated placeholder for now?

## Proposed Changes

### Docker & Config Layer
- Modify `docker-compose.yml` to include a `redis` container.
- Update `src/philoagents/config.py` to add `REDIS_URI` setting.
- Add `redis` to dependencies in `pyproject.toml` and lock using `uv`.

### Infrastructure Layer

#### [NEW] `src/philoagents/infrastructure/memory_orchestrator.py`
Create the `MemoryOrchestrator` class utilizing `redis.asyncio` with the logic exactly as designed (LPUSH, LTRIM, fallback to AsyncMongoDBSaver).

### Application / Service Layer

#### [MODIFY] `src/philoagents/application/conversation_service/generate_response.py`
- Modify `get_response` and `get_streaming_response` to accept `MemoryOrchestrator`.
- Implement the "fast_state" fetch before `graph.ainvoke` / `graph.astream`.
- Append the "orchestrated_summary" to the LangGraph input.
- Call `orchestrator.save_interaction()` after receiving the AI response.

#### [MODIFY] `src/philoagents/infrastructure/api.py`
- Initialize `MemoryOrchestrator` during the app lifespan context manager.
- Inject `MemoryOrchestrator` into the `/chat` and `/ws/chat` routes and pass it to the service functions.

## Verification Plan

### Automated Checks
- Run `uv run ruff check` to identify any obvious codebase issues or errors.
- Ensure the FastAPI app starts successfully and connects to both MongoDB and Redis.

### Manual Verification
- You will be asked to start the stack (`docker compose up`) and trigger a chat via the UI or cURL to verify the cache hit/miss logic and background summarization.
