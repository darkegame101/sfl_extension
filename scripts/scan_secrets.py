"""
Secret Scanner Utility for sfl_extension.
Scans repository source files and configuration to ensure no credentials
or API secrets are committed, complying with Rule F (Security & Credential Hygiene).
"""

import os
import re
import sys

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SUSPICIOUS_PATTERNS = [
    (re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"), "OpenAI / Claude / Beeknoee API key pattern"),
    (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]{25,}", re.IGNORECASE), "Bearer authorization token"),
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "GitHub Personal Access Token"),
]

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "venv",
    ".venv",
}

IGNORED_FILES = {
    ".env",
    ".env.local",
    ".env.production",
}


def scan_file(filepath: str) -> list:
    findings = []
    # Skip binary or very large files
    if os.path.getsize(filepath) > 2 * 1024 * 1024:
        return findings

    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                # Allow comments or documentation explaining patterns
                if "placeholder" in line.lower() or "example" in line.lower() or "re.compile" in line:
                    continue
                for pattern, desc in SUSPICIOUS_PATTERNS:
                    if pattern.search(line):
                        findings.append((filepath, line_no, desc))
    except Exception as e:
        # Cannot read as text
        pass

    return findings


def scan_repository(root_dir: str) -> int:
    print(f"[SecretScanner] Scanning repository at: {root_dir}")
    total_findings = []

    for root, dirs, files in os.walk(root_dir):
        # Prune ignored directories
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            if file in IGNORED_FILES:
                continue
            # Don't scan this scanner script itself
            if file == "scan_secrets.py":
                continue

            full_path = os.path.join(root, file)
            findings = scan_file(full_path)
            total_findings.extend(findings)

    if total_findings:
        print(f"\n[!] VIOLATION: Found {len(total_findings)} potential secret(s) in repository:")
        for path, line_no, desc in total_findings:
            rel_path = os.path.relpath(path, root_dir)
            print(f"  - {rel_path}:{line_no} -> {desc}")
        print("\nRule F Violation: Scrub credentials immediately before committing!")
        return 1
    else:
        print("[SecretScanner] OK: No committed secrets detected in working tree.")
        return 0


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exit_code = scan_repository(repo_root)
    sys.exit(exit_code)
