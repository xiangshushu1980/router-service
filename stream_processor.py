import json
from logger import logger
from xml_parser import parse_qwen_xml_tools_ClaudeCode
from think_remover import strip_think_tags
from stop_reason_fixer import fix_stop_reason
from config import PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON

class StreamProcessor:
    """流式响应处理器"""
    
    def __init__(self):
        self.message = None
        self.content_blocks = []
        self.current_block = None
        self.current_text = ""
        self.current_thinking = ""
        self.current_tool_input = ""
        self.usage = None
        self.stop_reason = None
    
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
        """处理单个流式事件"""
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
    
    def process_content(self):
        """处理累积的内容"""
        if not self.content_blocks:
            return
        
        # 如果没有任何功能开启，直接返回
        if not PARSE_XML_TOOLS and not REMOVE_THINK_TAGS and not FIX_STOP_REASON:
            return
        
        original_data = {
            "content_blocks": self._deep_copy(self.content_blocks),
            "stop_reason": self.stop_reason
        }
        
        logger.info(f"Original content blocks: {json.dumps(self.content_blocks, ensure_ascii=False)}")
        
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
                
                if REMOVE_THINK_TAGS:
                    thinking = strip_think_tags(thinking)
                
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
            logger.info("-" * 80)
            logger.info("RESPONSE CHANGES:")
            for change in changes:
                logger.info(f"  {json.dumps(change, ensure_ascii=False)}")
            logger.info("-" * 80)
    
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
