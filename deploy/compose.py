#!/usr/bin/env python3
"""Select bundled (default) or external dependencies without changing app code."""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", choices=("bundled", "external"), default="bundled")
    parser.add_argument("--ingress", choices=("container", "host"), default="container")
    parser.add_argument("--preview", action="store_true", help="SSH-only HTTP demo overlay")
    parser.add_argument(
        "--demo-lite", action="store_true", help="Private Mock demo without workers",
    )
    parser.add_argument("--public-demo", action="store_true", help="HTTPS public Mock demo")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--project-name", default="open-compute-system")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Docker Compose command")
    args = parser.parse_args()
    if args.public_demo:
        args.demo_lite = True
    if args.demo_lite:
        args.preview = True
    if not args.command:
        parser.error("A Docker Compose command is required (e.g. config, build or up -d)")
    if not args.env_file.is_file():
        parser.error("Environment file does not exist; start with deploy/.env.example")
    command = ["docker", "compose", "--project-name", args.project_name,
               "--env-file", str(args.env_file.resolve()), "-f", str(ROOT / "compose.yaml")]
    if args.dependencies == "external":
        command.extend(["-f", str(ROOT / "compose.external.yaml")])
    if args.preview or args.ingress == "host":
        command.extend(["-f", str(ROOT / "compose.host-ingress.yaml")])
    if args.preview:
        command.extend(["-f", str(ROOT / "compose.preview.yaml")])
    if args.demo_lite:
        command.extend(["-f", str(ROOT / "compose.demo-lite.yaml")])
    if args.public_demo:
        command.extend(["-f", str(ROOT / "compose.public-demo.yaml")])
    environment = os.environ.copy()
    # Environment validation on disabled services occurs before profile filtering.
    # These placeholders cannot be used to start a valid bundled production stack.
    if args.dependencies == "external":
        environment.setdefault("POSTGRES_PASSWORD", "unused-external-dependencies")
    if args.preview:
        for key in ("PUBLIC_HOST", "ADMIN_HOST", "ADMIN_MFA_TOTP_SECRET"):
            environment.setdefault(key, "unused-preview")
    if args.preview or args.ingress == "host":
        environment.setdefault("TLS_CERT_PATH", "/dev/null")
        environment.setdefault("TLS_KEY_PATH", "/dev/null")
    if args.dependencies == "external":
        rendered = subprocess.run(
            [*command, "config", "--format", "json"], env=environment,
            capture_output=True, text=True, check=False,
        )
        if rendered.returncode:
            parser.error("External Compose configuration is invalid; check required settings")
        configured = json.loads(rendered.stdout)["services"]["api"]["environment"]
        for key in ("REDIS_KEY_PREFIX", "CELERY_QUEUE"):
            if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", configured.get(key) or ""):
                parser.error(f"External dependencies require a nonempty project-scoped {key}")
    result = subprocess.run([*command, *args.command], env=environment, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
