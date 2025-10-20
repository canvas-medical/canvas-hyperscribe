#!/usr/bin/env python3
"""Test script to verify environment variables are passed correctly"""

import os
from evaluations.helper_evaluation import HelperEvaluation

print(f"VendorTextLLM: {os.environ.get('VendorTextLLM', 'NOT SET')}")
print(f"KeyTextLLM: {'SET' if os.environ.get('KeyTextLLM') else 'NOT SET'}")

settings = HelperEvaluation.settings()
print(f"Settings vendor: {settings.llm_text.vendor}")
print(f"Settings API key: {'SET' if settings.llm_text.api_key else 'NOT SET'}")
print(f"Settings model: {settings.llm_text_model()}")