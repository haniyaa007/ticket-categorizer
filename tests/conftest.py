import os

# Tests must be fast and offline: use the TF-IDF backend.
os.environ["TC_EMBEDDING_BACKEND"] = "tfidf"
os.environ.pop("TC_API_KEY", None)
os.environ.pop("TC_LLM_LABELING", None)
