import os
import sys
import pytest


sys.stdout.reconfigure(encoding='utf-8')

if "NVIDIA_API_KEY" not in os.environ:
    pytest.skip("NVIDIA_API_KEY not found in environment. Skipping LLM tests.", allow_module_level=True)

from app.services.llm import call_nvidia_llm

prompt = """
Generate a mock Suspicious Activity Report based on these facts:
- Transaction size: $500,000
- Sender: John Doe
- Receiver: Unknown LLC
- Activity: Structuring
"""

result = call_nvidia_llm(prompt)
with open("llm_output.txt", "w", encoding="utf-8") as f:
    f.write(result)
print("Saved LLM output to llm_output.txt")
