import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import CONFIG

# 日志目录路径，基于当前脚本所在目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)  # 确保日志目录存在

# 配置日志 - 合并日志（按大小滚动）
logger = logging.getLogger(__name__)

# 检查是否启用 DEBUG 模式
enable_debug = CONFIG.get("logging", {}).get("debug", False)
logger.setLevel(logging.DEBUG if enable_debug else logging.INFO)

# 日志格式
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG if enable_debug else logging.INFO)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# 文件输出（按大小滚动）
file_handler = RotatingFileHandler(
    LOG_DIR / "router.log",
    maxBytes=CONFIG.get("logging", {}).get("router_log_max_bytes", 5*1024*1024),
    backupCount=CONFIG.get("logging", {}).get("router_log_backup_count", 5),
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG if enable_debug else logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def set_debug_logging(enabled):
    """设置是否启用 DEBUG 日志"""
    if enabled:
        logger.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.DEBUG)
        file_handler.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
        console_handler.setLevel(logging.INFO)
        file_handler.setLevel(logging.INFO)