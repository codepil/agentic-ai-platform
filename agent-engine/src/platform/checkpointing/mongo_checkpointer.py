"""
MongoDB-backed checkpoint saver for LangGraph.

Implements the BaseCheckpointSaver interface so LangGraph can persist workflow
state in MongoDB Atlas between runs and support human-in-the-loop interrupts.

Collection layout
-----------------
langgraph_checkpoints  — one document per (thread_id, checkpoint_id) pair
langgraph_writes       — pending channel writes not yet committed
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
import pymongo
from pymongo import MongoClient


class MongoCheckpointer(BaseCheckpointSaver):
    """
    Saves LangGraph checkpoints to a MongoDB collection.

    Parameters
    ----------
    mongo_uri:
        MongoDB connection string (e.g. ``mongodb+srv://...``).
    db_name:
        Name of the database to use.
    """

    CHECKPOINTS_COLLECTION = "langgraph_checkpoints"
    WRITES_COLLECTION = "langgraph_writes"

    def __init__(self, mongo_uri: str, db_name: str) -> None:
        super().__init__()
        self._client: MongoClient = MongoClient(mongo_uri)
        self._db = self._client[db_name]
        self._checkpoints = self._db[self.CHECKPOINTS_COLLECTION]
        self._writes = self._db[self.WRITES_COLLECTION]
        self._ensure_indexes()

    # ------------------------------------------------------------------
    # Index setup
    # ------------------------------------------------------------------

    def _ensure_indexes(self) -> None:
        self._checkpoints.create_index(
            [("thread_id", pymongo.ASCENDING), ("checkpoint_id", pymongo.DESCENDING)],
            unique=True,
            background=True,
        )
        self._writes.create_index(
            [("thread_id", pymongo.ASCENDING), ("task_id", pymongo.ASCENDING)],
            background=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _config_to_thread(config: RunnableConfig) -> str:
        return config["configurable"].get("thread_id", "")

    @staticmethod
    def _config_to_checkpoint_id(config: RunnableConfig) -> Optional[str]:
        return config["configurable"].get("checkpoint_id")

    @staticmethod
    def _serialize(obj: Any) -> str:
        """JSON-serialize a checkpoint or metadata dict."""
        return json.dumps(obj, default=str)

    @staticmethod
    def _deserialize(raw: str) -> Any:
        return json.loads(raw)

    def _doc_to_tuple(self, doc: Dict[str, Any]) -> CheckpointTuple:
        checkpoint: Checkpoint = self._deserialize(doc["checkpoint"])
        metadata: CheckpointMetadata = self._deserialize(doc.get("metadata", "{}"))
        config: RunnableConfig = {
            "configurable": {
                "thread_id": doc["thread_id"],
                "checkpoint_id": doc["checkpoint_id"],
            }
        }
        parent_config: Optional[RunnableConfig] = None
        if doc.get("parent_checkpoint_id"):
            parent_config = {
                "configurable": {
                    "thread_id": doc["thread_id"],
                    "checkpoint_id": doc["parent_checkpoint_id"],
                }
            }
        return CheckpointTuple(
            config=config,
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
        )

    # ------------------------------------------------------------------
    # BaseCheckpointSaver interface
    # ------------------------------------------------------------------

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Dict[str, Any],
    ) -> RunnableConfig:
        """Upsert a checkpoint document."""
        thread_id = self._config_to_thread(config)
        checkpoint_id = checkpoint["id"]
        parent_id = self._config_to_checkpoint_id(config)

        doc = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "parent_checkpoint_id": parent_id,
            "checkpoint": self._serialize(checkpoint),
            "metadata": self._serialize(metadata),
            "new_versions": self._serialize(new_versions),
            "saved_at": datetime.now(timezone.utc),
        }
        self._checkpoints.replace_one(
            {"thread_id": thread_id, "checkpoint_id": checkpoint_id},
            doc,
            upsert=True,
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Persist pending channel writes for a task."""
        thread_id = self._config_to_thread(config)
        checkpoint_id = self._config_to_checkpoint_id(config)
        docs = [
            {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "channel": channel,
                "value": self._serialize(value),
                "saved_at": datetime.now(timezone.utc),
            }
            for channel, value in writes
        ]
        if docs:
            self._writes.insert_many(docs)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Return the latest (or specific) checkpoint for a thread."""
        thread_id = self._config_to_thread(config)
        checkpoint_id = self._config_to_checkpoint_id(config)

        query: Dict[str, Any] = {"thread_id": thread_id}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id

        doc = self._checkpoints.find_one(
            query,
            sort=[("checkpoint_id", pymongo.DESCENDING)],
        )
        if doc is None:
            return None
        return self._doc_to_tuple(doc)

    def list(
        self,
        config: RunnableConfig,
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """Iterate checkpoints for a thread in reverse chronological order."""
        thread_id = self._config_to_thread(config)
        query: Dict[str, Any] = {"thread_id": thread_id}

        if before:
            before_id = self._config_to_checkpoint_id(before)
            if before_id:
                query["checkpoint_id"] = {"$lt": before_id}

        if filter:
            for key, value in filter.items():
                query[f"metadata.{key}"] = value

        cursor = self._checkpoints.find(
            query,
            sort=[("checkpoint_id", pymongo.DESCENDING)],
        )
        if limit is not None:
            cursor = cursor.limit(limit)

        for doc in cursor:
            yield self._doc_to_tuple(doc)
