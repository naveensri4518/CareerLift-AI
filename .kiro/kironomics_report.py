#!/usr/bin/env python3
"""Kironomics session reporter - reads Kiro's state.vscdb and sends to the backend."""
import os, sys, ssl, json, sqlite3, urllib.request, urllib.error, time
from pathlib import Path

# Secret comes ONLY from the environment — never hardcoded. If it is unset, the reporter does nothing
# (no network call, no placeholder token). This keeps every key out of source and git history.
API_KEY = os.environ.get("KIRONOMICS_API_KEY")
API_BASE = "https://2q4zt5zl9e.execute-api.us-east-1.amazonaws.com/dev"

if not API_KEY:
    # No key configured -> skip silently. Nothing to report, nothing to leak.
    raise SystemExit(0)

# On Windows use %TEMP%; fallback to /tmp for Linux/macOS
_TEMP = os.environ.get("TEMP") or os.environ.get("TMPDIR") or "/tmp"

def read_int(filename, default=0):
    try:
        return int(Path(os.path.join(_TEMP, filename)).read_text().strip())
    except Exception:
        return default

tools   = read_int("kironomics_tools.txt")
prompts = read_int("kironomics_prompts.txt")
start   = read_int("kironomics_start.txt", int(time.time()))
elapsed = max(0, int(time.time()) - start)

# Read Kiro's state.vscdb (silent fail if missing or no usageState)
plan_data = {}
try:
    home = Path.home()
    if sys.platform == "darwin":
        db = home / "Library/Application Support/Kiro/User/globalStorage/state.vscdb"
    elif sys.platform.startswith("win"):
        db = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "Kiro/User/globalStorage/state.vscdb"
    else:
        db = home / ".config/Kiro/User/globalStorage/state.vscdb"
    if db.exists():
        conn = sqlite3.connect(f"file:{db}?mode=ro&immutable=1", uri=True)
        row = conn.execute(
            "SELECT value FROM ItemTable WHERE key=?",
            ("kiro.kiroAgent",),
        ).fetchone()
        conn.close()
        if row:
            state = json.loads(row[0])
            usage = state.get("kiro.resourceNotifications.usageState", {})
            breakdowns = usage.get("usageBreakdowns", [])
            if breakdowns:
                bd = breakdowns[0]
                plan_data = {
                    "currentUsage": bd.get("currentUsage"),
                    "usageLimit": bd.get("usageLimit"),
                    "percentageUsed": bd.get("percentageUsed"),
                    "resetDate": bd.get("resetDate"),
                }
except Exception:
    pass

payload = {
    "token": API_KEY,
    "tool_calls": tools,
    "prompts": prompts,
    "elapsed_seconds": elapsed,
    **plan_data,
}

def _ssl_context():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        try:
            return ssl.create_default_context()
        except Exception:
            return None

try:
    req = urllib.request.Request(
        f"{API_BASE}/kironomics/session",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5, context=_ssl_context()).read()
    except (ssl.SSLError, urllib.error.URLError) as e:
        if "certificate verify failed" in str(e).lower():
            urllib.request.urlopen(req, timeout=5, context=ssl._create_unverified_context()).read()
        else:
            raise
except Exception:
    pass

# Cleanup temp counters
for fname in ("kironomics_tools.txt", "kironomics_prompts.txt", "kironomics_start.txt"):
    try:
        os.remove(os.path.join(_TEMP, fname))
    except Exception:
        pass
