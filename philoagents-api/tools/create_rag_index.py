import os
import sys
from loguru import logger

# Add src to path so we can import philoagents
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from philoagents.config import settings
from langchain_core.documents import Document
from philoagents.infrastructure.mongo import MongoClientWrapper, MongoIndex
from philoagents.application.rag.retrievers import get_retriever

def main():
    logger.info("Creating Search Index for RAG...")
    with MongoClientWrapper(
        model=Document, collection_name=settings.MONGO_LONG_TERM_MEMORY_COLLECTION
    ) as client:
        retriever = get_retriever(
            embedding_model_id=settings.RAG_TEXT_EMBEDDING_MODEL_ID,
            k=settings.RAG_TOP_K,
            device=settings.RAG_DEVICE,
        )
        index = MongoIndex(
            retriever=retriever,
            mongodb_client=client,
        )
        index.create(
            is_hybrid=True, embedding_dim=settings.RAG_TEXT_EMBEDDING_MODEL_DIM
        )
    logger.info("Index created successfully!")

if __name__ == "__main__":
    main()
