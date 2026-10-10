# -*- coding: utf-8 -*-
"""
lc_boot.py – Python-Laufzeit der Lernplattform (Pyodide im Browser)

Wird von lc-runner.js als Modul ``lc_boot`` geladen. Stellt bereit:

* Ersatzmodule (Shims) für Colab- und API-Code: ``openai``, ``requests``,
  ``google.colab`` (``userdata``, ``files``, ``drive``), ``IPython.display``
* einen Import-Hook für Pakete, die im Browser nicht laufen
* ``lc_run(code)`` zum Ausführen einer Notebook-Zelle (Jupyter-ähnliche Anzeige)
* ``lc_reset()`` zum Leeren des Namensraums

Brücken nach JavaScript (in lc-runner.js definiert):
``lcEmit(kind, data)``, ``lcHttpSync(...)``, ``lcHttpAsync(...)``,
``lcInterruptRequested()``, optional ``lcInput(prompt)`` und ``lcDownload(name, bytes)``.
Schlüssel kommen über das JS-Modul ``_lc_js`` (``getSecret``) und werden nie ausgegeben.
"""

import base64
import builtins
import collections.abc
import datetime
import http
import importlib
import importlib.abc
import importlib.machinery
import io
import json
import os
import pprint
import re
import sys
import time
import traceback
import types
import urllib.parse
import warnings

import js
from pyodide.code import eval_code_async, find_imports
from pyodide.ffi import JsProxy, to_js

try:  # JSPI: synchron auf ein JS-Promise warten, ohne den Browser einzufrieren
    from pyodide.ffi import can_run_sync as _pyo_can_run_sync
    from pyodide.ffi import run_sync as _pyo_run_sync
except ImportError:  # pragma: no cover
    _pyo_run_sync = None

    def _pyo_can_run_sync():
        return False


# ---------------------------------------------------------------------------
# 1. Umgebung
# ---------------------------------------------------------------------------
os.environ["MPLBACKEND"] = "agg"
HOME = "/home/pyodide"
os.makedirs(HOME, exist_ok=True)
os.chdir(HOME)
if "" not in sys.path:
    sys.path.insert(0, "")
warnings.filterwarnings("ignore", message=".*non-interactive, and thus cannot be shown.*")
warnings.filterwarnings("ignore", message=".*Matplotlib is currently using agg.*")

USE_RUN_SYNC = True          # kann von JS abgeschaltet werden (Test des XHR-Wegs)
LANG_HINT_COLAB = "Diese Zelle bitte in Colab ausführen."

_MSG_VERBINDUNG = (
    "Keine Verbindung zu {host} möglich. Mögliche Ursachen: "
    "(1) Die Vorschau der Plattform erlaubt keine Verbindungen zu fremden Servern. "
    "(2) Der Server erlaubt keine Zugriffe aus dem Browser (CORS). "
    "(3) Es besteht keine Internetverbindung."
)


def _host(url):
    try:
        return urllib.parse.urlsplit(url).netloc or url
    except Exception:
        return str(url)


def _can_run_sync():
    if not USE_RUN_SYNC or _pyo_run_sync is None:
        return False
    try:
        return bool(_pyo_can_run_sync())
    except Exception:
        return False


def _js_fn(name):
    try:
        f = getattr(js, name)
    except AttributeError:
        return None
    return None if f is None else f


def _check_interrupt():
    f = _js_fn("lcInterruptRequested")
    if f is not None:
        try:
            if f():
                raise KeyboardInterrupt("Ausführung abgebrochen.")
        except KeyboardInterrupt:
            raise
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2. Ausgabe: lcEmit, display, matplotlib
# ---------------------------------------------------------------------------
def _flush_std():
    for s in (sys.stdout, sys.stderr):
        try:
            s.flush()
        except Exception:
            pass


def _emit(kind, data):
    _flush_std()
    f = _js_fn("lcEmit")
    if f is None:
        print(f"[{kind}] {str(data)[:200]}")
        return
    f(kind, data)


def _pretty(obj):
    try:
        if isinstance(obj, (dict, list, tuple, set, frozenset)):
            return pprint.pformat(obj, width=79, sort_dicts=False)
        return repr(obj)
    except Exception as e:  # repr selbst ist kaputt
        return f"<Anzeige fehlgeschlagen: {type(e).__name__}: {e}>"


def _is_figure(obj):
    mf = sys.modules.get("matplotlib.figure")
    return mf is not None and isinstance(obj, mf.Figure)


def _fig_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _img_mime(data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _rich(obj):
    """Liefert (kind, data) für ein Objekt, ähnlich wie Jupyter die reichste Darstellung wählt."""
    if _is_figure(obj):
        return "png", _fig_to_b64(obj)
    if not isinstance(obj, type) and not isinstance(obj, JsProxy):
        for meth, kind in (("_repr_html_", "html"), ("_repr_markdown_", "markdown"),
                           ("_repr_png_", "png"), ("_repr_svg_", "html"), ("_repr_jpeg_", "jpeg"),
                           ("_repr_latex_", "markdown")):
            f = getattr(obj, meth, None)
            if f is None or not callable(f):
                continue
            try:
                r = f()
            except Exception:
                continue
            if r is None:
                continue
            if isinstance(r, tuple):
                r = r[0]
            if kind == "png":
                if isinstance(r, (bytes, bytearray)):
                    r = base64.b64encode(bytes(r)).decode("ascii")
                return "png", r
            if kind == "jpeg":
                if isinstance(r, (bytes, bytearray)):
                    r = base64.b64encode(bytes(r)).decode("ascii")
                return "html", f'<img src="data:image/jpeg;base64,{r}">'
            return kind, str(r)
    return "text", _pretty(obj)


class DisplayHandle:
    def __init__(self, display_id=None):
        self.display_id = display_id

    def display(self, obj, **kw):
        display(obj)

    def update(self, obj, **kw):
        display(obj)

    def __repr__(self):
        return f"<DisplayHandle display_id={self.display_id}>"


def display(*objs, include=None, exclude=None, metadata=None, transient=None,
            display_id=None, raw=False, clear=False, **kwargs):
    """Wie IPython.display.display: zeigt Objekte als HTML, Bild, Markdown oder Text an."""
    for obj in objs:
        if raw and isinstance(obj, dict):
            if "text/html" in obj:
                _emit("html", str(obj["text/html"]))
            elif "image/png" in obj:
                _emit("png", obj["image/png"])
            elif "text/markdown" in obj:
                _emit("markdown", str(obj["text/markdown"]))
            else:
                _emit("text", str(obj.get("text/plain", obj)))
            continue
        kind, data = _rich(obj)
        _emit(kind, data)
    if display_id:
        return DisplayHandle(display_id if display_id is not True else "lc")
    return None


def _show_value(value):
    """Rückgabewert des letzten Ausdrucks anzeigen (wie Jupyter; None nicht)."""
    if value is None:
        return
    kind, data = _rich(value)
    _emit(kind, data)


def _flush_figures():
    plt = sys.modules.get("matplotlib.pyplot")
    if plt is None:
        return
    try:
        nums = list(plt.get_fignums())
    except Exception:
        return
    for num in nums:
        try:
            fig = plt.figure(num)
            if fig.axes or fig.texts or fig.images:
                _emit("png", _fig_to_b64(fig))
        except Exception as e:
            _emit("stderr", f"Abbildung konnte nicht angezeigt werden: {type(e).__name__}: {e}\n")
        finally:
            try:
                plt.close(num)
            except Exception:
                pass


def _patch_pyplot(plt):
    if getattr(plt, "_lc_patched", False):
        return

    def show(*args, **kwargs):
        """Zeigt alle offenen Abbildungen in der Zellausgabe an (wie %matplotlib inline)."""
        _flush_figures()

    show.__module__ = "matplotlib.pyplot"
    plt.show = show
    plt._lc_patched = True
    try:
        import matplotlib
        matplotlib.rcParams["figure.dpi"] = 100
    except Exception:
        pass


class _PostImportFinder(importlib.abc.MetaPathFinder):
    """Patcht matplotlib.pyplot direkt nach dem Import (plt.show → Bild in der Ausgabe)."""

    hooks = {"matplotlib.pyplot": _patch_pyplot}

    def __init__(self):
        self._busy = set()

    def find_spec(self, fullname, path=None, target=None):
        hook = self.hooks.get(fullname)
        if hook is None or fullname in self._busy:
            return None
        self._busy.add(fullname)
        try:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        finally:
            self._busy.discard(fullname)
        if spec is None or spec.loader is None:
            return None
        orig = spec.loader

        class _Loader(importlib.abc.Loader):
            def create_module(self, spec_):
                return orig.create_module(spec_)

            def exec_module(self, module):
                orig.exec_module(module)
                hook(module)

            def __getattr__(self, name):
                return getattr(orig, name)

        spec.loader = _Loader()
        return spec


# --- IPython.display-Objekte -------------------------------------------------
class _DisplayObject:
    _read_flags = "r"

    def __init__(self, data=None, url=None, filename=None, metadata=None):
        if data is not None and isinstance(data, str) and url is None and filename is None:
            if data.startswith(("http://", "https://")) and "\n" not in data:
                url, data = data, None
            elif len(data) < 300 and "\n" not in data and os.path.isfile(data):
                filename, data = data, None
        if filename is not None and data is None:
            with open(filename, self._read_flags) as f:
                data = f.read()
        self.data, self.url, self.filename, self.metadata = data, url, filename, metadata

    def __repr__(self):
        return f"<IPython.core.display.{type(self).__name__} object>"


class HTML(_DisplayObject):
    def _repr_html_(self):
        if self.data is None and self.url:
            return f'<iframe src="{self.url}" style="width:100%;height:400px;border:0"></iframe>'
        return str(self.data)


class Markdown(_DisplayObject):
    def _repr_markdown_(self):
        return str(self.data)


class Latex(_DisplayObject):
    def _repr_latex_(self):
        return str(self.data)


class SVG(_DisplayObject):
    def _repr_svg_(self):
        return str(self.data)


class Pretty(_DisplayObject):
    def __repr__(self):
        return str(self.data)


class Javascript(_DisplayObject):
    def __repr__(self):
        return "<JavaScript wird auf der Plattform nicht ausgeführt>"


class JSON(_DisplayObject):
    def __init__(self, data=None, url=None, filename=None, expanded=False, metadata=None, root="root", **kw):
        super().__init__(data=data, url=url, filename=filename, metadata=metadata)

    def __repr__(self):
        try:
            return json.dumps(self.data, ensure_ascii=False, indent=2)
        except Exception:
            return repr(self.data)


class IFrame:
    def __init__(self, src, width, height, extras=None, **kwargs):
        self.src, self.width, self.height = src, width, height

    def _repr_html_(self):
        return f'<iframe src="{self.src}" width="{self.width}" height="{self.height}" style="border:0"></iframe>'


class FileLink:
    def __init__(self, path, url_prefix="", result_html_prefix="", result_html_suffix="<br>"):
        self.path = path

    def _repr_html_(self):
        return f"<code>{self.path}</code>"

    def __repr__(self):
        return self.path


class Image(_DisplayObject):
    _read_flags = "rb"

    def __init__(self, data=None, url=None, filename=None, format=None, embed=None, width=None,
                 height=None, retina=False, unconfined=False, metadata=None, alt=None):
        super().__init__(data=data, url=url, filename=filename, metadata=metadata)
        self.format, self.width, self.height, self.alt = format, width, height, alt

    def _bytes(self):
        return self.data if isinstance(self.data, (bytes, bytearray)) else None

    def _repr_html_(self):
        b = self._bytes()
        size = "".join(f' {k}="{v}"' for k, v in (("width", self.width), ("height", self.height)) if v)
        if b is None:
            if self.url:
                return f'<img src="{self.url}"{size}>'
            return None
        mime = _img_mime(bytes(b))
        if mime == "image/png" and not size:
            return None  # → _repr_png_
        return f'<img src="data:{mime};base64,{base64.b64encode(bytes(b)).decode()}"{size}>'

    def _repr_png_(self):
        b = self._bytes()
        return bytes(b) if b is not None and _img_mime(bytes(b)) == "image/png" else None


def clear_output(wait=False):
    """Auf der Plattform ohne Wirkung (Ausgaben werden nicht gelöscht)."""
    return None


def get_ipython():
    return None


# ---------------------------------------------------------------------------
# 3. input()
# ---------------------------------------------------------------------------
def _input(prompt=""):
    prompt = "" if prompt is None else str(prompt)
    _check_interrupt()
    if prompt:
        sys.stdout.write(prompt)
    _flush_std()
    answer = None
    hook = _js_fn("lcInput")
    try:
        if hook is not None:
            answer = hook(prompt)
            if not isinstance(answer, str) and (hasattr(answer, "__await__") or hasattr(answer, "then")):
                if _can_run_sync():
                    answer = _pyo_run_sync(answer)
                else:
                    answer = None
                    raise EOFError("Eingaben über ein Eingabefeld gehen hier nur in Browsern mit JSPI (z. B. aktuelles Chrome).")
        else:
            p = _js_fn("prompt")
            answer = p(prompt or "Eingabe:") if p is not None else None
    except EOFError:
        raise
    except Exception:
        answer = None
    if not isinstance(answer, str):
        sys.stdout.write("\n")
        raise EOFError("Keine Eingabe erhalten (Dialog abgebrochen oder in der Vorschau gesperrt).")
    sys.stdout.write(answer + "\n")
    _flush_std()
    return answer


# ---------------------------------------------------------------------------
# 4. HTTP-Brücke
# ---------------------------------------------------------------------------
def _ms(timeout):
    if timeout is None:
        return 0
    try:
        return max(0, int(float(timeout) * 1000))
    except Exception:
        return 0


def _js_body(body):
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray, memoryview)):
        return to_js(bytes(body))
    return str(body)


