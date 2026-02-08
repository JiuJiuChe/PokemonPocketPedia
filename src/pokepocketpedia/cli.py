"""Project CLI entry points used by local runs and GitHub Actions."""


def _todo(task_name: str) -> int:
    print(f"[TODO] {task_name} is scaffolded but not implemented yet.")
    return 0


def ingest() -> int:
    return _todo("ingest")


def normalize() -> int:
    return _todo("normalize")


def analyze() -> int:
    return _todo("analyze")


def recommend() -> int:
    return _todo("recommend")


def build_site() -> int:
    return _todo("build_site")


def run_daily() -> int:
    # CI placeholder for the end-to-end daily pipeline command.
    return _todo("run_daily")
