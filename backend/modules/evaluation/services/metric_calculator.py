import re


class MetricCalculator:
    def calculate_retrieval_metrics(
        self, expected_ids: list[str], retrieved_ids: list[str]
    ) -> tuple[float, float, float]:
        """
        Calculates Precision, Recall, and F1 score for document retrieval.
        """
        if not expected_ids and not retrieved_ids:
            return 1.0, 1.0, 1.0
        if not expected_ids or not retrieved_ids:
            return 0.0, 0.0, 0.0

        expected_set = set(expected_ids)
        retrieved_set = set(retrieved_ids)

        true_positives = len(expected_set.intersection(retrieved_set))

        precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
        recall = true_positives / len(expected_set) if expected_set else 0.0

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * (precision * recall) / (precision + recall)

        return precision, recall, f1

    def calculate_answer_similarity(
        self, expected_answer: str, actual_answer: str
    ) -> float:
        """
        Simple token overlap for exact answer match estimation.
        """
        words1 = set(re.findall(r"\w+", expected_answer.lower()))
        words2 = set(re.findall(r"\w+", actual_answer.lower()))
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / max(len(words1), len(words2))
