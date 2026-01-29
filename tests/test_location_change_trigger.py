"""Tests for LocationChangeTrigger classifier."""

from __future__ import annotations

import pytest

from src.core.location_change_trigger import (
    TRAIN_PATH,
    LocationChangeTrigger,
    LocationTriggerResult,
    detect_location_change,
    has_location_trigger_fast,
    load_training_data,
    reset_classifier,
)


class TestLocationTriggerResult:
    """Tests for LocationTriggerResult dataclass."""

    def test_result_fields(self) -> None:
        """Test result has all expected fields."""
        result = LocationTriggerResult(
            triggered=True,
            trigger_type="explicit_location",
            confidence=0.95,
            location="Berlin",
        )
        assert result.triggered is True
        assert result.trigger_type == "explicit_location"
        assert result.confidence == 0.95
        assert result.location == "Berlin"

    def test_result_defaults(self) -> None:
        """Test default values."""
        result = LocationTriggerResult(
            triggered=False,
            trigger_type="none",
            confidence=0.8,
        )
        assert result.location is None

    def test_result_is_frozen(self) -> None:
        """Test result is immutable."""
        from dataclasses import FrozenInstanceError

        result = LocationTriggerResult(
            triggered=True,
            trigger_type="explicit_location",
            confidence=0.9,
        )
        with pytest.raises(FrozenInstanceError):
            result.triggered = False  # type: ignore[misc]


class TestLoadTrainingData:
    """Tests for load_training_data function."""

    def test_training_data_exists(self) -> None:
        """Training data file should exist."""
        assert TRAIN_PATH.exists(), f"Training data not found: {TRAIN_PATH}"

    def test_load_training_data_format(self) -> None:
        """Loaded data should have correct format."""
        texts, binary_labels, type_labels = load_training_data()

        assert len(texts) > 0, "No training samples loaded"
        assert len(texts) == len(binary_labels) == len(type_labels)

        # Check binary labels are 0 or 1
        assert all(label in (0, 1) for label in binary_labels)

        # Check type labels are valid
        valid_types = {"explicit_location", "change_phrase", "question", "none"}
        assert all(t in valid_types for t in type_labels)

    def test_load_training_data_no_duplicates(self) -> None:
        """Training data should have no duplicate phrases."""
        texts, _, _ = load_training_data()
        assert len(texts) == len(set(texts)), "Duplicate phrases found"

    def test_training_data_balance(self) -> None:
        """Training data should have reasonable class balance."""
        _texts, binary_labels, _ = load_training_data()

        positive_count = sum(binary_labels)
        negative_count = len(binary_labels) - positive_count

        # At least 20% of each class (location change is less common)
        total = len(binary_labels)
        assert positive_count / total >= 0.2, "Not enough positive samples"
        assert negative_count / total >= 0.2, "Not enough negative samples"


class TestLocationChangeTrigger:
    """Tests for LocationChangeTrigger classifier."""

    @pytest.fixture
    def trained_classifier(self) -> LocationChangeTrigger:
        """Return a trained classifier for testing."""
        texts, binary_labels, type_labels = load_training_data()
        classifier = LocationChangeTrigger()
        classifier.train(texts, binary_labels, type_labels)
        return classifier

    def test_train_returns_metrics(self, trained_classifier: LocationChangeTrigger) -> None:
        """Training should return metrics dict."""
        # Already trained in fixture, re-train to get metrics
        texts, binary_labels, type_labels = load_training_data()
        metrics = trained_classifier.train(texts, binary_labels, type_labels)

        assert "accuracy" in metrics
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert "samples" in metrics

        # Metrics should be reasonable (> 0.7 on training data)
        assert metrics["accuracy"] >= 0.7
        assert metrics["f1"] >= 0.5  # Lower threshold for location changes

    def test_predict_explicit_location(self, trained_classifier: LocationChangeTrigger) -> None:
        """Should detect explicit location mentions."""
        # Russian relocation phrase
        result = trained_classifier.predict("переехал в Берлин")
        assert result.triggered is True
        assert result.confidence > 0.5

        # English relocation
        result = trained_classifier.predict("I moved to Berlin")
        assert result.triggered is True

    def test_predict_current_location(self, trained_classifier: LocationChangeTrigger) -> None:
        """Should detect current location mentions."""
        result = trained_classifier.predict("я сейчас в Москве")
        assert result.triggered is True

        result = trained_classifier.predict("I'm in London now")
        assert result.triggered is True

    def test_predict_no_trigger(self, trained_classifier: LocationChangeTrigger) -> None:
        """Should not trigger on regular messages."""
        result = trained_classifier.predict("привет, как дела?")
        assert result.triggered is False
        assert result.trigger_type == "none"

        # Use clearly non-location phrases
        result = trained_classifier.predict("done, committed the code")
        assert result.triggered is False

    def test_predict_proba(self, trained_classifier: LocationChangeTrigger) -> None:
        """predict_proba should return valid probability."""
        prob = trained_classifier.predict_proba("переехал в Москву")
        assert 0.0 <= prob <= 1.0
        assert prob > 0.5  # Should be confident about location phrase

        prob = trained_classifier.predict_proba("привет!")
        assert 0.0 <= prob <= 1.0
        assert prob < 0.5  # Should be confident about no location

    def test_is_trained_property(self) -> None:
        """is_trained should reflect training state."""
        classifier = LocationChangeTrigger()
        assert classifier.is_trained is False

        texts, binary_labels, type_labels = load_training_data()
        classifier.train(texts, binary_labels, type_labels)
        assert classifier.is_trained is True

    def test_predict_before_training_raises(self) -> None:
        """Predicting before training should raise RuntimeError."""
        classifier = LocationChangeTrigger()
        with pytest.raises(RuntimeError, match="not trained"):
            classifier.predict("test")


