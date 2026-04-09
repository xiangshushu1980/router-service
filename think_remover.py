import re

def strip_think_tags(text):
    """移除think标签及其内容"""
    try:
        # 移除完整的 think 标签对
        text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        # 移除单独的 </think> 标签
        text = re.sub(r'^</think>\s*', '', text)
        # 移除单独的 <think> 标签
        text = re.sub(r'<think>\s*', '', text)
        # 返回处理后的文本（不使用strip，保持原始空白）
        return text
    except Exception:
        return text
