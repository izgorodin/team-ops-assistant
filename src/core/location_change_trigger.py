"""Location change trigger classifier.

Detects when a message mentions a location that might indicate
user's physical location change (relocation, travel, presence).

Examples that trigger:
- "я в Берлине" (I'm in Berlin)
- "переехал в Москву" (moved to Moscow)
- "лечу в Париж" (flying to Paris)
- "нахожусь в Лондоне" (currently in London)

Examples that don't trigger:
- "привет, как дела?" (just greeting)
- "готово, закоммитил" (work update)
- "version 3.0" (version number)

Uses TF-IDF + Logistic Regression, same pattern as TzContextTrigger.
"""

from __future__ import annotations

import csv
import pickle
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

# Paths
TRAIN_PATH = Path(__file__).parent.parent.parent / "data" / "tz_location_change_train.csv"
TEST_PATH = Path(__file__).parent.parent.parent / "data" / "tz_location_change_test.csv"
MODEL_PATH = Path(__file__).parent.parent.parent / "data" / "location_change_trigger.pkl"


@dataclass(frozen=True)
class LocationTriggerResult:
    """Result of location change trigger detection."""

    triggered: bool
    trigger_type: str  # "explicit_location", "question", "change_phrase", "none"
    confidence: float
    location: str | None = None  # Detected location name if any


class LocationChangeTrigger:
    """Classifier for detecting location change mentions.

    Two-stage approach:
    1. Binary classifier: does message mention a location?
    2. If yes, classify trigger type
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
            binary_labels: 1 = has location mention, 0 = no location
            type_labels: "explicit_location", "question", "change_phrase", or "none"

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

        # Binary classifier: has location or not
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

    def predict(self, text: str) -> LocationTriggerResult:
        """Predict if text mentions a location.

        Args:
            text: Input phrase

        Returns:
            LocationTriggerResult with triggered, trigger_type, confidence
        """
        if not self._is_trained or self.vectorizer is None or self.binary_model is None:
            raise RuntimeError("Classifier not trained. Call train() or load() first.")

        X = self.vectorizer.transform([text])

        # Binary prediction
        binary_proba = self.binary_model.predict_proba(X)[0]
        positive_proba = float(binary_proba[1])

        # Not triggered
        if positive_proba < 0.5:
            return LocationTriggerResult(
                triggered=False,
                trigger_type="none",
                confidence=1.0 - positive_proba,
            )

        # Triggered - get type
        trigger_type = "explicit_location"  # default
        if self.type_model is not None:
            type_pred = self.type_model.predict(X)[0]
            trigger_type = str(type_pred)

        return LocationTriggerResult(
            triggered=True,
            trigger_type=trigger_type,
            confidence=positive_proba,
        )

    def predict_proba(self, text: str) -> float:
        """Get probability of location mention.

        Args:
            text: Input phrase

        Returns:
            Probability (0.0 to 1.0) that text mentions a location
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
            has_loc = row.get("has_location_change", "")
            if has_loc is None:
                continue
            has_loc = has_loc.strip()
            trigger_type = row.get("trigger_type", "") or ""
            trigger_type = trigger_type.strip()

            # Skip empty, duplicates, or malformed rows
            if not phrase or phrase in seen:
                continue
            if has_loc not in ("0", "1"):
                continue

            seen.add(phrase)

            texts.append(phrase)
            binary_labels.append(int(has_loc))
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
    classifier = LocationChangeTrigger()
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
_classifier: LocationChangeTrigger | None = None
_classifier_lock = threading.Lock()


def reset_classifier() -> None:
    """Reset global classifier (useful for testing)."""
    global _classifier
    with _classifier_lock:
        _classifier = None


def get_classifier() -> LocationChangeTrigger:
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

        new_classifier = LocationChangeTrigger()
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

# Location verbs in Russian
_LOCATION_VERBS_RU = re.compile(
    r"(переехал[а]?|перебрал[ао]?сь|теперь\s+в|сейчас\s+в|живу\s+в|буду\s+в|"
    r"лечу\s+в|прилета[юе]|приехал[а]?|нахожусь\s+в|я\s+в|уехал[а]?\s+в)\s+",
    re.IGNORECASE,
)

# Location verbs in English
_LOCATION_VERBS_EN = re.compile(
    r"(I\s+am\s+in|we\s+are\s+in|now\s+in|moving\s+to|moved\s+to|"
    r"flying\s+to|landing\s+in|based\s+in|living\s+in)\s+",
    re.IGNORECASE,
)

# Common cities (subset for fast-path)
_CITIES_PATTERN = re.compile(
    r"\b(москв[аеуы]?|питер[еу]?|берлин[еу]?|париж[еу]?|лондон[еу]?|"
    r"тбилиси|киев[еу]?|минск[еу]?|moscow|berlin|paris|london|"
    r"new\s+york|los\s+angeles|san\s+francisco|tokyo|seoul)\b",
    re.IGNORECASE,
)


def has_location_trigger_fast(text: str) -> bool:
    """Fast check if text likely has a location-related cue.

    Uses regex patterns for quick filtering before ML.
    Returns True if any location verb pattern OR any city pattern matches.

    Note: This is intentionally broad - it triggers on:
    1. Location verbs (RU/EN) without requiring a city name
    2. City names without requiring a verb

    The ML classifier makes the final decision; this is just for fast-path filtering.
    """
    # Check for location verbs (RU/EN), regardless of whether a city is mentioned
    if _LOCATION_VERBS_RU.search(text) or _LOCATION_VERBS_EN.search(text):
        return True
    # Also trigger on standalone city mentions from the common cities subset
    return bool(_CITIES_PATTERN.search(text))


def detect_location_change(text: str, use_fast_path: bool = True) -> LocationTriggerResult:
    """Detect if text mentions a location change.

    Args:
        text: Input message text
        use_fast_path: Whether to use regex fast-path before ML

    Returns:
        LocationTriggerResult with detection info
    """
    # Fast path: regex patterns for obvious cases
    if use_fast_path:
        if _LOCATION_VERBS_RU.search(text) and _CITIES_PATTERN.search(text):
            return LocationTriggerResult(
                triggered=True,
                trigger_type="explicit_location",
                confidence=0.95,
            )
        if _LOCATION_VERBS_EN.search(text) and _CITIES_PATTERN.search(text):
            return LocationTriggerResult(
                triggered=True,
                trigger_type="explicit_location",
                confidence=0.95,
            )

    # ML path
    classifier = get_classifier()
    return classifier.predict(text)
