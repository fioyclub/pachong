#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram机器人主程序
用于控制BC.Game足球1X2赔率爬虫
"""

import os
import asyncio
import logging
import json
import psutil
import gc
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
from bc_game_monitor import BCGameMonitor
from bc_game_scraper import BCGameScraper
from health_server import start_health_server_thread

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.allowed_users = self._parse_allowed_users()
        self.monitor_tasks: Dict[int, asyncio.Task] = {}  # 用户ID -> 监控任务
        self.monitor = None
        self.scraper = None
        
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN环境变量未设置")
    
    def _parse_allowed_users(self) -> Set[int]:
        """解析允许的用户ID列表"""
        users_str = os.getenv('ALLOWED_USERS', '')
        if not users_str:
            logger.warning("ALLOWED_USERS环境变量未设置，将允许所有用户")
            return set()
        
        try:
            user_ids = [int(uid.strip()) for uid in users_str.split(',') if uid.strip()]
            return set(user_ids)
        except ValueError as e:
            logger.error(f"解析ALLOWED_USERS失败: {e}")
            return set()
    
    def _check_permission(self, user_id: int) -> bool:
        """检查用户权限"""
        if not self.allowed_users:  # 如果没有设置允许用户，则允许所有用户
            return True
        return user_id in self.allowed_users
    
    async def _get_memory_info(self) -> str:
        """获取内存使用信息"""
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        return f"内存使用: {memory_mb:.1f}MB"
    
    async def _cleanup_memory(self):
        """清理内存"""
        gc.collect()
        logger.info("执行内存清理")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/start命令"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 抱歉，您没有使用此机器人的权限。")
            return
        
        welcome_text = """
🤖 **BC.Game足球赔率监控机器人**

📋 **可用命令：**
/start - 显示帮助信息
/odds - 获取当前所有足球1X2赔率
/monitor - 开始实时监控赔率变化
/stop - 停止当前监控
/status - 查看机器人状态
/memory - 查看内存使用情况
/help - 显示详细帮助

💡 **使用提示：**
• 监控模式会实时推送赔率变化
• 批量获取模式一次性返回所有赔率
• 支持多用户同时使用
"""
        
        keyboard = [
            [InlineKeyboardButton("📊 获取赔率", callback_data="get_odds")],
            [InlineKeyboardButton("👁️ 开始监控", callback_data="start_monitor")],
            [InlineKeyboardButton("📈 查看状态", callback_data="check_status")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def odds_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/odds命令 - 获取当前赔率"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        await update.message.reply_text("🔄 正在获取当前足球1X2赔率，请稍候...")
        
        try:
            if not self.scraper:
                self.scraper = BCGameScraper()
            
            async with self.scraper:
                odds_data = await self.scraper.get_current_odds()
            
            if not odds_data:
                await update.message.reply_text("❌ 未获取到赔率数据，请稍后重试。")
                return
            
            # 格式化赔率数据
            formatted_message = self._format_odds_message(odds_data)
            
            # 分批发送消息（Telegram消息长度限制）
            await self._send_long_message(update, formatted_message)
            
            # 内存清理
            await self._cleanup_memory()
            
        except Exception as e:
            logger.error(f"获取赔率失败: {e}")
            await update.message.reply_text(f"❌ 获取赔率失败: {str(e)}")
    
    async def monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/monitor命令 - 开始监控"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        # 检查是否已有监控任务
        if user_id in self.monitor_tasks and not self.monitor_tasks[user_id].done():
            await update.message.reply_text("⚠️ 您已经在监控中，请先使用 /stop 停止当前监控。")
            return
        
        await update.message.reply_text("🚀 开始监控足球1X2赔率变化...")
        
        try:
            # 创建监控任务
            task = asyncio.create_task(
                self._run_monitor_for_user(user_id, update)
            )
            self.monitor_tasks[user_id] = task
            
        except Exception as e:
            logger.error(f"启动监控失败: {e}")
            await update.message.reply_text(f"❌ 启动监控失败: {str(e)}")
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/stop命令 - 停止监控"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        if user_id not in self.monitor_tasks or self.monitor_tasks[user_id].done():
            await update.message.reply_text("ℹ️ 您当前没有运行中的监控任务。")
            return
        
        # 取消监控任务
        self.monitor_tasks[user_id].cancel()
        del self.monitor_tasks[user_id]
        
        await update.message.reply_text("⏹️ 监控已停止。")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/status命令 - 查看状态"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        # 统计信息
        active_monitors = len([t for t in self.monitor_tasks.values() if not t.done()])
        total_users = len(self.monitor_tasks)
        memory_info = await self._get_memory_info()
        
        status_text = f"""
