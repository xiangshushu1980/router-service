import json

# 加载配置
CONFIG = {}
try:
    with open('config.json', 'r', encoding='utf-8') as f:
        CONFIG = json.load(f)
except Exception as e:
    print(f"Error loading config: {e}")
    # 使用默认配置
    CONFIG = {
        "server": {
            "host": "localhost",
            "port": 25565
        },
        "target": {
            "host": "localhost",
            "port": 12134
        },
        "logging": {
            "log_all_traffic": True,
            "compress_log_data": True,
            "router_log_max_bytes": 5*1024*1024,
            "router_log_backup_count": 5
        },
        "features": {
            "force_stream_false": True,
            "parse_xml_tools": True,
            "remove_think_tags": True,
            "fix_stop_reason": True,
            "enable_thinking": False,
            "smart_streaming": False
        }
    }

# 日志配置常量
LOG_ALL_TRAFFIC = CONFIG.get("logging", {}).get("log_all_traffic", True)
COMPRESS_LOG_DATA = CONFIG.get("logging", {}).get("compress_log_data", True)

# 功能开关常量
FEATURES = CONFIG.get("features", {})
FORCE_STREAM_FALSE = FEATURES.get("force_stream_false", True)
PARSE_XML_TOOLS = FEATURES.get("parse_xml_tools", True)
REMOVE_THINK_TAGS = FEATURES.get("remove_think_tags", True)
FIX_STOP_REASON = FEATURES.get("fix_stop_reason", True)
ENABLE_THINKING = FEATURES.get("enable_thinking", None)
SMART_STREAMING = FEATURES.get("smart_streaming", False)