def _http_sync(method, url, headers, body=None, timeout=None, binary=False):
    """Synchroner HTTP-Aufruf. Mit JSPI über fetch (Browser bleibt bedienbar), sonst synchrones XHR."""
    _check_interrupt()
    hj = json.dumps(headers or {})
    if _can_run_sync():
        raw = _pyo_run_sync(js.lcHttpAsync(method, url, hj, _js_body(body), _ms(timeout), bool(binary)))
    else:
        raw = js.lcHttpSync(method, url, hj, _js_body(body), bool(binary))
    res = json.loads(str(raw))
    if res.get("aborted"):
        raise KeyboardInterrupt("Ausführung abgebrochen.")
    _check_interrupt()
    return res


async def _http_async(method, url, headers, body=None, timeout=None, binary=False):
    _check_interrupt()
    hj = json.dumps(headers or {})
    raw = await js.lcHttpAsync(method, url, hj, _js_body(body), _ms(timeout), bool(binary))
    res = json.loads(str(raw))
    if res.get("aborted"):
        raise KeyboardInterrupt("Ausführung abgebrochen.")
    return res


def _res_bytes(res):
    if "b64" in res:
        return base64.b64decode(res.get("b64") or "")
    return (res.get("text") or "").encode("utf-8")


def _json_default(o):
    if hasattr(o, "model_dump") and callable(o.model_dump):
        return o.model_dump(mode="json")
    if hasattr(o, "tolist"):
        return o.tolist()
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (set, frozenset, tuple)):
        return list(o)
    if isinstance(o, (datetime.date, datetime.datetime)):
        return o.isoformat()
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


class CaseInsensitiveDict(collections.abc.MutableMapping):
    def __init__(self, data=None, **kw):
        self._s = {}
        self.update(data or {}, **kw)

    def __setitem__(self, k, v):
        self._s[k.lower()] = (k, v)

    def __getitem__(self, k):
        return self._s[k.lower()][1]

    def __delitem__(self, k):
        del self._s[k.lower()]

    def __iter__(self):
        return (k for k, _ in self._s.values())

    def __len__(self):
        return len(self._s)

    def copy(self):
        return CaseInsensitiveDict(dict(self.items()))

    def __repr__(self):
        return repr(dict(self.items()))


# ---------------------------------------------------------------------------
# 5. requests (Ersatzmodul)
# ---------------------------------------------------------------------------
class RequestException(IOError):
    def __init__(self, *args, response=None, request=None, **kw):
        super().__init__(*args)
        self.response = response
        self.request = request if request is not None else getattr(response, "request", None)


class HTTPError(RequestException):
    pass


class _RConnectionError(RequestException):
    pass


class ProxyError(_RConnectionError):
    pass


class SSLError(_RConnectionError):
    pass


class Timeout(RequestException):
    pass


class ConnectTimeout(_RConnectionError, Timeout):
    pass


class ReadTimeout(Timeout):
    pass


class URLRequired(RequestException):
    pass


class TooManyRedirects(RequestException):
    pass


class MissingSchema(RequestException, ValueError):
    pass


class InvalidSchema(RequestException, ValueError):
    pass


class InvalidURL(RequestException, ValueError):
    pass


class InvalidHeader(RequestException, ValueError):
    pass


class InvalidJSONError(RequestException):
    pass


class _RJSONDecodeError(InvalidJSONError, json.JSONDecodeError):
    def __init__(self, *args, **kwargs):
        json.JSONDecodeError.__init__(self, *args)
        InvalidJSONError.__init__(self, *self.args, **kwargs)


class ChunkedEncodingError(RequestException):
    pass


class ContentDecodingError(RequestException):
    pass


_RConnectionError.__name__ = _RConnectionError.__qualname__ = "ConnectionError"
_RJSONDecodeError.__name__ = _RJSONDecodeError.__qualname__ = "JSONDecodeError"


class PreparedRequest:
    def __init__(self, method, url, body=None):
        self.method, self.url, self.body = method, url, body
        self.headers = CaseInsensitiveDict()   # bewusst leer: keine Schlüssel nach außen

    def __repr__(self):
        return f"<PreparedRequest [{self.method}]>"


