from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )

    # --- OpenCode Configuration ---
    OPENCODE_API_KEY: str
    OPENCODE_BASE_URL: str = "https://opencode.ai/zen/v1"
    OPENCODE_LLM_MODEL: str = "deepseek-v4-flash-free"
    OPENCODE_LLM_MODEL_SUMMARY: str = "deepseek-v4-flash-free"
    OPENCODE_LLM_MODEL_CONTEXT_SUMMARY: str = "deepseek-v4-flash-free"
    OPENCODE_LLM_MODEL_JUDGE: str = "deepseek-v4-flash-free"  # Used as LLM judge in Opik evaluation

    # --- OpenAI Configuration (optional — only needed if you want to use OpenAI-based evaluation) ---
    OPENAI_API_KEY: str | None = None

    # --- MongoDB Configuration ---
    MONGO_URI: str = Field(
        default="mongodb://philoagents:philoagents@local_dev_atlas:27017/?directConnection=true",
        description="Connection URI for the local MongoDB Atlas instance.",
    )
    MONGO_DB_NAME: str = "philoagents"
    MONGO_STATE_CHECKPOINT_COLLECTION: str = "philosopher_state_checkpoints"
    MONGO_STATE_WRITES_COLLECTION: str = "philosopher_state_writes"
    MONGO_LONG_TERM_MEMORY_COLLECTION: str = "philosopher_long_term_memory"

    # --- Redis Configuration ---
    REDIS_URI: str = Field(
        default="redis://localhost:6379/0",
        description="Connection URI for the local Redis instance."
    )

    # --- Comet ML & Opik Configuration ---
    COMET_API_KEY: str | None = Field(
        default=None, description="API key for Comet ML and Opik services."
    )
    COMET_PROJECT: str = Field(
        default="philoagents_course",
        description="Project name for Comet ML and Opik tracking.",
    )

    # --- Agents Configuration ---
    TOTAL_MESSAGES_SUMMARY_TRIGGER: int = 30
    TOTAL_MESSAGES_AFTER_SUMMARY: int = 5

    # --- RAG Configuration ---
    RAG_TEXT_EMBEDDING_MODEL_ID: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_TEXT_EMBEDDING_MODEL_DIM: int = 384
    RAG_TOP_K: int = 5
    RAG_DEVICE: str = "cpu"
    RAG_CHUNK_SIZE: int = 256

    # --- Paths Configuration ---
    EVALUATION_DATASET_FILE_PATH: Path = Path("data/evaluation_dataset.json")
    EXTRACTION_METADATA_FILE_PATH: Path = Path("data/extraction_metadata.json")


settings = Settings()
