"""Tier 2 Classifier for sloth-sorter.

Uses Model2Vec static embeddings and cosine similarity against category prototypes.
Features:
- Lazy loads model2vec only when --smart is enabled.
- Precomputes one normalized centroid per category.
- Evaluates cosine similarity with numpy.
- Rejects matches below a configurable similarity threshold.
- Supports custom model paths for offline air-gapped environments.
"""

from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional
import numpy as np

from sloth_sorter.config import (
    DEFAULT_MODEL_NAME,
    DEFAULT_PROTOTYPES,
    DEFAULT_SIMILARITY_THRESHOLD,
    SMART_CATEGORIES,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SmartClassificationResult:
    """Outcome of Tier 2 classification."""

    category: str
    score: float
    confidence: str = "embedding"
    reason: str = ""


class SmartClassifier:
    """Embeds text and classifies into categories using cosine similarity to centroids."""

    def __init__(
        self,
        model_name_or_path: str = DEFAULT_MODEL_NAME,
        prototypes: Optional[Dict[str, List[str]]] = None,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        model_instance: Optional[Any] = None,
    ):
        self.model_name_or_path = model_name_or_path
        self.prototypes = prototypes or dict(DEFAULT_PROTOTYPES)
        self.threshold = threshold
        self._model = model_instance
        self._centroids: Optional[Dict[str, np.ndarray]] = None

    def _ensure_loaded(self) -> None:
        """Lazy load the model and calculate category centroids if not already loaded."""
        if self._model is None:
            # Lazy import so runs without --smart never import model2vec
            from model2vec import StaticModel

            self._model = StaticModel.from_pretrained(self.model_name_or_path)

        if self._centroids is None:
            self._compute_centroids()

    def _compute_centroids(self) -> None:
        """Compute and store L2-normalized centroids for each prototype category."""
        self._centroids = {}
        for cat, phrases in self.prototypes.items():
            if not phrases:
                continue
            embeddings = self._model.encode(phrases)
            # embeddings shape: (N, D)
            centroid = np.mean(embeddings, axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid = centroid / norm
            self._centroids[cat] = centroid

    def classify_text(self, text: str) -> Optional[SmartClassificationResult]:
        """Classify extracted text using cosine similarity against prototype centroids.

        Args:
            text: Extracted text content from a file.

        Returns:
            SmartClassificationResult if score >= threshold, otherwise None.
        """
        if not text or not text.strip():
            return None

        self._ensure_loaded()
        if not self._centroids:
            return None

        # Encode query text and normalize
        emb = self._model.encode([text])[0]
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        else:
            return None

        best_cat: Optional[str] = None
        best_score: float = -1.0

        for cat, centroid in self._centroids.items():
            sim = float(np.dot(emb, centroid))
            if sim > best_score:
                best_score = sim
                best_cat = cat

        if best_cat is not None and best_score >= self.threshold:
            return SmartClassificationResult(
                category=best_cat,
                score=best_score,
                confidence="embedding",
                reason=f"embedding:{best_cat}:{best_score:.2f}",
            )

        return None


# Module-level singleton cache for CLI runs
_CACHED_CLASSIFIER: Optional[SmartClassifier] = None


def get_smart_classifier(
    model_name_or_path: str = DEFAULT_MODEL_NAME,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    prototypes: Optional[Dict[str, List[str]]] = None,
) -> SmartClassifier:
    """Retrieve or create the cached SmartClassifier instance."""
    global _CACHED_CLASSIFIER
    if (
        _CACHED_CLASSIFIER is None
        or _CACHED_CLASSIFIER.model_name_or_path != model_name_or_path
        or _CACHED_CLASSIFIER.threshold != threshold
    ):
        _CACHED_CLASSIFIER = SmartClassifier(
            model_name_or_path=model_name_or_path,
            prototypes=prototypes,
            threshold=threshold,
        )
    return _CACHED_CLASSIFIER
