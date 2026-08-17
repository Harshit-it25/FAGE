import os
import requests
import logging

logger = logging.getLogger("FAGE.API.LLM")

def call_nvidia_llm(prompt: str, fallback: str = None) -> str:
    """
    Invokes the NVIDIA NIM API to generate a response based on the prompt.
    Strips <think>...</think> tags from the output.
    """
    invoke_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    api_key = os.environ.get("NVIDIA_API_KEY")
    
    if not api_key:
        logger.warning("NVIDIA_API_KEY is missing. Using fallback response.")
        if fallback is not None:
            return fallback
        return "Error: LLM Service Unavailable. Cannot generate SAR."

    from app.services.guardrails import guardrails_manager
    import asyncio

    try:
        # We are inside a threadpool (run_in_threadpool), so we create a new event loop or use asyncio.run
        # to execute the async guardrails function.
        content = asyncio.run(guardrails_manager.generate_safe_sar(prompt))
        
        # Strip <think> tags (if NIM returns them)
        if "<think>" in content and "</think>" in content:
            content = content.split("</think>")[-1].strip()
            
        return content
    except Exception as e:
        logger.error(f"Error calling Guardrails LLM API: {e}")
        if fallback is not None:
            return fallback
        return "Error: An unexpected error occurred while generating the report."
