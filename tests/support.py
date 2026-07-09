import sys
from pathlib import Path


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

