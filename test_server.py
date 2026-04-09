import http.server
import socketserver
import json
import threading
import time

class TestHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            response_data = {
                "id": "test-123",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "test-model",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Hello from test server!"
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
        except Exception as e:
            self.send_error(500, f"Error: {str(e)}")

def start_test_server(host='localhost', port=12345):
    with socketserver.TCPServer((host, port), TestHandler) as httpd:
        print(f"Test server starting on {host}:{port}")
        httpd.serve_forever()

if __name__ == "__main__":
    # 启动测试服务器
    test_server_thread = threading.Thread(
        target=start_test_server,
        args=('localhost', 12345)
    )
    test_server_thread.daemon = True
    test_server_thread.start()
    
    print("Test server started in background")
    print("You can now run the router server and test it")
    print("Press Ctrl+C to exit")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nExiting...")