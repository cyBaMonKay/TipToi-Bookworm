import io
import sys
from pathlib import Path

import requests


def ensure_src_on_path():
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    return src_path


class FakeTextResponse:
    def __init__(self, text="", url="https://service.ravensburger.de/cat", status_error=None):
        self.text = text
        self.url = url
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error
        return None


class FakeHtmlSession:
    def __init__(self, html, url="https://service.ravensburger.de/cat"):
        self._html = html
        self._url = url

    def get(self, _url, timeout=None):
        return FakeTextResponse(self._html, self._url)


class RaisingSession:
    def __init__(self, exc):
        self._exc = exc

    def get(self, _url, timeout=None):
        raise self._exc


class FakeDownloadResponse:
    is_redirect = False

    def __init__(self, body=b"abc", status_error=None, chunks=None, iter_error=None):
        self._body = body
        self._chunks = chunks
        self._status_error = status_error
        self._iter_error = iter_error
        self.closed = False

        if chunks is None:
            content_length = len(body)
        else:
            content_length = sum(len(chunk) for chunk in chunks)
        self.headers = {"content-length": str(content_length)}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        if self._status_error is not None:
            raise self._status_error
        return None

    def iter_content(self, chunk_size=8192):
        if self._chunks is None:
            yield self._body
        else:
            for chunk in self._chunks:
                yield chunk

        if self._iter_error is not None:
            raise self._iter_error


class ScriptedTransport:
    """Replacement for ``HTTPAdapter.send`` that replays canned responses by URL.

    Patch with ``patch("requests.adapters.HTTPAdapter.send", new=transport.send)``
    so requests' real session and redirect handling run without network access.
    Unscripted URLs raise ``AssertionError`` to flag unexpected requests.
    """

    def __init__(self, routes):
        self.routes = routes
        self.calls = []
        self.responses = []

    def send(self, request, **kwargs):
        self.calls.append(request.url)
        if request.url not in self.routes:
            raise AssertionError(f"Unexpected request to {request.url}")

        status, headers, body = self.routes[request.url]
        response = requests.Response()
        response.request = request
        response.url = request.url
        response.status_code = status
        response.headers.update(headers)
        response.raw = io.BytesIO(body)
        self.responses.append(response)
        return response


def redirect_route(location, status=302):
    return status, {"Location": location}, b""


def payload_route(body):
    return 200, {"Content-Length": str(len(body))}, body

