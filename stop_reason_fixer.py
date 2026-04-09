def fix_stop_reason(stop_reason, content=None):
    """修复finish_reason
    
    支持两种调用方式：
    1. fix_stop_reason(stop_reason, content) - 传入单独的参数
    2. fix_stop_reason(message) - 传入整个消息对象
    """
    try:
        # 检查是否传入的是整个消息对象
        if isinstance(stop_reason, dict) and content is None:
            message = stop_reason
            has_tools = any(b.get("type") == "tool_call" for b in message.get("content", []))
            if has_tools and message.get("stop_reason") in ("stop", "error", "eos_token", "end_turn", "", None):
                message["stop_reason"] = "tool_use"
            return message.get("stop_reason", stop_reason)
        
        # 传入的是单独的参数
        # 检查 content 中是否包含工具调用
        has_tools = False
        if content:
            if isinstance(content, list):
                has_tools = any(b.get("type") == "tool_call" for b in content)
            elif isinstance(content, str):
                # 检查字符串中是否包含工具调用相关内容
                has_tools = "tool_call" in content or "function=" in content
        
        if has_tools and stop_reason in ("stop", "error", "eos_token", "end_turn", "", None):
            return "tool_use"
        return stop_reason
    except Exception:
        return stop_reason
