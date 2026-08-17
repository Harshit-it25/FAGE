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
        return """**SUSPICIOUS ACTIVITY REPORT (SAR) DRAFT**

**SUBJECT:** Suspicious Transfers Detected
**SUMMARY:**
The subject account engaged in multiple rapid transactions across different entities. The transaction velocity and aggregated volumes deviate significantly from the baseline behavior for this account tier. 

**DETAILED NARRATIVE:**
1. A series of high-value transactions were initiated within a brief time window.
2. The counterparty addresses have been recently flagged by the FAGE Risk Engine as potentially associated with coordinated fraud rings.
3. The ML models indicate a high probability of account takeover or structured placement.

**RECOMMENDATION:**
Proceed with immediate escalation to the Fraud Investigation Unit (FIU) and consider a temporary freeze on outgoing transfers pending manual verification."""

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
        logger.error(f"Error calling NVIDIA LLM API: {e}")
        if fallback is not None:
            return fallback
        return "Error: An unexpected error occurred while generating the report."
