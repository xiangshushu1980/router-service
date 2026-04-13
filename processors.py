import json
import traceback
import datetime
from pathlib import Path

from xml_parser import parse_qwen_xml_tools_ClaudeCode, remove_parsed_tool_calls_from_thinking
from think_remover import strip_think_tags
from stop_reason_fixer import fix_stop_reason
from utils import log_complete_message
from logger import logger
from config import PARSE_XML_TOOLS, REMOVE_THINK_TAGS, FIX_STOP_REASON

class ResponseProcessor:
    """响应处理器类"""
    
    def _detect_changes(self, original, modified):
        """检测两个对象之间的变化"""
        changes = []
        
        def compare_objects(o, m, path=""):
            if isinstance(o, dict) and isinstance(m, dict):
                # 检查新增和修改的键
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
                # 检查删除的键
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
                # 检查列表长度变化
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
    
    def process_anthropic_response(self, response_json):
        """处理 Anthropic 格式的响应（Claude Code）"""
        try:
            # 记录原始响应用于比较
            original_response = json.loads(json.dumps(response_json))
            
            # 处理 content 字段
            if 'content' in response_json:
                content = response_json['content']
                if isinstance(content, list):
                    new_content = []
                    for item in content:
                        if isinstance(item, dict):
                            # 处理 text 类型
                            if 'text' in item:
                                text_content = item['text']
                                
                                # 解析 XML 工具调用（可配置）
                                if PARSE_XML_TOOLS:
                                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(text_content)
                                    if parsed_tools:
                                        logger.info(f"Created ClaudeCode tools from text: {json.dumps(parsed_tools, ensure_ascii=False)}")
                                        for tool in parsed_tools:
                                            new_content.append(tool)
                                        continue
                                
                                # 移除 think 标签（可配置）
                                if REMOVE_THINK_TAGS:
                                    stripped_content = strip_think_tags(text_content)
                                    if stripped_content != text_content:
                                        item['text'] = stripped_content
                                        logger.debug("Removed think tags from response")
                                
                                new_content.append(item)
                            # 处理 thinking 类型
                            elif 'thinking' in item:
                                thinking_content = item['thinking']
                                
                                # 解析 XML 工具调用（可配置）
                                if PARSE_XML_TOOLS:
                                    parsed_tools = parse_qwen_xml_tools_ClaudeCode(thinking_content)
                                    if parsed_tools:
                                        logger.warning(f"Found tool_call in thinking block, converting to normal tool_use: {json.dumps(parsed_tools, ensure_ascii=False)}")
                                        
                                        # 记录错误日志 - 模型错误地将tool_call放在thinking中
                                        error_info = {
                                            "error_type": "ToolCallInThinkingBlock",
                                            "message": "Model incorrectly placed tool_call inside thinking block",
                                            "original_thinking": thinking_content,
                                            "parsed_tools": parsed_tools,
                                            "timestamp": datetime.datetime.now().isoformat()
                                        }
                                        log_complete_message(error_info, "error")
                                        
                                        # 从thinking内容中移除已解析的tool_call XML
                                        cleaned_thinking = remove_parsed_tool_calls_from_thinking(thinking_content, parsed_tools)
                                        
                                        # 如果有剩余的thinking内容，添加清理后的thinking块
                                        if cleaned_thinking and cleaned_thinking.strip():
                                            new_content.append({
                                                "type": "thinking",
                                                "thinking": cleaned_thinking,
                                                "signature": item.get("signature", "")
                                            })
                                        
                                        # 添加解析后的tool_use块
                                        for tool in parsed_tools:
                                            new_content.append(tool)
                                        continue
                                
                                new_content.append(item)
                            else:
                                new_content.append(item)
                        else:
                            new_content.append(item)
                    response_json['content'] = new_content
                elif isinstance(content, str):
                    # 解析 XML 工具调用（可配置）
                    if PARSE_XML_TOOLS:
                        parsed_tools = parse_qwen_xml_tools_ClaudeCode(content)
                        if parsed_tools:
                            logger.info(f"Created ClaudeCode tools from string content: {json.dumps(parsed_tools, ensure_ascii=False)}")
                            response_json['content'] = parsed_tools
                        elif REMOVE_THINK_TAGS:
                            # 如果没有解析出工具调用，移除 think 标签
                            stripped_content = strip_think_tags(content)
                            if stripped_content != content:
                                response_json['content'] = stripped_content
                                logger.debug("Removed think tags from response")
                    elif REMOVE_THINK_TAGS:
                        stripped_content = strip_think_tags(content)
                        if stripped_content != content:
                            response_json['content'] = stripped_content
                            logger.debug("Removed think tags from response")
            
            # 修复 stop_reason（可配置）
            if FIX_STOP_REASON and 'stop_reason' in response_json:
                fixed_stop_reason = fix_stop_reason(response_json['stop_reason'], response_json.get('content', ''))
                if fixed_stop_reason != response_json['stop_reason']:
                    response_json['stop_reason'] = fixed_stop_reason
                    logger.debug(f"Fixed stop_reason to: {fixed_stop_reason}")
            
            # 记录修改前后的对比
            if original_response != response_json:
                changes = self._detect_changes(original_response, response_json)
                logger.debug(f"Response modified: {json.dumps(changes, ensure_ascii=False)}")
                # 记录到详细日志
                log_complete_message({"changes": changes}, "changes")
            
            # 记录完整的响应消息
            log_complete_message(response_json, "response")
            
        except Exception as e:
            error_info = {
                "error": str(e),
                "response_json": response_json,
                "traceback": traceback.format_exc(),
                "error_type": "Anthropic response processing"
            }
            log_complete_message(error_info, "error")
            logger.error(f"Error processing Anthropic response: {str(e)}")

# 创建响应处理器实例
response_processor = ResponseProcessor()
