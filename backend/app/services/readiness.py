def calculate_readiness_score(
    aptitude: float,
    technical: float,
    communication: float,
    problem_solving: float
) -> float:

    score = (
        aptitude +
        technical +
        communication +
        problem_solving
    ) / 4

    return round(score, 2)