📊 **机器人状态**

🔄 活跃监控: {active_monitors} 个
👥 总用户数: {total_users} 个
💾 {memory_info}
⏰ 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🔍 **您的状态:**
监控状态: {'🟢 运行中' if user_id in self.monitor_tasks and not self.monitor_tasks[user_id].done() else '🔴 已停止'}
"""
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
    
    async def memory_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/memory命令 - 查看内存"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = process.memory_percent()
        
        memory_text = f"""
💾 **内存使用情况**

📊 当前使用: {memory_mb:.1f}MB
📈 使用百分比: {memory_percent:.1f}%
🧹 垃圾回收: {len(gc.get_objects())} 个对象
"""
        
        keyboard = [
            [InlineKeyboardButton("🧹 清理内存", callback_data="cleanup_memory")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            memory_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理/help命令"""
        user_id = update.effective_user.id
        
        if not self._check_permission(user_id):
            await update.message.reply_text("❌ 您没有使用此机器人的权限。")
            return
        
        help_text = """
📖 **详细帮助文档**

**🎯 主要功能：**
• 实时监控BC.Game足球1X2赔率变化
• 批量获取当前所有足球赔率
• 支持多用户同时使用
• 内存管理和性能优化

**📋 命令说明：**

`/start` - 启动机器人，显示欢迎信息
`/odds` - 获取当前所有足球1X2赔率
`/monitor` - 开始实时监控赔率变化
`/stop` - 停止当前的监控任务
`/status` - 查看机器人运行状态
`/memory` - 查看内存使用情况
`/help` - 显示此帮助信息

**💡 使用技巧：**
• 监控模式会持续推送变化，适合长期关注
• 批量模式适合快速查看当前状态
• 可以随时停止和重新开始监控
• 支持内存清理，保持性能稳定

**⚠️ 注意事项：**
• 每个用户同时只能运行一个监控任务
• 长时间监控建议定期重启
• 如遇问题请联系管理员
"""
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮回调"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        if not self._check_permission(user_id):
            await query.edit_message_text("❌ 您没有使用此机器人的权限。")
            return
        
        if query.data == "get_odds":
            await query.edit_message_text("🔄 正在获取赔率数据...")
            # 模拟/odds命令
            await self.odds_command(update, context)
            
        elif query.data == "start_monitor":
            await query.edit_message_text("🚀 正在启动监控...")
            # 模拟/monitor命令
            await self.monitor_command(update, context)
            
        elif query.data == "check_status":
            # 模拟/status命令
            await self.status_command(update, context)
            
        elif query.data == "cleanup_memory":
            await self._cleanup_memory()
            await query.edit_message_text("✅ 内存清理完成！")
    
    async def _run_monitor_for_user(self, user_id: int, update: Update):
        """为特定用户运行监控任务"""
        try:
            if not self.monitor:
                self.monitor = BCGameMonitor()
            
            async def on_odds_change(changes):
                """赔率变化回调函数"""
                if changes:
                    message = self._format_changes_message(changes)
                    try:
                        await update.get_bot().send_message(
                            chat_id=user_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except Exception as e:
                        logger.error(f"发送变化消息失败: {e}")
            
            async with self.monitor:
                await self.monitor.run_continuous_monitoring(callback=on_odds_change)
                
        except asyncio.CancelledError:
            logger.info(f"用户 {user_id} 的监控任务被取消")
        except Exception as e:
            logger.error(f"用户 {user_id} 监控任务异常: {e}")
            try:
                await update.get_bot().send_message(
                    chat_id=user_id,
                    text=f"❌ 监控任务异常: {str(e)}"
                )
            except:
                pass
    
    def _format_odds_message(self, odds_data: List[Dict[str, Any]]) -> str:
        """格式化赔率消息"""
        if not odds_data:
            return "❌ 暂无赔率数据"
        
        message_parts = [f"📊 **当前足球1X2赔率** ({len(odds_data)}场比赛)\n"]
        
        for i, event in enumerate(odds_data[:20], 1):  # 限制显示前20场
            league = event.get('league', '未知联赛')
            home_team = event.get('home_team', '主队')
            away_team = event.get('away_team', '客队')
            odds_1 = event.get('odds_1', 'N/A')
            odds_x = event.get('odds_x', 'N/A')
            odds_2 = event.get('odds_2', 'N/A')
            
            message_parts.append(
                f"{i}. **{league}**\n"
                f"   {home_team} vs {away_team}\n"
                f"   1️⃣ {odds_1} | ❌ {odds_x} | 2️⃣ {odds_2}\n"
            )
        
        if len(odds_data) > 20:
            message_parts.append(f"\n... 还有 {len(odds_data) - 20} 场比赛")
        
        message_parts.append(f"\n⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}")
        
        return "\n".join(message_parts)
    
    def _format_changes_message(self, changes: List[Dict[str, Any]]) -> str:
        """格式化变化消息"""
        if not changes:
            return "ℹ️ 暂无赔率变化"
        
        message_parts = [f"🔄 **赔率变化提醒** ({len(changes)}场)\n"]
        
        for change in changes[:10]:  # 限制显示前10个变化
            league = change.get('league', '未知联赛')
            home_team = change.get('home_team', '主队')
            away_team = change.get('away_team', '客队')
            change_type = change.get('change_type', '变化')
            
            message_parts.append(
                f"📈 **{league}**\n"
                f"   {home_team} vs {away_team}\n"
                f"   {change_type}\n"
            )
        
        if len(changes) > 10:
            message_parts.append(f"\n... 还有 {len(changes) - 10} 个变化")
        
        message_parts.append(f"\n⏰ {datetime.now().strftime('%H:%M:%S')}")
        
        return "\n".join(message_parts)
    
    async def _send_long_message(self, update: Update, message: str, max_length: int = 4000):
        """分批发送长消息"""
        if len(message) <= max_length:
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
            return
        
        # 分割消息
        parts = []
        current_part = ""
        
        for line in message.split('\n'):
            if len(current_part + line + '\n') > max_length:
                if current_part:
                    parts.append(current_part.strip())
                current_part = line + '\n'
            else:
                current_part += line + '\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        # 发送分割后的消息
        for i, part in enumerate(parts):
            if i == 0:
                await update.message.reply_text(part, parse_mode=ParseMode.MARKDOWN)
            else:
                await update.message.reply_text(f"续 {i+1}/{len(parts)}:\n{part}", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(0.5)  # 避免发送过快
    
    async def health_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """健康检查端点"""
        await update.message.reply_text("✅ 机器人运行正常")
    
    def run(self):
        """启动机器人"""
        # 启动健康检查服务器
        start_health_server_thread()
        
        # 创建应用
        application = Application.builder().token(self.bot_token).build()
        
        # 添加命令处理器
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("odds", self.odds_command))
        application.add_handler(CommandHandler("monitor", self.monitor_command))
        application.add_handler(CommandHandler("stop", self.stop_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("memory", self.memory_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("health", self.health_check))
        
        # 添加按钮回调处理器
        application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # 添加错误处理
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"异常: {context.error}")
            if update and hasattr(update, 'message') and update.message:
                try:
                    await update.message.reply_text("❌ 处理请求时发生错误，请稍后重试。")
                except:
                    pass
        
        application.add_error_handler(error_handler)
        
        # 启动机器人
        logger.info("Telegram机器人启动中...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """主函数"""
    try:
        bot = TelegramBot()
        bot.run()
    except KeyboardInterrupt:
        logger.info("机器人已停止")
    except Exception as e:
        logger.error(f"机器人启动失败: {e}")
        raise

if __name__ == "__main__":
    main()