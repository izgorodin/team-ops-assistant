#!/usr/bin/env python3
"""Evaluate TZ context trigger classifier on test set."""

from src.core.tz_context_trigger import TEST_PATH, TRAIN_PATH, TzContextTrigger, load_training_data


def main():
    # Train fresh model
    print("=== Training model ===")
    texts, binary_labels, type_labels = load_training_data(TRAIN_PATH)
    classifier = TzContextTrigger()
    train_metrics = classifier.train(texts, binary_labels, type_labels)
    print(
        f"Train samples: {train_metrics['samples']} (pos: {train_metrics['positive_samples']}, neg: {train_metrics['negative_samples']})"
    )
    print(f"Train accuracy: {train_metrics['accuracy']:.3f}")
    print(f"Train F1: {train_metrics['f1']:.3f}")
    classifier.save()

    # Evaluate on test
    print()
    print("=== Evaluating on test set ===")
    test_texts, test_binary, test_types = load_training_data(TEST_PATH)
    print(f"Test samples: {len(test_texts)}")

    # Predict
    correct = 0
    false_positives = []
    false_negatives = []

    for text, label, ttype in zip(test_texts, test_binary, test_types, strict=False):
        result = classifier.predict(text)
        pred = 1 if result.triggered else 0
        if pred == label:
            correct += 1
        elif pred == 1 and label == 0:
            false_positives.append((text, result.confidence, result.trigger_type))
        else:
            false_negatives.append((text, result.confidence, ttype))

    accuracy = correct / len(test_texts)
    print(f"Test accuracy: {accuracy:.3f}")

    # Show errors
    if false_positives:
        print(f"\n=== False Positives ({len(false_positives)}) ===")
        for text, conf, ttype in false_positives[:15]:
            print(f'  [{conf:.2f}] {ttype}: "{text}"')

    if false_negatives:
        print(f"\n=== False Negatives ({len(false_negatives)}) ===")
        for text, conf, expected in false_negatives[:15]:
            print(f'  [{conf:.2f}] expected {expected}: "{text}"')

    print("\n=== Summary ===")
    print(f"Accuracy: {accuracy:.1%}")
    print(f"False Positives: {len(false_positives)}")
    print(f"False Negatives: {len(false_negatives)}")


if __name__ == "__main__":
    main()
