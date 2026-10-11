"""Tests for the isolated voice-over utility; no provider calls are made."""

import json
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

try:
    import devtools.voice.generate_audio as voice_tool
except ModuleNotFoundError as exc:
    if exc.name and exc.name.startswith("devtools"):
        raise unittest.SkipTest("local voice tooling does not ship") from exc
    raise
from devtools.voice.generate_audio import (
    VoiceGenerationError,
    api_key_for,
    build_request,
    default_voice,
    validate_paths,
)


class VoiceRequestTests(unittest.TestCase):
    def test_provider_error_shows_safe_details_but_redacts_text_and_key(self):
        error = HTTPError(
            "https://example.invalid", 401, "Unauthorized", {},
            BytesIO(
                b'{"detail":{"status":"missing_permissions",'
                b'"message":"Denied for synthetic phrase and secret-key"}}'
            ),
        )
        message = voice_tool._safe_provider_error(
            error, "synthetic phrase", "secret-key"
        )
        self.assertIn("HTTP 401 (missing_permissions:", message)
        self.assertNotIn("synthetic phrase", message)
        self.assertNotIn("secret-key", message)

    def test_elevenlabs_default_voice_is_selected_by_language(self):
        self.assertEqual(default_voice("elevenlabs", "ru"), "zWSsRd3J6WyZFl12aGMB")
        self.assertEqual(default_voice("elevenlabs", "en"), "hpp4J3VqNfWAUOO0d1Us")

    def test_openai_voice_default_is_unchanged_by_language(self):
        self.assertEqual(default_voice("openai", "ru"), "marin")

    def test_openai_request_uses_tts_payload_and_header(self):
        request = build_request(
            "openai", "Synthetic demo.", "marin", "gpt-4o-mini-tts", "secret",
            "Speak clearly.",
        )
        self.assertIsInstance(request, Request)
        self.assertEqual(request.full_url, "https://api.openai.com/v1/audio/speech")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        self.assertEqual(
            json.loads(request.data),
            {"model": "gpt-4o-mini-tts", "input": "Synthetic demo.",
             "voice": "marin", "response_format": "mp3", "instructions": "Speak clearly."},
        )

    def test_elevenlabs_request_uses_voice_route_and_api_key_header(self):
        request = build_request(
            "elevenlabs", "Synthetic demo.", "voice-123", "eleven_multilingual_v2", "secret"
        )
        self.assertEqual(
            request.full_url,
            "https://api.elevenlabs.io/v1/text-to-speech/voice-123?output_format=mp3_44100_128",
        )
        self.assertEqual(request.get_header("Xi-api-key"), "secret")
        self.assertEqual(
            json.loads(request.data),
            {"text": "Synthetic demo.", "model_id": "eleven_multilingual_v2"},
        )

    def test_missing_key_and_voice_are_rejected(self):
        with self.assertRaises(VoiceGenerationError):
            build_request("openai", "text", "marin", "model", "")
        with self.assertRaises(VoiceGenerationError):
            build_request("elevenlabs", "text", "", "model", "key")

    def test_environment_key_takes_precedence(self):
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "env-secret"}):
            with patch.object(sys, "platform", "darwin"):
                with patch("devtools.voice.generate_audio.subprocess.run") as run:
                    self.assertEqual(api_key_for("elevenlabs"), "env-secret")
                    run.assert_not_called()

    def test_keychain_lookup_is_quiet_and_uses_fixed_service_name(self):
        completed = subprocess.CompletedProcess([], 0, stdout="keychain-secret\n", stderr="")
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(sys, "platform", "darwin"):
                with patch("devtools.voice.generate_audio.subprocess.run", return_value=completed) as run:
                    self.assertEqual(api_key_for("elevenlabs"), "keychain-secret")
        self.assertEqual(
            run.call_args.args[0],
            ["/usr/bin/security", "find-generic-password", "-a", "scholion",
             "-s", "scholion-elevenlabs-tts", "-w"],
        )
        self.assertTrue(run.call_args.kwargs["capture_output"])

    def test_personal_project_path_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protected_dir = root / "profile"
            protected_dir.mkdir()
            protected = protected_dir / "private-demo-source.txt"
            protected.write_text("synthetic test sentinel", encoding="utf-8")
            original_root = voice_tool.PROJECT_ROOT
            voice_tool.PROJECT_ROOT = root
            try:
                with self.assertRaises(VoiceGenerationError):
                    validate_paths(protected, root / "output.mp3")
            finally:
                voice_tool.PROJECT_ROOT = original_root

    def test_audio_output_in_personal_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "profile").mkdir()
            source = root / "demo.txt"
            source.write_text("Synthetic demonstration text.", encoding="utf-8")
            original_root = voice_tool.PROJECT_ROOT
            voice_tool.PROJECT_ROOT = root
            try:
                with self.assertRaises(VoiceGenerationError):
                    validate_paths(source, root / "profile" / "voice.mp3")
            finally:
                voice_tool.PROJECT_ROOT = original_root


if __name__ == "__main__":
    unittest.main()
