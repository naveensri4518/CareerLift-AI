"""Live verification of the Phase 2 Docker sandbox isolation mechanisms.

Run this ONLY when a Docker daemon is available and the sandbox image is built:
    bash scripts/build-sandbox.sh
    ~/.strands-ship/venv/bin/python scripts/verify_sandbox.py

It executes real code in the sandbox to PROVE each security control actually holds, rather than trusting
that the docker-run flags do what we think. Nothing here touches AWS. It exits non-zero if any isolation
check fails, so it can gate a claim of "sandbox verified".
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import coding_eval, coding_exec, coding_problems  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def record(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append((name, passed, detail))
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    ok, reason = coding_exec.preflight()
    if not ok:
        print(f"Sandbox not available: {reason}")
        print("Build it first:  bash scripts/build-sandbox.sh  (needs a running Docker daemon)")
        return 3

    # 1) Correct Python solution to P-SUM-TWO -> ACCEPTED on all tests.
    p = coding_problems.get_problem("P-SUM-TWO")
    acc = coding_eval.evaluate_submission(p, "python", "print(sum(map(int, input().split())))")
    record("python ACCEPTED", acc["verdict"] == "ACCEPTED", acc["verdict"])

    # 2) C++ correct solution compiles and passes.
    cpp = "#include <iostream>\nint main(){long long a,b;std::cin>>a>>b;std::cout<<a+b<<\"\\n\";}"
    acc_cpp = coding_eval.evaluate_submission(p, "cpp", cpp)
    record("cpp ACCEPTED", acc_cpp["verdict"] == "ACCEPTED", acc_cpp["verdict"])

    # 3) Java correct solution compiles and passes.
    java = ("import java.util.*;public class Main{public static void main(String[] a){"
            "Scanner s=new Scanner(System.in);System.out.println(s.nextLong()+s.nextLong());}}")
    acc_java = coding_eval.evaluate_submission(p, "java", java)
    record("java ACCEPTED", acc_java["verdict"] == "ACCEPTED", acc_java["verdict"])

    # 4) Wrong answer.
    wa = coding_eval.evaluate_submission(p, "python", "print(0)")
    record("WRONG ANSWER", wa["verdict"] == "WRONG ANSWER", wa["verdict"])

    # 5) Compilation error (C++).
    ce = coding_eval.evaluate_submission(p, "cpp", "int main(){")
    record("COMPILATION ERROR", ce["verdict"] == "COMPILATION ERROR", ce["verdict"])

    # 6) Infinite loop -> TIME LIMIT EXCEEDED (and the container is reaped by the host timeout).
    tle = coding_eval.evaluate_submission(p, "python", "while True:\n    pass")
    record("TIME LIMIT EXCEEDED on infinite loop", tle["verdict"] == "TIME LIMIT EXCEEDED", tle["verdict"])

    # 7) Runtime error (crash).
    re = coding_eval.evaluate_submission(p, "python", "import sys; sys.exit(3)")
    record("RUNTIME ERROR on crash", re["verdict"] == "RUNTIME ERROR", re["verdict"])

    # 8) NETWORK DISABLED: a program that tries to open a socket must fail (network none).
    net_code = (
        "import socket\n"
        "try:\n"
        "    socket.create_connection(('1.1.1.1', 80), timeout=2)\n"
        "    print('NET_OK')\n"
        "except Exception:\n"
        "    print('NET_BLOCKED')\n"
    )
    net = coding_exec.run_once("python", net_code, stdin="", time_ms=4000, memory_mb=256)
    record("network disabled", "NET_BLOCKED" in net.stdout and "NET_OK" not in net.stdout,
           net.stdout.strip() or net.stderr.strip()[:80])

    # 9) FILESYSTEM ISOLATION: root fs is read-only; writing outside the tmpfs workspace must fail.
    fs_code = (
        "try:\n"
        "    open('/etc/cl_probe', 'w').write('x')\n"
        "    print('WROTE_ROOT')\n"
        "except Exception:\n"
        "    print('ROOT_READONLY')\n"
    )
    fs = coding_exec.run_once("python", fs_code, stdin="", time_ms=4000, memory_mb=256)
    record("read-only root filesystem", "ROOT_READONLY" in fs.stdout and "WROTE_ROOT" not in fs.stdout,
           fs.stdout.strip() or fs.stderr.strip()[:80])

    # 10) NON-ROOT execution: the process must not be uid 0.
    whoami = coding_exec.run_once("python", "import os; print(os.getuid())", stdin="",
                                  time_ms=4000, memory_mb=256)
    record("non-root execution (uid != 0)", whoami.stdout.strip() not in ("", "0"),
           f"uid={whoami.stdout.strip()}")

    # 11) MEMORY LIMIT: allocating far beyond the limit must be killed (OOM -> RUNTIME ERROR), not succeed.
    mem_code = "x = bytearray(1024*1024*1024)  # 1 GiB, well above the 256 MB cap\nprint('ALLOC_OK')"
    mem = coding_exec.run_once("python", mem_code, stdin="", time_ms=4000, memory_mb=128)
    record("memory limit enforced", "ALLOC_OK" not in mem.stdout,
           f"exit={mem.exit_code} oom={mem.oom_killed}")

    passed = sum(1 for _, ok, _ in CHECKS if ok)
    print(f"\n{passed}/{len(CHECKS)} isolation checks passed.")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
