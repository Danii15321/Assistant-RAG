import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from configure_llm import configure


class LlmConfigurationTests(unittest.TestCase):
    def test_only_groq_key_is_copied_with_private_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = "GROQ_API_KEY=synthetic-groq-fixture\nVERCEL_OIDC_TOKEN=keep-private\n"
            (root/".env.local").write_text(original)
            (root/".env").write_text("BETTER_AUTH_SECRET=existing-secret\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                configure(root); configure(root)
            self.assertEqual((root/".env.local").read_text(), original)
            self.assertEqual((root/".secrets/groq_api_key").read_text(), "synthetic-groq-fixture")
            self.assertEqual((root/".secrets/groq_api_key").stat().st_mode & 0o777, 0o600)
            self.assertEqual((root/".secrets").stat().st_mode & 0o777, 0o700)
            self.assertNotIn("synthetic-groq-fixture", output.getvalue())
            self.assertIn("existing-secret", (root/".env").read_text())

    def test_empty_key_cannot_enable_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/".env.local").write_text("GROQ_API_KEY=\n")
            (root/".env").write_text("BETTER_AUTH_SECRET=existing-secret\n")
            with self.assertRaises(RuntimeError): configure(root)
            self.assertFalse((root/".secrets").exists())
            self.assertNotIn("LLM_FREE_PLAN_CONFIRMED", (root/".env").read_text())


if __name__ == "__main__": unittest.main()
