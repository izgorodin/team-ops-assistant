"""Timezone context trigger classifier.

Detects when a message requires timezone context resolution:
- Explicit timezone mentions (Мск, PST, "по Тбилиси")
- Clarification questions ("это по москве?", "what timezone?")

Uses TF-IDF + Logistic Regression, same pattern as TimeClassifier.
"""

from __future__ import annotations

import csv
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

# Paths
TRAIN_PATH = Path(__file__).parent.parent.parent / "data" / "tz_context_trigger_train.csv"
TEST_PATH = Path(__file__).parent.parent.parent / "data" / "tz_context_trigger_test.csv"
MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "tz_context_trigger.pkl"


@dataclass(frozen=True)
class TzTriggerResult:
    """Result of timezone context trigger detection."""

    triggered: bool
    trigger_type: str  # "explicit_tz", "clarification_question", "none"
    confidence: float
    source_tz: str | None = None  # IANA timezone if detected


class TzContextTrigger:
    """Classifier for detecting timezone context triggers.

    Two-stage approach:
    1. Binary classifier: does message need TZ resolution?
    2. If yes, classify trigger type (explicit_tz vs clarification_question)
    """

    def __init__(self) -> None:
        self.vectorizer: TfidfVectorizer | None = None
        self.binary_model: LogisticRegression | None = None
        self.type_model: LogisticRegression | None = None
        self._is_trained = False
        self._type_labels: list[str] = []

    def train(
        self,
        texts: list[str],
        binary_labels: list[int],
        type_labels: list[str],
    ) -> dict[str, float]:
        """Train classifier on labeled data.

        Args:
            texts: List of phrases
            binary_labels: 1 = has TZ context, 0 = no TZ context
            type_labels: "explicit_tz", "clarification_question", or "none"

        Returns:
            Training metrics
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

        # TF-IDF with character n-grams (helps with multilingual)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(2, 5),
            analyzer="char_wb",
            min_df=2,
            max_df=0.95,
        )

        X = self.vectorizer.fit_transform(texts)

        # Binary classifier: has TZ context or not
        self.binary_model = LogisticRegression(
            class_weight="balanced",
            max_iter=1000,
            random_state=42,
        )
        self.binary_model.fit(X, binary_labels)

        # Type classifier: only train on positive examples
        positive_indices = [i for i, label in enumerate(binary_labels) if label == 1]
        if positive_indices:
            import numpy as np

            X_positive = X[np.array(positive_indices)]
            type_labels_positive = [type_labels[i] for i in positive_indices]

            # Store unique type labels for prediction
            self._type_labels = sorted(set(type_labels_positive))

            self.type_model = LogisticRegression(
                class_weight="balanced",
                max_iter=1000,
                random_state=42,
            )
            self.type_model.fit(X_positive, type_labels_positive)

        self._is_trained = True

        # Compute metrics on training data
        binary_predictions = self.binary_model.predict(X)
        return {
            "accuracy": accuracy_score(binary_labels, binary_predictions),
            "precision": precision_score(binary_labels, binary_predictions, zero_division="warn"),
            "recall": recall_score(binary_labels, binary_predictions, zero_division="warn"),
            "f1": f1_score(binary_labels, binary_predictions, zero_division="warn"),
            "samples": len(texts),
            "positive_samples": sum(binary_labels),
            "negative_samples": len(binary_labels) - sum(binary_labels),
        }

    def predict(self, text: str) -> TzTriggerResult:
        """Predict if text triggers TZ context resolution.

        Args:
            text: Input phrase

        Returns:
            TzTriggerResult with triggered, trigger_type, confidence
        """
        if not self._is_trained or self.vectorizer is None or self.binary_model is None:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")

        X = self.vectorizer.transform([text])

        # Binary prediction
        binary_proba = self.binary_model.predict_proba(X)[0]
        positive_proba = float(binary_proba[1])

        # Not triggered
        if positive_proba < 0.5:
            return TzTriggerResult(
                triggered=False,
                trigger_type="none",
                confidence=1.0 - positive_proba,
            )

        # Triggered - get type
        trigger_type = "explicit_tz"  # default
        if self.type_model is not None:
            type_pred = self.type_model.predict(X)[0]
            trigger_type = str(type_pred)

        return TzTriggerResult(
            triggered=True,
            trigger_type=trigger_type,
            confidence=positive_proba,
        )

    def predict_proba(self, text: str) -> float:
        """Get probability of TZ context trigger.

        Args:
            text: Input phrase

        Returns:
            Probability (0.0 to 1.0) that text triggers TZ resolution
        """
        if not self._is_trained or self.vectorizer is None or self.binary_model is None:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")

        X = self.vectorizer.transform([text])
        proba = self.binary_model.predict_proba(X)[0]
        return float(proba[1])

    def save(self, path: Path | None = None) -> None:
        """Save trained model to disk."""
        if not self._is_trained:
            raise RuntimeError("Cannot save untrained model.")

        save_path = path or MODEL_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with save_path.open("wb") as f:
            pickle.dump(
                {
                    "vectorizer": self.vectorizer,
                    "binary_model": self.binary_model,
                    "type_model": self.type_model,
                    "type_labels": self._type_labels,
                },
                f,
            )

    def load(self, path: Path | None = None) -> None:
        """Load trained model from disk."""
        load_path = path or MODEL_PATH

        if not load_path.exists():
            raise FileNotFoundError(f"Model not found: {load_path}")

        with load_path.open("rb") as f:
            data = pickle.load(f)
            self.vectorizer = data["vectorizer"]
            self.binary_model = data["binary_model"]
            self.type_model = data.get("type_model")
            self._type_labels = data.get("type_labels", [])
            self._is_trained = True

    @property
    def is_trained(self) -> bool:
        """Check if model is ready for predictions."""
        return self._is_trained


def load_training_data(
    path: Path | None = None,
) -> tuple[list[str], list[int], list[str]]:
    """Load training data from CSV.

    Args:
        path: Path to CSV file. Defaults to TRAIN_PATH.

    Returns:
        Tuple of (texts, binary_labels, type_labels)
    """
    data_path = path or TRAIN_PATH

    if not data_path.exists():
        raise FileNotFoundError(f"Training data not found: {data_path}")

    texts: list[str] = []
    binary_labels: list[int] = []
    type_labels: list[str] = []
    seen: set[str] = set()

    with data_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phrase = row.get("phrase", "")
            # Skip comments (rows where phrase starts with #)
            if phrase is None or phrase.startswith("#"):
                continue
            phrase = phrase.strip()
            has_tz = row.get("has_tz_context", "")
            if has_tz is None:
                continue
            has_tz = has_tz.strip()
            trigger_type = row.get("trigger_type", "") or ""
            trigger_type = trigger_type.strip()

            # Skip empty, duplicates, or malformed rows
            if not phrase or phrase in seen:
                continue
            if has_tz not in ("0", "1"):
                continue

            seen.add(phrase)

            texts.append(phrase)
            binary_labels.append(int(has_tz))
            type_labels.append(trigger_type if trigger_type else "none")

    return texts, binary_labels, type_labels


def train_from_corpus(save: bool = True) -> dict[str, float]:
    """Train classifier from training data.

    Args:
        save: Whether to save model to disk

    Returns:
        Training metrics
    """
    texts, binary_labels, type_labels = load_training_data()
    classifier = TzContextTrigger()
    metrics = classifier.train(texts, binary_labels, type_labels)
    if save:
        classifier.save()
    return metrics


def evaluate_on_test() -> dict[str, float]:
    """Evaluate trained model on test set.

    Returns:
        Test metrics
    """
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

    # Load test data
    texts, binary_labels, _type_labels = load_training_data(TEST_PATH)

    # Load trained model
    classifier = get_classifier()

    # Predict
    predictions = [1 if classifier.predict(text).triggered else 0 for text in texts]

    return {
        "test_accuracy": accuracy_score(binary_labels, predictions),
        "test_precision": precision_score(binary_labels, predictions, zero_division="warn"),
        "test_recall": recall_score(binary_labels, predictions, zero_division="warn"),
        "test_f1": f1_score(binary_labels, predictions, zero_division="warn"),
        "test_samples": len(texts),
    }


# Global classifier instance (lazy loaded with thread-safe initialization)
import threading

_classifier: TzContextTrigger | None = None
_classifier_lock = threading.Lock()


def reset_classifier() -> None:
    """Reset global classifier (useful for testing)."""
    global _classifier
    with _classifier_lock:
        _classifier = None


def get_classifier() -> TzContextTrigger:
    """Get trained classifier (loads from disk if needed).

    Thread-safe with double-checked locking pattern.
    """
    global _classifier

    # Fast path: already initialized
    if _classifier is not None:
        return _classifier

    # Slow path: acquire lock and initialize
    with _classifier_lock:
        # Double-check after acquiring lock
        if _classifier is not None:
            return _classifier

        new_classifier = TzContextTrigger()
        if MODEL_PATH.exists():
            new_classifier.load()
        else:
            # Train on first use if no saved model
            texts, binary_labels, type_labels = load_training_data()
            new_classifier.train(texts, binary_labels, type_labels)
            new_classifier.save()

        _classifier = new_classifier
        return _classifier


# ============================================================================
# Quick trigger patterns (for fast-path before ML)
# ============================================================================

# Common TZ abbreviations that strongly indicate explicit_tz
# Negative lookaheads exclude:
# - Ticket IDs: MSK-2024-001, EST-123
# - File references: "PST файл", "PST file"
_TZ_ABBREV_PATTERN = re.compile(
    r"\b(мск|msk|pst|pdt|est|edt|cst|cdt|gmt|utc|cet|cest|bst|jst|kst|ist|aest|aedt|nzst)\b"
    r"(?!-\d)"  # Not followed by ticket ID pattern
    r"(?!\s+файл\b)"  # Not followed by "файл" (file in Russian)
    r"(?!\s+file\b)",  # Not followed by "file"
    re.IGNORECASE,
)

# "по" + city pattern (Russian)
# "москов" catches "московскому", "московское", etc.
_PO_CITY_PATTERN = re.compile(
    r"по\s+(москов|москв|питер|тбилиси|киев|минск|баку|ереван|алмат|астан|берлин|лондон|париж)",
    re.IGNORECASE,
)

# UTC offset pattern
_UTC_OFFSET_PATTERN = re.compile(r"(utc|gmt)\s*[+-]\s*\d{1,2}", re.IGNORECASE)

# Clarification question patterns
_CLARIFICATION_PATTERNS = [
    re.compile(r"это\s+по\s+(москов|москв|мск|местн)", re.IGNORECASE),
    re.compile(r"по\s+каком(?:у)?\s+(времен|зон)", re.IGNORECASE),
    re.compile(r"какая\s+(таймзона|timezone|зона)", re.IGNORECASE),
    re.compile(r"what\s+timezone", re.IGNORECASE),
    re.compile(r"which\s+tz", re.IGNORECASE),
    re.compile(r"is\s+that\s+(pst|est|gmt|local)", re.IGNORECASE),
]


def has_tz_trigger_fast(text: str) -> bool:
    """Fast check if text likely has TZ trigger.

    Uses regex patterns for quick filtering before ML.
    Returns True if any pattern matches.
    """
    if _TZ_ABBREV_PATTERN.search(text):
        return True
    if _PO_CITY_PATTERN.search(text):
        return True
    if _UTC_OFFSET_PATTERN.search(text):
        return True
    return any(pattern.search(text) for pattern in _CLARIFICATION_PATTERNS)


def detect_tz_context(text: str, use_fast_path: bool = True) -> TzTriggerResult:
    """Detect if text triggers TZ context resolution.

    Args:
        text: Input message text
        use_fast_path: Whether to use regex fast-path before ML

    Returns:
        TzTriggerResult with detection info
    """
    # Fast path: regex patterns for obvious cases
    if use_fast_path:
        # Check clarification patterns FIRST (higher priority)
        if any(pattern.search(text) for pattern in _CLARIFICATION_PATTERNS):
            return TzTriggerResult(
                triggered=True,
                trigger_type="clarification_question",
                confidence=0.90,
            )
        # Then check explicit TZ patterns
        if _TZ_ABBREV_PATTERN.search(text) or _PO_CITY_PATTERN.search(text):
            return TzTriggerResult(
                triggered=True,
                trigger_type="explicit_tz",
                confidence=0.95,
            )
        if _UTC_OFFSET_PATTERN.search(text):
            return TzTriggerResult(
                triggered=True,
                trigger_type="explicit_tz",
                confidence=0.95,
            )

    # ML path
    classifier = get_classifier()
    return classifier.predict(text)
