import os
import logging
from openai import OpenAI

logger = logging.getLogger("FAGE.API.LLM")

def call_nvidia_llm(prompt: str, fallback: str = None) -> str:
    """
    Invokes the NVIDIA NIM API using the OpenAI client to generate a response.
    Captures both reasoning content and actual content for SAR generation.
    """
    api_key = os.environ.get("NVIDIA_API_KEY")
    
    if not api_key:
        logger.warning("NVIDIA_API_KEY is missing. Using fallback response.")
        if fallback is not None:
            return fallback
        return "Error: LLM Service Unavailable. Cannot generate SAR."

    try:
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )

        completion = client.chat.completions.create(
            model="nvidia/nemotron-3-super-120b-a12b",
            messages=[
                {
                    "role": "user",
                    "content": f"You are an expert financial crimes investigator filing a formal FinCEN Form 111 / BSA 31 CFR § 1020.320 Suspicious Activity Report (SAR).\n\n{prompt}"
                }
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
            stream=True
        )

        full_content = ""
        full_reasoning = ""
        
        for chunk in completion:
            if not chunk.choices:
                continue
            
            reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
            if reasoning:
                full_reasoning += reasoning
                
            if chunk.choices[0].delta.content is not None:
                full_content += chunk.choices[0].delta.content

        # For SAR reports, we primarily return the content. 
        # But we could optionally append or log the reasoning.
        logger.debug(f"Nemotron Reasoning Length: {len(full_reasoning)}")
        
        return full_content.strip()

    except Exception as e:
        logger.error(f"Error calling NVIDIA LLM API: {e}")
        if fallback is not None:
            return fallback
        return "Error: An unexpected error occurred while generating the report."
