import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from doc_azure.settings import Settings, SettingsError, ensure_runtime_directories


class SettingsTests(TestCase):
    def test_load_reads_pat_without_exposing_it_in_repr(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("AZDO_PAT=secret-value\n", encoding="utf-8")

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.load(root)

            self.assertEqual(settings.pat, "secret-value")
            self.assertNotIn("secret-value", repr(settings))

    def test_load_prefers_environment_pat_over_dotenv(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("AZDO_PAT=file-token\n", encoding="utf-8")

            with patch.dict(os.environ, {"AZDO_PAT": "environment-token"}, clear=True):
                settings = Settings.load(root)

            self.assertEqual(settings.pat, "environment-token")

    def test_load_validates_dotenv_before_using_environment_pat(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text("invalid entry\n", encoding="utf-8")

            with patch.dict(os.environ, {"AZDO_PAT": "environment-token"}, clear=True):
                with self.assertRaisesRegex(
                    SettingsError, "Invalid .env entry on line 1"
                ):
                    Settings.load(root)

    def test_load_parses_quoted_values_and_ignores_comments(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "# local configuration\n\nAZDO_PAT='quoted-token'\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                settings = Settings.load(root)

            self.assertEqual(settings.pat, "quoted-token")

    def test_load_rejects_missing_pat_without_leaking_configuration(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(
                    SettingsError,
                    "AZDO_PAT is required; add it to .env or the environment",
                ):
                    Settings.load(root)

    def test_setup_is_idempotent(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)

            first = ensure_runtime_directories(root)
            second = ensure_runtime_directories(root)

            self.assertEqual(first, second)
            self.assertTrue(all(path.is_dir() for path in second))
