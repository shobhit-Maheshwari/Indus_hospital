# PhiloAgents Architecture & Flow

A high-speed, Hybrid Async-Writebehind system connecting a real-time UI with a stateful LLM backend.

## 🏗️ High-Level Design & Main Components

- **Frontend (Vite + Vanilla JS)**: Provides the real-time UI.
- **Backend (FastAPI)**: Routes WebSocket connections (`/ws/chat`).
- **Memory Orchestrator (Redis)**: High-speed L1 Cache for immediate conversation retrieval.
- **Workflow Engine (LangGraph)**: Directs the cyclical execution graph and tool routing.
- **Cold Storage (MongoDB)**: L2 Checkpointer for long-term state persistence.
- **LLM API (Groq / Llama)**: Generates character dialogue and responses.

## 🛠️ Technology & Key Features

- **Redis**: Fast sliding-window memory buffer. Triggers background async summarization to compress context when full.
- **MongoDB**: Persistent LangGraph state and checkpoint storage.
- **LangGraph & RAG**: Graph state management combined with `sentence-transformers` for local embedding retrieval.
- **Opik / LangChain**: Execution tracing, monitoring, and LLMOps observability.
- **Era Guardrails**: Custom instructions injected into system prompts to enforce temporal boundaries and prevent personas from breaking character.

## 🔄 Sequence Flow

1. **User Input** → UI sends a message via WebSocket to FastAPI.
2. **State Retrieval** → `MemoryOrchestrator` fetches the active buffer and summary from Redis (falling back to MongoDB on cold starts).
3. **Execution** → LangGraph combines system prompts (with Era Guardrails), past summaries, and retrieved context, routing to the LLM.
4. **Streaming** → The LLM generates tokens; LangGraph streams them instantly back to the UI.
5. **State Update** → The exchange is appended to the Redis buffer. If the limit is reached, an async task compresses the history into a summary.