class Response:
    def __init__(self):
        self.status_code = None
        self.headers = CaseInsensitiveDict()
        self.url = None
        self.encoding = None
        self.reason = ""
        self.history = []
        self.cookies = {}
        self.elapsed = datetime.timedelta(0)
        self.request = None
        self._content = b""

    @property
    def content(self):
        return self._content

    @property
    def apparent_encoding(self):
        return "utf-8"

    @property
    def text(self):
        enc = self.encoding
        if enc is None:
            m = re.search(r"charset=([\w-]+)", self.headers.get("content-type", ""), re.I)
            enc = m.group(1) if m else "utf-8"
        try:
            return self._content.decode(enc, errors="replace")
        except LookupError:
            return self._content.decode("utf-8", errors="replace")

    def json(self, **kwargs):
        try:
            return json.loads(self.text, **kwargs)
        except json.JSONDecodeError as e:
            raise _RJSONDecodeError(e.msg, e.doc, e.pos, response=self) from None

    @property
    def ok(self):
        return self.status_code is not None and self.status_code < 400

    def __bool__(self):
        return self.ok

    @property
    def is_redirect(self):
        return False

    @property
    def links(self):
        return {}

    def raise_for_status(self):
        reason = self.reason or ""
        if 400 <= self.status_code < 500:
            msg = f"{self.status_code} Client Error: {reason} for url: {self.url}"
        elif 500 <= self.status_code < 600:
            msg = f"{self.status_code} Server Error: {reason} for url: {self.url}"
        else:
            return
        raise HTTPError(msg, response=self)

    def iter_content(self, chunk_size=1, decode_unicode=False):
        data = self.text if decode_unicode else self._content
        step = chunk_size or len(data) or 1
        for i in range(0, len(data), step):
            yield data[i:i + step]

    def iter_lines(self, chunk_size=512, decode_unicode=False, delimiter=None):
        text = self.text if decode_unicode else self._content
        sep = delimiter if delimiter is not None else ("\n" if decode_unicode else b"\n")
        for line in text.split(sep):
            yield line.rstrip("\r" if decode_unicode else b"\r")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def __repr__(self):
        return f"<Response [{self.status_code}]>"


def _encode_params(params):
    if params is None:
        return ""
    if isinstance(params, (str, bytes)):
        return params.decode() if isinstance(params, bytes) else params
    items = params.items() if hasattr(params, "items") else params
    pairs = []
    for k, v in items:
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            pairs.extend((k, x) for x in v if x is not None)
        else:
            pairs.append((k, v))
    return urllib.parse.urlencode(pairs)


def _build_url(url, params):
    if not isinstance(url, str):
        url = str(url)
    url = url.strip()
    scheme = urllib.parse.urlsplit(url).scheme
    if not scheme:
        raise MissingSchema(f"Invalid URL '{url}': No scheme supplied. Perhaps you meant https://{url}?")
    if scheme not in ("http", "https"):
        raise InvalidSchema(f"No connection adapters were found for '{url}'")
    q = _encode_params(params)
    if q:
        url = url + ("&" if "?" in url else "?") + q
    return url


def _requests_request(method, url, params=None, data=None, headers=None, cookies=None, files=None,
                      auth=None, timeout=None, allow_redirects=True, proxies=None, hooks=None,
                      stream=None, verify=None, cert=None, json=None, _session_headers=None):
    method = str(method).upper()
    full = _build_url(url, params)
    h = CaseInsensitiveDict(_session_headers or {})
    for k, v in (headers or {}).items():
        if v is not None:
            h[k] = v
    body = None
    if files:
        raise NotImplementedError("requests: Datei-Uploads (files=...) werden im Browser nicht unterstützt.")
    if json is not None and data is None:
        import json as _json
        body = _json.dumps(json, default=_json_default)
        h.setdefault("Content-Type", "application/json")
    elif data is not None:
        if isinstance(data, dict) or (isinstance(data, (list, tuple)) and data and isinstance(data[0], tuple)):
            body = _encode_params(data)
            h.setdefault("Content-Type", "application/x-www-form-urlencoded")
        else:
            body = data
    if auth is not None and isinstance(auth, tuple) and len(auth) == 2:
        tok = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
        h["Authorization"] = f"Basic {tok}"
    if isinstance(timeout, tuple):
        timeout = sum(t for t in timeout if t) or None
    t0 = time.time()
    res = _http_sync(method, full, dict(h.items()), body, timeout, binary=True)
    req = PreparedRequest(method, full, body)
    if not res.get("status"):
        if res.get("timeout"):
            raise ReadTimeout(f"Zeitüberschreitung: {_host(full)} hat nicht innerhalb von {timeout} s geantwortet.",
                              request=req)
        raise _RConnectionError(_MSG_VERBINDUNG.format(host=_host(full)), request=req)
    r = Response()
    r.status_code = int(res["status"])
    r.headers = CaseInsensitiveDict(res.get("headers") or {})
    r.url = res.get("url") or full
    r.reason = res.get("statusText") or _reason(r.status_code)
    r._content = _res_bytes(res)
    r.elapsed = datetime.timedelta(seconds=time.time() - t0)
    r.request = req
    return r


def _reason(code):
    try:
        return http.HTTPStatus(code).phrase
    except Exception:
        return ""


class Session:
    def __init__(self):
        self.headers = CaseInsensitiveDict({"Accept": "*/*"})
        self.params = {}
        self.auth = None

    def request(self, method, url, **kw):
        if self.params:
            p = dict(self.params)
            p.update(kw.pop("params", None) or {})
            kw["params"] = p
        if self.auth is not None and "auth" not in kw:
            kw["auth"] = self.auth
        return _requests_request(method, url, _session_headers=dict(self.headers.items()), **kw)

    def get(self, url, params=None, **kw):
        return self.request("GET", url, params=params, **kw)

    def post(self, url, data=None, json=None, **kw):
        return self.request("POST", url, data=data, json=json, **kw)

    def put(self, url, data=None, **kw):
        return self.request("PUT", url, data=data, **kw)

    def patch(self, url, data=None, **kw):
        return self.request("PATCH", url, data=data, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)

    def head(self, url, **kw):
        return self.request("HEAD", url, **kw)

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


def _make_requests_module():
    m = types.ModuleType("requests")
    m.__doc__ = "Ersatz für requests im Browser (synchron über die Plattform)."
    m.__version__ = "2.32.4"
    exc = types.ModuleType("requests.exceptions")
    names = dict(RequestException=RequestException, HTTPError=HTTPError, ConnectionError=_RConnectionError,
                 ProxyError=ProxyError, SSLError=SSLError, Timeout=Timeout, ConnectTimeout=ConnectTimeout,
                 ReadTimeout=ReadTimeout, URLRequired=URLRequired, TooManyRedirects=TooManyRedirects,
                 MissingSchema=MissingSchema, InvalidSchema=InvalidSchema, InvalidURL=InvalidURL,
                 InvalidHeader=InvalidHeader, InvalidJSONError=InvalidJSONError, JSONDecodeError=_RJSONDecodeError,
                 ChunkedEncodingError=ChunkedEncodingError, ContentDecodingError=ContentDecodingError)
    for k, v in names.items():
        v.__module__ = "requests.exceptions"
        setattr(exc, k, v)
        setattr(m, k, v)
    for cls in (Response, Session, PreparedRequest):
        cls.__module__ = "requests"
    m.exceptions = exc
    m.Response, m.Session, m.PreparedRequest = Response, Session, PreparedRequest
    m.session = Session
    m.request = lambda method, url, **kw: _requests_request(method, url, **kw)
    m.get = lambda url, params=None, **kw: _requests_request("GET", url, params=params, **kw)
    m.post = lambda url, data=None, json=None, **kw: _requests_request("POST", url, data=data, json=json, **kw)
    m.put = lambda url, data=None, **kw: _requests_request("PUT", url, data=data, **kw)
    m.patch = lambda url, data=None, **kw: _requests_request("PATCH", url, data=data, **kw)
    m.delete = lambda url, **kw: _requests_request("DELETE", url, **kw)
    m.head = lambda url, **kw: _requests_request("HEAD", url, **kw)
    m.options = lambda url, **kw: _requests_request("OPTIONS", url, **kw)
    for n in ("request", "get", "post", "put", "patch", "delete", "head", "options"):
        getattr(m, n).__name__ = n
    structures = types.ModuleType("requests.structures")
    structures.CaseInsensitiveDict = CaseInsensitiveDict
    m.structures = structures
    m.codes = types.SimpleNamespace(ok=200, created=201, no_content=204, bad_request=400, unauthorized=401,
                                    forbidden=403, not_found=404, too_many_requests=429,
                                    internal_server_error=500)
    m.utils = types.ModuleType("requests.utils")
    m.utils.quote = urllib.parse.quote
    m.utils.unquote = urllib.parse.unquote
    return {"requests": m, "requests.exceptions": exc, "requests.structures": structures,
            "requests.utils": m.utils}


# ---------------------------------------------------------------------------
# 6. openai (Ersatzmodul, OpenAI-kompatible Schnittstelle)
# ---------------------------------------------------------------------------
OPENAI_VERSION = "3.24.0"


class NotGiven:
    def __bool__(self):
        return False

    def __repr__(self):
        return "NOT_GIVEN"


NOT_GIVEN = NotGiven()


class Omit:
    def __bool__(self):
        return False


omit = Omit()


def _given(v):
    return v is not None and not isinstance(v, (NotGiven, Omit))


class OpenAIError(Exception):
    pass


class _HttpxRequest:
    def __init__(self, method, url):
        self.method, self.url = method, url

    def __repr__(self):
        return f"<Request('{self.method}', '{self.url}')>"


class _HttpxResponse:
    def __init__(self, status_code, headers, text, request, url=None):
        self.status_code = status_code
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = text or ""
        self.request = request
        self.url = url or (request.url if request else None)
        self.reason_phrase = _reason(status_code)

    @property
    def content(self):
        return self.text.encode("utf-8")

    def json(self):
        return json.loads(self.text)

    def __repr__(self):
        return f"<Response [{self.status_code} {self.reason_phrase}]>"


class APIError(OpenAIError):
    def __init__(self, message, request=None, *, body=None):
        super().__init__(message)
        self.message = message
        self.request = request
        self.body = body
        if isinstance(body, dict):
            self.code, self.param, self.type = body.get("code"), body.get("param"), body.get("type")
        else:
            self.code = self.param = self.type = None