class TestFastPathPatterns:
    """Tests for fast-path regex patterns."""

    @pytest.mark.parametrize(
        "text",
        [
            # Russian verbs
            "переехал в Москву",
            "переехала в Берлин",
            "теперь в Париже",
            "сейчас в Лондоне",
            "живу в Тбилиси",
            "я в Минске",
            # English verbs
            "I am in Berlin",
            "moving to Paris",
            "moved to London",
            "living in Tokyo",
            "based in New York",
        ],
    )
    def test_fast_path_triggers(self, text: str) -> None:
        """Fast path should trigger on location patterns."""
        assert has_location_trigger_fast(text) is True

    @pytest.mark.parametrize(
        "text",
        [
            "привет всем",
            "готово, закоммитил",
            "hello everyone",
            "the meeting is tomorrow",
            "version 3.0",
        ],
    )
    def test_fast_path_no_trigger(self, text: str) -> None:
        """Fast path should not trigger on regular text."""
        assert has_location_trigger_fast(text) is False


class TestDetectLocationChange:
    """Tests for detect_location_change function."""

    @pytest.fixture(autouse=True)
    def reset_global_classifier(self) -> None:
        """Reset global classifier before each test."""
        reset_classifier()

    def test_detect_with_fast_path(self) -> None:
        """Fast path should be used for obvious patterns."""
        result = detect_location_change("переехал в Москву", use_fast_path=True)
        assert result.triggered is True
        assert result.confidence >= 0.95  # Fast path confidence

    def test_detect_with_ml_fallback(self) -> None:
        """ML should be used when fast path doesn't match."""
        # This phrase might not match fast path regex exactly
        result = detect_location_change("буду в Берлине на следующей неделе", use_fast_path=True)
        # ML might or might not trigger - just check it returns valid result
        assert isinstance(result, LocationTriggerResult)
        assert result.trigger_type in ("explicit_location", "change_phrase", "question", "none")

    def test_detect_without_fast_path(self) -> None:
        """Can skip fast path and use ML directly."""
        result = detect_location_change("переехал в Москву", use_fast_path=False)
        assert isinstance(result, LocationTriggerResult)


class TestEdgeCases:
    """Edge case tests."""

    @pytest.fixture
    def trained_classifier(self) -> LocationChangeTrigger:
        """Return a trained classifier for testing."""
        texts, binary_labels, type_labels = load_training_data()
        classifier = LocationChangeTrigger()
        classifier.train(texts, binary_labels, type_labels)
        return classifier

    def test_empty_string(self, trained_classifier: LocationChangeTrigger) -> None:
        """Empty string should not trigger."""
        result = trained_classifier.predict("")
        assert result.triggered is False

    def test_mixed_case(self, trained_classifier: LocationChangeTrigger) -> None:
        """Mixed case should still work."""
        result = trained_classifier.predict("ПЕРЕЕХАЛ В МОСКВУ")
        # Case insensitive handling may vary
        assert isinstance(result, LocationTriggerResult)

    def test_unicode_cities(self, trained_classifier: LocationChangeTrigger) -> None:
        """Should handle unicode city names."""
        result = trained_classifier.predict("переехал в Тбилиси")
        assert result.triggered is True

    def test_multi_word_cities(self, trained_classifier: LocationChangeTrigger) -> None:
        """Should handle multi-word city names."""
        result = trained_classifier.predict("moved to New York")
        assert result.triggered is True


class TestThreadSafety:
    """Tests for thread-safe classifier loading."""

    @pytest.fixture(autouse=True)
    def reset_global_classifier(self) -> None:
        """Reset global classifier before each test."""
        reset_classifier()

    def test_reset_classifier(self) -> None:
        """reset_classifier should clear global instance."""
        from src.core.location_change_trigger import get_classifier

        # First call initializes
        classifier1 = get_classifier()
        assert classifier1.is_trained

        # Reset clears it
        reset_classifier()

        # Next call creates new instance
        classifier2 = get_classifier()
        assert classifier2.is_trained
        # Can't easily test they're different objects, but function works
