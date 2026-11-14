from typing import Hashable, Sequence


def classification_metrics(
    actual: Sequence[Hashable],
    predicted: Sequence[Hashable],
    *,
    labels: Sequence[Hashable] | None = None,
) -> dict[str, object]:
    if len(actual) != len(predicted):
        raise ValueError("Actual and predicted label counts must match.")
    if not actual:
        raise ValueError("Classification metrics require at least one sample.")
    classes = list(labels) if labels is not None else sorted(
        set(actual) | set(predicted), key=str
    )
    if len(classes) != len(set(classes)):
        raise ValueError("Classification labels must be unique.")
    matrix = {
        str(expected): {
            str(observed): sum(
                true == expected and guess == observed
                for true, guess in zip(actual, predicted, strict=True)
            )
            for observed in classes
        }
        for expected in classes
    }
    per_class: dict[str, dict[str, float | int]] = {}
    supports: dict[Hashable, int] = {}
    for label in classes:
        tp = sum(
            true == label and guess == label
            for true, guess in zip(actual, predicted, strict=True)
        )
        fp = sum(
            true != label and guess == label
            for true, guess in zip(actual, predicted, strict=True)
        )
        fn = sum(
            true == label and guess != label
            for true, guess in zip(actual, predicted, strict=True)
        )
        support = sum(value == label for value in actual)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        supports[label] = support
        per_class[str(label)] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    total = len(actual)
    correct = sum(true == guess for true, guess in zip(actual, predicted, strict=True))
    weighted_f1 = sum(
        per_class[str(label)]["f1"] * supports[label] for label in classes
    ) / total
    return {
        "sample_count": total,
        "accuracy": correct / total,
        "macro_f1": sum(item["f1"] for item in per_class.values()) / len(classes),
        "weighted_f1": weighted_f1,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "labels": [str(label) for label in classes],
    }


def binary_classification_metrics(
    actual: Sequence[bool],
    predicted: Sequence[bool],
) -> dict[str, object]:
    result = classification_metrics(actual, predicted, labels=[True, False])
    positive = result["per_class"]["True"]
    return {
        **result,
        "true_positive": positive["true_positive"],
        "false_positive": positive["false_positive"],
        "true_negative": result["per_class"]["False"]["true_positive"],
        "false_negative": positive["false_negative"],
        "precision": positive["precision"],
        "recall": positive["recall"],
        "f1": positive["f1"],
    }
