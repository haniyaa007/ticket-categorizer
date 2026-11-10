"""Runtime configuration. Every setting can be set via env var (prefix ``TC_``) or ``.env``."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULTS_DIR = Path(__file__).parent / "defaults"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TC_", env_file=".env", extra="ignore", populate_by_name=True
    )

    # --- Embeddings -------------------------------------------------------------------
    # "sentence-transformers" = production quality (local model, no data leaves your infra).
    # "tfidf" = zero-download fallback, used for tests/CI and tiny deployments.
    embedding_backend: Literal["sentence-transformers", "tfidf"] = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # --- Taxonomy & routing (YAML). None -> use packaged defaults ---------------------
    categories_path: Path | None = None
    routing_path: Path | None = None

    # --- Categorization ---------------------------------------------------------------
    # Minimum score to accept a category; below it the ticket goes to "other".
    # None -> sensible default for the chosen backend.
    category_threshold: float | None = None
    keyword_weight: float = 0.12

    # --- Clustering -------------------------------------------------------------------
    cluster_method: Literal["hdbscan", "agglomerative"] = "hdbscan"
    min_cluster_size: int = 3
    # Only for agglomerative: cosine distance cut-off (None -> backend default).
    agglomerative_distance: float | None = None

    # --- Optional LLM labeling of clusters (Anthropic) --------------------------------
    llm_labeling: bool = False
    llm_model: str = "claude-haiku-5-5"
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    # --- API service ------------------------------------------------------------------
    api_key: str | None = None  # if set, clients must send X-API-Key
    max_batch_size: int = 1000
    log_level: str = "INFO"

    @property
    def effective_threshold(self) -> float:
        if self.category_threshold is not None:
            return self.category_threshold
        return 0.30 if self.embedding_backend == "sentence-transformers" else 0.12

    @property
    def effective_agglomerative_distance(self) -> float:
        if self.agglomerative_distance is not None:
            return self.agglomerative_distance
        return 0.55 if self.embedding_backend == "sentence-transformers" else 0.9

    @property
    def categories_file(self) -> Path:
        return self.categories_path or DEFAULTS_DIR / "categories.yaml"

    @property
    def routing_file(self) -> Path:
        return self.routing_path or DEFAULTS_DIR / "routing.yaml"
