"""Servidor local que imita o SMR (login + cartões), para testar o scraper sem acessar o site real."""

import http.server
import threading
import urllib.parse

LOGIN = """<html><body><form method="post" action="/login">
<input type="text" name="usuario"><input type="password" name="senha">
<button type="submit">Entrar</button></form></body></html>"""

CARD = """<div class="card"><div>{cat}<span>{pct}</span></div><h3>{name}</h3>
<h2>{value}</h2><p>{extra}</p><div class="footer">{footer}</div></div>"""

CARDS = [
    ("Reservatório", "53%", "R0 SOBRADO (NÍVEL)", "{level} m", "-", "04/10/2026 17:03:13"),
    ("Vazão", "87%", "R0 900mm (VAZÃO)", "2.059 m<sup>3</sup>/h", "100 m<sup>3</sup>", "04/10/2026 17:17:21"),
    ("Vazão", "78%", "R0-R2 (VAZÃO)", "2.140,13 m<sup>3</sup>/h", "57 m<sup>3</sup>", "04/10/2026 17:17:55"),
    ("Vazão", "59%", "R0-R8 MACRO", "904,22 m<sup>3</sup>/h", "47 m<sup>3</sup>", "04/10/2026 17:18:46"),
    ("Vazão", "87%", "R1-R2 (VAZÃO)", "0 m<sup>3</sup>/h", "-1 m<sup>3</sup>",
     "Sem comunicação desde 18/09/2025 15:06:43"),
]


def make_server(user="Washington", password="segredo", level="3,62"):
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, body, status=200, headers=None):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            if "auth=1" in self.headers.get("Cookie", ""):
                # Cartões renderizados via JavaScript, como em muitos painéis
                cards = "".join(CARD.format(cat=c, pct=p, name=n, value=v.format(level=level), extra=e, footer=f)
                                for c, p, n, v, e, f in CARDS)
                js = f"<div id=app></div><script>setTimeout(()=>{{app.innerHTML={cards!r}}},300)</script>"
                self._send(f"<html><body>{js}</body></html>")
            else:
                self._send(LOGIN)

        def do_POST(self):
            data = urllib.parse.parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
            if data.get("usuario") == [user] and data.get("senha") == [password]:
                self._send("", 302, {"Location": "/", "Set-Cookie": "auth=1"})
            else:
                self._send(LOGIN)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
