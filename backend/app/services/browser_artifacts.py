import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID


class ArtifactStore:
    """Write bounded artifacts beneath a configured root using fixed names."""

    _MAX_JSON_BYTES = 2_000_000

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, execution_id: UUID, relative_name: str) -> Path:
        path = (self.root / str(execution_id) / relative_name).resolve()
        if self.root not in path.parents:
            raise ValueError("Artifact path is outside the configured root.")
        return path

    async def write_bytes(
        self,
        execution_id: UUID,
        relative_name: str,
        content: bytes,
        media_type: str,
    ) -> dict[str, Any]:
        path = self._path(execution_id, relative_name)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(write)
        return {
            "name": relative_name,
            "media_type": media_type,
            "size_bytes": len(content),
        }

    async def write_json(
        self,
        execution_id: UUID,
        relative_name: str,
        data: Any,
    ) -> dict[str, Any]:
        content = json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(content) > self._MAX_JSON_BYTES:
            raise ValueError("Inspection artifact exceeds the configured size limit.")
        return await self.write_bytes(
            execution_id,
            relative_name,
            content,
            "application/json",
        )
