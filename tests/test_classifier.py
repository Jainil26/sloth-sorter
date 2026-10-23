"""Tests for Tier 2 SmartClassifier (with model mocking for fast offline runs)."""

import numpy as np
import pytest

from sloth_sorter.classifier import SmartClassificationResult, SmartClassifier


class MockStaticModel:
    """Mock Model2Vec StaticModel returning deterministic embeddings."""

    def __init__(self):
        # Known category mappings for testing
        self.dim = 8

    def encode(self, texts):
        results = []
        for text in texts:
            t = text.lower()
            vec = np.zeros(self.dim, dtype=np.float32)
            if "invoice" in t or "bill" in t or "payment" in t:
                vec[0] = 1.0
            elif "resume" in t or "curriculum vitae" in t or "experience" in t:
                vec[1] = 1.0
            elif "homework" in t or "assignment" in t:
                vec[2] = 1.0
            elif "report" in t or "annual" in t:
                vec[3] = 1.0
            else:
                vec[7] = 1.0  # other/noise
            results.append(vec)
        return np.array(results)


def test_classifier_mock_inference():
    prototypes = {
        "Invoices": ["invoice billing payment statement"],
        "Resumes": ["curriculum vitae work experience education"],
        "Assignments": ["homework assignment problem set submission"],
    }
    mock_model = MockStaticModel()
    classifier = SmartClassifier(
        prototypes=prototypes,
        threshold=0.3,
        model_instance=mock_model,
    )

    # Test invoice classification
    res_inv = classifier.classify_text("Please pay this monthly invoice bill total")
    assert res_inv is not None
    assert res_inv.category == "Invoices"
    assert res_inv.score > 0.9
    assert res_inv.confidence == "embedding"

    # Test resume classification
    res_res = classifier.classify_text("Senior developer with 5 years work experience and resume")
    assert res_res is not None
    assert res_res.category == "Resumes"
    assert res_res.score > 0.9

    # Test assignment classification
    res_assign = classifier.classify_text("Complete this homework assignment before Friday")
    assert res_assign is not None
    assert res_assign.category == "Assignments"


def test_classifier_threshold_rejection():
    prototypes = {
        "Invoices": ["invoice billing payment"],
    }
    mock_model = MockStaticModel()
    classifier = SmartClassifier(
        prototypes=prototypes,
        threshold=0.8,
        model_instance=mock_model,
    )

    # Completely unrelated text that won't match vector 0
    res = classifier.classify_text("Random cat video recipe baking cookies")
    assert res is None


def test_classifier_empty_text():
    mock_model = MockStaticModel()
    classifier = SmartClassifier(model_instance=mock_model)
    assert classifier.classify_text("") is None
    assert classifier.classify_text("    ") is None


def test_lazy_loading():
    classifier = SmartClassifier()
    # Model should not be loaded yet
    assert classifier._model is None
    assert classifier._centroids is None
