from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from opik.integrations.langchain import OpikTracer
from pydantic import BaseModel

from philoagents.application.conversation_service.generate_response import (
    get_response,
    get_streaming_response,
)
from philoagents.application.conversation_service.reset_conversation import (
    reset_conversation_state,
)
from philoagents.domain.philosopher_factory import PhilosopherFactory
from philoagents.config import settings

from .opik_utils import configure
from .memory_orchestrator import MemoryOrchestrator
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

configure()

# Global dependencies (set during lifespan startup)
_orchestrator: MemoryOrchestrator = None
_mongodb_saver: AsyncMongoDBSaver = None


async def get_orchestrator() -> MemoryOrchestrator:
    return _orchestrator


async def get_mongodb_saver() -> AsyncMongoDBSaver:
    return _mongodb_saver


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events for the API."""
    global _orchestrator, _mongodb_saver

    # AsyncMongoDBSaver.from_conn_string() is an @asynccontextmanager — use async with.
    # It does NOT have a .setup() method; simply yielding the saver is sufficient.
    async with AsyncMongoDBSaver.from_conn_string(
        conn_string=settings.MONGO_URI,
        db_name=settings.MONGO_DB_NAME,
        checkpoint_collection_name=settings.MONGO_STATE_CHECKPOINT_COLLECTION,
        writes_collection_name=settings.MONGO_STATE_WRITES_COLLECTION,
    ) as saver:
        _mongodb_saver = saver

        # Initialize LLM for background summarization
        llm = ChatOpenAI(
            api_key=settings.OPENCODE_API_KEY,
            base_url=settings.OPENCODE_BASE_URL,
            model=settings.OPENCODE_LLM_MODEL_SUMMARY,
            temperature=0.0,
        )

        # Initialize Memory Orchestrator (Redis L1 cache + summarization)
        _orchestrator = MemoryOrchestrator(
            redis_url=settings.REDIS_URI,
            llm_client=llm,
            mongodb_saver=_mongodb_saver,
        )

        yield

    # Shutdown: flush Opik traces (MongoDB client closed automatically by `async with` above)
    opik_tracer = OpikTracer()
    opik_tracer.flush()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    message: str
    philosopher_id: str


@app.post("/chat")
async def chat(
    chat_message: ChatMessage,
    orch: MemoryOrchestrator = Depends(get_orchestrator),
    saver: AsyncMongoDBSaver = Depends(get_mongodb_saver),
):
    try:
        philosopher_factory = PhilosopherFactory()
        philosopher = philosopher_factory.get_philosopher(chat_message.philosopher_id)

        response, _ = await get_response(
            messages=chat_message.message,
            philosopher_id=chat_message.philosopher_id,
            philosopher_name=philosopher.name,
            philosopher_perspective=philosopher.perspective,
            philosopher_style=philosopher.style,
            philosopher_era=philosopher.era,
            philosopher_context="",
            orchestrator=orch,
            mongodb_saver=saver,
        )
        return {"response": response}
    except Exception as e:
        opik_tracer = OpikTracer()
        opik_tracer.flush()
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    orch: MemoryOrchestrator = Depends(get_orchestrator),
    saver: AsyncMongoDBSaver = Depends(get_mongodb_saver),
):
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if "message" not in data or "philosopher_id" not in data:
                await websocket.send_json(
                    {
                        "error": "Invalid message format. Required fields: 'message' and 'philosopher_id'"
                    }
                )
                continue

            try:
                philosopher_factory = PhilosopherFactory()
                philosopher = philosopher_factory.get_philosopher(
                    data["philosopher_id"]
                )

                # Use streaming response
                response_stream = get_streaming_response(
                    messages=data["message"],
                    philosopher_id=data["philosopher_id"],
                    philosopher_name=philosopher.name,
                    philosopher_perspective=philosopher.perspective,
                    philosopher_style=philosopher.style,
                    philosopher_era=philosopher.era,
                    philosopher_context="",
                    orchestrator=orch,
                    mongodb_saver=saver,
                )

                # Signal streaming has started
                await websocket.send_json({"streaming": True})

                # Stream each chunk
                full_response = ""
                async for chunk in response_stream:
                    full_response += chunk
                    await websocket.send_json({"chunk": chunk})

                await websocket.send_json(
                    {"response": full_response, "streaming": False}
                )

                # Persist the completed interaction to Redis for the MemoryOrchestrator
                await orch.save_interaction(
                    thread_id=data["philosopher_id"],
                    philosopher_id=data["philosopher_id"],
                    human_msg=data["message"],
                    ai_msg=full_response,
                )

            except Exception as e:
                opik_tracer = OpikTracer()
                opik_tracer.flush()
                await websocket.send_json({"error": str(e)})

    except WebSocketDisconnect:
        pass


@app.post("/reset-memory")
async def reset_conversation(
    orch: MemoryOrchestrator = Depends(get_orchestrator),
):
    """Resets ALL conversation state: drops MongoDB checkpoint collections AND
    flushes the Redis L1 cache.

    Raises:
        HTTPException: If there is an error resetting the conversation state.
    Returns:
        dict: A dictionary containing the result of the reset operation.
    """
    try:
        result = await reset_conversation_state(orch)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