class APIResponseValidationError(APIError):
    def __init__(self, response, body, *, message=None):
        super().__init__(message or "Data returned by API invalid for expected schema.", response.request, body=body)
        self.response = response
        self.status_code = response.status_code


class APIStatusError(APIError):
    def __init__(self, message, *, response, body):
        super().__init__(message, response.request, body=body)
        self.response = response
        self.status_code = response.status_code
        self.request_id = response.headers.get("x-request-id")


class APIConnectionError(APIError):
    def __init__(self, *, message="Connection error.", request=None):
        super().__init__(message, request, body=None)


class APITimeoutError(APIConnectionError):
    def __init__(self, request=None, *, message="Request timed out."):
        super().__init__(message=message, request=request)


class BadRequestError(APIStatusError):
    status_code = 400


class AuthenticationError(APIStatusError):
    status_code = 401


class PermissionDeniedError(APIStatusError):
    status_code = 403


class NotFoundError(APIStatusError):
    status_code = 404


class ConflictError(APIStatusError):
    status_code = 409


class UnprocessableEntityError(APIStatusError):
    status_code = 422


class RateLimitError(APIStatusError):
    status_code = 429


class InternalServerError(APIStatusError):
    pass


class LengthFinishReasonError(OpenAIError):
    def __init__(self, *, completion=None):
        msg = "Could not parse response content as the length limit was reached"
        if completion is not None and getattr(completion, "usage", None):
            msg += f" - {completion.usage}"
        super().__init__(msg)
        self.completion = completion


class ContentFilterFinishReasonError(OpenAIError):
    def __init__(self):
        super().__init__("Could not parse response content as the request was rejected by the content filter")


_STATUS_ERRORS = {400: BadRequestError, 401: AuthenticationError, 403: PermissionDeniedError, 404: NotFoundError,
                  409: ConflictError, 422: UnprocessableEntityError, 429: RateLimitError}


def _make_status_error(resp):
    text = (resp.text or "").strip()
    try:
        body = json.loads(text) if text else None
    except Exception:
        body = text
    err_msg = f"Error code: {resp.status_code} - {body}"
    data = body.get("error", body) if isinstance(body, dict) else body
    cls = _STATUS_ERRORS.get(resp.status_code)
    if cls is None:
        cls = InternalServerError if resp.status_code >= 500 else APIStatusError
    return cls(err_msg, response=resp, body=data)


# --- Antwortobjekte ------------------------------------------------------------
def _dump_value(v, kw):
    if isinstance(v, APIObject):
        return v.model_dump(**kw)
    if hasattr(v, "model_dump") and callable(getattr(v, "model_dump")) and not isinstance(v, type):
        try:
            return v.model_dump(mode=kw.get("mode", "python"))
        except TypeError:
            return v.model_dump()
    if isinstance(v, list):
        return [_dump_value(x, kw) for x in v]
    if isinstance(v, tuple):
        return [_dump_value(x, kw) for x in v]
    if isinstance(v, dict):
        return {k: _dump_value(x, kw) for k, x in v.items()}
    return v


class APIObject:
    """Antwortobjekt mit Attributzugriff (verhält sich wie die Pydantic-Modelle des openai-Pakets)."""

    _fields = ()
    _types = {}

    def __init__(self, **data):
        object.__setattr__(self, "_lc_set", set(data))
        for f in self._fields:
            self.__dict__[f] = None
        for k, v in data.items():
            self.__dict__[k] = _construct(v, self._types.get(k))

    @classmethod
    def construct(cls, data):
        obj = cls.__new__(cls)
        object.__setattr__(obj, "_lc_set", set(data))
        for f in cls._fields:
            obj.__dict__[f] = None
        for k, v in data.items():
            obj.__dict__[str(k)] = _construct(v, cls._types.get(k))
        return obj

    model_construct = construct

    @classmethod
    def model_validate(cls, data, **kw):
        return cls.construct(dict(data))

    def __setattr__(self, k, v):
        self.__dict__[k] = v
        if not k.startswith("_"):
            self._lc_set.add(k)

    def _items(self):
        return [(k, v) for k, v in self.__dict__.items() if not k.startswith("_")]

    def __iter__(self):
        return iter(self._items())

    def model_dump(self, *, mode="python", include=None, exclude=None, by_alias=False, exclude_unset=False,
                   exclude_defaults=False, exclude_none=False, round_trip=False, warnings=True, **kw):
        sub = dict(mode=mode, exclude_unset=exclude_unset, exclude_none=exclude_none)
        out = {}
        for k, v in self._items():
            if exclude_unset and k not in self._lc_set:
                continue
            if exclude_none and v is None:
                continue
            if include is not None and k not in include:
                continue
            if exclude is not None and k in exclude:
                continue
            out[k] = _dump_value(v, sub)
        return out

    def model_dump_json(self, *, indent=None, **kw):
        kw.pop("mode", None)
        d = self.model_dump(mode="json", **kw)
        if indent is None:
            return json.dumps(d, ensure_ascii=False, separators=(",", ":"), default=_json_default)
        return json.dumps(d, ensure_ascii=False, indent=indent, default=_json_default)

    def to_dict(self, *, mode="python", use_api_names=True, exclude_unset=True, exclude_defaults=False,
                exclude_none=False, warnings=True):
        return self.model_dump(mode=mode, exclude_unset=exclude_unset, exclude_none=exclude_none)

    def to_json(self, *, indent=2, use_api_names=True, exclude_unset=True, exclude_defaults=False,
                exclude_none=False, warnings=True):
        return self.model_dump_json(indent=indent, exclude_unset=exclude_unset, exclude_none=exclude_none)

    def dict(self, **kw):
        return self.model_dump(**kw)

    def json(self, **kw):
        return self.model_dump_json(**kw)

    def model_copy(self, *, update=None, deep=False):
        import copy
        new = copy.deepcopy(self) if deep else copy.copy(self)
        object.__setattr__(new, "_lc_set", set(self._lc_set))
        for k, v in (update or {}).items():
            setattr(new, k, v)
        return new

    @property
    def model_fields_set(self):
        return set(self._lc_set)

    def __copy__(self):
        new = type(self).__new__(type(self))
        new.__dict__.update(self.__dict__)
        object.__setattr__(new, "_lc_set", set(self._lc_set))
        return new

    def __eq__(self, other):
        if type(other) is not type(self):
            return NotImplemented
        return self.model_dump() == other.model_dump()

    __hash__ = None

    def __repr__(self):
        inner = ", ".join(f"{k}={v!r}" for k, v in self._items())
        return f"{type(self).__name__}({inner})"

    def __rich_repr__(self):  # pragma: no cover
        yield from self._items()


def _construct(v, typ):
    if typ is None or v is None:
        return v
    if isinstance(v, list):
        return [_construct(x, typ) for x in v]
    if isinstance(v, dict):
        return typ.construct(v)
    return v


def _model(name, fields, types_=None, base=APIObject):
    cls = type(name, (base,), {"_fields": tuple(fields), "_types": dict(types_ or {})})
    cls.__module__ = "openai.types"
    return cls


Function = _model("Function", ["arguments", "name"])
ParsedFunction = _model("ParsedFunction", ["arguments", "name", "parsed_arguments"])
FunctionCall = _model("FunctionCall", ["arguments", "name"])
ChatCompletionMessageToolCall = _model("ChatCompletionMessageToolCall", ["id", "function", "type"],
                                       {"function": Function})
ParsedFunctionToolCall = _model("ParsedFunctionToolCall", ["id", "function", "type"], {"function": ParsedFunction})
ChatCompletionMessage = _model("ChatCompletionMessage",
                               ["content", "refusal", "role", "annotations", "audio", "function_call", "tool_calls"],
                               {"tool_calls": ChatCompletionMessageToolCall, "function_call": FunctionCall})
ParsedChatCompletionMessage = _model("ParsedChatCompletionMessage",
                                     list(ChatCompletionMessage._fields) + ["parsed"],
                                     {"tool_calls": ParsedFunctionToolCall, "function_call": FunctionCall})
ChoiceLogprobs = _model("ChoiceLogprobs", ["content", "refusal"])
Choice = _model("Choice", ["finish_reason", "index", "logprobs", "message"],
                {"message": ChatCompletionMessage, "logprobs": ChoiceLogprobs})
ParsedChoice = _model("ParsedChoice", ["finish_reason", "index", "logprobs", "message"],
                      {"message": ParsedChatCompletionMessage, "logprobs": ChoiceLogprobs})
CompletionTokensDetails = _model("CompletionTokensDetails", ["accepted_prediction_tokens", "audio_tokens",
                                                             "reasoning_tokens", "rejected_prediction_tokens"])
PromptTokensDetails = _model("PromptTokensDetails", ["audio_tokens", "cached_tokens"])
CompletionUsage = _model("CompletionUsage", ["completion_tokens", "prompt_tokens", "total_tokens",
                                             "completion_tokens_details", "prompt_tokens_details"],
                         {"completion_tokens_details": CompletionTokensDetails,
                          "prompt_tokens_details": PromptTokensDetails})
ChatCompletion = _model("ChatCompletion", ["id", "choices", "created", "model", "object", "service_tier",
                                           "system_fingerprint", "usage"],
                        {"choices": Choice, "usage": CompletionUsage})
