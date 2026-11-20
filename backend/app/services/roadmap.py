def generate_recommendation(skill, current, required):

    if current == 0:
        return f"Start learning {skill} fundamentals and practice basic concepts."

    return (
        f"Improve your {skill} proficiency through hands-on practice "
        f"and projects. Target level: {required}/5."
    )


def get_priority(current, required):
    if current == 0:
        return "High"

    return "Medium"