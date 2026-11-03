"""Phase 2 — Secure code execution engine (Docker-isolated, fail-closed).

SECURITY MODEL
--------------
Student code is NEVER executed in the FastAPI process. Every compile and run happens inside a throwaway
Docker container created from SANDBOX_IMAGE with, per Phase 2 Step 5:
  - network disabled               (--network none)
  - CPU limit                      (--cpus)
  - memory limit + swap pinned      (--memory, --memory-swap equal => no swap)
  - process/thread limit            (--pids-limit)
  - read-only root filesystem       (--read-only) with a small writable tmpfs for the workspace
  - non-root user                   (--user, image also drops privileges)
  - no added capabilities           (--cap-drop ALL, --security-opt no-new-privileges)
  - wall-clock timeout              (enforced by the host via subprocess timeout; TLE kills the container)
  - temporary isolated workspace    (a host temp dir bind-mounted; removed after each submission)
  - automatic cleanup               (--rm + guaranteed `docker rm -f` + temp dir removal in finally)

FAIL-CLOSED
-----------
If the Docker daemon is unavailable, `preflight()` returns a reason and every execution path raises
`SandboxUnavailableError`. There is NO insecure fallback: code is never run outside the sandbox.

This module is deterministic plumbing. No model, no AWS, no network from the sandbox.
"""
from __future__ import annotations

import dataclasses
import pathlib
import shutil
import subprocess
import tempfile
import uuid

from .coding_languages import SANDBOX_IMAGE, config

# Host-side safety margins added on top of the per-test wall-clock limit so a hung container is always
# reaped even if the in-container process ignores signals.
_HOST_TIMEOUT_MARGIN_S = 5.0
_CPU_LIMIT = "1.0"       # one core
_PIDS_LIMIT = "128"      # cap threads/processes (fork-bomb protection)
_WORKSPACE = "/workspace"
_CONTAINER_USER = "1000:1000"


class SandboxUnavailableError(RuntimeError):
    """Raised when the Docker sandbox cannot run (daemon down, image missing, docker CLI absent).

    Carries a user-facing message. The API turns this into a clear 503 — the feature degrades honestly
    rather than running student code in an insecure way.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.user_message = message


@dataclasses.dataclass
class ExecResult:
    """Outcome of one in-sandbox command (compile OR a single test run)."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    oom_killed: bool
    max_memory_kb: int | None = None


def _docker() -> str:
    exe = shutil.which("docker")
    if not exe:
        raise SandboxUnavailableError(
            "Docker CLI not found. The Coding Arena requires a running Docker daemon for isolated "
            "execution. Install Docker and build the sandbox image."
        )
    return exe


def preflight(timeout_s: float = 8.0) -> tuple[bool, str]:
    """Check that the sandbox is usable WITHOUT running student code.

    Returns (ok, reason). ok=True means the daemon responds and SANDBOX_IMAGE exists. Never raises.
    """
    exe = shutil.which("docker")
    if not exe:
        return False, "Docker CLI not found on PATH."
    try:
        info = subprocess.run([exe, "info", "--format", "{{.ServerVersion}}"],
                              capture_output=True, text=True, timeout=timeout_s)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"Docker daemon did not respond ({e.__class__.__name__})."
    if info.returncode != 0:
        return False, "Docker daemon is not running or not reachable."
    try:
        img = subprocess.run([exe, "image", "inspect", SANDBOX_IMAGE],
                             capture_output=True, text=True, timeout=timeout_s)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"Could not inspect the sandbox image ({e.__class__.__name__})."
    if img.returncode != 0:
        return False, (f"Sandbox image {SANDBOX_IMAGE!r} is not built. Build it with "
                       "`docker build -t careerlift-coding-sandbox:latest -f docker/coding-sandbox.Dockerfile docker`.")
    return True, "ok"


def ensure_available() -> None:
    ok, reason = preflight()
    if not ok:
        raise SandboxUnavailableError(
            "The secure code sandbox is unavailable, so code cannot be executed. " + reason
        )


_COMPILE_MARKER = "___CL_COMPILE_FAILED___"


def _shlex_join(argv: list[str]) -> str:
    import shlex
    return " ".join(shlex.quote(a) for a in argv)


