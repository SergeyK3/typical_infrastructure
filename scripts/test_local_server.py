"""Проверка: грузится ли вообще локальный сервер в браузере.
Запуск из корня проекта: python scripts/test_local_server.py
Откройте http://127.0.0.1:9999/ в браузере.
Если страница не грузится — блокирует брандмауэр или антивирус.
"""
import socketserver
import webbrowser
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 9999

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h1>OK</h1><p>Локальный сервер работает.</p>")

    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {args[0]}")

def open_browser():
    time.sleep(1)
    webbrowser.open(f"http://127.0.0.1:{PORT}/")

threading.Thread(target=open_browser, daemon=True).start()

with HTTPServer(("", PORT), Handler) as httpd:
    print(f"Тестовый сервер: http://127.0.0.1:{PORT}/")
    print("Браузер должен открыться автоматически. Если страница не грузится —")
    print("добавьте правило в брандмауэр: .\\scripts\\add_firewall_rule.ps1 (от администратора)")
    print("Ctrl+C для выхода.")
    httpd.serve_forever()
