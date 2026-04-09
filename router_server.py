import socketserver

from config import CONFIG, LOG_ALL_TRAFFIC
from handlers import RouterHTTPHandler
from logger import logger

# 启动服务器
def main():
    host = CONFIG.get("server", {}).get("host", "localhost")
    port = CONFIG.get("server", {}).get("port", 25565)
    
    logger.info(f"Router server starting on {host}:{port}")
    logger.info(f"Forwarding requests to {CONFIG.get('target', {}).get('host', 'localhost')}:{CONFIG.get('target', {}).get('port', 12134)}")
    logger.info(f"log_all_traffic: {LOG_ALL_TRAFFIC}")
    
    Handler = RouterHTTPHandler
    
    # 使用 ThreadingTCPServer 支持并发请求
    with socketserver.ThreadingTCPServer((host, port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server stopped by user")

if __name__ == "__main__":
    main()