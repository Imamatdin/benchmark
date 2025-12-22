def score_rule_example(reference: str, candidate: str) -> float:
    """Very simple scoring rule placeholder."""
    return 1.0 if reference.strip() == candidate.strip() else 0.0
