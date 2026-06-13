"""
Stdlib HTTP JSON API for the Vedic engine (no third-party deps).

    python -m api.server 8000

Endpoints
    GET  /health
    GET  /ayanamsas
    GET  /chart?datetime=...&(city=...|lat=...&lon=...)&tz=...&ayanamsa=lahiri
    POST /chart    {"datetime": "...", "city": "...", "ayanamsa": "..."}
                   (or "lat"/"lon"/"tz" instead of "city")

A zoneless datetime is read as local time when a city or tz is supplied,
otherwise as UTC. Append 'Z' for an explicit UTC instant.
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from vedic_engine import compute_chart
from vedic_engine.ayanamsa import available
from vedic_engine.places import resolve_moment


class Handler(BaseHTTPRequestHandler):
    server_version = "vedic_engine/1.0"

    def _send(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _chart_from(self, params: dict):
        def _get(k):
            v = params.get(k)
            return v if v not in ("",) else None

        if _get("datetime") is None:
            return None, "missing parameter: datetime"
        aya = _get("ayanamsa") or "lahiri"
        if aya not in available():
            return None, f"unknown ayanamsa '{aya}'; options: {', '.join(available())}"
        try:
            dt_utc, lat, lon, info = resolve_moment(
                str(_get("datetime")),
                lat=_get("lat"), lon=_get("lon"),
                city=_get("city"), tz=_get("tz"))
            chart = compute_chart(dt_utc, lat, lon, aya)
            chart["input"]["resolved"] = info
            return chart, None
        except (ValueError, TypeError) as e:
            return None, str(e)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            return self._send(200, {"status": "ok"})
        if parsed.path == "/ayanamsas":
            return self._send(200, {"ayanamsas": available()})
        if parsed.path == "/chart":
            q = {k: v[0] for k, v in parse_qs(parsed.query).items()}
            chart, err = self._chart_from(q)
            return self._send(400, {"error": err}) if err else self._send(200, chart)
        return self._send(404, {"error": f"not found: {parsed.path}"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/chart":
            return self._send(404, {"error": f"not found: {parsed.path}"})
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError as e:
            return self._send(400, {"error": f"invalid JSON: {e}"})
        chart, err = self._chart_from(body)
        return self._send(400, {"error": err}) if err else self._send(200, chart)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else 8000
    httpd = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"vedic_engine API on http://0.0.0.0:{port}  "
          f"(GET /health, /ayanamsas, GET|POST /chart)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
