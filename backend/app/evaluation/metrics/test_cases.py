def calculate_test_generation_metrics(
    *,
    expected_requirements: set[str],
    covered_requirements: set[str],
    expected_scenarios: set[str],
    generated_scenarios: set[str],
    generated_count: int,
    relevant_generated_count: int,
    duplicate_count: int,
    unsupported_count: int,
) -> dict[str, float | int]:
    if min(
        generated_count,
        relevant_generated_count,
        duplicate_count,
        unsupported_count,
    ) < 0:
        raise ValueError("Counts cannot be negative.")
    if relevant_generated_count > generated_count:
        raise ValueError("Relevant count cannot exceed generated count.")
    if duplicate_count > generated_count or unsupported_count > generated_count:
        raise ValueError("Duplicate and unsupported counts cannot exceed generated count.")
    return {
        "requirement_coverage": (
            len(expected_requirements & covered_requirements) / len(expected_requirements)
            if expected_requirements
            else 0.0
        ),
        "test_case_precision": (
            relevant_generated_count / generated_count if generated_count else 0.0
        ),
        "test_case_recall": (
            len(expected_scenarios & generated_scenarios) / len(expected_scenarios)
            if expected_scenarios
            else 0.0
        ),
        "duplicate_rate": duplicate_count / generated_count if generated_count else 0.0,
        "unsupported_test_rate": (
            unsupported_count / generated_count if generated_count else 0.0
        ),
        "expected_scenario_count": len(expected_scenarios),
        "matched_scenario_count": len(expected_scenarios & generated_scenarios),
        "generated_count": generated_count,
    }