def _run_in_container(workspace: pathlib.Path, shell_cmd: str, *, stdin: str,
                      time_ms: int, memory_mb: int) -> ExecResult:
    """Run `shell_cmd` (a /bin/sh -c script) inside a locked-down container. The read-only source dir is
    mounted at /src and copied into a writable tmpfs workspace first. The host enforces a hard wall-clock
    timeout so a hung container is always reaped."""
    exe = _docker()
    name = f"cl-cx-{uuid.uuid4().hex[:12]}"
    wall_s = max(0.1, time_ms / 1000.0)
    host_timeout = wall_s + _HOST_TIMEOUT_MARGIN_S

    full_script = "cp -r /src/. " + _WORKSPACE + "/ && " + shell_cmd

    docker_argv = [
        exe, "run", "--rm", "-i", "--name", name,  # -i: forward stdin (test input) to the program
        "--network", "none",                     # no network at all
        "--cpus", _CPU_LIMIT,
        "--memory", f"{memory_mb}m",
        "--memory-swap", f"{memory_mb}m",        # == memory => swap disabled
        "--pids-limit", _PIDS_LIMIT,             # fork-bomb / thread-bomb protection
        "--read-only",                           # root fs read-only
        "--tmpfs", f"{_WORKSPACE}:rw,exec,size={memory_mb}m,uid=1000,gid=1000",
        "--tmpfs", "/tmp:rw,exec,size=64m,uid=1000,gid=1000",
        "--user", _CONTAINER_USER,               # non-root
        "--cap-drop", "ALL",                     # drop all Linux capabilities
        "--security-opt", "no-new-privileges",   # cannot gain privileges via setuid
        "--workdir", _WORKSPACE,
        "-v", f"{workspace.as_posix()}:/src:ro",  # source mounted READ-ONLY
        SANDBOX_IMAGE,
        "/bin/sh", "-c", full_script,
    ]

    timed_out = False
    try:
        proc = subprocess.run(docker_argv, input=stdin, capture_output=True, text=True,
                              timeout=host_timeout)
        exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        timed_out = True
        exit_code = 124
        stdout = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr = e.stderr.decode() if isinstance(e.stderr, bytes) else (e.stderr or "")
    finally:
        # Guaranteed cleanup even if --rm didn't fire (e.g. on timeout kill).
        subprocess.run([exe, "rm", "-f", name], capture_output=True, text=True)

    # Docker reports OOM kills with exit code 137 (128 + SIGKILL).
    oom = (exit_code == 137) and not timed_out
    return ExecResult(exit_code=exit_code, stdout=stdout, stderr=stderr, duration_ms=0,
                      timed_out=timed_out, oom_killed=oom)


@dataclasses.dataclass
class CompileOutcome:
    ok: bool
    stderr: str
    duration_ms: int


def compile_source(language: str, source: str, *, memory_mb: int, time_ms: int) -> CompileOutcome | None:
    """Validate that the source COMPILES inside the sandbox. Returns None for interpreted languages (no
    compile step), a CompileOutcome otherwise. Used as an upfront gate so a build error short-circuits to
    a COMPILATION ERROR verdict without running any tests.

    Raises SandboxUnavailableError if the sandbox is not usable.
    """
    import time
    ensure_available()
    cfg = config(language)
    if not cfg["compile"]:
        return None
    with _workspace_with_source(language, source) as ws:
        t0 = time.perf_counter()
        res = _run_in_container(ws, _shlex_join(cfg["compile"]), stdin="",
                                time_ms=max(time_ms, 10000), memory_mb=max(memory_mb, 512))
        dur = int((time.perf_counter() - t0) * 1000)
    return CompileOutcome(ok=(res.exit_code == 0 and not res.timed_out), stderr=res.stderr, duration_ms=dur)


def run_once(language: str, source: str, *, stdin: str, time_ms: int, memory_mb: int,
             precompiled_ws: pathlib.Path | None = None) -> ExecResult:
    """Run one test case. Compiled languages are compiled AND run inside the SAME container so the build
    artifact persists (the workspace tmpfs is per-container). If compilation fails here it is surfaced as
    a non-zero exit with the compiler stderr (the evaluator already gated compilation upfront).

    Raises SandboxUnavailableError if the sandbox is not usable.
    """
    import time
    ensure_available()
    cfg = config(language)
    if cfg["compile"]:
        # compile && run, in one container. A compile failure prints a marker so we never mistake it for
        # a program crash on valid code.
        shell_cmd = (f"{_shlex_join(cfg['compile'])} || {{ echo {_COMPILE_MARKER} 1>&2; exit 97; }}; "
                     f"exec {_shlex_join(cfg['run'])}")
    else:
        shell_cmd = "exec " + _shlex_join(cfg["run"])
    with _workspace_with_source(language, source) as ws:
        t0 = time.perf_counter()
        res = _run_in_container(ws, shell_cmd, stdin=stdin, time_ms=time_ms, memory_mb=memory_mb)
        res.duration_ms = int((time.perf_counter() - t0) * 1000)
        return res


class _workspace_with_source:
    """Context manager: a fresh host temp dir containing the student's source file. Removed on exit.

    The directory is bind-mounted read-only into the container; the container copies it into a writable
    tmpfs, so build artifacts never touch the host and the host dir is cleaned up here regardless.
    """

    def __init__(self, language: str, source: str):
        self.language = language
        self.source = source
        self.path: pathlib.Path | None = None

    def __enter__(self) -> pathlib.Path:
        cfg = config(self.language)
        self.path = pathlib.Path(tempfile.mkdtemp(prefix="cl-sub-"))
        (self.path / cfg["source_name"]).write_text(self.source, encoding="utf-8")
        return self.path

    def __exit__(self, *exc) -> None:
        if self.path:
            shutil.rmtree(self.path, ignore_errors=True)
        return None
