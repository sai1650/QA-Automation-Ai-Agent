import math
from collections.abc import Sequence


def retrieval_metrics(
    relevant_documents: set[str],
    retrieved_documents: Sequence[str],
    *,
    k: int,
    relevance_grades: dict[str, int] | None = None,
) -> dict[str, float | int]:
    if k < 1:
        raise ValueError("K must be at least one.")
    if len(retrieved_documents) != len(set(retrieved_documents)):
        raise ValueError("Retrieved document identifiers must be unique.")
    ranked = list(retrieved_documents[:k])
    relevant_retrieved = sum(document in relevant_documents for document in ranked)
    reciprocal_rank = next(
        (1.0 / rank for rank, document in enumerate(ranked, start=1)
         if document in relevant_documents),
        0.0,
    )
    dcg = sum(
        (2 ** max(0, (relevance_grades or {}).get(document, int(document in relevant_documents))) - 1)
        / math.log2(rank + 1)
        for rank, document in enumerate(ranked, start=1)
    )
    ideal_grades = sorted(
        (
            (relevance_grades or {}).get(document, 1)
            for document in relevant_documents
        ),
        reverse=True,
    )[:k]
    idcg = sum((2**grade - 1) / math.log2(rank + 1)
               for rank, grade in enumerate(ideal_grades, start=1))
    return {
        "precision_at_k": relevant_retrieved / k,
        "recall_at_k": relevant_retrieved / len(relevant_documents) if relevant_documents else 0.0,
        "hit_rate_at_k": float(relevant_retrieved > 0),
        "mean_reciprocal_rank": reciprocal_rank,
        "ndcg_at_k": dcg / idcg if idcg else 0.0,
        "relevant_document_count": len(relevant_documents),
        "irrelevant_document_count": len(ranked) - relevant_retrieved,
        "retrieved_document_count": len(ranked),
        "k": k,
    }
