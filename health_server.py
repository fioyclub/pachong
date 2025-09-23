#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康检查服务器
用于Render部署的健康检查和防止服务休眠
"""

import os
import threading
import time
from flask import Flask, jsonify
from waitress import serve
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/health')
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'timestamp': time.time(),
        'service': 'telegram-bot'
    })

@app.route('/')
def index():
    """根路径"""
    return jsonify({
        'message': 'BC.Game Telegram Bot is running',
        'status': 'active'
    })

@app.route('/ping')
def ping():
    """简单的ping端点"""
    return 'pong'

def run_health_server():
    """运行健康检查服务器"""
    port = int(os.environ.get('PORT', 10000))
    logger.info(f"健康检查服务器启动在端口 {port}")
    serve(app, host='0.0.0.0', port=port)

def start_health_server_thread():
    """在后台线程中启动健康检查服务器"""
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    logger.info("健康检查服务器线程已启动")
    return health_thread

if __name__ == '__main__':
    run_health_server()