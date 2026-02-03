import os
import litellm
from litellm import completion, streaming_completion
from typing import List, Dict, Any, Generator
import logging

logger = logging.getLogger(__name__)

class LiteRouter:
    def __init__(self):
        self.model_fallbacks = {
            "gpt-4o": ["claude-3-5-sonnet-20240620", "ollama/qwen2.5-coder:7b"],
            "claude-3-5-sonnet-20240620": ["gpt-4o", "ollama/qwen2.5-coder:7b"]
        }
        # Configure LiteLLM
        litellm.telemetry = False
        litellm.drop_params = True

    def get_response(self, model: str, messages: List[Dict[str, str]], stream: bool = True) -> Any:
        try:
            # Check if we should use local fallback if model indicates or if offline mode is triggered
            # In a real scenario, this would check if the primary API is reachable
            
            if stream:
                return streaming_completion(
                    model=model,
                    messages=messages,
                    fallbacks=self.model_fallbacks.get(model, []),
                    stream=True
                )
            else:
                return completion(
                    model=model,
                    messages=messages,
                    fallbacks=self.model_fallbacks.get(model, [])
                )
        except Exception as e:
            logger.error(f"Error in LiteRouter: {str(e)}")
            # Fallback to local Ollama model if everything fails
            if stream:
                return streaming_completion(
                    model="ollama/qwen2.5-coder:7b",
                    messages=messages,
                    stream=True
                )
            return completion(
                model="ollama/qwen2.5-coder:7b",
                messages=messages
            )

router = LiteRouter()
