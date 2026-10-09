/*
 * lc-runner.js – Python im Browser (Pyodide 0.29.5) für die Kurs-Notebooks.
 * Klassisches Script, definiert window.LCPy. Alles same-origin unter py/, kein CDN, kein Worker.
 *
 *   await LCPy.init({base: "py/", onStatus: text => …})
 *   const r = await LCPy.run(code, (kind, data) => …)   // kind: stdout|stderr|text|html|markdown|png|error
 *   r → {ok: true} | {ok: false, error: "TypeError: …", ename, traceback}
 *
 * Weitere API: LCPy.setSecrets(obj), LCPy.reset(), LCPy.writeFile(pfad, daten), LCPy.readFile(pfad),
 * LCPy.listFiles(ordner), LCPy.unpackZip(arrayBuffer, zielordner), LCPy.loadPackages(namen),
 * LCPy.interrupt(), LCPy.ready, LCPy.busy, LCPy.info().
 * Optionale Hooks, die die Oberfläche setzen kann: window.lcInput(prompt) → string | Promise<string>,
 * window.lcDownload(name, Uint8Array).
 * Schlüssel liegen nur im Speicher dieses Scripts und werden nie geloggt.
 */
(function () {
  "use strict";
  if (window.LCPy && window.LCPy.__lc) return;

  var HOME = "/home/pyodide";
  var MAX_TEXT_PER_RUN = 2 * 1024 * 1024; // Schutz vor endlosen Ausgaben (DOM)

  var pyodide = null;
  var boot = null;
  var lcRun = null;
  var initPromise = null;
  var statusCb = null;
  var currentEmit = null;
  var queue = Promise.resolve();
  var secrets = Object.create(null);
  var interruptFlag = false;
  var controllers = new Set();
  var lockNames = new Set();
  var baseURL = null;
  var state = { ready: false, busy: false, broken: false };
  var timings = {};

  // ------------------------------------------------------------------ Status
  function status(text) {
    if (typeof statusCb === "function") {
      try { statusCb(String(text)); } catch (e) { /* Oberfläche */ }
    }
  }

  // ------------------------------------------------------------------ Ausgabe
  var segs = [];
  var decoders = { stdout: new TextDecoder(), stderr: new TextDecoder() };
  var flushTimer = null;
  var textCount = 0;
  var truncated = false;

  function redact(data) {
    if (typeof data !== "string") return data;
    for (var k in secrets) {
      var v = secrets[k];
      if (v && v.length >= 6 && data.indexOf(v) !== -1) data = data.split(v).join("[Schlüssel ausgeblendet]");
    }
    return data;
  }

  function deliver(kind, data) {
    var fn = currentEmit;
    if (!fn) return;
    if (kind === "stdout" || kind === "stderr" || kind === "text") {
      if (truncated) return;
      textCount += data.length;
      if (textCount > MAX_TEXT_PER_RUN) {
        truncated = true;
        data = "\n… Ausgabe gekürzt (mehr als 2 MB Text in dieser Zelle).\n";
        kind = "stderr";
      }
    }
    if (kind !== "png") data = redact(data);
    try { fn(kind, data); } catch (e) { /* Fehler der Oberfläche nicht an Python weitergeben */ }
  }

  function stdWrite(kind, buf) {
    var text = decoders[kind].decode(buf, { stream: true });
    if (text) {
      var last = segs[segs.length - 1];
      if (last && last[0] === kind) last[1] += text;
      else segs.push([kind, text]);
      if (!flushTimer) flushTimer = setTimeout(flushStd, 25);
    }
    return buf.length;
  }

  function flushStd() {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    while (segs.length) {
      var s = segs.shift();
      deliver(s[0], s[1]);
    }
  }

  // Brücke Python → Oberfläche
  globalThis.lcEmit = function (kind, data) {
    flushStd();
    deliver(String(kind), data == null ? "" : String(data));
  };

  // ------------------------------------------------------------------ HTTP
  var UNSAFE = new Set(["accept-charset", "accept-encoding", "access-control-request-headers",
    "access-control-request-method", "connection", "content-length", "cookie", "cookie2", "date", "dnt",
    "expect", "host", "keep-alive", "origin", "referer", "te", "trailer", "transfer-encoding", "upgrade",
    "user-agent", "via"]);

  function safeHeaders(json) {
    var h = {};
    try { h = json ? JSON.parse(String(json)) : {}; } catch (e) { h = {}; }
    var out = {};
    Object.keys(h).forEach(function (k) {
      var lk = k.toLowerCase();
      if (UNSAFE.has(lk) || lk.indexOf("sec-") === 0 || lk.indexOf("proxy-") === 0) return;
      if (h[k] == null) return;
      out[k] = String(h[k]);
    });
    return out;
  }

  function parseHeaders(raw) {
    var h = {};
    String(raw || "").trim().split(/[\r\n]+/).forEach(function (line) {
      var i = line.indexOf(":");
      if (i > 0) h[line.slice(0, i).trim().toLowerCase()] = line.slice(i + 1).trim();
    });
    return h;
  }

  function toBody(body) {
    if (body == null) return null;
    if (typeof body === "string") return body;
    if (body instanceof Uint8Array || body instanceof ArrayBuffer) return body;
    if (typeof body.toJs === "function") { try { return body.toJs(); } catch (e) { /* weiter */ } }
    return String(body);
  }

  function bytesToB64(bytes) {
    var s = "";
    var CH = 0x8000;
    for (var i = 0; i < bytes.length; i += CH) s += String.fromCharCode.apply(null, bytes.subarray(i, i + CH));
    return btoa(s);
  }

  function errName(e) {
    return (e && e.name) ? String(e.name) : "Error";
  }

  // Synchron (XMLHttpRequest im Hauptthread). Liefert JSON-Text {status, statusText, headers, text|b64, url}
  // oder {status: 0, error}. Ohne Timeout (synchrones XHR im Fenster erlaubt keinen).
  globalThis.lcHttpSync = function (method, url, headersJson, body, binary) {
    var xhr = new XMLHttpRequest();
    try {
      xhr.open(String(method || "GET").toUpperCase(), String(url), false);
      if (binary) xhr.overrideMimeType("text/plain; charset=x-user-defined");
      var h = safeHeaders(headersJson);
      Object.keys(h).forEach(function (k) { try { xhr.setRequestHeader(k, h[k]); } catch (e) { /* unzulässig */ } });
      xhr.send(toBody(body));
    } catch (e) {
      return JSON.stringify({ status: 0, error: errName(e) });
    }
    if (!xhr.status) return JSON.stringify({ status: 0, error: "network" });
    var out = { status: xhr.status, statusText: xhr.statusText || "",
      headers: parseHeaders(xhr.getAllResponseHeaders()), url: xhr.responseURL || String(url) };
    if (binary) {
      var t = xhr.responseText || "";
      var b = new Uint8Array(t.length);
      for (var i = 0; i < t.length; i++) b[i] = t.charCodeAt(i) & 0xff;
      out.b64 = bytesToB64(b);
    } else {
      out.text = xhr.responseText || "";
    }
    return JSON.stringify(out);
  };

  // Asynchron (fetch, mit Timeout und Abbruch). Gleiches Ergebnisformat, als Promise.
  globalThis.lcHttpAsync = async function (method, url, headersJson, body, timeoutMs, binary) {
    var ctrl = new AbortController();
    controllers.add(ctrl);
    var timedOut = false;
    var timer = null;
    if (timeoutMs > 0) timer = setTimeout(function () { timedOut = true; ctrl.abort(); }, timeoutMs);
    try {
      var m = String(method || "GET").toUpperCase();
      var resp = await fetch(String(url), {
        method: m, headers: safeHeaders(headersJson), body: (m === "GET" || m === "HEAD") ? null : toBody(body),
        signal: ctrl.signal, credentials: "omit", cache: "no-store", redirect: "follow"
      });
      var headers = {};
      resp.headers.forEach(function (v, k) { headers[k.toLowerCase()] = v; });
      var out = { status: resp.status, statusText: resp.statusText || "", headers: headers, url: resp.url || String(url) };
      if (binary) out.b64 = bytesToB64(new Uint8Array(await resp.arrayBuffer()));
      else out.text = await resp.text();
      return JSON.stringify(out);
    } catch (e) {
      if (timedOut) return JSON.stringify({ status: 0, error: "timeout", timeout: true });
      if (interruptFlag) return JSON.stringify({ status: 0, error: "aborted", aborted: true });
      return JSON.stringify({ status: 0, error: errName(e) });
    } finally {
      if (timer) clearTimeout(timer);
      controllers.delete(ctrl);
    }
  };

  globalThis.lcInterruptRequested = function () { return interruptFlag; };

  // ------------------------------------------------------------------ Magics
  var MAGIC_LINE = /^(\s*)([%!])(?!=)(.*)$/;
  var MAGIC_ASSIGN = /^(\s*)([A-Za-z_]\w*)\s*=\s*([%!])(?!=)(.*)$/;
  var PIP_LINE = /^\s*[%!]\s*(?:pip3?|uv\s+pip|python3?\s+-m\s+pip)\s+install\s+(.*)$/;

  function pipPackages(line) {
    var m = PIP_LINE.exec(line);
    if (!m) return [];
    return m[1].split(/\s+/).filter(function (t) { return t && t[0] !== "-"; })
      .map(function (t) { return t.split(/[\[=<>!~;@]/)[0].toLowerCase().replace(/[-_.]+/g, "-"); });
  }

  // Ersetzt Zeilen-Magics (%…, !…) durch __lc_magic__("…") – nur am Anfang logischer Zeilen,
  // also nicht in mehrzeiligen Strings, Klammern oder Fortsetzungszeilen.
  function transform(code) {
    var res = { code: code, cell: null, pip: [] };
    var lines = code.split("\n");
    var first = 0;
    while (first < lines.length && lines[first].trim() === "") first++;
    if (first < lines.length && /^\s*%%/.test(lines[first])) {
      var head = lines[first].trim();
      var parts = head.slice(2).trim().split(/\s+/);
      res.cell = { name: parts[0] || "", args: parts.slice(1), body: lines.slice(first + 1).join("\n"), head: head };
      return res;
    }
    var str = null, depth = 0, cont = false;
    for (var li = 0; li < lines.length; li++) {
      var L = lines[li];
      var isStart = str === null && depth === 0 && !cont;
      if (isStart) {
        var ma = MAGIC_ASSIGN.exec(L);
        var m = ma ? null : MAGIC_LINE.exec(L);
        if (ma || m) {
          var cmd = ma ? ma[3] + ma[4] : m[2] + m[3];
          res.pip = res.pip.concat(pipPackages(cmd));
          lines[li] = ma ? ma[1] + ma[2] + " = __lc_magic__(" + JSON.stringify(cmd) + ")"
            : m[1] + "__lc_magic__(" + JSON.stringify(cmd) + ")";
          cont = false;
          continue;
        }
      }
      // Zustand über die Zeile fortschreiben
      var j = 0;
      var commentAt = -1;
      while (j < L.length) {
        var c = L[j];
        if (str) {
          if (c === "\\") { j += 2; continue; }
          if (L.substr(j, str.length) === str) { j += str.length; str = null; continue; }
          j++;
          continue;
        }
        if (c === "#") { commentAt = j; break; }
        if (c === "'" || c === '"') {
          var tq = L.substr(j, 3) === c + c + c;
          str = tq ? c + c + c : c;
          j += tq ? 3 : 1;
          continue;
        }
        if (c === "(" || c === "[" || c === "{") depth++;
        else if (c === ")" || c === "]" || c === "}") depth = Math.max(0, depth - 1);
        j++;
      }
      var code0 = commentAt >= 0 ? L.slice(0, commentAt) : L;
      if (str === "'" || str === '"') {
        if (!/\\$/.test(L)) str = null; // einfacher String endet spätestens am Zeilenende
        cont = false;
      } else {
        cont = str === null && /\\\s*$/.test(code0);
      }
    }
    res.code = lines.join("\n");
    return res;
  }

  // ------------------------------------------------------------------ Pakete
  function norm(n) { return String(n).toLowerCase().replace(/[-_.]+/g, "-"); }

  var importMap = Object.create(null);   // Importname → Paketname (aus pyodide-lock.json)
  var wantedNow = [];                     // direkt angeforderte Pakete des aktuellen Ladevorgangs

  // „Loading numpy, pillow, …“ → „numpy, matplotlib werden installiert (mit 10 Hilfspaketen) …“
  function onLoadMessage(msg) {
    var m = /^Loading (.+)$/.exec(String(msg));
    if (!m) return;
    var pk = m[1].split(/,\s*/).filter(Boolean);
    var main = pk.filter(function (p) { return wantedNow.indexOf(norm(p)) >= 0; });
    if (!main.length) main = pk.slice(0, Math.min(3, pk.length));
    var rest = pk.length - main.length;
    status(main.join(", ") + (main.length === 1 ? " wird" : " werden") + " installiert" +
      (rest ? " (mit " + rest + " Hilfspaket" + (rest === 1 ? "" : "en") + ")" : "") + " …");
  }

  function wantedFromCode(code) {
    var names = [];
    try {
      var px = boot.lc_imports(code);
      names = px.toJs();
      px.destroy();
    } catch (e) { names = []; }
    var out = [];
    names.forEach(function (n) { var p = importMap[n]; if (p && out.indexOf(p) < 0) out.push(p); });
    return out;
  }

  function onLoadError(msg) {
    deliver("stderr", "Paket konnte nicht geladen werden: " + String(msg).split("\n")[0] + "\n");
  }

  async function loadForCode(code) {
    wantedNow = wantedFromCode(code);
    try {
      await pyodide.loadPackagesFromImports(code, { messageCallback: onLoadMessage, errorCallback: onLoadError });
    } catch (e) {
      deliver("stderr", "Pakete konnten nicht geladen werden (" + errName(e) + "). Prüfe die Verbindung zur Plattform.\n");
    }
  }

  async function loadNames(names) {
    var want = [];
    (names || []).forEach(function (n) { var k = norm(n); if (lockNames.has(k) && want.indexOf(k) < 0) want.push(k); });
    if (!want.length) return [];
    wantedNow = want.slice();
    try {
      await pyodide.loadPackage(want, { messageCallback: onLoadMessage, errorCallback: onLoadError });
    } catch (e) {
      deliver("stderr", "Pakete konnten nicht geladen werden (" + errName(e) + ").\n");
    }
    return want;
  }

  // ------------------------------------------------------------------ Start
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = function () { resolve(); };
      s.onerror = function () { reject(new Error("Datei nicht ladbar: " + src)); };
      document.head.appendChild(s);
    });
  }

  function germanInitError(e) {
    var msg = String((e && e.message) || e || "");
    if (/nicht verfügbar/.test(msg)) {
      return "Python konnte nicht gestartet werden: Dieser Browser unterstützt kein WebAssembly.";
    }
    if (/WebAssembly|wasm|Content Security Policy|CompileError|unsafe-eval/i.test(msg)) {
      return "Python konnte nicht gestartet werden: Die Vorschau blockiert WebAssembly " +
        "(Content-Security-Policy ohne 'wasm-unsafe-eval').";
    }
    if (/Zeitüberschreitung/.test(msg)) {
      return "Python konnte nicht gestartet werden: " + msg + ". Bitte Verbindung prüfen und die Seite neu laden.";
    }
    if (/nicht ladbar|Failed to fetch|NetworkError|404|load/i.test(msg)) {
      return "Python konnte nicht gestartet werden: Dateien unter py/ sind nicht erreichbar (" + msg.slice(0, 160) + ").";
    }
    return "Python konnte nicht gestartet werden: " + msg.slice(0, 300);
  }

  // Prüft vorab, ob die Seite WebAssembly kompilieren darf (CSP 'wasm-unsafe-eval').
  // Ohne diese Prüfung bleibt loadPyodide unter einer strengen CSP einfach hängen.
  function wasmCheck() {
    if (typeof WebAssembly !== "object" || typeof WebAssembly.Module !== "function") {
      throw new Error("WebAssembly ist in diesem Browser nicht verfügbar.");
    }
    try {
      new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]));
    } catch (e) {
      throw new Error("WebAssembly blockiert (Content Security Policy): " + String(e && e.message || e).slice(0, 120));
    }
  }

  function withTimeout(promise, ms, what) {
    if (!(ms > 0)) return promise;
    var timer;
    return Promise.race([
      promise,
      new Promise(function (_, reject) {
        timer = setTimeout(function () { reject(new Error("Zeitüberschreitung beim Laden (" + what + ")")); }, ms);
      })
    ]).finally(function () { clearTimeout(timer); });
  }


  // ---- Archive aus auslieferbaren Teilen zusammensetzen ----
  // Die Vorschau liefert keine ZIP- oder Wheel-Dateien aus. Deshalb liegen Standardbibliothek und Pakete als
  // JSON (Quelltext) plus .wasm (Maschinencode) unter py/b/. Beim Laden baut der Browser daraus wieder ein
  // unkomprimiertes Archiv und reicht es an Pyodide weiter, als käme es direkt vom Server.
  var bundleIndex = null, bundleCache = {}, realFetch = null;
  var CRC_T = (function () { var t = new Uint32Array(256); for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  function crc32(u8) { var c = 0xFFFFFFFF; for (var i = 0; i < u8.length; i++) c = CRC_T[(c ^ u8[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
  function b64bytes(s) { var bin = atob(s), u = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i); return u; }
  function buildZip(entries) {
    var enc = new TextEncoder(), local = [], central = [], offset = 0, size = 0;
    entries.forEach(function (e) {
      var name = enc.encode(e.name), d = e.data, crc = crc32(d);
      var h = new DataView(new ArrayBuffer(30));
      h.setUint32(0, 0x04034b50, true); h.setUint16(4, 20, true); h.setUint16(6, 0x0800, true); h.setUint16(8, 0, true);
      h.setUint16(10, 0, true); h.setUint16(12, 0x21, true); h.setUint32(14, crc, true); h.setUint32(18, d.length, true);
      h.setUint32(22, d.length, true); h.setUint16(26, name.length, true); h.setUint16(28, 0, true);
      local.push(new Uint8Array(h.buffer), name, d);
      var c = new DataView(new ArrayBuffer(46));
      c.setUint32(0, 0x02014b50, true); c.setUint16(4, 20, true); c.setUint16(6, 20, true); c.setUint16(8, 0x0800, true);
      c.setUint16(10, 0, true); c.setUint16(12, 0, true); c.setUint16(14, 0x21, true); c.setUint32(16, crc, true);
      c.setUint32(20, d.length, true); c.setUint32(24, d.length, true); c.setUint16(28, name.length, true);
      c.setUint32(42, offset, true);
      central.push(new Uint8Array(c.buffer), name);
      offset += 30 + name.length + d.length;
    });
    var cdSize = central.reduce(function (a, x) { return a + x.length; }, 0);
    var end = new DataView(new ArrayBuffer(22));
    end.setUint32(0, 0x06054b50, true); end.setUint16(8, entries.length, true); end.setUint16(10, entries.length, true);
    end.setUint32(12, cdSize, true); end.setUint32(16, offset, true);
    var all = local.concat(central, [new Uint8Array(end.buffer)]);
    size = all.reduce(function (a, x) { return a + x.length; }, 0);
    var out = new Uint8Array(size), pos = 0;
    all.forEach(function (x) { out.set(x, pos); pos += x.length; });
    return out;
  }
  async function bundleBytes(fileName) {
    if (bundleCache[fileName]) return bundleCache[fileName];
    var info = bundleIndex[fileName];
    var prom = (async function () {
      var parts = await Promise.all(info.parts.map(function (u) { return realFetch(new URL(u, document.baseURI)).then(function (r) { if (!r.ok) throw new Error(u + ": " + r.status); return r.json(); }); }));
      var items = [].concat.apply([], parts);
      var enc = new TextEncoder();
      var entries = await Promise.all(items.map(async function (it) {
        var data;
        if (it[1] === "t") data = enc.encode(it[2]);
        else if (it[1] === "b") data = b64bytes(it[2]);
        else { var r = await realFetch(new URL(it[2], document.baseURI)); if (!r.ok) throw new Error(it[2] + ": " + r.status); data = new Uint8Array(await r.arrayBuffer()); }
        return { name: it[0], data: data };
      }));
      return buildZip(entries);
    })();
    bundleCache[fileName] = prom;
    return prom;
  }
  async function installBundleFetch() {
    if (realFetch) return;
    var r = await fetch(baseURL + "bundles.json");
    if (!r.ok) return;                        // ohne Index: Archive direkt laden (z. B. lokale Testseite)
    bundleIndex = await r.json();
    realFetch = globalThis.fetch.bind(globalThis);
    globalThis.fetch = function (input, init) {
      try {
        var u = new URL(typeof input === "string" ? input : (input && input.url) || String(input), document.baseURI);
        if (u.href.indexOf(baseURL) === 0) {
          var fn = decodeURIComponent(u.pathname.split("/").pop());
          if (bundleIndex[fn]) {
            return bundleBytes(fn).then(function (bytes) {
              return new Response(bytes, { status: 200, headers: { "Content-Type": "application/zip" } });
            });
          }
        }
      } catch (e) { /* weiter mit normalem fetch */ }
      return realFetch(input, init);
    };
  }
  async function doInit(opts) {
    if (opts.onStatus) statusCb = opts.onStatus;
    baseURL = new URL(opts.base || "py/", document.baseURI).href;
    if (!/\/$/.test(baseURL)) baseURL += "/";
    var t0 = performance.now();
    status("Python wird geladen …");
    try {
      wasmCheck();
      if (opts.bundles !== false) await installBundleFetch();
      if (typeof globalThis.loadPyodide !== "function") await loadScript(baseURL + "pyodide.js");
      pyodide = await withTimeout(globalThis.loadPyodide({ indexURL: baseURL, env: { HOME: HOME }, fullStdLib: false }),
        opts.timeoutMs == null ? 180000 : opts.timeoutMs, "Pyodide");
      timings.pyodideMs = Math.round(performance.now() - t0);
      status("Laufzeit wird eingerichtet …");
      pyodide.setStdout({ write: function (buf) { return stdWrite("stdout", buf); } });
      pyodide.setStderr({ write: function (buf) { return stdWrite("stderr", buf); } });
      pyodide.registerJsModule("_lc_js", {
        getSecret: function (name) {
          var k = String(name);
          return Object.prototype.hasOwnProperty.call(secrets, k) ? secrets[k] : undefined;
        },
        // Nachladen bei Bedarf aus Python (Import in einer eigenen Datei), mit Statusmeldung statt Konsole
        loadPackage: function (name) {
          wantedNow = [norm(name)];
          return pyodide.loadPackage([String(name)], { messageCallback: onLoadMessage, errorCallback: onLoadError })
            .finally(function () { if (state.busy) status("Bereit"); });
        }
      });
      var lockResp = await fetch(baseURL + "pyodide-lock.json");
      var lock = await lockResp.json();
      Object.keys(lock.packages || {}).forEach(function (k) {
        lockNames.add(norm(k));
        (lock.packages[k].imports || []).forEach(function (i) { importMap[i] = norm(k); });
      });
      var srcResp = await fetch(baseURL + "lc_boot.py", { cache: "no-cache" });
      if (!srcResp.ok) throw new Error("lc_boot.py nicht ladbar (HTTP " + srcResp.status + ")");
      var src = await srcResp.text();
      pyodide.FS.mkdirTree("/lc");
      pyodide.FS.writeFile("/lc/lc_boot.py", src);
      pyodide.runPython("import sys\nif '/lc' not in sys.path:\n    sys.path.append('/lc')\nimport lc_boot\n");
      boot = pyodide.pyimport("lc_boot");
      lcRun = boot.lc_run;
      if (opts.jspi === false) boot.lc_set_options(false);
      state.ready = true;
      timings.readyMs = Math.round(performance.now() - t0);
      if (opts.packages && opts.packages.length) {
        await loadNames(opts.packages);
        timings.packagesMs = Math.round(performance.now() - t0);
      }
      status("Bereit");
      return { ok: true, timings: Object.assign({}, timings), info: JSON.parse(boot.lc_info()) };
    } catch (e) {
      var msg = germanInitError(e);
      status(msg);
      throw new Error(msg);
    }
  }

  // ------------------------------------------------------------------ Ausführen
  function cellFilename(opts) {
    return opts && opts.label != null ? "<zelle " + String(opts.label).replace(/[<>]/g, "") + ">" : "<zelle>";
  }

  function resultFromPy(r) {
    if (r == null) return { ok: true, error: null };
    var info = {};
    try { info = JSON.parse(String(r)); } catch (e) { info = { error: String(r) }; }
    return { ok: false, error: redact(info.error || "Fehler"), ename: info.ename || null,
      traceback: redact(info.traceback || "") };
  }

  async function runPython(code, opts) {
    await loadForCode(code);
    var r = await lcRun(code, cellFilename(opts));
    flushStd();
    return resultFromPy(r);
  }

  async function runCellMagic(t, opts) {
    var name = t.cell.name, args = t.cell.args, body = t.cell.body;
    if (name === "writefile") {
      var append = args[0] === "-a" || args[0] === "--append";
      var fname = (append ? args.slice(1) : args).join(" ");
      if (!fname) { deliver("error", "UsageError: %%writefile braucht einen Dateinamen."); return { ok: false, error: "UsageError" }; }
      boot.lc_writefile(fname, body, append);
      flushStd();
      if (/\.py$/.test(fname)) await loadForCode(body);
      return { ok: true, error: null };
    }
    if (name === "time") {
      var t0 = performance.now();
      var r = await runPython(transform(body).code, opts);
      var dt = (performance.now() - t0) / 1000;
      deliver("stdout", "Wall time: " + (dt < 1 ? (dt * 1000).toFixed(1) + " ms" : dt.toFixed(2) + " s") + "\n");
      return r;
    }
    if (name === "capture") {
      var keep = currentEmit;
      currentEmit = function (kind, data) { if (kind === "error" && keep) keep(kind, data); };
      try { return await runPython(transform(body).code, opts); } finally { flushStd(); currentEmit = keep; }
    }
    if (name === "html") { deliver("html", body); return { ok: true, error: null }; }
    if (name === "markdown" || name === "latex") { deliver("markdown", body); return { ok: true, error: null }; }
    if (name === "javascript" || name === "js") {
      deliver("stderr", "ℹ️ JavaScript-Zellen werden auf der Plattform nicht ausgeführt.\n");
      return { ok: true, error: null };
    }
    if (/^(bash|sh|shell|script|system|perl|ruby)$/.test(name)) {
      deliver("stderr", "ℹ️ %%" + name + " läuft im Browser nicht (keine Kommandozeile). Diese Zelle bitte in Colab ausführen.\n");
      return { ok: true, error: null };
    }
    deliver("stderr", "ℹ️ Die Zellen-Magic %%" + name + " wird auf der Plattform nicht unterstützt.\n");
    return { ok: true, error: null };
  }

  async function runNow(code, emit, opts) {
    opts = opts || {};
    if (!state.ready) await LCPy.init(opts.init || {});
    if (state.broken) {
      var m0 = "Die Python-Laufzeit ist abgestürzt. Bitte die Seite neu laden.";
      if (typeof emit === "function") { try { emit("error", m0); } catch (e) { /* */ } }
      return { ok: false, error: m0 };
    }
    state.busy = true;
    interruptFlag = false;
    textCount = 0;
    truncated = false;
    currentEmit = typeof emit === "function" ? emit : null;
    try {
      var t = transform(String(code == null ? "" : code));
      if (t.pip.length) await loadNames(t.pip);
      if (t.cell) return await runCellMagic(t, opts);
      return await runPython(t.code, opts);
    } catch (e) {
      flushStd();
      var msg = String((e && e.message) || e);
      if (/fatal error|has been destroyed|RuntimeError: memory access out of bounds|Aborted\(/i.test(msg)) {
        state.broken = true;
        msg = "Die Python-Laufzeit ist abgestürzt (z. B. Speicher voll). Bitte die Seite neu laden.";
      } else {
        msg = "Interner Fehler der Laufzeit: " + msg.split("\n")[0].slice(0, 300);
      }
      deliver("error", msg);
      return { ok: false, error: redact(msg) };
    } finally {
      flushStd();
      currentEmit = null;
      state.busy = false;
      interruptFlag = false;
      if (state.ready && !state.broken) status("Bereit");
    }
  }

  function enqueue(fn) {
    var job = queue.then(fn);
    queue = job.catch(function () { /* weiter */ });
    return job;
  }

  // ------------------------------------------------------------------ Dateien
  function absPath(p) {
    p = String(p == null ? "" : p);
    if (!p) return HOME;
    return p[0] === "/" ? p : HOME + "/" + p;
  }

  function requireReady() {
    if (!state.ready) throw new Error("LCPy ist noch nicht bereit (erst await LCPy.init()).");
  }

  function dirname(p) { var i = p.lastIndexOf("/"); return i > 0 ? p.slice(0, i) : "/"; }

  function toBytes(data) {
    if (typeof data === "string") return new TextEncoder().encode(data);
    if (data instanceof Uint8Array) return data;
    if (data instanceof ArrayBuffer) return new Uint8Array(data);
    if (ArrayBuffer.isView(data)) return new Uint8Array(data.buffer, data.byteOffset, data.byteLength);
    throw new TypeError("writeFile erwartet Uint8Array, ArrayBuffer oder String.");
  }

  function walk(dir, rel, out) {
    var FS = pyodide.FS;
    var names = FS.readdir(dir);
    names.sort();
    for (var i = 0; i < names.length && out.length < 5000; i++) {
      var name = names[i];
      if (name === "." || name === ".." || name === "__pycache__") continue;
      var full = (dir === "/" ? "" : dir) + "/" + name;
      var st = FS.stat(full);
      var isDir = FS.isDir(st.mode);
      out.push({ path: rel + name, fullPath: full, size: isDir ? 0 : st.size, dir: isDir,
        mtime: st.mtime instanceof Date ? st.mtime.getTime() : st.mtime });
      if (isDir) walk(full, rel + name + "/", out);
    }
  }

  // ------------------------------------------------------------------ öffentliche API
  var LCPy = {
    __lc: true,
    version: "0.29.5-lc1",
    get ready() { return state.ready; },
    get busy() { return state.busy; },
    get timings() { return Object.assign({}, timings); },

    init: function (opts) {
      opts = opts || {};
      if (opts.onStatus) statusCb = opts.onStatus;
      if (!initPromise) {
        initPromise = doInit(opts).catch(function (e) { initPromise = null; throw e; });
      }
      return initPromise;
    },

    run: function (code, emit, opts) {
      return enqueue(function () { return runNow(code, emit, opts); });
    },

    setSecrets: function (obj) {
      secrets = Object.create(null);
      if (obj && typeof obj === "object") {
        Object.keys(obj).forEach(function (k) {
          if (typeof obj[k] === "string" && obj[k] !== "") secrets[k] = obj[k];
        });
      }
    },

    hasSecret: function (name) { return Object.prototype.hasOwnProperty.call(secrets, String(name)); },

    reset: function () {
      return enqueue(async function () {
        if (!state.ready) return;
        boot.lc_reset();
      });
    },

    interrupt: function () {
      if (!state.busy) return false;
      interruptFlag = true;
      controllers.forEach(function (c) { try { c.abort(); } catch (e) { /* */ } });
      return true;
    },

    loadPackages: function (names) {
      return enqueue(async function () {
        if (!state.ready) await LCPy.init({});
        var r = await loadNames(Array.isArray(names) ? names : [names]);
        status("Bereit");
        return r;
      });
    },

    writeFile: function (path, data) {
      requireReady();
      var p = absPath(path);
      pyodide.FS.mkdirTree(dirname(p));
      pyodide.FS.writeFile(p, toBytes(data));
      return p;
    },

    readFile: function (path, encoding) {
      requireReady();
      var p = absPath(path);
      return encoding ? pyodide.FS.readFile(p, { encoding: "utf8" }) : pyodide.FS.readFile(p);
    },

    listFiles: function (ordner) {
      requireReady();
      var p = absPath(ordner || HOME);
      var out = [];
      try { walk(p, "", out); } catch (e) { return []; }
      return out;
    },

    unpackZip: function (arrayBuffer, zielordner) {
      requireReady();
      var p = absPath(zielordner || HOME);
      pyodide.FS.mkdirTree(p);
      pyodide.unpackArchive(arrayBuffer, "zip", { extractDir: p });
      pyodide.runPython("import importlib\nimportlib.invalidate_caches()");
      return LCPy.listFiles(p);
    },

    info: function () {
      if (!state.ready) return { ready: false };
      var i = JSON.parse(boot.lc_info());
      i.ready = true;
      return i;
    },

    // nur für Tests und Fehlersuche
    _transform: transform,
    get _pyodide() { return pyodide; }
  };

  Object.defineProperty(LCPy, "onStatus", {
    get: function () { return statusCb; },
    set: function (fn) { statusCb = fn; }
  });

  window.LCPy = LCPy;
})();
