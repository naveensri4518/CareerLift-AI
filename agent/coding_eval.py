"""Phase 2 — Deterministic coding evaluation + verdict engine.

Given a problem (public + hidden tests) and a submission (language + source), compiles once and runs every
test case in the secure sandbox, then produces a deterministic verdict. Output comparison normalises
trailing whitespace per line and ignores trailing blank lines (common, fair conventions) — nothing else.

VERDICTS (first one that applies wins, in this order):
  COMPILATION ERROR    compile step failed
  TIME LIMIT EXCEEDED  any test exceeded the wall-clock limit
  RUNTIME ERROR        a program crashed / OOM / non-zero exit without producing the right answer
  WRONG ANSWER         ran cleanly but output did not match on some test
  ACCEPTED             every test (public AND hidden) matched

HIDDEN-TEST PROTECTION: per-hidden-test stdin/expected/actual are NEVER included in the returned payload.
Hidden tests contribute only to aggregate pass/fail counts and the verdict. Public tests may show a
diff to help the learner.

No model, no AWS. Raises SandboxUnavailableError (from coding_exec) if Docker is unavailable.
"""
from __future__ import annotations

from . import coding_exec, coding_languages, coding_problems

VERDICT_ACCEPTED = "ACCEPTED"
VERDICT_WRONG = "WRONG ANSWER"
VERDICT_COMPILE = "COMPILATION ERROR"
VERDICT_TLE = "TIME LIMIT EXCEEDED"
VERDICT_RUNTIME = "RUNTIME ERROR"


def _normalise(text: str) -> list[str]:
    """Normalise program output for comparison: strip trailing whitespace on each line, drop trailing
    blank lines. Leading/interior content is preserved."""
    lines = [ln.rstrip() for ln in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _matches(expected: str, actual: str) -> bool:
    return _normalise(expected) == _normalise(actual)


def _truncate(s: str, limit: int = 2000) -> str:
    s = s or ""
    return s if len(s) <= limit else s[:limit] + "\n…(truncated)"


def evaluate_submission(problem: dict, language: str, source: str) -> dict:
    """Compile + run all tests, returning a verdict payload safe to persist and to show the client.

    The payload intentionally excludes hidden-test I/O. Raises ValueError for an unsupported language;
    raises coding_exec.SandboxUnavailableError if Docker is unavailable (the caller maps that to 503).
    """
    if not coding_languages.is_supported(language):
        raise ValueError(f"unsupported language {language!r}")

    limits = coding_problems.effective_limits(problem)
    time_ms, memory_mb = limits["time_ms"], limits["memory_mb"]

    # 1) Compile once (interpreted languages return None).
    comp = coding_exec.compile_source(language, source, memory_mb=memory_mb, time_ms=time_ms)
    if comp is not None and not comp.ok:
        return {
            "verdict": VERDICT_COMPILE,
            "language": language,
            "compiled": False,
            "compile_error": _truncate(comp.stderr),
            "public_results": [],
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_total": len(problem.get("public_tests", [])) + len(problem.get("hidden_tests", [])),
            "max_time_ms": 0,
            "max_memory_mb": None,
            "limits": limits,
        }

    public_tests = problem.get("public_tests", [])
    hidden_tests = problem.get("hidden_tests", [])

    public_results: list[dict] = []
    passed = failed = 0
    max_time = 0
    worst_verdict = None  # track the most severe non-accept verdict for the overall result

    def _severity(v: str) -> int:
        return {VERDICT_TLE: 3, VERDICT_RUNTIME: 2, VERDICT_WRONG: 1}.get(v, 0)

    def _run_bucket(tests: list[dict], *, public: bool):
        nonlocal passed, failed, max_time, worst_verdict
        for idx, t in enumerate(tests):
            res = coding_exec.run_once(language, source, stdin=t["stdin"], time_ms=time_ms,
                                       memory_mb=memory_mb)
            max_time = max(max_time, res.duration_ms)
            case_verdict = _classify(res, t["stdout"])
            if case_verdict == VERDICT_ACCEPTED:
                passed += 1
            else:
                failed += 1
                if worst_verdict is None or _severity(case_verdict) > _severity(worst_verdict):
                    worst_verdict = case_verdict
            if public:
                # Public tests may show the diff; hidden tests NEVER do.
                public_results.append({
                    "index": idx + 1,
                    "verdict": case_verdict,
                    "passed": case_verdict == VERDICT_ACCEPTED,
                    "input": _truncate(t["stdin"], 500),
                    "expected": _truncate(t["stdout"], 500),
                    "actual": _truncate(res.stdout, 500),
                    "stderr": _truncate(res.stderr, 500) if case_verdict == VERDICT_RUNTIME else "",
                    "time_ms": res.duration_ms,
                })

    _run_bucket(public_tests, public=True)
    _run_bucket(hidden_tests, public=False)

    total = len(public_tests) + len(hidden_tests)
    verdict = VERDICT_ACCEPTED if failed == 0 else (worst_verdict or VERDICT_WRONG)

    return {
        "verdict": verdict,
        "language": language,
        "compiled": True,
        "compile_error": "",
        "public_results": public_results,
        "tests_passed": passed,
        "tests_failed": failed,
        "tests_total": total,
        "hidden_tests_total": len(hidden_tests),
        "max_time_ms": max_time,
        "max_memory_mb": memory_mb if verdict != VERDICT_ACCEPTED and worst_verdict == VERDICT_RUNTIME else None,
        "limits": limits,
    }


def _classify(res: "coding_exec.ExecResult", expected_stdout: str) -> str:
    """Per-test verdict from one sandbox run."""
    if res.timed_out:
        return VERDICT_TLE
    if res.oom_killed:
        return VERDICT_RUNTIME
    if res.exit_code != 0:
        return VERDICT_RUNTIME
    return VERDICT_ACCEPTED if _matches(expected_stdout, res.stdout) else VERDICT_WRONG


def run_only(problem: dict, language: str, source: str) -> dict:
    """'Run' action: execute ONLY the public (sample) tests — never hidden tests. Used by the Run button
    so students can iterate without consuming a graded submission. Same hidden-test protection applies.
    """
    if not coding_languages.is_supported(language):
        raise ValueError(f"unsupported language {language!r}")
    sample_problem = dict(problem)
    sample_problem["hidden_tests"] = []   # hard guarantee: run never touches hidden tests
    out = evaluate_submission(sample_problem, language, source)
    out["mode"] = "run"
    return out
