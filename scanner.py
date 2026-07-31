"""
Quick-Scan: a lightweight, rule-based pre-check on uploaded files.

NOTE: This is NOT a real AI/LLM call — you told me you don't have an AI API
key, so this is a honest, static pattern-scanner instead. It looks for
common red flags (destructive shell commands, obfuscated/encoded payloads,
crypto-miner keywords, suspicious network calls) and adds a summary to the
admin's approval message so small/obvious cases are easy to eyeball fast.

It NEVER blocks or auto-approves anything by itself — the admin always
makes the final call. Treat "✅ Looks OK" as "nothing obvious was found",
not as a guarantee the file is safe.
"""
import os
import re

RISKY_PATTERNS = [
    (r"rm\s+-rf\s+/", "🔥 Destructive shell command (rm -rf /)"),
    (r"os\.system\(|subprocess\.(Popen|call|run)\(.*shell\s*=\s*True", "⚠️ Shell command execution"),
    (r"eval\(|exec\(", "⚠️ Dynamic code execution (eval/exec)"),
    (r"base64\.b64decode", "⚠️ Base64-decoded payload (possible obfuscation)"),
    (r"socket\.socket\(.*SOCK_STREAM", "🌐 Raw socket usage"),
    (r"(xmrig|minerd|stratum\+tcp|cryptonight)", "⛏️ Possible crypto-miner keywords"),
    (r"requests\.get\(.*token|requests\.post\(.*password", "⚠️ Credential-looking network call"),
    (r"\.\/\.\.\/|\.\.\\\.\.\\", "⚠️ Path traversal pattern"),
    (r"child_process\.exec\(|child_process\.spawn\(", "⚠️ Node shell execution"),
]


def scan_file(filepath: str) -> str:
    """Returns a short human-readable summary string for the admin."""
    try:
        if os.path.isdir(filepath):
            return "📁 Website folder — static files only, no code executed by us."

        size_kb = os.path.getsize(filepath) / 1024
        with open(filepath, "r", errors="ignore") as f:
            content = f.read(200_000)  # cap read size

        hits = []
        for pattern, label in RISKY_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                hits.append(label)

        lines = content.count("\n") + 1
        header = f"📏 {lines} lines, {size_kb:.1f} KB"

        if hits:
            return f"🔎 *Quick-Scan:* {header}\n🚩 Flags found:\n" + "\n".join(f"  • {h}" for h in hits)
        return f"🔎 *Quick-Scan:* {header}\n✅ No obvious red flags (still review before approving)"
    except Exception as e:
        return f"🔎 *Quick-Scan:* could not analyze file ({e})"
