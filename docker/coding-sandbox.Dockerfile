# CareerLift AI — Phase 2 Coding Arena sandbox image.
#
# Carries the three supported toolchains (Python 3, g++ / C++17, JDK 17) and a NON-ROOT user. All the
# runtime isolation (no network, cpu/memory/pids limits, read-only rootfs, dropped capabilities,
# no-new-privileges, tmpfs workspace) is applied by `docker run` flags in agent/coding_exec.py — this
# image only has to provide the compilers and a low-privilege user.
#
# Build:
#   docker build -t careerlift-coding-sandbox:latest -f docker/coding-sandbox.Dockerfile docker
#
# The image is NEVER given credentials, source is injected per-run via a read-only bind mount, and the
# container is removed after every test run.

FROM eclipse-temurin:17-jdk-jammy

# Add Python 3 and the GNU C++ toolchain on top of the JDK base. Clean apt lists to keep the image lean.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 g++ \
    && rm -rf /var/lib/apt/lists/*

# A fixed non-root uid:gid (1000:1000) matching the --user flag the runner passes. The container runs
# with a read-only root filesystem; the writable workspace is a tmpfs mounted at /workspace at run time.
RUN groupadd -g 1000 sandbox \
    && useradd -m -u 1000 -g 1000 -s /usr/sbin/nologin sandbox

USER sandbox
WORKDIR /workspace

# No ENTRYPOINT: the runner passes an explicit `/bin/sh -c "..."` command per invocation.
