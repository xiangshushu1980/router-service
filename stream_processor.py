import json
import datetime
from logger import logger
from xml_parser import parse_qwen_xml_tools_ClaudeCode, remove_parsed_tool_calls_from_thinking
from think_remover import strip_think_tags
from stop_reason_fixer import fix_stop_reason
from utils import log_complete_message
from config import PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON

class StreamProcessor:
    """流式响应处理器 - 支持两种模式"""
    
    def __init__(self, smart_streaming=False):
        self.smart_streaming = smart_streaming
        
        # 旧模式状态
        self.message = None
        self.content_blocks = []
        self.current_block = None
        self.current_text = ""
        self.current_thinking = ""
        self.current_tool_input = ""
        self.usage = None
        self.stop_reason = None
        
        # 混合流式状态
        self._reset_smart_state()
    
    def _reset_smart_state(self):
        """重置混合流式状态"""
        self.smart_current_block_type = None
        self.smart_buffer_text = ""
        self.smart_buffer_thinking = ""
        self.smart_final_blocks = []
        self.smart_raw_events = []  # 保存原始事件用于重新生成
        self.smart_current_index = 0
        self.smart_message = None
        self.smart_usage = None
        self.smart_stop_reason = None
    
    def _detect_changes(self, original, modified):
        """检测两个对象之间的变化"""
        changes = []
        
        def compare_objects(o, m, path=""):
            if isinstance(o, dict) and isinstance(m, dict):
                for key in m:
                    new_path = f"{path}.{key}" if path else key
                    if key not in o:
                        changes.append({
                            "path": new_path,
                            "old_value": None,
                            "new_value": m[key]
                        })
                    else:
                        compare_objects(o[key], m[key], new_path)
                for key in o:
                    if key not in m:
                        new_path = f"{path}.{key}" if path else key
                        changes.append({
                            "path": new_path,
                            "old_value": o[key],
                            "new_value": None
                        })
            elif isinstance(o, list) and isinstance(m, list):
                for i, (o_item, m_item) in enumerate(zip(o, m)):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    compare_objects(o_item, m_item, new_path)
                if len(o) != len(m):
                    changes.append({
                        "path": path,
                        "old_length": len(o),
                        "new_length": len(m)
                    })
            elif o != m:
                changes.append({
                    "path": path,
                    "old_value": o,
                    "new_value": m
                })
        
        compare_objects(original, modified)
        return changes
        
    def process_event(self, event_type, data):
        """处理单个流式事件 - 分发到对应模式"""
        if self.smart_streaming:
            self._process_event_smart(event_type, data)
        else:
            self._process_event_legacy(event_type, data)
    
    def _process_event_legacy(self, event_type, data):
        """旧模式：累积所有事件"""
        if event_type == "message_start":
            self.message = data.get("message", {})
            logger.debug(f"Message start: {json.dumps(self.message, ensure_ascii=False)}")
        elif event_type == "content_block_start":
            self.current_block = data.get("content_block", {})
            logger.debug(f"Content block start: {json.dumps(self.current_block, ensure_ascii=False)}")
            if self.current_block.get("type") == "thinking":
                self.current_thinking = ""
            elif self.current_block.get("type") == "tool_use":
                self.current_tool_input = ""
            else:
                self.current_text = ""
        elif event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "thinking_delta":
                self.current_thinking += delta.get("thinking", "")
            elif delta.get("type") == "text_delta":
                self.current_text += delta.get("text", "")
            elif delta.get("type") == "input_json_delta":
                self.current_tool_input += delta.get("partial_json", "")
        elif event_type == "content_block_stop":
            if self.current_block:
                block_type = self.current_block.get("type")
                if block_type == "thinking":
                    self.content_blocks.append({
                        "type": "thinking",
                        "thinking": self.current_thinking
                    })
                elif block_type == "tool_use":
                    tool_block = dict(self.current_block)
                    if self.current_tool_input:
                        try:
                            tool_block["input"] = json.loads(self.current_tool_input)
                        except json.JSONDecodeError:
                            tool_block["input"] = {}
                    self.content_blocks.append(tool_block)
                else:
                    self.content_blocks.append({
                        "type": "text",
                        "text": self.current_text
                    })
            self.current_block = None
            self.current_text = ""
            self.current_thinking = ""
            self.current_tool_input = ""
        elif event_type == "message_delta":
            self.usage = data.get("usage", {})
            self.stop_reason = data.get("delta", {}).get("stop_reason")
        elif event_type == "message_stop":
            pass
    
    def _process_event_smart(self, event_type, data):
        """混合流式模式：根据块类型选择处理方式"""
        self.smart_raw_events.append((event_type, data))
        
        if event_type == "message_start":
            self.smart_message = data.get("message", {})
        elif event_type == "content_block_start":
            content_block = data.get("content_block", {})
            self.smart_current_block_type = content_block.get("type")
        elif event_type == "content_block_delta":
            delta = data.get("delta", {})
            if self.smart_current_block_type == "thinking":
                self.smart_buffer_thinking += delta.get("thinking", "")
            elif self.smart_current_block_type == "text":
                self.smart_buffer_text += delta.get("text", "")
        elif event_type == "content_block_stop":
            if self.smart_current_block_type == "thinking":
                thinking_content = self.smart_buffer_thinking

                if PARSE_XML_TOOLS:
                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(thinking_content)
                    if parsed_tools:
                        logger.warning(f"[SMART MODE] Found tool_call in thinking block, converting to normal tool_use: {json.dumps(parsed_tools, ensure_ascii=False)}")

                        # 记录错误日志 - 模型错误地将tool_call放在thinking中
                        error_info = {
                            "error_type": "ToolCallInThinkingBlock",
                            "message": "Model incorrectly placed tool_call inside thinking block (streaming mode)",
                            "original_thinking": thinking_content,
                            "parsed_tools": parsed_tools,
                            "timestamp": datetime.datetime.now().isoformat()
                        }
                        log_complete_message(error_info, "error")

                        # 从thinking内容中移除已解析的tool_call XML
                        cleaned_thinking = remove_parsed_tool_calls_from_thinking(thinking_content, parsed_tools)

                        # 如果有剩余的thinking内容，添加清理后的thinking块
                        if cleaned_thinking and cleaned_thinking.strip():
                            self.smart_final_blocks.append({
                                "type": "thinking",
                                "thinking": cleaned_thinking,
                                "signature": ""
                            })

                        # 添加解析后的tool_use块
                        self.smart_final_blocks.extend(parsed_tools)
                    else:
                        # 没有解析到工具调用，正常添加thinking块
                        self.smart_final_blocks.append({
                            "type": "thinking",
                            "thinking": thinking_content
                        })
                else:
                    # 未启用XML工具解析，正常添加thinking块
                    self.smart_final_blocks.append({
                        "type": "thinking",
                        "thinking": thinking_content
                    })
            elif self.smart_current_block_type == "text":
                text = self.smart_buffer_text
                if PARSE_XML_TOOLS:
                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(text)
                    if parsed_tools:
                        self.smart_final_blocks.extend(parsed_tools)
                    else:
                        if REMOVE_THINK_TAGS:
                            text = strip_think_tags(text)
                        self.smart_final_blocks.append({"type": "text", "text": text})
                else:
                    if REMOVE_THINK_TAGS:
                        text = strip_think_tags(text)
                    self.smart_final_blocks.append({"type": "text", "text": text})
            elif self.smart_current_block_type == "tool_use":
                tool_block = None
                for evt_type, evt_data in self.smart_raw_events:
                    if evt_type == "content_block_start":
                        cb = evt_data.get("content_block", {})
                        if cb.get("type") == "tool_use":
                            tool_block = dict(cb)
                            break
                if tool_block:
                    self.smart_final_blocks.append(tool_block)
            
            self.smart_current_block_type = None
            self.smart_buffer_text = ""
            self.smart_buffer_thinking = ""
        elif event_type == "message_delta":
            self.smart_usage = data.get("usage", {})
            self.smart_stop_reason = data.get("delta", {}).get("stop_reason")
    
    def process_content(self):
        """处理累积的内容"""
        if self.smart_streaming:
            self._process_content_smart()
        else:
            self._process_content_legacy()
        
        # 记录完整的流式响应消息
        if self.smart_streaming:
            if self.smart_message:
                response_data = {
                    "message": self.smart_message,
                    "content": self.smart_final_blocks,
                    "stop_reason": self.smart_stop_reason,
                    "usage": self.smart_usage
                }
                log_complete_message(response_data, "response")
        else:
            if self.message:
                response_data = {
                    "message": self.message,
                    "content": self.content_blocks,
                    "stop_reason": self.stop_reason,
                    "usage": self.usage
                }
                log_complete_message(response_data, "response")
    
    def _process_content_legacy(self):
        """旧模式：处理累积的内容"""
        if not self.content_blocks:
            return
        
        if not PARSE_XML_TOOLS and not REMOVE_THINK_TAGS and not FIX_STOP_REASON:
            return
        
        original_data = {
            "content_blocks": self._deep_copy(self.content_blocks),
            "stop_reason": self.stop_reason
        }
        
        new_blocks = []
        for block in self.content_blocks:
            if block.get("type") == "text":
                text = block.get("text", "")
                
                if PARSE_XML_TOOLS:
                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(text)
                    if parsed_tools:
                        new_blocks.extend(parsed_tools)
                        continue
                
                if REMOVE_THINK_TAGS:
                    text = strip_think_tags(text)
                
                new_blocks.append({"type": "text", "text": text})
            
            elif block.get("type") == "thinking":
                thinking = block.get("thinking", "")
                
                if PARSE_XML_TOOLS:
                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(thinking)
                    if parsed_tools:
                        new_blocks.extend(parsed_tools)
                        continue
                
                new_blocks.append({"type": "thinking", "thinking": thinking})
            
            else:
                new_blocks.append(block)
        
        self.content_blocks = new_blocks
        
        if FIX_STOP_REASON and self.stop_reason:
            has_tools = any(b.get("type") == "tool_use" for b in self.content_blocks)
            if has_tools and self.stop_reason in ("end_turn", "stop", "eos_token", "", None):
                self.stop_reason = "tool_use"
        
        modified_data = {
            "content_blocks": self.content_blocks,
            "stop_reason": self.stop_reason
        }
        
        changes = self._detect_changes(original_data, modified_data)
        if changes:
            logger.info(f"Response modified: {json.dumps(changes, ensure_ascii=False)}")
    
    def _process_content_smart(self):
        """混合流式模式：处理已完成的块"""
        if FIX_STOP_REASON and self.smart_stop_reason:
            has_tools = any(b.get("type") == "tool_use" for b in self.smart_final_blocks)
            if has_tools and self.smart_stop_reason in ("end_turn", "stop", "eos_token", "", None):
                self.smart_stop_reason = "tool_use"
    
    def _deep_copy(self, obj):
        """深拷贝对象（比 json.loads(json.dumps) 更快）"""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(v) for v in obj]
        else:
            return obj
    
    def generate_events(self):
        """重新生成流式事件"""
        if self.smart_streaming:
            return self._generate_events_smart()
        else:
            return self._generate_events_legacy()
    
    def _generate_events_legacy(self):
        """旧模式：重新生成事件"""
        events = []
        
        if self.message:
            msg = dict(self.message)
            msg["content"] = []
            events.append(("message_start", {"type": "message_start", "message": msg}))
        
        for i, block in enumerate(self.content_blocks):
            events.append(("content_block_start", {
                "type": "content_block_start",
                "index": i,
                "content_block": block
            }))
            
            if block.get("type") == "text":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "text_delta",
                        "text": block.get("text", "")
                    }
                }))
            elif block.get("type") == "thinking":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "thinking_delta",
                        "thinking": block.get("thinking", "")
                    }
                }))
            elif block.get("type") == "tool_use":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block.get("input", {}))
                    }
                }))
            
            events.append(("content_block_stop", {
                "type": "content_block_stop",
                "index": i
            }))
        
        delta = {"type": "message_delta", "delta": {}}
        if self.stop_reason:
            delta["delta"]["stop_reason"] = self.stop_reason
        if self.usage:
            delta["usage"] = self.usage
        events.append(("message_delta", delta))
        
        events.append(("message_stop", {"type": "message_stop"}))
        
        return events
    
    def _generate_events_smart(self):
        """混合流式模式：重新生成事件"""
        events = []
        
        if self.smart_message:
            msg = dict(self.smart_message)
            msg["content"] = []
            events.append(("message_start", {"type": "message_start", "message": msg}))
        
        for i, block in enumerate(self.smart_final_blocks):
            events.append(("content_block_start", {
                "type": "content_block_start",
                "index": i,
                "content_block": block
            }))
            
            if block.get("type") == "text":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "text_delta",
                        "text": block.get("text", "")
                    }
                }))
            elif block.get("type") == "thinking":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "thinking_delta",
                        "thinking": block.get("thinking", "")
                    }
                }))
            elif block.get("type") == "tool_use":
                events.append(("content_block_delta", {
                    "type": "content_block_delta",
                    "index": i,
                    "delta": {
                        "type": "input_json_delta",
                        "partial_json": json.dumps(block.get("input", {}))
                    }
                }))
            
            events.append(("content_block_stop", {
                "type": "content_block_stop",
                "index": i
            }))
        
        delta = {"type": "message_delta", "delta": {}}
        if self.smart_stop_reason:
            delta["delta"]["stop_reason"] = self.smart_stop_reason
        if self.smart_usage:
            delta["usage"] = self.smart_usage
        events.append(("message_delta", delta))
        
        events.append(("message_stop", {"type": "message_stop"}))
        
        return events

def parse_sse_line(line):
    """解析 SSE 行"""
    if line.startswith("event: "):
        return "event", line[7:]
    elif line.startswith("data: "):
        return "data", line[6:]
    return None, None

def format_sse_event(event_type, data):
    """格式化 SSE 事件"""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
