"""Check first-run settings and preservation without accessing the real .env."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bootstrap


class BootstrapTests(unittest.TestCase):
    def test_empty_placeholders_are_completed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "POSTGRES_PASSWORD=\nBETTER_AUTH_SECRET=\nFRONTEND_PORT=3010\n"
            )
            with patch.object(bootstrap, "ROOT", root), contextlib.redirect_stdout(io.StringIO()):
                bootstrap.main()
            lines = (root / ".env").read_text().splitlines()
            values = dict(line.split("=", 1) for line in lines if "=" in line)
            self.assertGreaterEqual(len(values["POSTGRES_PASSWORD"]), 32)
            self.assertGreaterEqual(len(values["BETTER_AUTH_SECRET"]), 32)
            self.assertEqual(values["BETTER_AUTH_URL"], "http://localhost:3010")
            self.assertEqual(sum(line.startswith("POSTGRES_PASSWORD=") for line in lines), 1)

    def test_existing_secrets_and_llm_file_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "POSTGRES_PASSWORD=existing-db-secret\nBETTER_AUTH_SECRET=existing-auth-secret\n"
            )
            (root / ".env.local").write_text("GROQ_API_KEY=untouched-fixture\n")
            output = io.StringIO()
            with patch.object(bootstrap, "ROOT", root), contextlib.redirect_stdout(output):
                bootstrap.main()
                initial = (root / ".env").read_text()
                bootstrap.main()
            self.assertEqual((root / ".env").read_text(), initial)
            self.assertIn("BETTER_AUTH_SECRET=existing-auth-secret", initial)
            self.assertIn("POSTGRES_PASSWORD=existing-db-secret", initial)
            self.assertEqual((root / ".env").stat().st_mode & 0o777, 0o600)
            self.assertEqual((root / ".env.local").read_text(), "GROQ_API_KEY=untouched-fixture\n")
            self.assertNotIn("existing-auth-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
