import http.server
import json
import urllib.request
import urllib.error
import traceback

from config import CONFIG, LOG_ALL_TRAFFIC, COMPRESS_LOG_DATA, FORCE_STREAM_FALSE, ENABLE_THINKING, PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON
from utils import compress_log_data, format_size, log_complete_message
from processors import response_processor
from stream_processor import StreamProcessor, parse_sse_line, format_sse_event
from logger import logger

class RouterHTTPHandler(http.server.BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def __init__(self, *args, **kwargs):
        self.target_host = CONFIG.get("target", {}).get("host", "localhost")
        self.target_port = CONFIG.get("target", {}).get("port", 12134)
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """处理 POST 请求"""
        try:
            # 读取请求数据
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 解析请求数据
            request_data = json.loads(post_data.decode('utf-8'))
            
            # 检查请求格式并转发
            if self.path.startswith('/v1/messages/count_tokens'):
                # Claude Code 自动压缩时调用此端点，LM Studio 不支持，直接返回 mock
                self.handle_count_tokens(request_data)
            elif self.path.startswith('/v1/messages'):
                # 处理 Anthropic 格式请求（Claude Code）
                self.handle_anthropic_direct(post_data)
            else:
                # 其他路径返回错误
                logger.warning(f"Unsupported path: {self.path}")
                self.send_error(404, "Not Found")
                
        except json.JSONDecodeError:
            # 记录详细的异常信息
            error_info = {
                "error_type": "JSON decode error",
                "error": "Invalid JSON in request",
                "traceback": traceback.format_exc()
            }
            log_complete_message(error_info, "error")
            logger.error("Invalid JSON in request")
            self.send_error(400, "Invalid JSON")
        except Exception as e:
            # 记录详细的异常信息
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
            # 粗估 token 数：将整个请求体序列化后按字符数/4估算
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
        """处理 Anthropic 请求，转发到 LM Studio 的 Anthropic 端点"""
        # 初始化变量，避免 except 块中引用未定义变量
        request_data = None
        target_url = ""
        
        try:
            # 解析请求
            request_data = json.loads(post_data.decode('utf-8'))
            
            # 记录完整请求
            log_complete_message(request_data, "request")
            
            # 记录原始请求（如果开启）
            if LOG_ALL_TRAFFIC:
                logger.debug("=== ORIGINAL ANTHROPIC REQUEST ===")
                if COMPRESS_LOG_DATA:
                    compressed_data = compress_log_data(request_data)
                    logger.debug(json.dumps(compressed_data, indent=2, ensure_ascii=False))
                else:
                    logger.debug(json.dumps(request_data, indent=2, ensure_ascii=False))
            
            # 构建目标URL - 直接使用相同的路径
            target_url = f"http://{self.target_host}:{self.target_port}{self.path}"
            
            # 计算消息大小
            message_json = json.dumps(request_data, ensure_ascii=False)
            message_size = len(message_json.encode('utf-8'))
            formatted_size = format_size(message_size)
            
            logger.info(f"--> Forwarding to {target_url} (size: {formatted_size})")
            
            # 强制禁用流式传输（可配置）
            if FORCE_STREAM_FALSE:
                request_data['stream'] = False

            # 处理 thinking 参数：优先用 ENABLE_THINKING 配置，否则根据 effort 动态映射
            if ENABLE_THINKING is not None:
                request_data['enable_thinking'] = ENABLE_THINKING
            else:
                # 从 output_config.effort 动态映射: effort >= medium 开启思考，否则关闭
                output_config = request_data.get('output_config', {})
                effort = output_config.get('effort', 'medium') if isinstance(output_config, dict) else 'medium'
                request_data['enable_thinking'] = effort in ('medium', 'high')

            # 删除 Claude Code 专有参数，避免 LM Studio 不识别产生 warning
            request_data.pop('thinking', None)
            request_data.pop('output_config', None)
            request_data.pop('context_management', None)
            
            modified_post_data = json.dumps(request_data).encode('utf-8')
            
            # 创建请求
            req = urllib.request.Request(
                target_url,
                data=modified_post_data,
                headers={
                    'Content-Type': 'application/json',
                    'Content-Length': len(modified_post_data)
                },
                method='POST'
            )
            
            # 发送请求到目标服务器
            with urllib.request.urlopen(req) as response:
                response_headers = dict(response.headers)
                
                logger.info(f"<-- Received response from {target_url}")
                
                # 检测是否为流式响应
                content_type = response.headers.get('Content-Type', '')
                
                if 'text/event-stream' in content_type:
                    # 流式响应处理
                    logger.info("Streaming response detected")
                    logger.debug(f"Streaming response headers: {response_headers}")
                    self.send_response(response.status)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Connection', 'keep-alive')
                    self.end_headers()
                    
                    # 流式处理 - 累积、处理、重新生成
                    try:
                        processor = StreamProcessor()
                        buffer = b''
                        event_type = None
                        event_count = 0
                        
                        while True:
                            chunk = response.read(4096)
                            if not chunk:
                                break
                            buffer += chunk
                            
                            # 解析 SSE 事件
                            lines = buffer.split(b'\n')
                            buffer = lines[-1]  # 保留未完成的行
                            
                            for line in lines[:-1]:
                                if not line:
                                    continue
                                line_str = line.decode('utf-8', errors='ignore')
                                key, value = parse_sse_line(line_str)
                                
                                if key == "event":
                                    event_type = value
                                elif key == "data" and event_type:
                                    try:
                                        data = json.loads(value)
                                        processor.process_event(event_type, data)
                                        event_count += 1
                                        logger.debug(f"Received event {event_count}: {event_type}")
                                    except json.JSONDecodeError:
                                        logger.warning(f"Failed to parse JSON: {value}")
                                    event_type = None
                        
                        logger.info(f"Total events received: {event_count}")
                        
                        # 处理累积的内容
                        if PARSE_XML_TOOLS or REMOVE_THINK_TAGS or FIX_STOP_REASON:
                            processor.process_content()
                            logger.info("Stream content processed")
                        
                        # 重新生成并发送事件
                        events = processor.generate_events()
                        for evt_type, evt_data in events:
                            sse_data = format_sse_event(evt_type, evt_data)
                            self.wfile.write(sse_data.encode('utf-8'))
                            self.wfile.flush()
                        
                        logger.info(f"Streaming response completed, total events: {len(events)}")
                        self.close_connection = True
                        
                    except (ConnectionResetError, BrokenPipeError) as e:
                        logger.warning(f"Client disconnected during streaming: {e}")
                    except Exception as e:
                        logger.error(f"Error during streaming: {e}", exc_info=True)
                else:
                    # 非流式响应处理
                    response_data = response.read()
                    
                    # 处理响应数据
                    try:
                        response_json = json.loads(response_data.decode('utf-8'))
                        
                        # 记录原始 LM Studio 响应（如果开启）
                        if LOG_ALL_TRAFFIC:
                            logger.debug("=== ORIGINAL LM STUDIO RESPONSE ===")
                            if COMPRESS_LOG_DATA:
                                compressed_data = compress_log_data(response_json)
                                logger.debug(json.dumps(compressed_data, indent=2, ensure_ascii=False))
                            else:
                                logger.debug(json.dumps(response_json, indent=2, ensure_ascii=False))
                        
                        # 处理 Qwen 问题（如果开启相关功能）
                        if PARSE_XML_TOOLS or REMOVE_THINK_TAGS or FIX_STOP_REASON:
                            response_processor.process_anthropic_response(response_json)
                        
                        # 重新编码响应
                        processed_response_data = json.dumps(response_json).encode('utf-8')
                        
                        # 发送处理后的响应给客户端
                        self.send_response(response.status)
                        for key, value in response_headers.items():
                            if key.lower() not in ['content-length', 'transfer-encoding']:
                                self.send_header(key, value)
                        self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', len(processed_response_data))
                        self.end_headers()
                        self.wfile.write(processed_response_data)
                        
                    except json.JSONDecodeError:
                        # 如果响应不是JSON格式，直接发送
                        logger.warning("Response is not JSON format, forwarding as-is")
                        self.send_response(response.status)
                        for key, value in response_headers.items():
                            self.send_header(key, value)
                        self.end_headers()
                        self.wfile.write(response_data)
                
        except urllib.error.HTTPError as e:
            # 记录详细的 HTTP 错误信息
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
            # 记录详细的异常信息
            error_info = {
                "error": str(e),
                "request_data": request_data,
                "target_url": target_url,
                "traceback": traceback.format_exc()
            }
            log_complete_message(error_info, "error")
            logger.error(f"Error in handle_anthropic_direct: {str(e)}")
            self.send_error(500, "Internal Server Error")
