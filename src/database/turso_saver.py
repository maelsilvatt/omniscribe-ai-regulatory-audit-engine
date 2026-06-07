import base64
import json
from typing import Any, AsyncIterator, Optional, Sequence, Tuple

import libsql_client
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)


class TursoCheckpointSaver(BaseCheckpointSaver):
    """
    Custom asynchronous checkpointer for LangGraph that connects directly
    to a Turso DB (libSQL) in the cloud using stable typed APIs.
    """

    def __init__(self, url: str, auth_token: str) -> None:
        super().__init__()
        self.url = url
        self.auth_token = auth_token
        self.client: Optional[libsql_client.Client] = None

    async def __aenter__(self):
        self.client = libsql_client.create_client(
            url=self.url, auth_token=self.auth_token
        )

        # 1. Create the main Checkpoints table
        await self.client.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                parent_checkpoint_id TEXT,
                checkpoint TEXT NOT NULL,
                metadata TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
            )
        """)

        # 2. Create the pending writes table (Required for aput_writes)
        await self.client.execute("""
            CREATE TABLE IF NOT EXISTS checkpoint_writes (
                thread_id TEXT NOT NULL,
                checkpoint_ns TEXT NOT NULL DEFAULT '',
                checkpoint_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                idx INTEGER NOT NULL,
                channel TEXT NOT NULL,
                type TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
            )
        """)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.client:
            await self.client.close()

    def _encode_payload(self, payload: Any) -> Tuple[str, str]:
        """Serializes and encodes a payload into a base64-JSON string for safe DB storage."""
        payload_type, payload_bytes = self.serde.dumps_typed(payload)
        encoded_str = json.dumps(
            {
                "type": payload_type,
                "bytes": base64.b64encode(payload_bytes).decode("utf-8"),
            }
        )
        return payload_type, encoded_str

    def _decode_payload(self, raw_data: Any) -> Any:
        """Decodes a base64-JSON string back into a Python object, with legacy fallback."""
        try:
            parsed_json = json.loads(raw_data)
            payload_type = parsed_json["type"]
            payload_bytes = base64.b64decode(parsed_json["bytes"])
            return self.serde.loads_typed((payload_type, payload_bytes))
        except (json.JSONDecodeError, KeyError, TypeError):
            # Legacy fallback: Handle raw bytes or unencoded strings from older schema versions
            raw_bytes = (
                raw_data.encode("utf-8") if isinstance(raw_data, str) else raw_data
            )
            try:
                return self.serde.loads_typed(("json", raw_bytes))
            except Exception:
                return None

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Retrieves a specific or the most recent state of a thread, including pending writes."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if checkpoint_id:
            res = await self.client.execute(
                """SELECT checkpoint, metadata, parent_checkpoint_id 
                   FROM checkpoints 
                   WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?""",
                [thread_id, checkpoint_ns, checkpoint_id],
            )
        else:
            res = await self.client.execute(
                """SELECT checkpoint, metadata, parent_checkpoint_id, checkpoint_id 
                   FROM checkpoints 
                   WHERE thread_id = ? AND checkpoint_ns = ? 
                   ORDER BY checkpoint_id DESC LIMIT 1""",
                [thread_id, checkpoint_ns],
            )

        if not res.rows:
            return None

        # Semantic unpacking
        row = res.rows[0]
        raw_checkpoint = row[0]
        raw_metadata = row[1]
        parent_id = row[2]
        actual_checkpoint_id = checkpoint_id if checkpoint_id else row[3]

        checkpoint = self._decode_payload(raw_checkpoint)
        metadata = self._decode_payload(raw_metadata)

        if checkpoint is None or metadata is None:
            return None

        # Fetch pending writes linked to this checkpoint
        res_writes = await self.client.execute(
            """SELECT task_id, channel, type, value 
               FROM checkpoint_writes 
               WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?""",
            [thread_id, checkpoint_ns, actual_checkpoint_id],
        )

        pending_writes = []
        for task_id, channel, write_type, raw_value in res_writes.rows:
            decoded_val = self._decode_payload(raw_value)
            if decoded_val is None:
                decoded_val = raw_value  # Fallback to raw value if decode fully fails
            pending_writes.append((task_id, channel, decoded_val))

        parent_config = (
            {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": parent_id,
                }
            }
            if parent_id
            else None
        )

        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": actual_checkpoint_id,
                }
            },
            checkpoint=checkpoint,
            metadata=metadata,
            parent_config=parent_config,
            pending_writes=pending_writes,
        )

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Saves the current state of the graph securely in binary format."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        _, checkpoint_str = self._encode_payload(checkpoint)
        _, metadata_str = self._encode_payload(metadata)

        await self.client.execute(
            """
            INSERT OR REPLACE INTO checkpoints 
            (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                parent_checkpoint_id,
                checkpoint_str,
                metadata_str,
            ],
        )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """Saves the intermediate writes from tasks connected to a specific checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            write_type, value_str = self._encode_payload(value)

            await self.client.execute(
                """
                INSERT OR REPLACE INTO checkpoint_writes 
                (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, type, value)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    task_id,
                    idx,
                    channel,
                    write_type,
                    value_str,
                ],
            )

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """Lists the history of saved checkpoints."""
        query = """
            SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata 
            FROM checkpoints
        """
        params = []

        if config:
            query += " WHERE thread_id = ?"
            params.append(config["configurable"]["thread_id"])

        query += " ORDER BY checkpoint_id DESC"

        if limit:
            query += f" LIMIT {limit}"

        res = await self.client.execute(query, params)

        for row in res.rows:
            (
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                parent_id,
                raw_checkpoint,
                raw_metadata,
            ) = row

            checkpoint = self._decode_payload(raw_checkpoint)
            metadata = self._decode_payload(raw_metadata)

            if checkpoint is None or metadata is None:
                continue

            parent_config = (
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": parent_id,
                    }
                }
                if parent_id
                else None
            )

            yield CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=parent_config,
            )
