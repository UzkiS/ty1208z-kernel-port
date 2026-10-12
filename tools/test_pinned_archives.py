#!/usr/bin/env python3
"""Verify retries preserve source identity and never publish partial archives."""
import contextlib
import hashlib
import io
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

import fetch_pinned_archives as downloader

URL = "https://source.example/archive.tar.xz"
DATA = b"an exact pinned source archive fixture"
SHA = hashlib.sha256(DATA).hexdigest()


class Response(io.BytesIO):
    def __init__(self, data=DATA, length="actual", url=URL, interrupted=False):
        super().__init__(data)
        self.headers = {} if length is None else {"Content-Length": str(len(data) if length == "actual" else length)}
        self.url = url
        self.interrupted = interrupted
        self.read_count = 0

    def geturl(self):
        return self.url

    def read(self, amount):
        self.read_count += 1
        if self.interrupted:
            if self.read_count == 1:
                return super().read(5)
            raise ConnectionResetError("transfer interrupted")
        return super().read(amount)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.archive = self.root / "archive.tar.xz"
        self.output = contextlib.redirect_stdout(io.StringIO())
        self.output.__enter__()
        self.addCleanup(self.output.__exit__, None, None, None)

    def fetch(self):
        downloader.fetch(URL, SHA, self.archive)

    def assert_empty(self):
        self.assertEqual(list(self.root.iterdir()), [])

    def test_connection_refused_then_exact_archive(self):
        failure = urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))
        with patch.object(downloader.urllib.request, "urlopen", side_effect=[failure, Response()]) as request:
            with patch.object(downloader.time, "sleep") as sleep:
                self.fetch()
                self.assertEqual(request.call_count, 2)
                sleep.assert_called_once_with(1)
                request.assert_called_with(URL, timeout=downloader.SOCKET_TIMEOUT)
        self.assertEqual(self.archive.read_bytes(), DATA)
        self.assertEqual(list(self.root.iterdir()), [self.archive])

    def test_interrupted_and_truncated_transfers_are_not_published(self):
        for response in (Response(interrupted=True), Response(DATA[:5], length=len(DATA))):
            with self.subTest(interrupted=response.interrupted):
                responses = iter([response, Response()])

                def open_response(*args, **kwargs):
                    self.assert_empty()
                    return next(responses)

                with patch.object(downloader.urllib.request, "urlopen", side_effect=open_response):
                    with patch.object(downloader.time, "sleep"):
                        self.fetch()
                self.assertEqual(self.archive.read_bytes(), DATA)
                self.archive.unlink()

    def test_http_503_has_three_attempts_and_no_final_archive(self):
        error = urllib.error.HTTPError(URL, 503, "Service Unavailable", {}, None)
        with patch.object(downloader.urllib.request, "urlopen", side_effect=error) as request:
            with patch.object(downloader.time, "sleep") as sleep:
                with self.assertRaises(urllib.error.HTTPError):
                    self.fetch()
                self.assertEqual(request.call_count, 3)
                self.assertEqual([call.args for call in sleep.call_args_list], [(1,), (2,)])
        self.assert_empty()

    def test_http_404_and_bad_certificate_fail_without_retry(self):
        errors = [urllib.error.HTTPError(URL, 404, "Not Found", {}, None),
                  urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed"))]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                with patch.object(downloader.urllib.request, "urlopen", side_effect=error) as request:
                    with patch.object(downloader.time, "sleep") as sleep:
                        with self.assertRaises(urllib.error.URLError):
                            self.fetch()
                        request.assert_called_once()
                        sleep.assert_not_called()
                self.assert_empty()

    def test_wrong_download_hash_is_terminal_and_removed(self):
        with patch.object(downloader.urllib.request, "urlopen", return_value=Response(b"changed source")) as request:
            with patch.object(downloader.time, "sleep") as sleep:
                with self.assertRaisesRegex(ValueError, "Downloaded archive hash mismatch"):
                    self.fetch()
                request.assert_called_once()
                sleep.assert_not_called()
        self.assert_empty()

    def test_cache_checked_without_network_or_replacement(self):
        self.archive.write_bytes(DATA)
        with patch.object(downloader.urllib.request, "urlopen") as request:
            self.fetch()
            request.assert_not_called()
            self.archive.write_bytes(b"corrupt cached source")
            with self.assertRaisesRegex(ValueError, "Cached archive hash mismatch"):
                self.fetch()
            self.assertEqual(self.archive.read_bytes(), b"corrupt cached source")
            request.assert_not_called()

    def test_redirect_size_and_commit_errors_cleanup_temporary_files(self):
        responses = (Response(url="http://source.example/archive.tar.xz"),
                     Response(length=downloader.MAX_BYTES + 1), Response(length=None))
        for response in responses:
            with self.subTest(url=response.url, length=response.headers):
                with patch.object(downloader.urllib.request, "urlopen", return_value=response) as request:
                    with patch.object(downloader, "MAX_BYTES", 10):
                        with self.assertRaises(ValueError):
                            self.fetch()
                    request.assert_called_once()
                self.assert_empty()
        with patch.object(downloader.urllib.request, "urlopen", return_value=Response()):
            with patch.object(downloader.os, "replace", side_effect=PermissionError("cannot publish")):
                with self.assertRaises(PermissionError):
                    self.fetch()
        self.assert_empty()

    def test_slow_attempts_have_deadlines_and_bounded_retries(self):
        with patch.object(downloader.time, "monotonic", side_effect=[0, 180, 200, 380, 400, 580]):
            with patch.object(downloader.urllib.request, "urlopen", side_effect=lambda *args, **kwargs: Response()) as request:
                with patch.object(downloader.time, "sleep"):
                    with self.assertRaises(TimeoutError):
                        self.fetch()
                    self.assertEqual(request.call_count, 3)
        self.assert_empty()

    def test_bad_metadata_does_not_open_network(self):
        for url, digest in (("http://source.example/archive", SHA), (URL, "bad-hash"),
                            ("https://user:password@source.example/archive", SHA)):
            with self.subTest(url=url):
                with patch.object(downloader.urllib.request, "urlopen") as request:
                    with self.assertRaises(ValueError):
                        downloader.fetch(url, digest, self.archive)
                    request.assert_not_called()
        self.assert_empty()


if __name__ == "__main__":
    unittest.main(verbosity=2)
