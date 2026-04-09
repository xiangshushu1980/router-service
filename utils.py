import json
import datetime
from pathlib import Path

from logger import logger

# 日志目录路径，基于当前脚本所在目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)  # 确保日志目录存在
MESSAGE_LOG_FILE = LOG_DIR / "router_message.log"
ERROR_LOG_FILE = LOG_DIR / "router_error.log"

# 压缩日志数据，避免重复内容
def compress_log_data(data):
    """压缩日志数据，用 ... 替换 system 和 tools 字段，只保留最近两条消息"""
    if isinstance(data, dict):
        compressed = {}
        for key, value in data.items():
            if key in ['system', 'tools']:
                compressed[key] = "... (truncated) ..."
            elif key == 'messages' and isinstance(value, list):
                # 只保留最近的两条消息
                if len(value) > 2:
                    # 创建新列表，避免修改原数据
                    compressed[key] = ["... (truncated, only showing last 2 messages) ..."] + value[-2:]
                else:
                    # 创建浅拷贝，避免修改原数据
                    compressed[key] = list(value)
            else:
                compressed[key] = compress_log_data(value)
        return compressed
    elif isinstance(data, list):
        return [compress_log_data(item) for item in data]
    else:
        return data

# 格式化消息大小
def format_size(size_bytes):
    """格式化消息大小，大于1K使用K为单位，否则使用bytes"""
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} K"
    else:
        return f"{size_bytes} bytes"

# 记录完整消息到单独文件
def log_complete_message(data, message_type):
    """记录完整消息到单独文件"""
    try:
        if message_type == "request":
            # 计算消息大小
            message_json = json.dumps(data, ensure_ascii=False)
            message_size = len(message_json.encode('utf-8'))
            formatted_size = format_size(message_size)
            
            # 直接写入文件，覆盖之前的内容
            with open(MESSAGE_LOG_FILE, "w", encoding='utf-8') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                f.write(f"{timestamp} - DEBUG - === COMPLETE REQUEST (size: {formatted_size}) ===\n")
                f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        elif message_type == "error":
            # 压缩错误数据，只保留最近两条消息，不记录 tool 和 system
            compressed_data = compress_log_data(data)
            
            # 计算消息大小
            error_json = json.dumps(compressed_data, ensure_ascii=False)
            error_size = len(error_json.encode('utf-8'))
            formatted_size = format_size(error_size)
            
            # 追加到错误日志文件
            with open(ERROR_LOG_FILE, "a", encoding='utf-8') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                error_type = data.get("error_type", "Unknown error")
                f.write(f"{timestamp} - ERROR - === COMPLETE ERROR (size: {formatted_size}, type: {error_type}) ===\n")
                f.write(json.dumps(compressed_data, indent=2, ensure_ascii=False) + "\n")
                f.write("\n" + "="*80 + "\n\n")  # 添加分隔线
        elif message_type == "changes":
            # 计算消息大小
            changes_json = json.dumps(data, ensure_ascii=False)
            changes_size = len(changes_json.encode('utf-8'))
            formatted_size = format_size(changes_size)

            # 追加到错误日志文件
            with open(ERROR_LOG_FILE, "a", encoding='utf-8') as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
                f.write(f"{timestamp} - DEBUG - === RESPONSE CHANGES (size: {formatted_size}) ===\n")
                # 使用 indent=2 格式化 JSON，方便阅读
                f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                f.write("\n" + "="*80 + "\n\n")  # 添加分隔线
    except Exception as e:
        logger.warning(f"Failed to log complete message: {str(e)}")