ParsedChatCompletion = _model("ParsedChatCompletion", list(ChatCompletion._fields),
                              {"choices": ParsedChoice, "usage": CompletionUsage})
Embedding = _model("Embedding", ["embedding", "index", "object"])
EmbeddingUsage = _model("Usage", ["prompt_tokens", "total_tokens"])
CreateEmbeddingResponse = _model("CreateEmbeddingResponse", ["data", "model", "object", "usage"],
                                 {"data": Embedding, "usage": EmbeddingUsage})
Model = _model("Model", ["id", "created", "object", "owned_by"])


class SyncPage(APIObject):
    _fields = ("data", "object")
    _types = {"data": Model}

    def __iter__(self):
        return iter(self.data or [])

    def __len__(self):
        return len(self.data or [])

    def __getitem__(self, i):
        return (self.data or [])[i]

    def has_next_page(self):
        return False

    def iter_pages(self):
        yield self

    def _items(self):
        return [(k, v) for k, v in self.__dict__.items() if not k.startswith("_")]


SyncPage.__module__ = "openai.pagination"


class AsyncPage(SyncPage):
    def __aiter__(self):
        async def gen():
            for x in self.data or []:
                yield x
        return gen()


class AsyncPaginator:
    """Wie im openai-Paket: awaitbar (liefert die Seite) und mit ``async for`` durchlaufbar."""

    def __init__(self, coro_factory):
        self._factory = coro_factory

    def __await__(self):
        return self._factory().__await__()

    def __aiter__(self):
        async def gen():
            page = await self._factory()
            for x in page.data or []:
                yield x
        return gen()


# --- Strukturierte Ausgaben ------------------------------------------------------
def _is_basemodel_type(t):
    if not isinstance(t, type):
        return False
    return any(c.__name__ == "BaseModel" and c.__module__.startswith("pydantic") for c in t.__mro__)


def _resolve_ref(root, ref):
    if not ref.startswith("#/"):
        raise ValueError(f"Unexpected $ref format {ref!r}; Does not start with #/")
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _ensure_strict(schema, root):
    if not isinstance(schema, dict):
        return schema
    for key in ("$defs", "definitions"):
        defs = schema.get(key)
        if isinstance(defs, dict):
            for v in defs.values():
                _ensure_strict(v, root)
    if schema.get("type") == "object" and "additionalProperties" not in schema:
        schema["additionalProperties"] = False
    props = schema.get("properties")
    if isinstance(props, dict):
        schema["required"] = list(props.keys())
        for v in props.values():
            _ensure_strict(v, root)
    items = schema.get("items")
    if isinstance(items, dict):
        _ensure_strict(items, root)
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        schema["anyOf"] = [_ensure_strict(v, root) for v in any_of]
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        if len(all_of) == 1:
            schema.update(_ensure_strict(all_of[0], root))
            schema.pop("allOf")
        else:
            schema["allOf"] = [_ensure_strict(v, root) for v in all_of]
    if "default" in schema and schema["default"] is None:
        schema.pop("default")
    ref = schema.get("$ref")
    if ref and len(schema) > 1:
        resolved = _resolve_ref(root, ref)
        schema.pop("$ref")
        merged = {**resolved, **schema}
        schema.clear()
        schema.update(merged)
        return _ensure_strict(schema, root)
    return schema


def to_strict_json_schema(model):
    schema = model.model_json_schema() if _is_basemodel_type(model) else dict(model)
    return _ensure_strict(schema, schema)


def _type_to_response_format(rf):
    if not _given(rf):
        return NOT_GIVEN
    if isinstance(rf, dict):
        return rf
    if _is_basemodel_type(rf):
        return {"type": "json_schema",
                "json_schema": {"schema": to_strict_json_schema(rf), "name": rf.__name__, "strict": True}}
    raise TypeError(f"Unsupported response_format type - {rf}")


class PydanticFunctionTool(dict):
    def __init__(self, defn, model):
        super().__init__(defn)
        self.model = model

    def cast(self):
        return dict(self)


def pydantic_function_tool(model, *, name=None, description=None):
    if description is None:
        description = model.__doc__
    fn = {"name": name or model.__name__, "strict": True, "parameters": to_strict_json_schema(model)}
    if description is not None:
        fn["description"] = description
    return PydanticFunctionTool({"type": "function", "function": fn}, model)


# --- Anfragen bauen ---------------------------------------------------------------
_CHAT_PARAMS = {
    "audio", "frequency_penalty", "function_call", "functions", "logit_bias", "logprobs", "max_completion_tokens",
    "max_tokens", "metadata", "modalities", "n", "parallel_tool_calls", "prediction", "presence_penalty",
    "prompt_cache_key", "reasoning_effort", "response_format", "safety_identifier", "seed", "service_tier", "stop",
    "store", "stream", "stream_options", "temperature", "tool_choice", "tools", "top_logprobs", "top_p", "user",
    "verbosity", "web_search_options",
}
_REQ_OPTS = {"extra_headers", "extra_query", "extra_body", "timeout"}


def _msg_to_dict(m):
    if isinstance(m, APIObject):
        d = m.model_dump(exclude_none=True)
        d.pop("parsed", None)
        return d
    if hasattr(m, "model_dump") and callable(getattr(m, "model_dump")) and not isinstance(m, type):
        d = m.model_dump(exclude_none=True)
        d.pop("parsed", None)
        return d
    return m


def _prepare_messages(messages):
    if isinstance(messages, (str, bytes)) or not hasattr(messages, "__iter__"):
        raise TypeError("messages muss eine Liste von Nachrichten sein, z. B. "
                        "[{\"role\": \"user\", \"content\": \"Hallo\"}]")
    return [_msg_to_dict(m) for m in messages]


def _check_kwargs(fname, kwargs, allowed):
    for k in kwargs:
        if k not in allowed and k not in _REQ_OPTS:
            raise TypeError(f"{fname}() got an unexpected keyword argument '{k}'")


def _split_opts(kwargs):
    opts = {k: kwargs.pop(k) for k in list(kwargs) if k in _REQ_OPTS}
    return opts


def _chat_body(fname, messages, model, kwargs):
    _check_kwargs(fname, kwargs, _CHAT_PARAMS)
    opts = _split_opts(kwargs)
    if kwargs.get("stream") is True:
        raise OpenAIError("stream=True wird im Browser nicht unterstützt. Lass stream weg; "
                          "die Antwort kommt dann vollständig auf einmal.")
    rf = kwargs.get("response_format")
    if fname.endswith("create") and _is_basemodel_type(rf):
        raise TypeError("You tried to pass a `BaseModel` class to `chat.completions.create()`; "
                        "You must use `chat.completions.parse()` instead")
    body = {"messages": _prepare_messages(messages), "model": model}
    for k, v in kwargs.items():
        if _given(v):
            if k == "tools":
                v = [dict(t) if isinstance(t, PydanticFunctionTool) else t for t in v]
            body[k] = v
    return body, opts


def _parse_completion(data, response_format, tools, request_id):
    completion = ParsedChatCompletion.construct(data)
    object.__setattr__(completion, "_request_id", request_id)
    strict_tools = {}
    for t in (tools if _given(tools) else []) or []:
        if isinstance(t, dict) and t.get("type") == "function":
            fn = t.get("function") or {}
            if isinstance(t, PydanticFunctionTool):
                strict_tools[fn.get("name")] = t.model
            elif fn.get("strict"):
                strict_tools[fn.get("name")] = None
    for choice in completion.choices or []:
        if choice.finish_reason == "length":
            raise LengthFinishReasonError(completion=completion)
        if choice.finish_reason == "content_filter":
            raise ContentFilterFinishReasonError()
        msg = choice.message
        if msg is None:
            continue
        for tc in msg.tool_calls or []:
            name = getattr(tc.function, "name", None)
            if name in strict_tools:
                model = strict_tools[name]
                args = tc.function.arguments or "{}"
                tc.function.parsed_arguments = model.model_validate_json(args) if model else json.loads(args)
        if _is_basemodel_type(response_format) and msg.content and not msg.refusal:
            msg.parsed = response_format.model_validate_json(msg.content)
    return completion


# --- Ressourcen -------------------------------------------------------------------------
class _Resource:
    def __init__(self, client):
        self._client = client


class Completions(_Resource):
    def create(self, *, messages, model, **kwargs):
        body, opts = _chat_body("Completions.create", messages, model, kwargs)
        data, rid = self._client._post("/chat/completions", body, opts)
        obj = ChatCompletion.construct(data)
        object.__setattr__(obj, "_request_id", rid)
        return obj

    def parse(self, *, messages, model, response_format=NOT_GIVEN, tools=NOT_GIVEN, **kwargs):
        kwargs["response_format"] = _type_to_response_format(response_format)
        kwargs["tools"] = tools
        body, opts = _chat_body("Completions.parse", messages, model, kwargs)
        data, rid = self._client._post("/chat/completions", body, opts)
        return _parse_completion(data, response_format, tools, rid)


class AsyncCompletions(_Resource):
    async def create(self, *, messages, model, **kwargs):
        body, opts = _chat_body("AsyncCompletions.create", messages, model, kwargs)
        data, rid = await self._client._post("/chat/completions", body, opts)
        obj = ChatCompletion.construct(data)
        object.__setattr__(obj, "_request_id", rid)
        return obj

    async def parse(self, *, messages, model, response_format=NOT_GIVEN, tools=NOT_GIVEN, **kwargs):
        kwargs["response_format"] = _type_to_response_format(response_format)
        kwargs["tools"] = tools
        body, opts = _chat_body("AsyncCompletions.parse", messages, model, kwargs)
        data, rid = await self._client._post("/chat/completions", body, opts)
        return _parse_completion(data, response_format, tools, rid)


