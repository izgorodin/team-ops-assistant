"""Tests for TzContextTrigger classifier."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.core.tz_context_trigger import (
    TEST_PATH,
    TRAIN_PATH,
    TzContextTrigger,
    TzTriggerResult,
    detect_tz_context,
    has_tz_trigger_fast,
    load_training_data,
)

if TYPE_CHECKING:
    from pathlib import Path


class TestTzTriggerResult:
    """Tests for TzTriggerResult dataclass."""

    def test_result_fields(self) -> None:
        """Test result has all expected fields."""
        result = TzTriggerResult(
            triggered=True,
            trigger_type="explicit_tz",
            confidence=0.95,
            source_tz="Europe/Moscow",
        )
        assert result.triggered is True
        assert result.trigger_type == "explicit_tz"
        assert result.confidence == 0.95
        assert result.source_tz == "Europe/Moscow"

    def test_result_defaults(self) -> None:
        """Test default values."""
        result = TzTriggerResult(
            triggered=False,
            trigger_type="none",
            confidence=0.8,
        )
        assert result.source_tz is None

    def test_result_is_frozen(self) -> None:
        """Test result is immutable."""
        from dataclasses import FrozenInstanceError

        result = TzTriggerResult(
            triggered=True,
            trigger_type="explicit_tz",
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
        valid_types = {"explicit_tz", "clarification_question", "none"}
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

        # At least 30% of each class
        total = len(binary_labels)
        assert positive_count / total >= 0.3, "Not enough positive samples"
        assert negative_count / total >= 0.3, "Not enough negative samples"


class TestTzContextTrigger:
    """Tests for TzContextTrigger classifier."""

    @pytest.fixture
    def trained_classifier(self) -> TzContextTrigger:
        """Return a trained classifier for testing."""
        texts, binary_labels, type_labels = load_training_data()
        classifier = TzContextTrigger()
        classifier.train(texts, binary_labels, type_labels)
        return classifier

    def test_train_returns_metrics(self, trained_classifier: TzContextTrigger) -> None:
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
        assert metrics["f1"] >= 0.7

    def test_predict_explicit_tz(self, trained_classifier: TzContextTrigger) -> None:
        """Should detect explicit timezone mentions."""
        # Moscow timezone abbreviation
        result = trained_classifier.predict("встреча в 15:00 МСК")
        assert result.triggered is True
        assert result.trigger_type == "explicit_tz"
        assert result.confidence > 0.5

        # English timezone
        result = trained_classifier.predict("meeting at 3pm PST")
        assert result.triggered is True

    def test_predict_clarification_question(self, trained_classifier: TzContextTrigger) -> None:
        """Should detect timezone clarification questions."""
        result = trained_classifier.predict("это по мск?")
        assert result.triggered is True
        assert result.trigger_type == "clarification_question"

        result = trained_classifier.predict("what timezone?")
        assert result.triggered is True

    def test_predict_no_trigger(self, trained_classifier: TzContextTrigger) -> None:
        """Should not trigger on regular messages."""
        result = trained_classifier.predict("привет, как дела?")
        assert result.triggered is False
        assert result.trigger_type == "none"

        result = trained_classifier.predict("ok sounds good")
        assert result.triggered is False

    def test_predict_proba_range(self, trained_classifier: TzContextTrigger) -> None:
        """Probability should be in [0, 1] range."""
        proba = trained_classifier.predict_proba("в 15 мск")
        assert 0.0 <= proba <= 1.0

        proba = trained_classifier.predict_proba("hello world")
        assert 0.0 <= proba <= 1.0

    def test_is_trained_property(self) -> None:
        """is_trained should reflect model state."""
        classifier = TzContextTrigger()
        assert classifier.is_trained is False

        texts, binary_labels, type_labels = load_training_data()
        classifier.train(texts, binary_labels, type_labels)
        assert classifier.is_trained is True

    def test_predict_untrained_raises(self) -> None:
        """Predicting with untrained model should raise."""
        classifier = TzContextTrigger()
        with pytest.raises(RuntimeError, match="not trained"):
            classifier.predict("test")

    def test_predict_proba_untrained_raises(self) -> None:
        """predict_proba with untrained model should raise."""
        classifier = TzContextTrigger()
        with pytest.raises(RuntimeError, match="not trained"):
            classifier.predict_proba("test")


class TestSaveLoad:
    """Tests for model persistence."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        """Model should save and load correctly."""
        # Train
        texts, binary_labels, type_labels = load_training_data()
        classifier = TzContextTrigger()
        classifier.train(texts, binary_labels, type_labels)

        # Save
        model_path = tmp_path / "model.pkl"
        classifier.save(model_path)
        assert model_path.exists()

        # Load
        new_classifier = TzContextTrigger()
        new_classifier.load(model_path)
        assert new_classifier.is_trained is True

        # Predictions should match
        test_text = "встреча в 14 мск"
        orig_result = classifier.predict(test_text)
        loaded_result = new_classifier.predict(test_text)
        assert orig_result.triggered == loaded_result.triggered
        assert orig_result.trigger_type == loaded_result.trigger_type

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        """Loading nonexistent model should raise FileNotFoundError."""
        classifier = TzContextTrigger()
        with pytest.raises(FileNotFoundError):
            classifier.load(tmp_path / "nonexistent.pkl")

    def test_save_untrained_raises(self, tmp_path: Path) -> None:
        """Saving untrained model should raise."""
        classifier = TzContextTrigger()
        with pytest.raises(RuntimeError, match="untrained"):
            classifier.save(tmp_path / "model.pkl")


class TestFastPath:
    """Tests for fast regex-based detection."""

    def test_tz_abbreviations_detected(self) -> None:
        """Common TZ abbreviations should be detected fast."""
        assert has_tz_trigger_fast("в 15:00 МСК")
        assert has_tz_trigger_fast("meeting at 3pm PST")
        assert has_tz_trigger_fast("call at 10 EST")
        assert has_tz_trigger_fast("14:00 GMT")
        assert has_tz_trigger_fast("09:00 UTC")
        assert has_tz_trigger_fast("18:00 CET")

    def test_po_city_detected(self) -> None:
        """Russian 'по + city' patterns should be detected."""
        assert has_tz_trigger_fast("в 15 по Москве")
        assert has_tz_trigger_fast("созвон в 10 по Тбилиси")
        assert has_tz_trigger_fast("в 14 по Киеву")
        assert has_tz_trigger_fast("на 9 по Минску")

    def test_utc_offset_detected(self) -> None:
        """UTC offset patterns should be detected."""
        assert has_tz_trigger_fast("meeting at 3pm UTC+3")
        assert has_tz_trigger_fast("в 15:00 GMT-5")
        assert has_tz_trigger_fast("call UTC +8")

    def test_clarification_patterns_detected(self) -> None:
        """Clarification questions should be detected."""
        assert has_tz_trigger_fast("это по мск?")
        assert has_tz_trigger_fast("это по московскому?")
        assert has_tz_trigger_fast("what timezone?")
        assert has_tz_trigger_fast("which tz?")

    def test_no_trigger_fast(self) -> None:
        """Regular messages should not trigger fast path."""
        assert not has_tz_trigger_fast("привет, как дела?")
        assert not has_tz_trigger_fast("ok sounds good")
        assert not has_tz_trigger_fast("встреча завтра в 15")
        assert not has_tz_trigger_fast("я в Москве")


class TestDetectTzContext:
    """Tests for high-level detect_tz_context function."""

    def test_detect_with_fast_path(self) -> None:
        """Fast path should work for obvious patterns."""
        result = detect_tz_context("в 15:00 МСК", use_fast_path=True)
        assert result.triggered is True
        assert result.trigger_type == "explicit_tz"
        assert result.confidence >= 0.9

    def test_detect_clarification_fast(self) -> None:
        """Clarification questions via fast path."""
        # Note: "это по мск?" contains MSK abbreviation, so fast path sees it as explicit_tz
        # Use a pattern that only matches clarification
        result = detect_tz_context("это по московскому времени?", use_fast_path=True)
        assert result.triggered is True
        assert result.trigger_type == "clarification_question"

    def test_detect_falls_back_to_ml(self) -> None:
        """Should fall back to ML for non-obvious cases."""
        # This might not match fast patterns but ML should catch it
        result = detect_tz_context("завтра 2 Мск", use_fast_path=True)
        assert result.triggered is True  # MSK detected by fast path

    def test_detect_without_fast_path(self) -> None:
        """Should use ML directly when fast path disabled."""
        result = detect_tz_context("в 15:00 МСК", use_fast_path=False)
        assert result.triggered is True


class TestEdgeCases:
    """Tests for edge cases and tricky inputs."""

    @pytest.fixture
    def classifier(self) -> TzContextTrigger:
        """Return trained classifier."""
        texts, binary_labels, type_labels = load_training_data()
        classifier = TzContextTrigger()
        classifier.train(texts, binary_labels, type_labels)
        return classifier

    def test_empty_string(self, classifier: TzContextTrigger) -> None:
        """Empty string should not trigger."""
        result = classifier.predict("")
        assert result.triggered is False

    def test_only_numbers(self, classifier: TzContextTrigger) -> None:
        """Just numbers should not trigger."""
        result = classifier.predict("123")
        assert result.triggered is False

    def test_time_without_tz(self, classifier: TzContextTrigger) -> None:
        """Time without TZ should not trigger."""
        result = classifier.predict("встреча в 15:00")
        assert result.triggered is False

    def test_city_without_time_context(self, classifier: TzContextTrigger) -> None:
        """City mention without time context should not trigger."""
        result = classifier.predict("я в Москве")
        assert result.triggered is False

    def test_mixed_case_tz(self, classifier: TzContextTrigger) -> None:
        """Mixed case timezone abbreviations should work."""
        result = classifier.predict("в 15 Мск")
        assert result.triggered is True

        result = classifier.predict("at 3pm pst")
        assert result.triggered is True

    def test_unicode_handling(self, classifier: TzContextTrigger) -> None:
        """Unicode characters should be handled correctly."""
        result = classifier.predict("встреча в 15:00 по Москве 🕐")
        # Should not crash, result depends on training data
        assert isinstance(result.triggered, bool)


@pytest.mark.skipif(not TEST_PATH.exists(), reason="Test data not available")
class TestOnTestSet:
    """Tests using the holdout test set."""

    def test_test_data_exists(self) -> None:
        """Test data file should exist."""
        assert TEST_PATH.exists()

    def test_test_data_format(self) -> None:
        """Test data should have same format as training data."""
        texts, binary_labels, type_labels = load_training_data(TEST_PATH)

        assert len(texts) > 0
        assert all(label in (0, 1) for label in binary_labels)

        valid_types = {"explicit_tz", "clarification_question", "none"}
        assert all(t in valid_types for t in type_labels)

    def test_no_overlap_with_training(self) -> None:
        """Test set should not overlap with training set."""
        train_texts, _, _ = load_training_data(TRAIN_PATH)
        test_texts, _, _ = load_training_data(TEST_PATH)

        train_set = set(train_texts)
        test_set = set(test_texts)

        overlap = train_set & test_set
        assert len(overlap) == 0, f"Found {len(overlap)} overlapping samples"
