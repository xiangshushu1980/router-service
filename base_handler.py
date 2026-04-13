import http.server
import json
import traceback

from config import CONFIG, LOG_ALL_TRAFFIC, COMPRESS_LOG_DATA
from utils import compress_log_data, format_size, log_complete_message
from logger import logger

class BaseHTTPHandler(http.server.BaseHTTPRequestHandler):
    """基础HTTP请求处理器"""
    
    def __init__(self, *args, **kwargs):
        self.target_host = CONFIG.get("target", {}).get("host", "localhost")
        self.target_port = CONFIG.get("target", {}).get("port", 12134)
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """处理 POST 请求"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            if self.path.startswith('/v1/messages/count_tokens'):
                self.handle_count_tokens(request_data)
            elif self.path.startswith('/v1/messages'):
                self.handle_anthropic_direct(post_data)
            else:
                logger.warning(f"Unsupported path: {self.path}")
                self.send_error(404, "Not Found")
                
        except json.JSONDecodeError:
            error_info = {
                "error_type": "JSON decode error",
                "error": "Invalid JSON in request",
                "traceback": traceback.format_exc()
            }
            log_complete_message(error_info, "error")
            logger.error("Invalid JSON in request")
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            error_info = {
                "error_type": "Request handling error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            log_complete_message(error_info, "error")
            logger.error(f"Error handling request: {str(e)}")
            logger.debug(f"Traceback: {traceback.format_exc()}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
    
    def handle_count_tokens(self, request_data):
        """处理 count_tokens 请求，返回 mock 响应（LM Studio 不支持此端点）"""
        try:
            text = json.dumps(request_data, ensure_ascii=False)
            estimated_tokens = max(len(text) // 4, 1)

            response = {"input_tokens": estimated_tokens}

            response_data = json.dumps(response).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(response_data))
            self.end_headers()
            self.wfile.write(response_data)

            logger.info(f"--> count_tokens request intercepted, estimated {estimated_tokens} tokens")
        except Exception as e:
            logger.error(f"Error in handle_count_tokens: {str(e)}")
            self.send_error(500, "Internal Server Error")
    
    def handle_anthropic_direct(self, post_data):
        """处理 Anthropic 请求，子类需要实现此方法"""
        raise NotImplementedError("Subclasses must implement handle_anthropic_direct")
