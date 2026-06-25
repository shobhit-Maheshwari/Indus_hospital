# Agentic RAG: PhiloAgents Course 🤖🏛️

Welcome to **Agentic RAG** (powered by the PhiloAgents architecture), a hands-on AI agent simulation engine that brings historical philosophers (Plato, Aristotle, Turing) to life in an interactive game environment.

This project demonstrates how to build a production-grade Agentic RAG system from scratch, complete with short-term/long-term memory, real-time API communication, and LLMOps monitoring.

---

## 🏛️ Project Features

- **Agentic RAG with LangGraph**: Multi-agent orchestration and character impersonation through structured prompts.
- **Dual-Layer Memory (MongoDB & Redis)**:
  - **Short-Term Memory**: Redis-backed session history for immediate context.
  - **Long-Term Memory**: MongoDB-backed vector databases loaded with historical databases (Wikipedia, Stanford Encyclopedia of Philosophy).
- **Real-Time API Layer**: Powered by FastAPI and WebSockets for low-latency chat interactions.
- **Observability & Evaluation (Opik)**: Prompt versioning, execution tracing, and LLM-as-a-judge automated evaluations.
- **Modern Python Tooling**: Dependency management using `uv` and modular packaging.
- **Frontend Game UI**: A lightweight, responsive web interface built with Vite and pure JavaScript.

---

## 🏗️ Project Structure

The codebase is split into two primary components:

```bash
.
├── philoagents-api/     # Backend API containing the PhiloAgents simulation engine (Python)
└── philoagents-ui/      # Frontend UI for the game (JavaScript / Vite)
```

---

## ⚡ Quick Start

Follow these steps to run the complete environment locally.

### 📋 Prerequisites

Ensure you have the following installed on your machine:
* Python 3.11
* [uv](https://github.com/astral-sh/uv) (Python package installer)
* Docker & Docker Compose
* Node.js (for the Frontend UI)

### 1. Spin Up MongoDB & Redis
Start the required databases using Docker:
```bash
# Start MongoDB (with default credentials)
docker run --name philoagents-mongo -d -p 27017:27017 -e MONGODB_INITDB_ROOT_USERNAME=philoagents -e MONGODB_INITDB_ROOT_PASSWORD=philoagents mongodb/mongodb-atlas-local:8.0

# Start Redis
docker run --name philoagents-redis -d -p 6379:6379 redis:7-alpine
```

### 2. Configure Environment variables
Navigate to the API folder and set up your `.env` configuration:
```bash
cd philoagents-api
cp .env.example .env
```
Open `.env` and fill in your credentials (such as your `GROQ_API_KEY`, etc.).

### 3. Run the Backend API
Install dependencies and start the FastAPI server:
```bash
# Install packages & sync environments
uv sync

# Run the dev server
uv run uvicorn philoagents.infrastructure.api:app --reload
```
The API documentation will be available at `http://localhost:8000/docs`.

### 4. Run the Frontend Game UI
In a separate terminal tab, navigate to the UI folder and start the dev server:
```bash
cd philoagents-ui
npm install
npm run dev
```
Open your browser and navigate to `http://localhost:5173` (or the port specified in the console) to start debating with the philosophers!

---

## 🔬 Evaluation & Testing

To run evaluation benchmarks on the agent:
```bash
cd philoagents-api
uv run python tools/evaluate_agent.py
```
Evaluation traces and metrics can be analyzed directly inside your [Opik Dashboard](https://github.com/comet-ml/opik).

## 📄 License

This repository is open-sourced under the [MIT License](LICENSE).
