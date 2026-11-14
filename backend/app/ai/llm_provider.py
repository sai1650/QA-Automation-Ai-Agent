from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIProviderError(RuntimeError):
    """Raised when an LLM provider cannot return validated structured output."""


class StructuredOutputProvider(Protocol):
    async def generate(self, prompt: str, schema: type[T]) -> T:
        """Return a response validated against a Pydantic model."""
