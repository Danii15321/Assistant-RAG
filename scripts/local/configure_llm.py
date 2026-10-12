"""Copy only the Groq key into a private local server mount; no cloud writes."""
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def configure(root: Path) -> None:
    values = dict(line.split("=", 1) for line in (root / ".env.local").read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    key = values.get("GROQ_API_KEY", "").strip().strip("\"").strip("'")
    if not key or "\n" in key or len(key) > 512:
        raise RuntimeError("Une clé Groq valide est requise dans .env.local.")
    folder = root / ".secrets"
    folder.mkdir(mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    temporary = folder / "groq_api_key.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(key)
    temporary.replace(folder / "groq_api_key")
    destination = root / ".env"
    content = destination.read_text()
    lines = [line for line in content.splitlines() if not line.startswith("LLM_FREE_PLAN_CONFIRMED=")]
    descriptor = os.open(root / ".env.llm.tmp", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write("\n".join(lines)+"\nLLM_FREE_PLAN_CONFIRMED=true\n")
    (root / ".env.llm.tmp").replace(destination)
    print("Groq Free configuré pour le serveur local ; secrets non affichés, .env.local conservé.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--free-confirmed", action="store_true", required=True,
                        help="Le titulaire a confirmé son compte Groq Free.")
    parser.parse_args()
    configure(ROOT)
