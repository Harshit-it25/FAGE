import os
import logging
from nemoguardrails import LLMRails, RailsConfig

logger = logging.getLogger("FAGE.GuardrailsManager")

class GuardrailsManager:
    def __init__(self):
        self.rails = None
        self._initialize()

    def _initialize(self):
        try:
            
            config_dir = os.path.join(os.path.dirname(__file__), "config")
            config = RailsConfig.from_path(config_dir)
            self.rails = LLMRails(config)
            logger.info("NeMo Guardrails successfully initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize NeMo Guardrails: {e}")

    async def generate_safe_sar(self, prompt: str) -> str:
        """
        Processes the LLM prompt through NeMo Guardrails input and output validation.
        """
        if not self.rails:
            raise RuntimeError("NeMo Guardrails not initialized")

        try:
            
            messages = [{"role": "user", "content": prompt}]
            
            
            response = await self.rails.generate_async(messages=messages)
            
            return response["content"]
        except Exception as e:
            logger.error(f"Guardrails generation error: {e}")
            raise


guardrails_manager = GuardrailsManager()
