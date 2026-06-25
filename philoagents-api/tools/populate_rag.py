import os
import sys
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mongodb import MongoDBAtlasVectorSearch
from loguru import logger
from pymongo import MongoClient

# Add src to path so we can import philoagents
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from philoagents.config import settings
from philoagents.application.rag.embeddings import get_embedding_model

URLS = [
    "https://indusjh.com/",
    "https://indusjh.com/about-us/",
    "https://indusjh.com/contact/",
    "https://indusjh.com/doctors/",
    "https://indusjh.com/leadership-message/",
    "https://indusjh.com/specialties/",
    "https://indusjh.com/cardiology-and-cardiac-surgery/",
    "https://indusjh.com/neurology-and-neurosurgery/",
    "https://indusjh.com/internal-medicine-and-diabetes/",
    "https://indusjh.com/orthopaedics-and-joint-replacement/",
    "https://indusjh.com/kidney-disease-and-dialysis/",
    "https://indusjh.com/bariatric-and-metabolic-surgery/",
    "https://indusjh.com/laparoscopic-and-general-surgery/"
]

def main():
    logger.info("Loading documents...")
    loader = WebBaseLoader(
        web_paths=URLS,
    )
    docs = loader.load()

    logger.info(f"Loaded {len(docs)} documents. Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, chunk_overlap=200
    )
    splits = text_splitter.split_documents(docs)

    logger.info(f"Split into {len(splits)} chunks. Getting embedding model...")
    embedding_model = get_embedding_model(settings.RAG_TEXT_EMBEDDING_MODEL_ID, settings.RAG_DEVICE)

    mongo_uri = settings.MONGO_URI.replace("local_dev_atlas", "localhost")
    logger.info(f"Connecting to MongoDB at {mongo_uri}...")
    client = MongoClient(mongo_uri)
    collection = client[settings.MONGO_DB_NAME][settings.MONGO_LONG_TERM_MEMORY_COLLECTION]
    
    logger.info("Clearing existing documents from collection...")
    collection.delete_many({})

    logger.info("Uploading to MongoDB Atlas Vector Search...")
    MongoDBAtlasVectorSearch.from_documents(
        documents=splits,
        embedding=embedding_model,
        collection=collection,
        index_name="hybrid_search_index",
        text_key="chunk",
        embedding_key="embedding"
    )
    logger.info("Done.")

if __name__ == "__main__":
    main()
