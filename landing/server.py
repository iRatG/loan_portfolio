"""
Простой HTTP сервер для лендинговой страницы NCL Analytics Platform.

Запуск:
    python server.py
    
Откроется: http://localhost:8000
"""

import http.server
import socketserver
import webbrowser
from pathlib import Path

PORT = 8000
DIRECTORY = Path(__file__).parent

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        # Добавляем заголовки для правильного отображения
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def log_message(self, format, *args):
        # Красивый лог
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    print("=" * 80)
    print(" " * 20 + "NCL Analytics Platform - Landing Page")
    print("=" * 80)
    print()
    
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        url = f"http://localhost:{PORT}"
        
        print(f"🌐 Сервер запущен: {url}")
        print()
        print("📊 Дашборд аналитики:  http://localhost:8050")
        print("🤖 AI-агент:          http://localhost:8501")
        print()
        print("Нажмите Ctrl+C для остановки")
        print("-" * 80)
        
        # Автоматически открыть в браузере
        try:
            webbrowser.open(url)
        except:
            pass
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n👋 Сервер остановлен")


if __name__ == "__main__":
    main()