class Chat(_Resource):
    def __init__(self, client, completions_cls):
        super().__init__(client)
        self.completions = completions_cls(client)


class Beta(_Resource):
    def __init__(self, client, completions_cls):
        super().__init__(client)
        self.chat = Chat(client, completions_cls)


def _embedding_body(kwargs, input, model):
    _check_kwargs("Embeddings.create", kwargs, {"dimensions", "encoding_format", "user"})
    opts = _split_opts(kwargs)
    body = {"input": input, "model": model}
    for k, v in kwargs.items():
        if _given(v):
            body[k] = v
    body.setdefault("encoding_format", "float")
    return body, opts


def _embedding_result(data, rid):
    for d in data.get("data") or []:
        e = d.get("embedding")
        if isinstance(e, str):   # base64-kodierte float32
            import struct
            raw = base64.b64decode(e)
            d["embedding"] = list(struct.unpack(f"<{len(raw) // 4}f", raw))
    obj = CreateEmbeddingResponse.construct(data)
    object.__setattr__(obj, "_request_id", rid)
    return obj


class Embeddings(_Resource):
    def create(self, *, input, model, **kwargs):
        body, opts = _embedding_body(kwargs, input, model)
        data, rid = self._client._post("/embeddings", body, opts)
        return _embedding_result(data, rid)


class AsyncEmbeddings(_Resource):
    async def create(self, *, input, model, **kwargs):
        body, opts = _embedding_body(kwargs, input, model)
        data, rid = await self._client._post("/embeddings", body, opts)
        return _embedding_result(data, rid)


class Models(_Resource):
    def list(self, **opts):
        _check_kwargs("Models.list", opts, set())
        data, rid = self._client._get("/models", opts)
        return SyncPage.construct(data)

    def retrieve(self, model, **opts):
        _check_kwargs("Models.retrieve", opts, set())
        data, rid = self._client._get(f"/models/{model}", opts)
        return Model.construct(data)


class AsyncModels(_Resource):
    def list(self, **opts):
        _check_kwargs("AsyncModels.list", opts, set())

        async def load():
            data, rid = await self._client._get("/models", opts)
            return AsyncPage.construct(data)
        return AsyncPaginator(load)

    async def retrieve(self, model, **opts):
        _check_kwargs("AsyncModels.retrieve", opts, set())
        data, rid = await self._client._get(f"/models/{model}", opts)
        return Model.construct(data)


# --- Clients ------------------------------------------------------------------------------
def _timeout_seconds(t, default):
    if not _given(t):
        return default
    if hasattr(t, "read"):
        return getattr(t, "read", None) or default
    try:
        return float(t)
    except Exception:
        return default


