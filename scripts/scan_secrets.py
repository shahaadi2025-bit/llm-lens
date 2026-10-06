"""Fail if tracked files contain what look like secrets. Run: python scripts/scan_secrets.py  (used in CI).
Placeholders in .env.example and docs (change-me, user:pass, YOUR_...) are allowed. This is a safety net, not a guarantee."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    "Neon password": re.compile(r"npg_[A-Za-z0-9]{10,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "API key (sk-)": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "Slack token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "JWT": re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),
    "database URL with password": re.compile(r"postgres(?:ql)?(?:\+\w+)?://[^:/\s@]+:([^@\s]+)@"),
}
PLACEHOLDER = re.compile(r"change-me|changeme|password|pass\b|YOUR|example|\$\{|\{\w+\}|xxxx|<[^>]+>|\*{3,}|\[REDACTED\]|secret123", re.I)
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".lock", ".zip"}
SKIP_FILES = {"package-lock.json", "scan_secrets.py", "test_scan_secrets.py", "test_security.py", "test_public_mode.py"}


def tracked_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout.decode()
    return [ROOT / f for f in out.split("\0") if f]


def scan_text(name: str, text: str) -> list[str]:
    hits = []
    for label, rx in PATTERNS.items():
        for m in rx.finditer(text):
            if label == "database URL with password" and PLACEHOLDER.search(m.group(1)):
                continue
            line = text.count("\n", 0, m.start()) + 1
            hits.append(f"{name}:{line}: possible {label}")
    return hits


def main() -> int:
    findings: list[str] = []
    for f in tracked_files():
        rel = f.relative_to(ROOT).as_posix()
        if f.name == ".env" or (f.name.startswith(".env.") and f.name != ".env.example") or f.name in {"token", "credentials"}:
            findings.append(f"{rel}: environment/credential file must not be tracked")
            continue
        if f.suffix in SKIP_SUFFIXES or f.name in SKIP_FILES or not f.is_file():
            continue
        try:
            findings += scan_text(rel, f.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    if findings:
        print("\n".join(findings))
        print(f"\n{len(findings)} possible secret(s) found.")
        return 1
    print("no secrets found in tracked files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
