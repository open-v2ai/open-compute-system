#!/usr/bin/env python3
"""Fail CI when release hygiene or local Markdown links regress."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "CHANGELOG.md",
    "Makefile",
    ".editorconfig",
    ".gitattributes",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    ".github/dependabot.yml",
    "api/uv.lock",
    "agent/uv.lock",
    "web/pnpm-lock.yaml",
}

FORBIDDEN_PARTS = {
    ".idea",
    ".next",
    ".playwright-cli",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "node_modules",
    "playwright-report",
    "test-results",
}
FORBIDDEN_SUFFIXES = {
    ".crt",
    ".db",
    ".key",
    ".pem",
    ".sqlite",
    ".sqlite3",
}
ALLOWED_ENV_FILES = {
    "agent/.env.example",
    "api/.env.example",
    "deploy/.env.example",
    "web/.env.example",
}
TEXT_SUFFIXES = {
    "",
    ".css",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
SECRET_PATTERNS = {
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b"),
}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def git_tracked_files() -> list[Path] | None:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return [ROOT / item.decode() for item in result.stdout.split(b"\0") if item]


def fallback_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in FORBIDDEN_PARTS or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            continue
        files.append(path)
    return files


def check_required(errors: list[str]) -> None:
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")


def check_tracked_hygiene(files: list[Path], errors: list[str]) -> None:
    for path in files:
        relative = path.relative_to(ROOT)
        relative_text = relative.as_posix()
        if any(part in FORBIDDEN_PARTS or part.endswith(".egg-info") for part in relative.parts):
            errors.append(f"generated or local path is tracked: {relative_text}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"sensitive or local file type is tracked: {relative_text}")
        if path.name.startswith(".env") and relative_text not in ALLOWED_ENV_FILES:
            errors.append(f"environment file is tracked: {relative_text}")


def check_secrets(files: list[Path], errors: list[str]) -> None:
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        if relative == "scripts/check_open_source.py":
            continue
        if (path.suffix.lower() not in TEXT_SUFFIXES or not path.exists()
                or path.stat().st_size > 2_000_000):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                errors.append(f"possible {label} in {relative}")


def check_markdown_links(files: list[Path], errors: list[str]) -> None:
    for path in files:
        if path.suffix.lower() != ".md" or not path.exists():
            continue
        content = path.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(content):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                relative = path.relative_to(ROOT).as_posix()
                errors.append(f"broken local link in {relative}: {raw_target}")


def main() -> int:
    errors: list[str] = []
    tracked = git_tracked_files()
    if tracked is None:
        print("warning: no Git metadata; checking visible source files instead of the tracked set")
        files = fallback_files()
    else:
        files = tracked
        check_tracked_hygiene(files, errors)

    check_required(errors)
    check_secrets(files, errors)
    check_markdown_links(files, errors)

    if errors:
        print("open-source readiness check failed:")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1

    print(f"open-source readiness check passed ({len(files)} files inspected)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
