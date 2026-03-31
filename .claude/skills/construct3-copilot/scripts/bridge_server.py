import http.server
import socketserver
import json
import os
import sys

PORT = 8999
JSON_FILE = ".local/scenario.json"

class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        if self.path == '/latest':
            if os.path.exists(JSON_FILE):
                try:
                    with open(JSON_FILE, 'r') as f:
                        data = f.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(data.encode('utf-8'))
                except Exception as e:
                    self.send_error(500, str(e))
            else:
                self.send_error(404, "No JSON generated yet")
        else:
            self.send_error(404)

def run_server():
    # Ensure .local exists
    if not os.path.exists(".local"):
        os.makedirs(".local")
        
    print(f"🌉 Copilot Bridge Server running on port {PORT}...")
    print(f"📡 Waiting for browser connection...")
    
    with socketserver.TCPServer(("", PORT), CORSRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n🛑 Server stopped.")

if __name__ == "__main__":
    run_server()
