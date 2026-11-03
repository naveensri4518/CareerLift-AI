"""Phase 2 — Coding Arena language configuration.

Declares, per supported language, the in-container source filename, optional compile step, and run
command. These commands are executed ONLY inside the isolated Docker sandbox (see agent/coding_exec.py),
never in the backend process. The Docker image name is centralised here so the sandbox and the build
script agree.
"""
from __future__ import annotations

# Single image carrying python3, g++ and a JDK. Built from docker/coding-sandbox.Dockerfile.
SANDBOX_IMAGE = "careerlift-coding-sandbox:latest"

SUPPORTED = ("python", "cpp", "java")

# source_name : filename the student's code is written to inside the workspace.
# compile      : argv list run first (None if interpreted). A non-zero exit => COMPILATION ERROR.
# run          : argv list executed for each test case; stdin is the test input.
# All commands run with the workspace as CWD inside the container.
LANGUAGES: dict[str, dict] = {
    "python": {
        "label": "Python 3",
        "source_name": "main.py",
        "compile": None,
        "run": ["python3", "main.py"],
    },
    "cpp": {
        "label": "C++17",
        "source_name": "main.cpp",
        # -O2 for realistic performance; static where available keeps runtime deps minimal.
        "compile": ["g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"],
        "run": ["./main"],
    },
    "java": {
        "label": "Java 17",
        "source_name": "Main.java",
        "compile": ["javac", "Main.java"],
        # -XX:-UsePerfData avoids writing perfdata to a (read-only) home dir.
        "run": ["java", "-XX:-UsePerfData", "Main"],
    },
}


def is_supported(language: str) -> bool:
    return language in LANGUAGES


def config(language: str) -> dict:
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language {language!r}; supported: {', '.join(SUPPORTED)}")
    return LANGUAGES[language]


def public_languages() -> list[dict]:
    """Client-safe list for the language selector (no commands/infra leaked)."""
    return [{"id": lid, "label": cfg["label"]} for lid, cfg in LANGUAGES.items()]
