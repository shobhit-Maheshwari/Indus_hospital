from typing import TYPE_CHECKING

from loguru import logger
from pymongo import MongoClient

from philoagents.config import settings

if TYPE_CHECKING:
    from philoagents.infrastructure.memory_orchestrator import MemoryOrchestrator


async def reset_conversation_state(orchestrator: "MemoryOrchestrator") -> dict:
    """Resets all conversation state: drops MongoDB checkpoint collections AND
    flushes the Redis L1 cache managed by the MemoryOrchestrator.

    This function removes all stored conversation checkpoints and writes,
    effectively resetting all philosopher conversations.

    Args:
        orchestrator: The MemoryOrchestrator instance used to flush Redis.

    Returns:
        dict: Status message indicating success or failure with details
              about which collections were deleted and how many Redis keys removed.

    Raises:
        Exception: If there's an error connecting to MongoDB/Redis or deleting data.
    """
    try:
        # --- 1. Flush Redis L1 Cache ---
        redis_keys_deleted = await orchestrator.flush_all_sessions()

        # --- 2. Drop MongoDB checkpoint collections ---
        client = MongoClient(settings.MONGO_URI)
        db = client[settings.MONGO_DB_NAME]

        collections_deleted = []

        if settings.MONGO_STATE_CHECKPOINT_COLLECTION in db.list_collection_names():
            db.drop_collection(settings.MONGO_STATE_CHECKPOINT_COLLECTION)
            collections_deleted.append(settings.MONGO_STATE_CHECKPOINT_COLLECTION)
            logger.info(
                f"Deleted collection: {settings.MONGO_STATE_CHECKPOINT_COLLECTION}"
            )

        if settings.MONGO_STATE_WRITES_COLLECTION in db.list_collection_names():
            db.drop_collection(settings.MONGO_STATE_WRITES_COLLECTION)
            collections_deleted.append(settings.MONGO_STATE_WRITES_COLLECTION)
            logger.info(f"Deleted collection: {settings.MONGO_STATE_WRITES_COLLECTION}")

        client.close()

        if collections_deleted:
            return {
                "status": "success",
                "message": (
                    f"Successfully deleted MongoDB collections: {', '.join(collections_deleted)}. "
                    f"Flushed {redis_keys_deleted} Redis session key(s)."
                ),
            }
        else:
            return {
                "status": "success",
                "message": (
                    f"No MongoDB collections needed deletion. "
                    f"Flushed {redis_keys_deleted} Redis session key(s)."
                ),
            }

    except Exception as e:
        logger.error(f"Failed to reset conversation state: {str(e)}")
        raise Exception(f"Failed to reset conversation state: {str(e)}")