class _BaseClient:
    _async = False

    def __init__(self, *, api_key=None, organization=None, project=None, webhook_secret=None, base_url=None,
                 websocket_base_url=None, timeout=NOT_GIVEN, max_retries=2, default_headers=None,
                 default_query=None, http_client=None, _strict_response_validation=False, **ignored):
        if api_key is None:
            api_key = os.environ.get("OPENAI_API_KEY")
        if api_key is None:
            raise OpenAIError(
                "The api_key client option must be set either by passing api_key to the client or by "
                "setting the OPENAI_API_KEY environment variable"
            )
        if callable(api_key):
            api_key = api_key()
        self.api_key = api_key
        self.organization = organization if organization is not None else os.environ.get("OPENAI_ORG_ID")
        self.project = project if project is not None else os.environ.get("OPENAI_PROJECT_ID")
        if base_url is None:
            base_url = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
        base_url = str(base_url)
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.timeout = _timeout_seconds(timeout, 600.0)
        self.max_retries = max_retries      # wird bewusst nicht genutzt: keine automatischen Wiederholungen
        self._default_headers = dict(default_headers or {})
        self._default_query = dict(default_query or {})
        self._init_kwargs = dict(api_key=api_key, organization=organization, project=project, base_url=base_url,
                                 timeout=timeout, max_retries=max_retries, default_headers=default_headers,
                                 default_query=default_query)

    # Schlüssel nie in repr
    def __repr__(self):
        return f"<openai.{type(self).__name__} base_url='{self.base_url}'>"

    def with_options(self, **kw):
        args = dict(self._init_kwargs)
        args.update(kw)
        return type(self)(**args)

    copy = with_options

    def _headers(self, extra):
        h = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if self.organization:
            h["OpenAI-Organization"] = self.organization
        if self.project:
            h["OpenAI-Project"] = self.project
        h.update(self._default_headers)
        for k, v in (extra or {}).items():
            if v is None:
                h.pop(k, None)
            else:
                h[k] = v
        return h

    def _url(self, path, extra_query):
        url = self.base_url.rstrip("/") + path
        q = dict(self._default_query)
        q.update(extra_query or {})
        if q:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(q, doseq=True)
        return url

    def _prepare(self, method, path, body, opts):
        url = self._url(path, opts.get("extra_query"))
        headers = self._headers(opts.get("extra_headers"))
        if body is not None:
            eb = opts.get("extra_body")
            if eb:
                body = {**body, **eb}
            data = json.dumps(body, ensure_ascii=False, default=_json_default)
        else:
            data = None
            headers.pop("Content-Type", None)
        timeout = _timeout_seconds(opts.get("timeout", NOT_GIVEN), self.timeout)
        return url, headers, data, timeout

    def _handle(self, method, url, res, timeout):
        req = _HttpxRequest(method, url)
        status = int(res.get("status") or 0)
        if status == 0:
            if res.get("timeout"):
                raise APITimeoutError(req, message=(
                    f"Request timed out. Zeitüberschreitung: {_host(url)} hat nicht innerhalb von "
                    f"{timeout:g} s geantwortet."))
            raise APIConnectionError(message=_MSG_VERBINDUNG.format(host=_host(url)), request=req)
        resp = _HttpxResponse(status, res.get("headers"), res.get("text"), req, res.get("url"))
        if status >= 400:
            raise _make_status_error(resp)
        try:
            data = json.loads(resp.text) if resp.text.strip() else {}
        except Exception:
            raise APIResponseValidationError(resp, resp.text, message=(
                "Die Antwort des Servers ist kein gültiges JSON (stimmt base_url? Sie muss meist auf /v1 enden)."))
        if not isinstance(data, dict):
            raise APIResponseValidationError(resp, data)
        return data, resp.headers.get("x-request-id")

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class OpenAI(_BaseClient):
    """Ersatz für openai.OpenAI im Browser (gleiche Schnittstelle für Chat, Parse, Embeddings, Modelle)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.chat = Chat(self, Completions)
        self.beta = Beta(self, Completions)
        self.embeddings = Embeddings(self)
        self.models = Models(self)

    def _post(self, path, body, opts):
        url, headers, data, timeout = self._prepare("POST", path, body, opts)
        res = _http_sync("POST", url, headers, data, timeout)
        return self._handle("POST", url, res, timeout)

    def _get(self, path, opts):
        url, headers, data, timeout = self._prepare("GET", path, None, opts)
        res = _http_sync("GET", url, headers, None, timeout)
        return self._handle("GET", url, res, timeout)


class AsyncOpenAI(_BaseClient):
    """Ersatz für openai.AsyncOpenAI im Browser (asynchron über fetch)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.chat = Chat(self, AsyncCompletions)
        self.beta = Beta(self, AsyncCompletions)
        self.embeddings = AsyncEmbeddings(self)
        self.models = AsyncModels(self)

    async def _post(self, path, body, opts):
        url, headers, data, timeout = self._prepare("POST", path, body, opts)
        res = await _http_async("POST", url, headers, data, timeout)
        return self._handle("POST", url, res, timeout)

    async def _get(self, path, opts):
        url, headers, data, timeout = self._prepare("GET", path, None, opts)
        res = await _http_async("GET", url, headers, None, timeout)
        return self._handle("GET", url, res, timeout)

    async def close(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        pass


def _make_openai_module():
    m = types.ModuleType("openai")
    m.__doc__ = "Ersatz für das openai-Paket im Browser (OpenAI-kompatible Schnittstelle, ohne Streaming)."
    m.__version__ = OPENAI_VERSION
    m.VERSION = OPENAI_VERSION
    exported = dict(
        OpenAI=OpenAI, AsyncOpenAI=AsyncOpenAI, OpenAIError=OpenAIError, APIError=APIError,
        APIStatusError=APIStatusError, APIConnectionError=APIConnectionError, APITimeoutError=APITimeoutError,
        APIResponseValidationError=APIResponseValidationError, BadRequestError=BadRequestError,
        AuthenticationError=AuthenticationError, PermissionDeniedError=PermissionDeniedError,
        NotFoundError=NotFoundError, ConflictError=ConflictError, UnprocessableEntityError=UnprocessableEntityError,
        RateLimitError=RateLimitError, InternalServerError=InternalServerError,
        LengthFinishReasonError=LengthFinishReasonError, ContentFilterFinishReasonError=ContentFilterFinishReasonError,
        NOT_GIVEN=NOT_GIVEN, NotGiven=NotGiven, Omit=Omit, omit=omit, pydantic_function_tool=pydantic_function_tool,
        BaseModel=APIObject,
    )
    for k, v in exported.items():
        if isinstance(v, type) and v.__module__ == __name__:
            v.__module__ = "openai"
        setattr(m, k, v)
    for cls in (Completions, AsyncCompletions, Chat, Beta, Embeddings, AsyncEmbeddings, Models, AsyncModels):
        cls.__module__ = "openai.resources"
    # openai.types (für Typ-Annotationen und isinstance)
    t = types.ModuleType("openai.types")
    tc = types.ModuleType("openai.types.chat")
    for cls in (ChatCompletion, ChatCompletionMessage, ChatCompletionMessageToolCall, ParsedChatCompletion,
                ParsedChatCompletionMessage, ParsedChoice, Choice, CompletionUsage):
        setattr(tc, cls.__name__, cls)
    tc.ChatCompletionMessageParam = dict
    tc.ChatCompletionToolParam = dict
    for cls in (CreateEmbeddingResponse, Embedding, Model, CompletionUsage):
        setattr(t, cls.__name__, cls)
    t.chat = tc
    m.types = t
    lib = types.ModuleType("openai.lib")
    lib._pydantic = types.SimpleNamespace(to_strict_json_schema=to_strict_json_schema)
    m.lib = lib
    return {"openai": m, "openai.types": t, "openai.types.chat": tc, "openai.lib": lib}


# ---------------------------------------------------------------------------
# 7. google.colab
# ---------------------------------------------------------------------------
_MSG_KEIN_SCHLUESSEL = "Kein Schlüssel hinterlegt. Trag ihn in den Kurs-Einstellungen ein (Schlüssel-Symbol oben rechts)."


class SecretNotFoundError(Exception):
    pass


class NotebookAccessError(Exception):
    pass


class TimeoutException(Exception):
    pass


def _get_secret(name):
    try:
        import _lc_js  # vom Runner registriertes JS-Modul
        v = _lc_js.getSecret(str(name))
    except Exception:
        v = None
    return v if isinstance(v, str) and v != "" else None


def _userdata_get(key):
    """Liest einen Schlüssel aus dem Schlüsselspeicher der Plattform (wie google.colab.userdata.get)."""
    v = _get_secret(key)
    if v is None:
        raise SecretNotFoundError(_MSG_KEIN_SCHLUESSEL)
    return v


def _files_upload(target_dir="", *args, **kwargs):
    print("ℹ️ Datei-Upload aus dem Notebook geht im Browser nicht. Lade Dateien über den Dateibereich "
          "des Kurses hoch; sie liegen dann im Arbeitsordner " + HOME + ". Danach die Zelle erneut ausführen.")
    return {}


def _files_download(filename):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Cannot find file: {filename}")
    with open(filename, "rb") as f:
        data = f.read()
    fn = _js_fn("lcDownload")
    if fn is not None:
        fn(os.path.basename(filename), to_js(data))
    else:
        print(f"ℹ️ {os.path.basename(filename)} liegt im Arbeitsordner und kann im Dateibereich "
              "des Kurses heruntergeladen werden.")


def _drive_mount(mountpoint="/content/drive", *args, **kwargs):
    raise NotImplementedError("Google Drive ist auf der Plattform nicht verfügbar. "
                              "Lade Dateien über den Dateibereich des Kurses hoch.")


def _make_colab_modules():
    google = types.ModuleType("google")
    google.__path__ = []
    colab = types.ModuleType("google.colab")
    colab.__path__ = []
    ud = types.ModuleType("google.colab.userdata")
    ud.get = _userdata_get
    ud.SecretNotFoundError = SecretNotFoundError
    ud.NotebookAccessError = NotebookAccessError
    ud.TimeoutException = TimeoutException
    for c in (SecretNotFoundError, NotebookAccessError, TimeoutException):
        c.__module__ = "google.colab.userdata"
    files = types.ModuleType("google.colab.files")
    files.upload = _files_upload
    files.download = _files_download
    drive = types.ModuleType("google.colab.drive")
    drive.mount = _drive_mount
    drive.flush_and_unmount = lambda *a, **k: None
    output = types.ModuleType("google.colab.output")
    output.clear = lambda *a, **k: None
    output.enable_custom_widget_manager = lambda *a, **k: None
    output.eval_js = lambda *a, **k: None
    google.colab = colab
    colab.userdata, colab.files, colab.drive, colab.output = ud, files, drive, output
    return {"google": google, "google.colab": colab, "google.colab.userdata": ud,
            "google.colab.files": files, "google.colab.drive": drive, "google.colab.output": output}


def _make_ipython_modules():
    ip = types.ModuleType("IPython")
    ip.__path__ = []
    ip.__version__ = "8.0.0-lc"
    disp = types.ModuleType("IPython.display")
    for name, obj in dict(display=display, HTML=HTML, Markdown=Markdown, Image=Image, SVG=SVG, JSON=JSON,
                          Latex=Latex, Pretty=Pretty, Javascript=Javascript, IFrame=IFrame, FileLink=FileLink,
                          clear_output=clear_output, DisplayHandle=DisplayHandle).items():
        setattr(disp, name, obj)
        if isinstance(obj, type):
            obj.__module__ = "IPython.display"
    ip.display = disp
    ip.get_ipython = get_ipython
    core = types.ModuleType("IPython.core")
    core.__path__ = []
    core_display = types.ModuleType("IPython.core.display")
    core_display.__dict__.update({k: v for k, v in disp.__dict__.items() if not k.startswith("__")})
    core.display = core_display
    ip.core = core
    return {"IPython": ip, "IPython.display": disp, "IPython.core": core, "IPython.core.display": core_display}


# ---------------------------------------------------------------------------
# 8. Import-Hooks
# ---------------------------------------------------------------------------
BLOCKED = {
    # laut Kurs: im Browser nicht lauffähig
    "torch", "transformers", "sentence_transformers", "chromadb", "fastmcp", "langgraph", "langchain_core",
    "langchain_openai", "gradio", "tiktoken",
    # weitere, ebenfalls nicht lauffähig (native Erweiterungen, Server, GPU)
    "langchain", "langchain_community", "langchain_text_splitters", "mcp", "tensorflow", "keras", "jax",
    "faiss", "huggingface_hub", "datasets", "accelerate", "torchvision", "uvicorn", "fastapi", "streamlit",
}

# Import-Name → Paket in der gekürzten pyodide-lock.json (für Nachladen bei Bedarf)
HOSTED = {
    "numpy": "numpy", "pandas": "pandas", "matplotlib": "matplotlib", "mpl_toolkits": "matplotlib",
    "pylab": "matplotlib", "pydantic": "pydantic", "pydantic_core": "pydantic-core", "PIL": "pillow",
    "dateutil": "python-dateutil", "pytz": "pytz", "six": "six", "cycler": "cycler", "kiwisolver": "kiwisolver",
    "contourpy": "contourpy", "fontTools": "fonttools", "pyparsing": "pyparsing", "packaging": "packaging",
    "typing_extensions": "typing-extensions", "typing_inspection": "typing-inspection",
    "annotated_types": "annotated-types", "rank_bm25": "rank-bm25", "seaborn": "seaborn",
}


def _blocked_error(name):
    e = ModuleNotFoundError(f"{name} läuft nicht im Browser. {LANG_HINT_COLAB}", name=name)
    e._PYODIDE_ADDED_NOTE = True
    e._lc_blocked = True
    return e


class _BlockFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.partition(".")[0]
        if top in BLOCKED:
            raise _blocked_error(top)
        return None


class _OnDemandFinder(importlib.abc.MetaPathFinder):
    """Lädt gehostete Pakete nach, die nicht vorab erkannt wurden (z. B. Import in einer %%writefile-Datei).
    Geht nur mit JSPI; sonst normaler ModuleNotFoundError."""

    def find_spec(self, fullname, path=None, target=None):
        if path is not None or "." in fullname or fullname not in HOSTED or not _can_run_sync():
            return None
        try:
            import _lc_js
            _pyo_run_sync(_lc_js.loadPackage(HOSTED[fullname]))
            importlib.invalidate_caches()
            return importlib.machinery.PathFinder.find_spec(fullname, None, target)
        except Exception:
            return None


def _install_import_hooks():
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, (_BlockFinder, _PostImportFinder,
                                                                        _OnDemandFinder))]
    sys.meta_path.insert(0, _BlockFinder())
    sys.meta_path.insert(1, _PostImportFinder())
    sys.meta_path.append(_OnDemandFinder())


# ---------------------------------------------------------------------------
# 9. Magics (von lc-runner.js in Aufrufe von __lc_magic__ umgeschrieben)
# ---------------------------------------------------------------------------
SHIMMED_PIP = {"openai": "Ersatz der Plattform", "requests": "Ersatz der Plattform",
               "ipython": "Ersatz der Plattform"}
HOSTED_PIP = {"numpy", "pandas", "matplotlib", "pydantic", "pydantic-core", "rank-bm25", "typing-extensions",
              "annotated-types", "typing-inspection", "pillow", "python-dateutil", "pytz", "six", "cycler",
              "kiwisolver", "contourpy", "fonttools", "pyparsing", "packaging"}
BLOCKED_PIP = {"torch", "transformers", "sentence-transformers", "chromadb", "fastmcp", "langgraph",
               "langchain-openai", "langchain-core", "langchain", "langchain-community", "gradio", "tiktoken",
               "mcp", "tensorflow", "keras", "jax", "faiss-cpu", "huggingface-hub", "datasets", "accelerate",
               "torchvision", "uvicorn", "fastapi", "streamlit"}


