from collections.abc import Iterable


def term_recall(text: str, required_terms: Iterable[str]) -> float:
    terms = [term.casefold().strip() for term in required_terms if term.strip()]
    if not terms:
        return 0.0
    content = text.casefold()
    return sum(term in content for term in terms) / len(terms)


def evidence_support_metrics(
    *,
    cited_evidence: set[str],
    available_evidence: set[str],
    expected_evidence: set[str],
) -> dict[str, float | int]:
    supported = cited_evidence & available_evidence
    return {
        "evidence_support_rate": (
            len(supported) / len(cited_evidence) if cited_evidence else 1.0
        ),
        "expected_evidence_coverage": (
            len(cited_evidence & expected_evidence) / len(expected_evidence)
            if expected_evidence
            else 1.0
        ),
        "unsupported_claim_count": len(cited_evidence - available_evidence),
        "cited_evidence_count": len(cited_evidence),
    }
