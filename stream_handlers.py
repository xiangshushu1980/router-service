import json

from config import PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON
from stream_processor import StreamProcessor, parse_sse_line, format_sse_event
from logger import logger
from anthropic_handler import AnthropicHandler

class StreamHandler(AnthropicHandler):
    """处理流式响应的HTTP处理器"""
    
    def _stream_legacy(self, response):
        """旧模式：累积所有事件，处理后一次性发送"""
        processor = StreamProcessor(smart_streaming=False)
        buffer = b''
        event_type = None
        event_count = 0
        
        logger.info("[LEGACY MODE] Starting stream accumulation...")
        
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            buffer += chunk
            
            lines = buffer.split(b'\n')
            buffer = lines[-1]
            
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
                        if LOG_ALL_TRAFFIC:
                            logger.debug(f"Raw event {event_count}: {event_type} - {json.dumps(data, ensure_ascii=False)}")
                        processor.process_event(event_type, data)
                        event_count += 1
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON: {value}")
                    event_type = None
        
        logger.info(f"[LEGACY MODE] Total events received: {event_count}")
        
        if PARSE_XML_TOOLS or REMOVE_THINK_TAGS or FIX_STOP_REASON:
            processor.process_content()
            logger.info("[LEGACY MODE] Stream content processed")
        
        events = processor.generate_events()
        for evt_type, evt_data in events:
            sse_data = format_sse_event(evt_type, evt_data)
            self.wfile.write(sse_data.encode('utf-8'))
            self.wfile.flush()
        
        logger.info(f"[LEGACY MODE] Streaming response completed, total events: {len(events)}")

    def _stream_smart(self, response):
        """混合流式模式：thinking/tool_use立即转发，text块智能流式"""
        buffer = b''
        event_type = None
        event_count = 0
        
        current_block_type = None
        current_block_index = 0
        text_buffer = ""
        text_block_index = -1
        message_data = None
        usage_data = None
        stop_reason = None
        pending_text_blocks = []
        
        text_state = "NORMAL"
        text_match_buffer = ""
        text_content_buffer = ""
        
        logger.info("[SMART MODE] Starting...")
        
        while True:
            chunk = response.read(4096)
            if not chunk:
                break
            buffer += chunk
            
            lines = buffer.split(b'\n')
            buffer = lines[-1]
            
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
                        event_count += 1
                        
                        if event_type == "message_start":
                            message_data = data.get("message", {})
                            self._send_sse_event("message_start", data)
                            
                        elif event_type == "content_block_start":
                            content_block = data.get("content_block", {})
                            current_block_type = content_block.get("type")
                            current_block_index = data.get("index", 0)
                            
                            if current_block_type == "text":
                                self._send_sse_event("content_block_start", data)
                                text_buffer = ""
                                text_match_buffer = ""
                                text_content_buffer = ""
                                text_state = "NORMAL"
                                text_block_index = current_block_index
                            elif current_block_type == "thinking":
                                self._send_sse_event("content_block_start", data)
                            elif current_block_type == "tool_use":
                                self._send_sse_event("content_block_start", data)
                            else:
                                self._send_sse_event("content_block_start", data)
                                
                        elif event_type == "content_block_delta":
                            delta = data.get("delta", {})
                            delta_type = delta.get("type")
                            
                            if current_block_type == "text" and delta_type == "text_delta":
                                delta_text = delta.get("text", "")
                                
                                if text_state == "NORMAL":
                                    has_potential = False
                                    for char in delta_text:
                                        if char == "<":
                                            has_potential = True
                                            break
                                    if not has_potential:
                                        self._send_sse_event("content_block_delta", data)
                                    else:
                                        for char in delta_text:
                                            if text_state == "NORMAL":
                                                if char == "<":
                                                    text_match_buffer += char
                                                    text_state = "MATCHING"
                                                else:
                                                    self._send_sse_event("content_block_delta", {
                                                        "type": "content_block_delta",
                                                        "index": current_block_index,
                                                        "delta": {
                                                            "type": "text_delta",
                                                            "text": char
                                                        }
                                                    })
                                            elif text_state == "MATCHING":
                                                text_match_buffer += char
                                                combined = text_match_buffer
                                                
                                                if combined.startswith("<think"):
                                                    if len(combined) >= len("<think>") and combined.startswith("<think>"):
                                                        text_content_buffer += combined
                                                        text_match_buffer = ""
                                                        text_state = "BUFFERING_THINK"
                                                    else:
                                                        pass
                                                elif combined.startswith("<tool_call"):
                                                    if len(combined) >= len("<tool_call>") and combined.startswith("<tool_call>"):
                                                        text_content_buffer += combined
                                                        text_match_buffer = ""
                                                        text_state = "BUFFERING_TOOL"
                                                    else:
                                                        pass
                                                elif not ("<think".startswith(combined) or "<tool_call".startswith(combined)):
                                                    logger.info(f"[SMART MODE] Match failed: '{text_match_buffer}' -> output as text")
                                                    self._send_sse_event("content_block_delta", {
                                                        "type": "content_block_delta",
                                                        "index": current_block_index,
                                                        "delta": {
                                                            "type": "text_delta",
                                                            "text": text_match_buffer
                                                        }
                                                    })
                                                    text_match_buffer = ""
                                                    text_state = "NORMAL"
                                else:
                                    for char in delta_text:
                                        if text_state == "BUFFERING_THINK":
                                            text_content_buffer += char
                                            if "</think>" in text_content_buffer:
                                                if REMOVE_THINK_TAGS:
                                                    from think_remover import strip_think_tags
                                                    processed = strip_think_tags(text_content_buffer)
                                                    logger.info(f"[SMART MODE] Matched <think/> tag, removed: {len(text_content_buffer) - len(processed)} chars")
                                                    if processed:
                                                        self._send_sse_event("content_block_delta", {
                                                            "type": "content_block_delta",
                                                            "index": current_block_index,
                                                            "delta": {
                                                                "type": "text_delta",
                                                                "text": processed
                                                            }
                                                        })
                                                text_content_buffer = ""
                                                text_state = "NORMAL"
                                        elif text_state == "BUFFERING_TOOL":
                                            text_content_buffer += char
                                            if "</tool_call>" in text_content_buffer:
                                                if PARSE_XML_TOOLS:
                                                    from xml_parser import parse_qwen_xml_tools_ClaudeCode
                                                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(text_content_buffer)
                                                    if parsed_tools:
                                                        logger.info(f"[SMART MODE] Matched <tool_call/> tag, parsed {len(parsed_tools)} tool(s)")
                                                        for tool_block in parsed_tools:
                                                            self._send_sse_event("content_block_stop", {
                                                                "type": "content_block_stop",
                                                                "index": current_block_index
                                                            })
                                                            current_block_index += 1
                                                            self._send_sse_event("content_block_start", {
                                                                "type": "content_block_start",
                                                                "index": current_block_index,
                                                                "content_block": tool_block
                                                            })
                                                            self._send_sse_event("content_block_delta", {
                                                                "type": "content_block_delta",
                                                                "index": current_block_index,
                                                                "delta": {
                                                                    "type": "input_json_delta",
                                                                    "partial_json": json.dumps(tool_block.get("input", {}))
                                                                }
                                                            })
                                                            self._send_sse_event("content_block_stop", {
                                                                "type": "content_block_stop",
                                                                "index": current_block_index
                                                            })
                                                            current_block_index += 1
                                                        self._send_sse_event("content_block_start", {
                                                            "type": "content_block_start",
                                                            "index": current_block_index,
                                                            "content_block": {"type": "text", "text": ""}
                                                        })
                                                text_content_buffer = ""
                                                text_state = "NORMAL"
                            elif current_block_type == "thinking" and delta_type == "thinking_delta":
                                self._send_sse_event("content_block_delta", data)
                            elif current_block_type == "tool_use" and delta_type == "input_json_delta":
                                self._send_sse_event("content_block_delta", data)
                            else:
                                self._send_sse_event("content_block_delta", data)
                                
                        elif event_type == "content_block_stop":
                            if current_block_type == "text":
                                if text_match_buffer:
                                    self._send_sse_event("content_block_delta", {
                                        "type": "content_block_delta",
                                        "index": current_block_index,
                                        "delta": {
                                            "type": "text_delta",
                                            "text": text_match_buffer
                                        }
                                    })
                                if text_content_buffer:
                                    processed_text = text_content_buffer
                                    if PARSE_XML_TOOLS:
                                        from xml_parser import parse_qwen_xml_tools_ClaudeCode
                                        parsed_tools = parse_qwen_xml_tools_ClaudeCode(text_content_buffer)
                                        if parsed_tools:
                                            logger.info(f"[SMART MODE] Parsed {len(parsed_tools)} tool(s) from buffered content")
                                            for tool_block in parsed_tools:
                                                self._send_sse_event("content_block_stop", {
                                                    "type": "content_block_stop",
                                                    "index": current_block_index
                                                })
                                                current_block_index += 1
                                                self._send_sse_event("content_block_start", {
                                                    "type": "content_block_start",
                                                    "index": current_block_index,
                                                    "content_block": tool_block
                                                })
                                                self._send_sse_event("content_block_delta", {
                                                    "type": "content_block_delta",
                                                    "index": current_block_index,
                                                    "delta": {
                                                        "type": "input_json_delta",
                                                        "partial_json": json.dumps(tool_block.get("input", {}))
                                                    }
                                                })
                                                self._send_sse_event("content_block_stop", {
                                                    "type": "content_block_stop",
                                                    "index": current_block_index
                                                })
                                                current_block_index += 1
                                            self._send_sse_event("content_block_start", {
                                                "type": "content_block_start",
                                                "index": current_block_index,
                                                "content_block": {"type": "text", "text": ""}
                                            })
                                            processed_text = ""
                                    if REMOVE_THINK_TAGS and processed_text:
                                        from think_remover import strip_think_tags
                                        processed_text = strip_think_tags(processed_text)
                                    if processed_text.strip():
                                        self._send_sse_event("content_block_delta", {
                                            "type": "content_block_delta",
                                            "index": current_block_index,
                                            "delta": {
                                                "type": "text_delta",
                                                "text": processed_text
                                            }
                                        })
                                self._send_sse_event("content_block_stop", data)
                                text_buffer = ""
                                text_match_buffer = ""
                                text_content_buffer = ""
                                text_state = "NORMAL"
                                text_block_index = -1
                            else:
                                self._send_sse_event("content_block_stop", data)
                            
                            current_block_type = None
                            
                        elif event_type == "message_delta":
                            usage_data = data.get("usage", {})
                            stop_reason = data.get("delta", {}).get("stop_reason")
                            self._send_sse_event("message_delta", data)
                            
                        elif event_type == "message_stop":
                            self._send_sse_event("message_stop", data)
                            
                        else:
                            self._send_sse_event(event_type, data)
                            
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON: {value}")
                    event_type = None
        
        logger.info(f"[SMART MODE] Completed, events: {event_count}")

    def _send_sse_event(self, event_type, data):
        """发送单个SSE事件"""
        sse_data = format_sse_event(event_type, data)
        self.wfile.write(sse_data.encode('utf-8'))
        self.wfile.flush()
