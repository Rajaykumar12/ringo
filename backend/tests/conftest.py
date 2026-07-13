import os

# main.py raises at import time if GROQ_API_KEY is missing, and several modules
# read GROQ_API_KEY at import/instantiation time — set a dummy key before any
# test module imports application code, so collection doesn't require real credentials.
os.environ.setdefault("GROQ_API_KEY", "test-key-for-ci")
