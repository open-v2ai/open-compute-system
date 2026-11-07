#!/usr/bin/env python3
"""Validate bundled/external Compose topology without starting containers."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(env_file: Path, *options: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(ROOT / "deploy/compose.py"), "--env-file", str(env_file),
         *options, "config", "--format", "json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        raise RuntimeError("Compose validation failed; no environment values are printed")
    return json.loads(result.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="ocs-compose-check-") as directory:
        env_file = Path(directory) / ".env"
        env_file.write_text((ROOT / "deploy/.env.example").read_text() + "\n" +
                            "DATABASE_URL=postgresql+asyncpg://test:test@db:5432/test\n"
                            "REDIS_URL=redis://test:test@redis:6379/0\n"
                            "DEMO_ORIGIN=https://demo.example.com\n"
                            "DEMO_HOST=demo.example.com\n")
        bundled = render(env_file)
        assert {"postgres", "redis", "nginx"} <= bundled["services"].keys()
        assert "postgres" in bundled["services"]["migrate"]["depends_on"]
        assert "redis" in bundled["services"]["api"]["depends_on"]
        lite = render(env_file, "--dependencies", "external", "--demo-lite")
        assert set(lite["services"]) == {"api", "web", "migrate"}
        assert lite["services"]["api"]["environment"]["APP_ENV"] == "development"
        assert lite["services"]["api"]["environment"]["DEMO_AUTO_DISPATCH"] == "true"
        assert lite["services"]["api"]["environment"]["CSRF_COOKIE"] == "ocs_preview_csrf"
        assert lite["services"]["web"]["ports"][0]["host_ip"] == "127.0.0.1"
        assert lite["services"]["api"]["mem_limit"] == "201326592"
        assert lite["services"]["web"]["mem_limit"] == "201326592"
        public = render(env_file, "--dependencies", "external", "--public-demo")
        assert set(public["services"]) == {"api", "web", "migrate"}
        public_env = public["services"]["api"]["environment"]
        assert public_env["PUBLIC_DEMO_ENABLED"] == "true"
        assert public_env["SESSION_COOKIE_SECURE"] == "true"
        assert public_env["COOKIE_PATH"] == "/open-compute-system"
        assert public_env["ADMIN_LOGIN_ENABLED"] == "false"
        assert public_env["SELF_REGISTRATION_ENABLED"] == "false"
        assert public_env["WEB_ORIGIN"] == "https://demo.example.com"
        assert public["services"]["web"]["ports"][0]["published"] == "18173"
        build_args = public["services"]["web"]["build"]["args"]
        assert build_args["NEXT_PUBLIC_BASE_PATH"] == public_env["COOKIE_PATH"]
        assert build_args["NEXT_PUBLIC_CSRF_COOKIE"] == public_env["CSRF_COOKIE"]
        for preview, host_ingress in ((False, False), (False, True), (True, True)):
            options = ["--dependencies", "external"]
            if host_ingress:
                options.extend(["--ingress", "host"])
            if preview:
                options.append("--preview")
            external = render(env_file, *options)
            services = external["services"]
            assert not ({"postgres", "redis"} & services.keys())
            assert not services["migrate"].get("depends_on")
            assert set(services["api"]["depends_on"]) == {"migrate"}
            assert external["networks"]["shared"]["external"] is True
            for name in ("api", "worker", "scheduler", "migrate"):
                assert services[name]["environment"]["REDIS_KEY_PREFIX"]
                assert "shared" in services[name]["networks"]
            images = {services[name]["image"] for name in ("api", "worker", "scheduler")}
            assert len(images) == 1
            assert (services["web"]["build"]["args"]["NEXT_PUBLIC_CSRF_COOKIE"]
                    == services["api"]["environment"]["CSRF_COOKIE"])
            if host_ingress:
                assert "nginx" not in services
                assert services["web"]["ports"][0]["host_ip"] == "127.0.0.1"
            if preview:
                assert services["api"]["environment"]["APP_ENV"] == "development"
                assert services["api"]["environment"]["DEMO_AUTO_DISPATCH"] == "false"
            else:
                assert services["api"]["environment"]["APP_ENV"] == "production"
                assert services["api"]["environment"]["DEMO_SEED_ENABLED"] == "false"
                assert (services["api"]["environment"]
                        ["ALLOW_MOCK_PROVIDER_IN_PRODUCTION"] == "false")
        env_file.write_text(env_file.read_text().replace(
            "REDIS_KEY_PREFIX=open_compute_system", "REDIS_KEY_PREFIX="))
        invalid = subprocess.run(
            [sys.executable, str(ROOT / "deploy/compose.py"), "--dependencies", "external",
             "--env-file", str(env_file), "config", "--quiet"], capture_output=True,
        )
        assert invalid.returncode != 0
        assert b"nonempty project-scoped" in invalid.stderr
    print("Deployment configuration passed: bundled, external, host ingress, preview, demo-lite")


if __name__ == "__main__":
    main()
