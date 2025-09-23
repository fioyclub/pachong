#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
提供统一的环境变量和配置管理功能
"""

import os
import logging
from typing import List, Optional, Union
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

logger = logging.getLogger(__name__)

class Config:
    """配置管理类"""
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        # Telegram Bot配置
        self.TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.TELEGRAM_WEBHOOK_URL = os.getenv('TELEGRAM_WEBHOOK_URL', '')
        
        # 用户权限配置
        allowed_users_str = os.getenv('ALLOWED_USER_IDS', '')
        self.ALLOWED_USER_IDS = self._parse_user_ids(allowed_users_str)
        
        admin_users_str = os.getenv('ADMIN_USER_IDS', '')
        self.ADMIN_USER_IDS = self._parse_user_ids(admin_users_str)
        
        # 服务器配置
        self.PORT = int(os.getenv('PORT', '8000'))
        self.HOST = os.getenv('HOST', '0.0.0.0')
        self.HEALTH_CHECK_PORT = int(os.getenv('HEALTH_CHECK_PORT', '8080'))
        
        # 内存管理配置
        self.MAX_MEMORY_MB = int(os.getenv('MAX_MEMORY_MB', '450'))
        self.MEMORY_CHECK_INTERVAL = int(os.getenv('MEMORY_CHECK_INTERVAL', '300'))
        self.ENABLE_MEMORY_MONITORING = os.getenv('ENABLE_MEMORY_MONITORING', 'true').lower() == 'true'
        
        # 监控配置
        self.MONITOR_INTERVAL = int(os.getenv('MONITOR_INTERVAL', '30'))
        self.MAX_MONITOR_DURATION = int(os.getenv('MAX_MONITOR_DURATION', '3600'))
        self.ODDS_CHANGE_THRESHOLD = float(os.getenv('ODDS_CHANGE_THRESHOLD', '0.05'))
        
        # 爬虫配置
        self.REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))
        self.REQUEST_DELAY = float(os.getenv('REQUEST_DELAY', '1.0'))
        self.MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
        self.USER_AGENT = os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # 日志配置
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # 数据配置
        self.MAX_EVENTS_PER_REQUEST = int(os.getenv('MAX_EVENTS_PER_REQUEST', '50'))
        self.CACHE_DURATION = int(os.getenv('CACHE_DURATION', '300'))
        
        # 安全配置
        self.RATE_LIMIT_PER_USER = int(os.getenv('RATE_LIMIT_PER_USER', '10'))
        self.RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))
        
        # 调试配置
        self.DEBUG_MODE = os.getenv('DEBUG_MODE', 'false').lower() == 'true'
        self.VERBOSE_LOGGING = os.getenv('VERBOSE_LOGGING', 'false').lower() == 'true'
    
    def _parse_user_ids(self, user_ids_str: str) -> List[int]:
        """解析用户ID字符串"""
        if not user_ids_str:
            return []
        
        try:
            return [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
        except ValueError as e:
            logger.error(f"解析用户ID失败: {e}")
            return []
    
    def is_user_allowed(self, user_id: int) -> bool:
        """检查用户是否被允许"""
        if not self.ALLOWED_USER_IDS:
            return True  # 如果没有设置允许列表，则允许所有用户
        return user_id in self.ALLOWED_USER_IDS
    
    def is_user_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        return user_id in self.ADMIN_USER_IDS
    
    def validate_config(self) -> List[str]:
        """验证配置"""
        errors = []
        
        # 检查必需的配置
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN 未设置")
        
        # 检查端口配置
        if not (1 <= self.PORT <= 65535):
            errors.append(f"PORT 配置无效: {self.PORT}")
        
        if not (1 <= self.HEALTH_CHECK_PORT <= 65535):
            errors.append(f"HEALTH_CHECK_PORT 配置无效: {self.HEALTH_CHECK_PORT}")
        
        # 检查内存配置
        if self.MAX_MEMORY_MB <= 0:
            errors.append(f"MAX_MEMORY_MB 配置无效: {self.MAX_MEMORY_MB}")
        
        if self.MEMORY_CHECK_INTERVAL <= 0:
            errors.append(f"MEMORY_CHECK_INTERVAL 配置无效: {self.MEMORY_CHECK_INTERVAL}")
        
        # 检查监控配置
        if self.MONITOR_INTERVAL <= 0:
            errors.append(f"MONITOR_INTERVAL 配置无效: {self.MONITOR_INTERVAL}")
        
        if self.MAX_MONITOR_DURATION <= 0:
            errors.append(f"MAX_MONITOR_DURATION 配置无效: {self.MAX_MONITOR_DURATION}")
        
        # 检查爬虫配置
        if self.REQUEST_TIMEOUT <= 0:
            errors.append(f"REQUEST_TIMEOUT 配置无效: {self.REQUEST_TIMEOUT}")
        
        if self.REQUEST_DELAY < 0:
            errors.append(f"REQUEST_DELAY 配置无效: {self.REQUEST_DELAY}")
        
        if self.MAX_RETRIES < 0:
            errors.append(f"MAX_RETRIES 配置无效: {self.MAX_RETRIES}")
        
        return errors
    
    def get_config_summary(self) -> str:
        """获取配置摘要"""
        return f"""
⚙️ **配置摘要**

🤖 Bot Token: {'✅ 已设置' if self.TELEGRAM_BOT_TOKEN else '❌ 未设置'}
👥 允许用户: {len(self.ALLOWED_USER_IDS)} 个
👑 管理员: {len(self.ADMIN_USER_IDS)} 个
🌐 端口: {self.PORT}
💾 最大内存: {self.MAX_MEMORY_MB}MB
⏱️ 监控间隔: {self.MONITOR_INTERVAL}秒
🔍 请求超时: {self.REQUEST_TIMEOUT}秒
📊 日志级别: {self.LOG_LEVEL}
🐛 调试模式: {'✅ 开启' if self.DEBUG_MODE else '❌ 关闭'}
"""
    
    def reload_config(self):
        """重新加载配置"""
        load_dotenv(override=True)
        self._load_config()
        logger.info("配置已重新加载")

# 全局配置实例
_global_config = None

def get_config() -> Config:
    """获取全局配置实例"""
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config

def validate_environment() -> bool:
    """验证环境配置"""
    config = get_config()
    errors = config.validate_config()
    
    if errors:
        logger.error("配置验证失败:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    logger.info("配置验证通过")
    return True

def setup_logging():
    """设置日志配置"""
    config = get_config()
    
    # 设置日志级别
    log_level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format=config.LOG_FORMAT,
        handlers=[
            logging.StreamHandler(),
        ]
    )
    
    # 如果启用详细日志，降低第三方库的日志级别
    if not config.VERBOSE_LOGGING:
        logging.getLogger('aiohttp').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('telegram').setLevel(logging.WARNING)
    
    logger.info(f"日志系统已初始化，级别: {config.LOG_LEVEL}")

def get_environment_info() -> dict:
    """获取环境信息"""
    config = get_config()
    
    return {
        'python_version': os.sys.version,
        'platform': os.name,
        'cwd': os.getcwd(),
        'env_vars_count': len(os.environ),
        'config_valid': len(config.validate_config()) == 0,
        'debug_mode': config.DEBUG_MODE,
        'memory_monitoring': config.ENABLE_MEMORY_MONITORING
    }