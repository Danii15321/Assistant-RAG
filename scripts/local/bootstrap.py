"""Create/complete private local settings without touching .env.local."""

import os
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    destination = ROOT / ".env"
    content = destination.read_text() if destination.exists() else "# Usage local uniquement.\n"
    values = dict(
        line.split("=", 1)
        for line in content.splitlines()
        if "=" in line and not line.startswith("#")
    )
    defaults = {
        "POSTGRES_PASSWORD": secrets.token_hex(24),
        "FRONTEND_PORT": "3000",
        "BACKEND_PORT": "8000",
        "DATABASE_PORT": "5433",
        "BETTER_AUTH_SECRET": secrets.token_hex(32),
        "TEST_AUTH_SECRET": secrets.token_hex(32),
        "BETTER_AUTH_URL": f"http://localhost:{values.get('FRONTEND_PORT') or '3000'}",
    }
    additions = {key: value for key, value in defaults.items() if not values.get(key, "").strip()}
    if additions:
        content = "\n".join(
            line
            for line in content.splitlines()
            if "=" not in line or line.split("=", 1)[0] not in additions
        )
        content = (
            content.rstrip()
            + "\n"
            + "\n".join(f"{key}={value}" for key, value in additions.items())
            + "\n"
        )
        temporary = ROOT / ".env.bootstrap.tmp"
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
        temporary.replace(destination)
    destination.chmod(0o600)
    print("Configuration locale prête ; valeurs existantes conservées, secrets non affichés.")


if __name__ == "__main__":
    main()
