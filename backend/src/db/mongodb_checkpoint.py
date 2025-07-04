import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.mongodb import AsyncMongoDBSaver
from langgraph.checkpoint.mongodb.utils import dumps_metadata, loads_metadata
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import UpdateOne
from pymongo.asynchronous.mongo_client import AsyncMongoClient
from pymongo.driver_info import DriverInfo


class CustomAsyncMongoDBSaver(AsyncMongoDBSaver):

    @classmethod
    @asynccontextmanager
    async def from_conn_string(
        cls,
        conn_string: str,
        db_name: str = "checkpointing_db",
        checkpoint_collection_name: str = "checkpoints_aio",
        writes_collection_name: str = "checkpoint_writes_aio",
        **kwargs: Any,
    ) -> AsyncIterator["CustomAsyncMongoDBSaver"]:
        """Create asynchronous checkpointer
        This includes creation of collections and indexes if they don't exist
        """
        client: Optional[AsyncIOMotorClient] = None
        try:
            client = AsyncIOMotorClient(
                conn_string,
                driver=DriverInfo(
                    name="Langgraph", version=version("langgraph-checkpoint-mongodb")
                ),
            )
            saver = CustomAsyncMongoDBSaver(
                client,
                db_name,
                checkpoint_collection_name,
                writes_collection_name,
                **kwargs,
            )
            await saver._setup()
            yield saver
        finally:
            if client:
                client.close()

    async def _setup(self):
        """Create indexes if not present."""
        if self._setup_future is not None:
            return await self._setup_future
        self._setup_future = asyncio.Future()
        if isinstance(self.client, AsyncMongoClient):
            num_indexes = len(
                await (await self.checkpoint_collection.list_indexes()).to_list()
            )
        else:
            num_indexes = len(await self.checkpoint_collection.list_indexes().to_list())
        if num_indexes < 2:
            await self.checkpoint_collection.create_index(
                keys=[("thread_id", 1), ("checkpoint_ns", 1), ("checkpoint_id", -1)],
                unique=True,
            )
        if isinstance(self.client, AsyncMongoClient):
            num_indexes = len(
                await (await self.writes_collection.list_indexes()).to_list()
            )
        else:
            num_indexes = len(await self.writes_collection.list_indexes().to_list())
        if num_indexes < 2:
            await self.writes_collection.create_index(
                keys=[
                    ("thread_id", 1),
                    ("checkpoint_ns", 1),
                    ("checkpoint_id", -1),
                    ("task_id", 1),
                    ("user_id", 1),
                    ("idx", 1),
                ],
                unique=True,
            )
        self._setup_future.set_result(None)

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        await self._setup()
        thread_id = config["configurable"]["thread_id"]
        user_id = config["configurable"]["user_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        if checkpoint_id := get_checkpoint_id(config):
            query = {
                "thread_id": thread_id,
                "user_id": user_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        else:
            query = {
                "thread_id": thread_id,
                "user_id": user_id,
                "checkpoint_ns": checkpoint_ns,
            }
        result = self.checkpoint_collection.find(
            query, sort=[("checkpoint_id", -1)], limit=1
        )
        async for doc in result:
            config_values = {
                "thread_id": thread_id,
                "user_id": user_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": doc["checkpoint_id"],
            }
            checkpoint = self.serde.loads_typed((doc["type"], doc["checkpoint"]))
            serialized_writes = self.writes_collection.find(config_values)
            pending_writes = [
                (
                    wrt["task_id"],
                    wrt["channel"],
                    self.serde.loads_typed((wrt["type"], wrt["value"])),
                )
                async for wrt in serialized_writes
            ]
            return CheckpointTuple(
                {"configurable": config_values},
                checkpoint,
                loads_metadata(doc["metadata"]),
                (
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "user_id": user_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": doc["parent_checkpoint_id"],
                        }
                    }
                    if doc.get("parent_checkpoint_id")
                    else None
                ),
                pending_writes,
            )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List checkpoints from the database asynchronously.
        This method retrieves a list of checkpoint tuples from the MongoDB database based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).
        Args:
            config (Optional[RunnableConfig]): Base configuration for filtering checkpoints.
            filter (Optional[dict[str, Any]]): Additional filtering criteria for metadata.
            before (Optional[RunnableConfig]): If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit (Optional[int]): Maximum number of checkpoints to return.
        Yields:
            AsyncIterator[CheckpointTuple]: An asynchronous iterator of matching checkpoint tuples.
        """
        await self._setup()
        query = {}
        if config is not None:
            if "thread_id" in config["configurable"]:
                query["thread_id"] = config["configurable"]["thread_id"]
            if "checkpoint_ns" in config["configurable"]:
                query["checkpoint_ns"] = config["configurable"]["checkpoint_ns"]
            if "user_id" in config["configurable"]:
                query["user_id"] = config["configurable"]["user_id"]
        if filter:
            for key, value in filter.items():
                query[f"metadata.{key}"] = dumps_metadata(value)
        if before is not None:
            query["checkpoint_id"] = {"$lt": before["configurable"]["checkpoint_id"]}
        result = self.checkpoint_collection.find(
            query, limit=0 if limit is None else limit, sort=[("checkpoint_id", -1)]
        )
        async for doc in result:
            config_values = {
                "thread_id": doc["thread_id"],
                "checkpoint_ns": doc["checkpoint_ns"],
                "checkpoint_id": doc["checkpoint_id"],
                "user_id": doc["user_id"],
            }
            serialized_writes = self.writes_collection.find(config_values)
            pending_writes = [
                (
                    wrt["task_id"],
                    wrt["channel"],
                    self.serde.loads_typed((wrt["type"], wrt["value"])),
                )
                async for wrt in serialized_writes
            ]
            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": doc["thread_id"],
                        "checkpoint_ns": doc["checkpoint_ns"],
                        "checkpoint_id": doc["checkpoint_id"],
                        "user_id": doc["user_id"],
                    }
                },
                checkpoint=self.serde.loads_typed((doc["type"], doc["checkpoint"])),
                metadata=loads_metadata(doc["metadata"]),
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": doc["thread_id"],
                            "checkpoint_ns": doc["checkpoint_ns"],
                            "checkpoint_id": doc["parent_checkpoint_id"],
                            "user_id": doc["user_id"],
                        }
                    }
                    if doc.get("parent_checkpoint_id")
                    else None
                ),
                pending_writes=pending_writes,
            )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database asynchronously.
        This method saves a checkpoint to the MongoDB database. The checkpoint is associated
        with the provided config and its parent config (if any).
        Args:
            config (RunnableConfig): The config to associate with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to save.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.
        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        await self._setup()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]
        user_id = config["configurable"]["user_id"]
        timestamp = datetime.now(tz=timezone.utc)
        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        doc = {
            "parent_checkpoint_id": config["configurable"].get("checkpoint_id"),
            "type": type_,
            "checkpoint": serialized_checkpoint,
            "metadata": dumps_metadata(metadata),
            "timestamp": timestamp,
            "user_id": user_id,
        }
        upsert_query = {
            "thread_id": thread_id,
            "user_id": user_id,
            "timestamp": timestamp,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        }
        # Perform your operations here
        await self.checkpoint_collection.update_one(
            upsert_query, {"$set": doc}, upsert=True
        )
        return {
            "configurable": {
                "thread_id": thread_id,
                "user_id": user_id,
                "timestamp": timestamp,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Store intermediate writes linked to a checkpoint asynchronously.
        This method saves intermediate writes associated with a checkpoint to the database.
        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (Sequence[tuple[str, Any]]): List of writes to store, each as (channel, value) pair.
            task_id (str): Identifier for the task creating the writes.
            task_path (str): Path of the task creating the writes.
        """
        await self._setup()
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = config["configurable"]["checkpoint_id"]
        user_id = config["configurable"]["user_id"]
        set_method = (  # Allow replacement on existing writes only if there were errors.
            "$set" if all(w[0] in WRITES_IDX_MAP for w in writes) else "$setOnInsert"
        )
        operations = []
        for idx, (channel, value) in enumerate(writes):
            upsert_query = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "user_id": user_id,
                "timestamp": datetime.now(tz=timezone.utc),
                "task_id": task_id,
                "task_path": task_path,
                "idx": WRITES_IDX_MAP.get(channel, idx),
            }
            type_, serialized_value = self.serde.dumps_typed(value)
            operations.append(
                UpdateOne(
                    upsert_query,
                    {
                        set_method: {
                            "channel": channel,
                            "type": type_,
                            "value": serialized_value,
                            "user_id": user_id,
                            "timestamp": datetime.now(tz=timezone.utc),
                        }
                    },
                    upsert=True,
                )
            )
        await self.writes_collection.bulk_write(operations)
