from typing import Any, TypeVar

from pydantic import BaseModel

from app.ai.llm_provider import StructuredOutputProvider

T = TypeVar("T", bound=BaseModel)


class BaseAgent:
    def __init__(self, provider: StructuredOutputProvider) -> None:
        self.provider = provider

    async def generate(self, prompt: str, schema: type[T]) -> T:
        return await self.provider.generate(prompt, schema)


def model_data(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
