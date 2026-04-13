import json
import urllib.request
import urllib.error
import traceback

from config import FORCE_STREAM_FALSE, ENABLE_THINKING, PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON, SMART_STREAMING, LOG_ALL_TRAFFIC, COMPRESS_LOG_DATA
from utils import log_complete_message, format_size, compress_log_data
from processors import response_processor
from stream_processor import StreamProcessor, parse_sse_line, format_sse_event
from logger import logger
from base_handler import BaseHTTPHandler

class AnthropicHandler(BaseHTTPHandler):
    """处理Anthropic请求的HTTP处理器"""
    
    def handle_anthropic_direct(self, post_data):
        """处理 Anthropic 请求，转发到 LM Studio 的 Anthropic 端点"""
        request_data = None
        target_url = ""
        
        try:
            request_data = json.loads(post_data.decode('utf-8'))
            log_complete_message(request_data, "request")
            
            if LOG_ALL_TRAFFIC:
                logger.debug("=== ORIGINAL ANTHROPIC REQUEST ===")
                if COMPRESS_LOG_DATA:
                    compressed_data = compress_log_data(request_data)
                    logger.debug(json.dumps(compressed_data, indent=2, ensure_ascii=False))
                else:
                    logger.debug(json.dumps(request_data, indent=2, ensure_ascii=False))
            
            target_url = f"http://{self.target_host}:{self.target_port}{self.path}"
            
            message_json = json.dumps(request_data, ensure_ascii=False)
            message_size = len(message_json.encode('utf-8'))
            formatted_size = format_size(message_size)
            
            logger.info(f"--> Forwarding to {target_url} (size: {formatted_size})")
            
            if FORCE_STREAM_FALSE:
                request_data['stream'] = False

            if ENABLE_THINKING is not None:
                request_data['enable_thinking'] = ENABLE_THINKING
                logger.info(f"Thinking config: enabled={ENABLE_THINKING} (from config)")
            else:
                output_config = request_data.get('output_config', {})
                effort = output_config.get('effort', 'medium') if isinstance(output_config, dict) else 'medium'
                request_data['enable_thinking'] = effort in ('medium', 'high', 'max')
                logger.info(f"Thinking config: enabled={request_data['enable_thinking']} (effort={effort})")

            request_data.pop('output_config', None)
            request_data.pop('context_management', None)
            
            modified_post_data = json.dumps(request_data).encode('utf-8')
            
            req = urllib.request.Request(
                target_url,
                data=modified_post_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': len(modified_post_data)
                },
                method='POST'
            )
            
            with urllib.request.urlopen(req) as response:
                response_headers = dict(response.headers)
                
                logger.info(f"<-- Received response from {target_url}")
                
                content_type = response.headers.get('Content-Type', '')
                
                if 'text/event-stream' in content_type:
                    logger.info("Streaming response detected")
                    logger.debug(f"Streaming response headers: {response_headers}")
                    self.send_response(response.status)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    
                    try:
                        if SMART_STREAMING:
                            self._stream_smart(response)
                        else:
                            self._stream_legacy(response)
                        self.close_connection = True
                    except (ConnectionResetError, BrokenPipeError) as e:
                        logger.warning(f"Client disconnected during streaming: {e}")
                    except Exception as e:
                        logger.error(f"Error during streaming: {e}", exc_info=True)
                        
                else:
                    response_data = response.read()
                    
                    try:
                        response_json = json.loads(response_data.decode('utf-8'))
                        
                        if LOG_ALL_TRAFFIC:
                            logger.debug("=== ORIGINAL LM STUDIO RESPONSE ===")
                            if COMPRESS_LOG_DATA:
                                compressed_data = compress_log_data(response_json)
                                logger.debug(json.dumps(compressed_data, indent=2, ensure_ascii=False))
                            else:
                                logger.debug(json.dumps(response_json, indent=2, ensure_ascii=False))
                        
                        if PARSE_XML_TOOLS or REMOVE_THINK_TAGS or FIX_STOP_REASON:
                            response_processor.process_anthropic_response(response_json)
                        
                        processed_response_data = json.dumps(response_json).encode('utf-8')
                        
                        self.send_response(response.status)
                        for key, value in response_headers.items():
                            if key.lower() not in ['content-length', 'transfer-encoding']:
                                self.send_header(key, value)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', len(processed_response_data))
                        self.end_headers()
                        self.wfile.write(processed_response_data)
                        
                    except json.JSONDecodeError:
                        logger.warning("Response is not JSON format, forwarding as-is")
                        self.send_response(response.status)
                        for key, value in response_headers.items():
                            self.send_header(key, value)
                        self.end_headers()
                        self.wfile.write(response_data)
                
        except urllib.error.HTTPError as e:
            error_info = {
                "error_type": "HTTP Error",
                "error": f"HTTP Error: {e.code} - {e.reason}",
                "request_data": request_data,
                "target_url": target_url,
                "status_code": e.code,
                "reason": e.reason
            }
            log_complete_message(error_info, "error")
            logger.error(f"HTTP Error: {e.code} - {e.reason}")
            self.send_error(e.code, e.reason)
        except Exception as e:
            error_info = {
                "error": str(e),
                "request_data": request_data,
                "target_url": target_url,
                "traceback": traceback.format_exc()
            }
            log_complete_message(error_info, "error")
            logger.error(f"Error in handle_anthropic_direct: {str(e)}")
            self.send_error(500, "Internal Server Error")
    
    def _stream_legacy(self, response):
        """旧模式：累积所有事件，处理后一次性发送"""
        raise NotImplementedError("Subclasses must implement _stream_legacy")
    
    def _stream_smart(self, response):
        """混合流式模式：thinking/tool_use立即转发，text块智能流式"""
        raise NotImplementedError("Subclasses must implement _stream_smart")
    
    def _send_sse_event(self, event_type, data):
        """发送单个SSE事件"""
        raise NotImplementedError("Subclasses must implement _send_sse_event")
