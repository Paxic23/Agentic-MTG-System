from app.core.config import Settings, get_settings
from app.llm.client import DisabledLLMClient, LLMClient, OpenAICompatibleLLMClient


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider in {"", "none", "off", "disabled"}:
        return DisabledLLMClient()

    if not settings.llm_model:
        raise ValueError("LLM_MODEL must be set when LLM_PROVIDER is enabled")

    if provider == "ollama":
        # In Docker Desktop on Windows/Mac, host.docker.internal usually points
        # from the container back to the host machine running Ollama.
        base_url = settings.llm_base_url or "http://host.docker.internal:11434/v1"
        api_key = settings.llm_api_key or "ollama"
        return OpenAICompatibleLLMClient(
            provider=provider,
            model=settings.llm_model,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider == "openai":
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY must be set when LLM_PROVIDER=openai")
        return OpenAICompatibleLLMClient(
            provider=provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=None,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    if provider in {"openai_compatible", "compatible"}:
        if not settings.llm_base_url:
            raise ValueError(
                "LLM_BASE_URL must be set when LLM_PROVIDER=openai_compatible"
            )
        return OpenAICompatibleLLMClient(
            provider=provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key or "not-needed-for-local-compatible-api",
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )

    raise ValueError(
        "Unsupported LLM_PROVIDER. Use one of: none, ollama, openai, openai_compatible"
    )
