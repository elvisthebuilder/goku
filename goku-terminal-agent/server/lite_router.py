import os
import litellm
from litellm import acompletion
from typing import List, Dict, Any, Generator
import logging

logger = logging.getLogger(__name__)

class LiteRouter:
    def __init__(self):
        # Configure LiteLLM
        litellm.telemetry = False
        litellm.drop_params = True

    @property
    def available_providers(self) -> List[str]:
        """Dynamically detect available providers based on current environment."""
        providers = []
        if os.getenv("OPENAI_API_KEY"):
            providers.append("openai")
        if os.getenv("ANTHROPIC_API_KEY"):
            providers.append("anthropic")
        if os.getenv("GITHUB_TOKEN"):
            providers.append("github")
            # Sync GitHub token to the environment variable LiteLLM expects
            os.environ["GITHUB_API_KEY"] = os.getenv("GITHUB_TOKEN")
        return providers

    def get_default_model(self) -> str:
        """Pick the best available model based on keys."""
        available = self.available_providers
        if "openai" in available:
            return "gpt-4o"
        if "anthropic" in available:
            return "claude-3-5-sonnet-20240620"
        if "github" in available:
            return "github/gpt-4o"
        return "ollama/qwen2.5-coder:7b" # Last resort fallback

    async def get_response(self, model: str, messages: List[Dict[str, str]], stream: bool = True) -> Any:
        try:
            # Use detected default if no specific model requested
            if not model or model == "default":
                model = self.get_default_model()
            
            # Detect currently available providers
            available = self.available_providers
            
            # Build dynamic fallbacks based on available keys
            fallbacks = []
            if "openai" in available and model != "gpt-4o":
                fallbacks.append("gpt-4o")
            if "anthropic" in available and model != "claude-3-5-sonnet-20240620":
                fallbacks.append("claude-3-5-sonnet-20240620")
            if "github" in available and not model.startswith("github/"):
                fallbacks.append("github/gpt-4o")
            
            return await acompletion(
                model=model,
                messages=messages,
                fallbacks=fallbacks,
                stream=stream
            )
        except Exception as e:
            logger.error(f"Error in LiteRouter: {str(e)}")
            # If everything fails, try to explain why
            if not self.available_providers:
                raise Exception("No API keys detected in backend. Please use Ctrl+S to save your keys again.")
            raise e

router = LiteRouter()
