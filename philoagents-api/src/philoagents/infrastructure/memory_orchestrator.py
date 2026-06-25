import asyncio
import json
import logging
from typing import Any, Dict

import redis.asyncio as redis
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver

logger = logging.getLogger(__name__)

BUFFER_LIMIT = 10
SESSION_TTL = 86400  # 24 hours in seconds


class MemoryOrchestrator:
    """
    Hybrid Async-Writebehind System.
    Bridges FastAPI and LangGraph by managing high-speed L1 state caching (Redis)
    while maintaining synchronized background summarization.
    """

    def __init__(self, redis_url: str, llm_client: Any, mongodb_saver: AsyncMongoDBSaver):
        """
        Initializes the non-blocking connection pool and external services.

        Args:
            redis_url: Connection string for Redis instance.
            llm_client: The LLM client used to generate summaries (e.g. ChatOpenAI).
            mongodb_saver: The AsyncMongoDBSaver instance from LangGraph.
        """
        # Utilize redis.asyncio for a non-blocking connection pool
        self.redis = redis.from_url(redis_url, decode_responses=True)
        self.llm = llm_client
        self.checkpointer = mongodb_saver

    def _get_summary_key(self, thread_id: str, philosopher_id: str) -> str:
        return f"session:{thread_id}:{philosopher_id}:summary"

    def _get_buffer_key(self, thread_id: str, philosopher_id: str) -> str:
        return f"session:{thread_id}:{philosopher_id}:buffer"

    async def flush_all_sessions(self) -> int:
        """
        Deletes ALL session keys from Redis (summary + buffer for every thread).
        Called on /reset-memory to ensure Redis stays in sync with a cleared MongoDB.

        Returns:
            Number of keys deleted.
        """
        # Scan for all session keys managed by this orchestrator
        keys_to_delete = []
        async for key in self.redis.scan_iter("session:*"):
            keys_to_delete.append(key)

        if keys_to_delete:
            deleted = await self.redis.delete(*keys_to_delete)
            logger.info(f"Redis: flushed {deleted} session keys.")
            return deleted

        logger.info("Redis: no session keys to flush.")
        return 0

    async def get_agent_state(self, thread_id: str, philosopher_id: str) -> Dict[str, Any]:
        """
        Attempts to fetch the agent's summary and buffer from L1 (Redis).
        Falls back to LangGraph's MongoDB checkpointer for cold-starts.
        """
        summary_key = self._get_summary_key(thread_id, philosopher_id)
        buffer_key = self._get_buffer_key(thread_id, philosopher_id)

        # Attempt high-speed fetch from Redis via pipeline
        async with self.redis.pipeline() as pipe:
            pipe.get(summary_key)
            pipe.lrange(buffer_key, 0, -1)
            summary, buffer_items = await pipe.execute()

        # Cache Hit Validation
        if summary is not None or len(buffer_items) > 0:
            logger.debug(f"L1 Cache HIT for thread {thread_id}")
            return {
                # Guarantee summary is always a str, never None
                "summary": summary or "",
                "buffer": [json.loads(item) for item in buffer_items],
            }

        logger.info(
            f"L1 Cache MISS for thread {thread_id}. Executing MongoDB cold-start logic."
        )

        # Cold-Start Logic: Fetch from LangGraph MongoDBSaver
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint_tuple = await self.checkpointer.aget_tuple(config)

        if checkpoint_tuple and checkpoint_tuple.checkpoint:
            # Extract historical messages stored natively by LangGraph
            state_messages = checkpoint_tuple.checkpoint["channel_values"].get("messages", [])
            last_messages = state_messages[-BUFFER_LIMIT:]

            # Format and warm up the Redis L1 Cache
            # Store as {"human": ..., "ai": ...} pairs where possible.
            # Since MongoDB messages are individual (HumanMessage / AIMessage alternating),
            # we store each one individually for simplicity and consistency with save_interaction.
            formatted_buffer = []
            async with self.redis.pipeline() as pipe:
                for i in range(0, len(last_messages) - 1, 2):
                    human_msg = last_messages[i]
                    ai_msg = last_messages[i + 1] if i + 1 < len(last_messages) else None
                    if ai_msg is None:
                        break
                    item_json = json.dumps(
                        {"human": human_msg.content, "ai": ai_msg.content}
                    )
                    formatted_buffer.append(item_json)
                    # RPUSH so oldest is at the bottom (index 0 = oldest)
                    pipe.lpush(buffer_key, item_json)

                # Apply the Session TTL to the newly warmed key
                if formatted_buffer:
                    pipe.expire(buffer_key, SESSION_TTL)
                    await pipe.execute()

            logger.info(
                f"Redis warmed with {len(formatted_buffer)} message pairs from MongoDB L2."
            )

            return {
                "summary": "",  # Wait for the first background summarize to populate this
                "buffer": [json.loads(item) for item in formatted_buffer],
            }

        # Total cold start (New thread, no MongoDB history)
        return {"summary": "", "buffer": []}

    async def save_interaction(
        self, thread_id: str, philosopher_id: str, human_msg: str, ai_msg: str
    ):
        """
        Saves interaction to Redis. Ensures strict sliding window constraints.
        Triggers non-blocking background summarization if buffer is full.
        """
        buffer_key = self._get_buffer_key(thread_id, philosopher_id)

        # Store as {"human": ..., "ai": ...} — consistent with _background_summarize reader
        interaction = json.dumps({"human": human_msg, "ai": ai_msg})

        async with self.redis.pipeline() as pipe:
            # 1. LPUSH: Add interaction to specific buffer (newest at index 0)
            pipe.lpush(buffer_key, interaction)
            # 2. LTRIM: Maintain the strict sliding window
            pipe.ltrim(buffer_key, 0, BUFFER_LIMIT - 1)
            # 3. EXPIRE: Refresh session TTL
            pipe.expire(buffer_key, SESSION_TTL)
            # 4. Fetch the new exact length of the buffer
            pipe.llen(buffer_key)

            results = await pipe.execute()
            buffer_length = results[-1]  # Result of the llen command

        # 5. Background Summarization Trigger
        if buffer_length >= BUFFER_LIMIT:
            logger.info(
                f"Buffer full for {thread_id}. Spawning background summary task."
            )
            # Spawn asyncio task to ensure the main thread is NOT blocked
            asyncio.create_task(
                self._background_summarize(thread_id, philosopher_id)
            )

    async def _background_summarize(self, thread_id: str, philosopher_id: str):
        """
        Background worker that compresses the interaction history into a summary.
        Executes without holding up the FastAPI request cycle.
        """
        summary_key = self._get_summary_key(thread_id, philosopher_id)
        buffer_key = self._get_buffer_key(thread_id, philosopher_id)

        # Pull existing summary and all buffer items
        async with self.redis.pipeline() as pipe:
            pipe.get(summary_key)
            pipe.lrange(buffer_key, 0, -1)
            results = await pipe.execute()

        current_summary = results[0] or ""
        buffer_items = results[1]

        if not buffer_items:
            return

        # Since we used LPUSH, items are newest-first. Reverse to chronological order for the LLM.
        interactions = [json.loads(item) for item in reversed(buffer_items)]

        # Format the strict prompt to compress this interaction history
        history_text = "\n".join(
            [f"Human: {i['human']}\nAI: {i['ai']}" for i in interactions]
        )
        prompt = (
            f"You are a state manager for the AI philosopher: {philosopher_id}.\n"
            f"Compress the following interaction history into a concise, updated summary.\n\n"
            f"CURRENT SUMMARY:\n{current_summary}\n\n"
            f"NEW INTERACTIONS:\n{history_text}\n\n"
            f"Return ONLY the updated summary text containing key facts, context, and philosophical stance maintained."
        )

        try:
            # Execute LLM call for summarization using ChatOpenAI instance
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            new_summary = response.content

            # Atomic commit of the new state
            async with self.redis.pipeline() as pipe:
                # Overwrite existing summary key with the new compressed state
                pipe.set(summary_key, new_summary, ex=SESSION_TTL)
                # Call DEL on the buffer key to reset the sliding window
                pipe.delete(buffer_key)
                await pipe.execute()

            logger.info(f"Background summarization completed successfully for {thread_id}.")

        except Exception as e:
            logger.error(f"Failed to run background summarization for {thread_id}: {e}")
