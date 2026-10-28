THEME_ALIASES = {
    "polity": "Polity",
    "polity governance": "Polity",
    "constitution": "Polity",
    "governance": "Governance",
    "economy": "Economy",
    "economics": "Economy",
    "agriculture": "Agriculture",
    "environment": "Environment",
    "ecology": "Environment",
    "climate": "Environment",
    "science": "Science & Tech",
    "technology": "Science & Tech",
    "s&t": "Science & Tech",
    "history": "History & Culture",
    "culture": "History & Culture",
    "art": "History & Culture",
    "society": "Society",
    "social": "Society",
    "women": "Gender",
    "gender": "Gender",
    "caste": "Caste",
    "urbanization": "Urbanization",
    "migration": "Migration",
    "poverty": "Economy",
    "ir": "IR",
    "international": "IR",
    "security": "Security",
    "ethics": "Ethics",
    "federalism": "Polity",
    "education": "Education",
}


def map_theme(raw):
    if not raw:
        return None
    key = " ".join(str(raw).lower().split())
    if key in THEME_ALIASES:
        return THEME_ALIASES[key]
    for k, v in THEME_ALIASES.items():
        if k in key:
            return v
    return None
