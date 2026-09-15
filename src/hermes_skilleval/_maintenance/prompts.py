"""Common request presentation for future maintenance replays."""


def maintenance_prompt(request, profile):
    if profile.file_policy is not None:
        from hermes_skilleval.file_policy import disclosure
        from dataclasses import replace

        common = maintenance_prompt(request, replace(profile, file_policy=None))
        return (
            common.split("\nThe controller only accepts", 1)[0]
            + "\n"
            + disclosure(profile.file_policy)
        )
    roots = ", ".join(profile.writable_roots)
    return (
        request
        + "\n\nImplement this request in the current repository. All source and public project documentation are from the provided base. Python dependencies are preinstalled; run Python from this directory. Network is disabled. Do not install globally, publish or use external resources. Skills are optional local workflow guidance; read relevant skills as needed. Leave your actual code changes in the workspace. Verify behavior using local tests. No external messages or subagents. No hidden tests are available."
        + "\nThe controller only accepts changed files under these configured roots: "
        + roots
        + ". This restriction also applies to added test data; use an allowed test directory for fixtures and remove temporary debugging artifacts."
    )
