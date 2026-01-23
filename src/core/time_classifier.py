"""ML-based time reference classifier.

Uses TF-IDF + Logistic Regression trained on corpus data.
Simple, fast (<1ms inference), no neural networks needed.
"""

from __future__ import annotations

import csv
import pickle
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

# Paths
TRAIN_PATH = Path(__file__).parent.parent.parent / "data" / "time_extraction_train.csv"
MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "time_classifier.pkl"


class TimeClassifier:
    """Binary classifier: does text contain a time reference?"""

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None
        self.model: LogisticRegression | None = None
        self._is_trained = False

    def train(self, texts: list[str], labels: list[int]) -> dict[str, float]:
        """Train classifier on labeled data.

        Args:
            texts: List of phrases
            labels: 1 = contains time, 0 = no time

        Returns:
            Training metrics (accuracy on full set)
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

        from src.settings import get_settings

        config = get_settings().config.classifier

        # TF-IDF with character n-grams (helps with multilingual)
        self.vectorizer = TfidfVectorizer(
            ngram_range=tuple(config.tfidf.ngram_range),
            analyzer="char_wb",  # character n-grams with word boundaries
            min_df=config.tfidf.min_df,
            max_df=config.tfidf.max_df,
        )

        X = self.vectorizer.fit_transform(texts)

        # Logistic regression with balanced class weights
        self.model = LogisticRegression(
            class_weight="balanced",
            max_iter=config.logistic_regression.max_iter,
            random_state=config.logistic_regression.random_state,
        )
        self.model.fit(X, labels)
        self._is_trained = True

        # Compute metrics on training data (for info)
        predictions = self.model.predict(X)
        return {
            "accuracy": accuracy_score(labels, predictions),
            "precision": precision_score(labels, predictions),
            "recall": recall_score(labels, predictions),
            "f1": f1_score(labels, predictions),
            "samples": len(texts),
        }

    def predict(self, text: str) -> bool:
        """Predict if text contains time reference.

        Args:
            text: Input phrase

        Returns:
            True if time reference detected
        """
        if not self._is_trained or self.vectorizer is None or self.model is None:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")

        X = self.vectorizer.transform([text])
        return bool(self.model.predict(X)[0] == 1)

    def predict_proba(self, text: str) -> float:
        """Get probability of time reference.

        Args:
            text: Input phrase

        Returns:
            Probability (0.0 to 1.0) that text contains time
        """
        if not self._is_trained or self.vectorizer is None or self.model is None:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")

        X = self.vectorizer.transform([text])
        proba = self.model.predict_proba(X)[0]
        # Index 1 is probability of positive class
        return float(proba[1])

    def save(self, path: Path | None = None) -> None:
        """Save trained model to disk."""
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model.")

        save_path = path or MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with save_path.open("wb") as f:
            pickle.dump({"vectorizer": self.vectorizer, "model": self.model}, f)

    def load(self, path: Path | None = None) -> None:
        """Load trained model from disk."""
        load_path = path or MODEL_PATH

        if not load_path.exists():
            raise FileNotFoundError(f"Model not found: {load_path}")

        with load_path.open("rb") as f:
            data = pickle.load(f)
            self.vectorizer = data["vectorizer"]
            self.model = data["model"]
            self._is_trained = True

    @property
    def is_trained(self) -> bool:
        """Check if model is ready for predictions."""
        return self._is_trained


def load_training_data() -> tuple[list[str], list[int]]:
    """Load training data from CSV.

    Returns:
        Tuple of (texts, labels) where label=1 means time reference
    """
    if not TRAIN_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {TRAIN_PATH}")

    texts: list[str] = []
    labels: list[int] = []
    seen: set[str] = set()

    with TRAIN_PATH.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase = row.get("phrase", "").strip()
            times_str = row.get("times", "").strip()

            if not phrase or phrase in seen:
                continue
            seen.add(phrase)

            texts.append(phrase)
            # Label: 1 if times column has value, 0 otherwise
            labels.append(1 if times_str else 0)

    return texts, labels


def train_from_corpus() -> dict[str, float]:
    """Train classifier from training data and save model.

    Returns:
        Training metrics
    """
    texts, labels = load_training_data()
    classifier = TimeClassifier()
    metrics = classifier.train(texts, labels)
    classifier.save()
    return metrics


# Global classifier instance (lazy loaded)
_classifier: TimeClassifier | None = None


def get_classifier() -> TimeClassifier:
    """Get trained classifier (loads from disk if needed)."""
    global _classifier

    if _classifier is None:
        _classifier = TimeClassifier()
        if MODEL_PATH.exists():
            _classifier.load()
        else:
            # Train on first use if no saved model
            texts, labels = load_training_data()
            _classifier.train(texts, labels)
            _classifier.save()

    return _classifier


# Trigger pattern - any digit (covers 95%+ of time references)
_TRIGGER = re.compile(r"\d")

# Time words without digits (rare but important)
_TIME_WORDS = frozenset(
    {
        "noon",
        "midnight",
        "midday",
        "полдень",
        "полночь",
        "midi",
        "minuit",
    }
)


def _get_classifier_config() -> tuple[float, float, int, int]:
    """Get classifier config from settings.

    Returns:
        Tuple of (low_threshold, high_threshold, long_text_threshold, window_size)
    """
    from src.settings import get_settings

    config = get_settings().config.classifier
    return (
        config.low_threshold,
        config.high_threshold,
        config.long_text_threshold,
        config.window_size,
    )


def _extract_windows(text: str, window_size: int) -> list[str]:
    """Extract context windows around potential time triggers.

    For each token containing a digit or time word, extracts
    a window of ±window_size tokens around it.

    Args:
        text: Input text
        window_size: Number of tokens before and after trigger

    Returns:
        List of context windows to check with ML
    """
    tokens = text.split()
    windows: list[str] = []
    seen_ranges: set[tuple[int, int]] = set()

    for i, token in enumerate(tokens):
        # Check if token is a trigger (has digit or is time word)
        if _TRIGGER.search(token) or token.lower() in _TIME_WORDS:
            # Calculate window bounds
            start = max(0, i - window_size)
            end = min(len(tokens), i + window_size + 1)

            # Avoid duplicate windows
            bounds = (start, end)
            if bounds in seen_ranges:
                continue
            seen_ranges.add(bounds)

            # Extract window
            window = " ".join(tokens[start:end])
            windows.append(window)

    return windows


def contains_time_ml(text: str, use_llm_fallback: bool = True) -> bool:
    """Check if text contains time reference using ML classifier.

    Pipeline:
    1. TRIGGER GUARD: Check for digits or time words (noon, midnight)
       - No triggers → return False immediately
    2. ML CLASSIFIER: Predict probability
       - prob > HIGH → return True
       - prob < LOW → return False
       - uncertain → use LLM fallback for detection

    Args:
        text: Message text to check
        use_llm_fallback: Whether to use LLM for uncertain cases (default True)

    Returns:
        True if time reference detected
    """
    # STEP 1: Trigger guard - quick filter
    # If no digits and no time words, skip immediately
    has_digit = bool(_TRIGGER.search(text))
    has_time_word = any(word in text.lower() for word in _TIME_WORDS)

    if not has_digit and not has_time_word:
        return False

    classifier = get_classifier()

    # Get config values
    _, _, long_text_threshold, window_size = _get_classifier_config()

    # Short text - check directly with thresholds
    if len(text) <= long_text_threshold:
        return _check_with_threshold(classifier, text, use_llm_fallback)

    # Long text - extract windows around triggers and check each
    windows = _extract_windows(text, window_size)

    # No windows = no time (shouldn't happen after trigger guard)
    if not windows:
        return False

    # Check each window with thresholds
    return any(_check_with_threshold(classifier, window, use_llm_fallback) for window in windows)


def _check_with_threshold(classifier: TimeClassifier, text: str, use_llm_fallback: bool) -> bool:
    """Check text with probability thresholds.

    LLM fallback parameter kept for API compatibility but LLM is now used
    for extraction, not detection. Uncertain cases use classifier binary prediction.

    Args:
        classifier: Trained classifier instance
        text: Text to check
        use_llm_fallback: Deprecated, kept for compatibility

    Returns:
        True if time reference detected
    """
    proba = classifier.predict_proba(text)

    # Confident YES
    low_threshold, high_threshold, _, _ = _get_classifier_config()
    if proba > high_threshold:
        return True

    # Confident NO
    if proba < low_threshold:
        return False

    # Uncertain - use classifier binary prediction
    # LLM is now used for extraction fallback, not detection
    return classifier.predict(text)
