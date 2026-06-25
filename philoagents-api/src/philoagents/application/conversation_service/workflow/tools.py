from langchain.tools.retriever import create_retriever_tool

from philoagents.application.rag.retrievers import get_retriever
from philoagents.config import settings

retriever = get_retriever(
    embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
    k=settings.RAG_TOP_K,
    device=settings.RAG_DEVICE)

retriever_tool = create_retriever_tool(
    retriever,
    "retrieve_philosopher_context",
    "Search and return context from the Indus Hospital pages. Always use this tool whenever the user asks ANY question about Indus Hospital, including its location, contact info, OPD timings, doctors, facilities, appointments, or services. You MUST rely on this tool's returned context.",
)

tools = [retriever_tool]