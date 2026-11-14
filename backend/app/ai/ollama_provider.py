import logging

from langchain_ollama import ChatOllama
from pydantic import ValidationError

from app.ai.llm_provider import AIProviderError, StructuredOutputProvider, T
from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, prompt: str, schema: type[T]) -> T:
        if len(prompt) > self.settings.llm_max_prompt_chars:
            raise AIProviderError(
                "The QA prompt exceeds the configured size limit. "
                "Reduce the requirements or inspection evidence and retry."
            )
        try:
            model = ChatOllama(
                model=self.settings.ollama_model,
                base_url=self.settings.ollama_base_url,
                temperature=0,
                validate_model_on_init=False,
                async_client_kwargs={
                    "timeout": self.settings.llm_timeout_seconds,
                },
                num_ctx=4096,
                num_predict=768,
            ).with_structured_output(schema, method="json_schema")
            response = await model.ainvoke(prompt)
            if isinstance(response, schema):
                return response
            return schema.model_validate(response)
        except ValidationError as exc:
            logger.warning(
                "Ollama returned invalid structured output for %s",
                schema.__name__,
            )
            raise AIProviderError(
                "Ollama returned a response that did not match the required "
                "QA schema. Retry the workflow after checking the configured model."
            ) from exc
        except Exception as exc:
            logger.exception(
                "Ollama structured-output request failed for %s (%s)",
                schema.__name__,
                type(exc).__name__,
            )
            raise AIProviderError(
                "The Ollama provider is unavailable or failed to generate a "
                "valid response. Check that Ollama is running at OLLAMA_BASE_URL "
                "and that OLLAMA_MODEL is already available. Models are not "
                "downloaded automatically."
            ) from exc


def create_llm_provider(settings: Settings | None = None) -> StructuredOutputProvider:
    configured = settings or get_settings()
    if configured.llm_provider.strip().lower() != "ollama":
        raise AIProviderError(
            f"Unsupported LLM_PROVIDER '{configured.llm_provider}'. "
            "The configured provider is not implemented."
        )
    return OllamaProvider(configured)