def _pip_name(token):
    name = re.split(r"[\[=<>!~;@ ]", token, maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", name).lower()


def _pip_magic(args):
    toks = [t for t in args if t and not t.startswith("-")]
    if not toks or toks[0] not in ("install", "uninstall"):
        print("ℹ️ pip ist im Browser nicht nötig. Verfügbar sind numpy, pandas, matplotlib, pydantic, rank-bm25 "
              "sowie Ersatzmodule für openai und requests.")
        return
    if toks[0] == "uninstall":
        print("ℹ️ Deinstallieren ist im Browser nicht möglich und nicht nötig.")
        return
    bereit, fehlt, unbekannt = [], [], []
    for t in toks[1:]:
        if t.startswith(("http:", "https:", "git+", "/", ".")) or t.endswith((".whl", ".txt")):
            unbekannt.append(t)
            continue
        n = _pip_name(t)
        if n in SHIMMED_PIP:
            bereit.append(f"{n} ({SHIMMED_PIP[n]})")
        elif n in HOSTED_PIP:
            bereit.append(n)
        elif n in BLOCKED_PIP:
            fehlt.append(n)
        else:
            unbekannt.append(n)
    if bereit:
        print("✓ Im Browser ist keine Installation nötig, bereit: " + ", ".join(bereit) + ".")
    if fehlt:
        print("⚠️ Läuft nicht im Browser: " + ", ".join(fehlt) + ". Zellen, die das brauchen, bitte in Colab ausführen.")
    if unbekannt:
        print("⚠️ Auf der Plattform nicht verfügbar: " + ", ".join(unbekannt) + ".")


def _magic(line):
    """Führt eine Zeilen-Magic aus (%pip, !pip, %cd, %pwd, %env, !ls, !cat …)."""
    line = line.strip()
    kind, cmd = line[0], line[1:].strip()
    if kind == "%" and cmd.startswith("%"):
        print(f"ℹ️ Die Zellen-Magic „{line.split()[0]}“ muss in der ersten Zeile der Zelle stehen.")
        return None
    parts = cmd.split()
    if not parts:
        return None
    name, args = parts[0], parts[1:]
    if name in ("pip", "pip3", "conda", "mamba", "uv") or (name in ("python", "python3") and args[:2] == ["-m", "pip"]):
        if name in ("python", "python3"):
            args = args[2:]
        elif name == "uv" and args[:1] == ["pip"]:
            args = args[1:]
        _pip_magic(args)
        return None
    if name in ("matplotlib", "config", "load_ext", "reload_ext", "autoreload", "capture"):
        return None
    if name == "cd":
        target = os.path.expanduser(args[0]) if args else HOME
        os.chdir(target)
        print(os.getcwd())
        return None
    if name == "pwd":
        return os.getcwd()
    if name == "env" and kind == "%":
        if not args:
            return dict(os.environ)
        rest = cmd[3:].strip()
        if "=" in rest:
            k, v = rest.split("=", 1)
            os.environ[k.strip()] = v.strip()
        else:
            return os.environ.get(rest)
        return None
    if name == "ls":
        target = next((a for a in args if not a.startswith("-")), ".")
        for e in sorted(os.listdir(target)):
            print(e + ("/" if os.path.isdir(os.path.join(target, e)) else ""))
        return None
    if name == "cat" and args:
        for a in args:
            with open(a, encoding="utf-8", errors="replace") as f:
                sys.stdout.write(f.read())
        return None
    if name == "mkdir" and args:
        for a in args:
            if not a.startswith("-"):
                os.makedirs(a, exist_ok=True)
        return None
    if name == "time" and kind == "%":
        code = cmd[4:].strip()
        t0 = time.perf_counter()
        exec(compile(code, "<zelle>", "exec"), G)
        print(f"Wall time: {(time.perf_counter() - t0) * 1000:.1f} ms")
        return None
    if kind == "!":
        print(f"ℹ️ Der Befehl „!{name}“ läuft im Browser nicht (keine Kommandozeile). {LANG_HINT_COLAB}")
    else:
        print(f"ℹ️ Die Magic „%{name}“ wird auf der Plattform nicht unterstützt.")
    return None


def lc_writefile(name, content, append=False):
    """%%writefile: schreibt den Zellinhalt in eine Datei im Arbeitsordner."""
    name = name.strip().strip("'\"")
    path = os.path.expanduser(name)
    existed = os.path.exists(path)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    if content and not content.endswith("\n"):
        content += "\n"
    with open(path, "a" if append else "w", encoding="utf-8") as f:
        f.write(content)
    importlib.invalidate_caches()
    if append:
        print(f"Appending to {name}")
    else:
        print(f"{'Overwriting' if existed else 'Writing'} {name}")


# ---------------------------------------------------------------------------
# 10. Ausführung
# ---------------------------------------------------------------------------
_main = None
G = {}


def _new_namespace():
    global _main, G
    _main = types.ModuleType("__main__")
    _main.__dict__.update({"__builtins__": builtins, "__name__": "__main__", "__doc__": None})
    sys.modules["__main__"] = _main
    G = _main.__dict__
    return G


def _is_user_file(fn):
    if not fn:
        return False
    if fn.startswith("<zelle"):
        return True
    if fn.startswith("<"):
        return False
    if fn.startswith(("/lib/", "/lc/", "/usr/")) or "site-packages" in fn:
        return False
    return True


_HINT_MODUL = ("Hinweis: Im Browser stehen numpy, pandas, matplotlib, pydantic und rank_bm25 bereit, dazu "
               "Ersatzmodule für openai, requests, google.colab und IPython. Andere Pakete bitte in Colab nutzen. "
               "Eigene Module zuerst mit %%writefile anlegen.")


def _format_exception(e):
    if isinstance(e, KeyboardInterrupt):
        return "KeyboardInterrupt: Ausführung abgebrochen.\n"
    frames = [f for f in traceback.extract_tb(e.__traceback__) if _is_user_file(f.filename)]
    lines = []
    if frames:
        lines.append("Traceback (most recent call last):\n")
        lines.extend(traceback.format_list(frames))
    lines.extend(traceback.format_exception_only(type(e), e))
    if isinstance(e, ModuleNotFoundError) and not getattr(e, "_lc_blocked", False):
        top = (e.name or "").partition(".")[0]
        if top and top not in HOSTED and top not in sys.stdlib_module_names:
            lines.append(_HINT_MODUL + "\n")
    return "".join(lines)


async def lc_run(code, filename="<zelle>"):
    """Führt eine Zelle aus. Gibt None (Erfolg) oder einen JSON-Text mit Fehlerinfos zurück."""
    try:
        result = await eval_code_async(code, globals=G, filename=filename)
        if result is not None:
            G["_"] = result
            _show_value(result)
        _flush_figures()
        return None
    except BaseException as e:  # noqa: B036 – auch KeyboardInterrupt/SystemExit sauber melden
        try:
            _flush_figures()
        except Exception:
            pass
        text = _format_exception(e)
        _emit("error", text)
        try:
            msg = str(e)
        except Exception:
            msg = ""
        return json.dumps({"ename": type(e).__name__, "evalue": msg,
                           "error": f"{type(e).__name__}: {msg}" if msg else type(e).__name__,
                           "traceback": text}, ensure_ascii=False)
    finally:
        _flush_std()


def lc_reset():
    """Leert den Namensraum, schließt Abbildungen und vergisst eigene Module (Dateien bleiben)."""
    plt = sys.modules.get("matplotlib.pyplot")
    if plt is not None:
        try:
            plt.close("all")
        except Exception:
            pass
    for name, mod in list(sys.modules.items()):
        fn = getattr(mod, "__file__", None) or ""
        if fn and _is_user_file(fn) and fn.startswith(HOME):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()
    _new_namespace()
    os.chdir(HOME)


def lc_imports(code):
    """Top-Level-Importnamen eines Codes (für das Vorladen von Paketen)."""
    try:
        return list(find_imports(code))
    except Exception:
        return []


def lc_set_options(use_run_sync=True):
    global USE_RUN_SYNC
    USE_RUN_SYNC = bool(use_run_sync)


def lc_info():
    return json.dumps({"python": sys.version.split()[0], "jspi": _can_run_sync(),
                       "use_run_sync": USE_RUN_SYNC, "cwd": os.getcwd()})


# ---------------------------------------------------------------------------
# 11. Start
# ---------------------------------------------------------------------------
def _write_dist_info():
    """Paket-Metadaten der Ersatzmodule, damit importlib.metadata.version("openai") wie in Colab antwortet."""
    base = "/lc/meta"
    try:
        for name, ver in (("openai", OPENAI_VERSION), ("requests", "2.32.4")):
            d = f"{base}/{name}-{ver}.dist-info"
            os.makedirs(d, exist_ok=True)
            with open(f"{d}/METADATA", "w", encoding="utf-8") as f:
                f.write(f"Metadata-Version: 2.1\nName: {name}\nVersion: {ver}\n"
                        "Summary: Ersatzmodul der Lernplattform (Browser)\n")
        if base not in sys.path:
            sys.path.append(base)
    except OSError:
        pass


def _boot():
    for mods in (_make_openai_module(), _make_requests_module(), _make_colab_modules(), _make_ipython_modules()):
        sys.modules.update(mods)
    _write_dist_info()
    builtins.display = display
    builtins.input = _input
    builtins.__lc_magic__ = _magic
    _install_import_hooks()
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(line_buffering=True)
        except Exception:
            pass
    _new_namespace()


_boot()
