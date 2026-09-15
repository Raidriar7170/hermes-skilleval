"""Request-independent fixed K=2 workflow selection. No heavy dependencies."""


def fixed_ids(repository, configuration, registry):
    ids = configuration["repositories"][repository]
    if len(ids) != 2 or len(set(ids)) != 2:
        raise ValueError("fixed selection requires two distinct skills")
    available = {skill["id"] for skill in registry["skills"]}
    if not set(ids) <= available:
        raise ValueError("fixed skill missing from registry")
    return sorted(ids)
