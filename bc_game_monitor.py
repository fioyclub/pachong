# -*- coding: utf-8 -*-
"""
BC.Game：方案B（版本探针 + 快照）
- 轻量轮询探针接口拿最新 version
- 只在 version 变化时拉一次快照
- 解析并打印：eventId | 联赛 | 主队 vs 客队 | 1X2(主/平/客)
- 做了增量对比：只输出赔率变化的场次（首次启动会全量输出）
"""

import asyncio
import aiohttp
import json
import time
import gc
import psutil
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

class BCGameMonitor:
    """BC.Game实时监控类"""
    
    def __init__(self):
        self.probe_url = "https://bc.game/api/sportsbook/v1/probe"
        self.snapshot_url = "https://bc.game/api/sportsbook/v1/snapshot"
        self.last_version = None
        self.last_snapshot = None
        self.session = None
        self.memory_threshold = 80  # 内存使用率阈值
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
            
    def check_memory_usage(self):
        """检查内存使用率"""
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > self.memory_threshold:
            self.cleanup_memory()
            return True
        return False
        
    def cleanup_memory(self):
        """清理内存"""
        # 清理旧数据
        if hasattr(self, 'last_snapshot') and self.last_snapshot:
            self.last_snapshot = None
        # 强制垃圾回收
        gc.collect()
        print(f"内存清理完成，当前使用率: {psutil.virtual_memory().percent}%")
    
    async def get_probe(self) -> Optional[Dict[str, Any]]:
        """异步获取探针数据"""
        try:
            async with self.session.get(self.probe_url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"探针接口请求失败，状态码: {response.status}")
                    return None
        except Exception as e:
            print(f"探针接口请求异常: {e}")
            return None
    
    async def get_snapshot(self) -> Optional[Dict[str, Any]]:
        """异步获取快照数据"""
        try:
            async with self.session.get(self.snapshot_url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"快照接口请求失败，状态码: {response.status}")
                    return None
        except Exception as e:
            print(f"快照接口请求异常: {e}")
            return None

import requests

# ---- 你可以按需改这些常量 ----
BASE    = "https://api-k-c7818b61-623.sptpub.com"
BRAND   = "2103509236163162112"
LANG    = "en"

# 初始探针的"种子版本号"（没要求必须准确，服务端会返回最新；可留空用默认）
SEED_VERSION = "3517201591912"

# 探针间隔（秒）。若能从响应里解析到 Cache-Control: max-age，会优先用那个。
DEFAULT_INTERVAL = 8

# ---- 常量配置 ----
POLL_INTERVAL = 5  # 轮询间隔（秒）

HEADERS = {
    "accept": "application/json",
    "origin": "https://bc.game",
    "referer": "https://bc.game/",
    "user-agent": "Mozilla/5.0"
}

# --------------------------------

def parse_max_age(cache_control: str) -> Optional[int]:
    if not cache_control:
        return None
    m = re.search(r"max-age=(\d+)", cache_control)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None

def get_latest_version(last_version: Optional[str]) -> Tuple[str, int, int]:
    """
    版本探针（side接口）。返回: (最新version, generated, 建议的sleep秒数)
    你之前抓到过 /api/v1/side/brand/{brand}/{some_number} 的响应里含 `version` 和 `generated`
    """
    seed = last_version or SEED_VERSION
    url = f"{BASE}/api/v1/side/brand/{BRAND}/{seed}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    js = r.json()
    ver = str(js.get("version"))
    gen = int(js.get("generated", 0))
    # 从响应头推测节流间隔
    cc = r.headers.get("Cache-Control", "")
    interval = parse_max_age(cc) or DEFAULT_INTERVAL
    return ver, gen, interval

def fetch_snapshot(version: str) -> Dict:
    """
    快照接口（整份大JSON，包含 events/tournaments/categories）
    路径格式：/api/v3/live/brand/{brand}/{lang}/{version}
    """
    url = f"{BASE}/api/v3/live/brand/{BRAND}/{LANG}/{version}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def league_name_from_maps(tournaments: dict, categories: dict, desc: dict) -> str:
    tid = desc.get("tournament_id")
    t = (tournaments.get(str(tid)) or tournaments.get(tid) or {}) if tid else {}
    league = t.get("name", "Unknown League")
    cid = t.get("category_id")
    if cid:
        cat = categories.get(str(cid)) or categories.get(cid) or {}
        country = cat.get("name")
        if country and country not in league:
            league = f"{country} — {league}"
    return league

def team_names(desc: dict) -> Tuple[str, str]:
    home = desc.get("home_name") or desc.get("home") or "Home"
    away = desc.get("away_name") or desc.get("away") or "Away"
    return home, away

def parse_1x2(markets: dict) -> Optional[Tuple[Optional[str], Optional[str], Optional[str]]]:
    """
    返回 (home, draw, away) 或 None
    支持两种常见结构：
    1) {"1":{"": {"1":{"k":..}, "X":{"k":..}, "2":{"k":..}}}}
    2) {"1":{"": {"1":{"k":..}, "2":{"k":..}, "3":{"k":..}}}}  # 2=平, 3=客
    """
    m = markets.get("1")
    if not isinstance(m, dict):
        return None
    for _, outcomes in m.items():  # 取第一条线（通常 key 为 ""）
        if not isinstance(outcomes, dict):
            continue
        if "X" in outcomes:
            return (
                (outcomes.get("1") or {}).get("k"),
                (outcomes.get("X") or {}).get("k"),
                (outcomes.get("2") or {}).get("k") or (outcomes.get("3") or {}).get("k"),
            )
        # 1/2/3结构
        return (
            (outcomes.get("1") or {}).get("k"),
            (outcomes.get("2") or {}).get("k"),
            (outcomes.get("3") or {}).get("k") or (outcomes.get("2") or {}).get("k"),
        )
    return None

def flatten_snapshot_for_1x2(snapshot: Dict) -> Dict[str, Dict]:
    """
    把快照转成 {eventId: {league, home, away, odds:(h,d,a)}} 的精简字典
    方便做增量对比
    """
    events      = snapshot.get("events", {}) or {}
    tournaments = snapshot.get("tournaments", {}) or {}
    categories  = snapshot.get("categories", {}) or {}

    out = {}
    for raw_id, node in events.items():
        event_id = str(raw_id)
        detail = node if isinstance(node, dict) else {}
        desc = detail.get("desc", {}) if detail else {}
        markets = detail.get("markets", {}) if detail else {}

        odds = parse_1x2(markets)
        if not odds:
            # 有些场次列表里没带1X2（但通常快照里多数是带的）
            continue

        league = league_name_from_maps(tournaments, categories, desc) if desc else "Unknown League"
        home, away = team_names(desc)

        out[event_id] = {
            "league": league,
            "home": home,
            "away": away,
            "odds": odds  # (h, d, a)
        }
    return out

def parse_snapshot_data(snapshot: Dict) -> Dict[str, Dict]:
    """
    解析快照数据，提取足球1X2赔率
    返回格式: {event_id: {league, home_team, away_team, odds_1, odds_x, odds_2}}
    """
    result = {}
    
    try:
        sports = snapshot.get('data', {}).get('sports', [])
        for sport in sports:
            if sport.get('name') != 'Football':
                continue
                
            tournaments = sport.get('tournaments', [])
            for tournament in tournaments:
                league_name = tournament.get('name', 'Unknown League')
                
                events = tournament.get('events', [])
                for event in events:
                    event_id = event.get('id')
                    if not event_id:
                        continue
                        
                    home_team = event.get('home', {}).get('name', 'Unknown')
                    away_team = event.get('away', {}).get('name', 'Unknown')
                    
                    # 查找1X2市场
                    markets = event.get('markets', [])
                    for market in markets:
                        if market.get('name') == '1X2':
                            outcomes = market.get('outcomes', [])
                            odds_data = {}
                            
                            for outcome in outcomes:
                                outcome_name = outcome.get('name')
                                odds = outcome.get('odds')
                                
                                if outcome_name == '1':
                                    odds_data['odds_1'] = odds
                                elif outcome_name == 'X':
                                    odds_data['odds_x'] = odds
                                elif outcome_name == '2':
                                    odds_data['odds_2'] = odds
                            
                            # 只有当三个赔率都存在时才记录
                            if len(odds_data) == 3:
                                result[event_id] = {
                                    'league': league_name,
                                    'home_team': home_team,
                                    'away_team': away_team,
                                    **odds_data
                                }
                            break
    except Exception as e:
        print(f"[ERROR] 解析快照数据失败: {e}")
    
    return result

    def diff_and_print(self, prev: Dict[str, Dict], curr: Dict[str, Dict], show_new_only=True) -> List[Dict]:
        """
        对比两次快照的差异，并打印变化的赔率
        返回变化的事件列表
        """
        changes = []
        
        if not prev:
            print(f"[INFO] 首次获取数据，共 {len(curr)} 场比赛")
            if not show_new_only:
                for event_id, data in curr.items():
                    print(f"  {data['league']} | {data['home_team']} vs {data['away_team']} | 1:{data['odds_1']} X:{data['odds_x']} 2:{data['odds_2']}")
            return changes
        
        # 找出有变化的比赛
        changed_events = []
        new_events = []
        
        for event_id, curr_data in curr.items():
            if event_id not in prev:
                new_events.append((event_id, curr_data))
                changes.append({
                    'type': 'new',
                    'event_id': event_id,
                    'data': curr_data
                })
            else:
                prev_data = prev[event_id]
                # 检查赔率是否有变化
                if (prev_data['odds_1'] != curr_data['odds_1'] or 
                    prev_data['odds_x'] != curr_data['odds_x'] or 
                    prev_data['odds_2'] != curr_data['odds_2']):
                    changed_events.append((event_id, prev_data, curr_data))
                    changes.append({
                        'type': 'changed',
                        'event_id': event_id,
                        'prev_data': prev_data,
                        'curr_data': curr_data
                    })
        
        # 打印变化
        if changed_events or new_events:
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 发现变化:")
            
            if new_events:
                print(f"  新增比赛 ({len(new_events)} 场):")
                for event_id, data in new_events:
                    print(f"    {data['league']} | {data['home_team']} vs {data['away_team']} | 1:{data['odds_1']} X:{data['odds_x']} 2:{data['odds_2']}")
            
            if changed_events:
                print(f"  赔率变化 ({len(changed_events)} 场):")
                for event_id, prev_data, curr_data in changed_events:
                    print(f"    {curr_data['league']} | {curr_data['home_team']} vs {curr_data['away_team']}")
                    print(f"      1: {prev_data['odds_1']} → {curr_data['odds_1']}")
                    print(f"      X: {prev_data['odds_x']} → {curr_data['odds_x']}")
                    print(f"      2: {prev_data['odds_2']} → {curr_data['odds_2']}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 无变化")
            
        return changes

    async def monitor_odds_changes(self, callback=None) -> List[Dict]:
        """
        监控赔率变化的主要方法
        callback: 可选的回调函数，当有变化时调用
        返回变化列表
        """
        # 检查内存使用
        self.check_memory_usage()
        
        # 1. 获取探针
        probe_data = await self.get_probe()
        if not probe_data:
            print("[WARN] 探针获取失败")
            return []
        
        current_version = probe_data.get('data', {}).get('version')
        if not current_version:
            print("[WARN] 探针数据中没有版本号")
            return []
        
        # 2. 检查版本是否变化
        if self.last_version is None:
            print(f"[INFO] 初始版本: {current_version}")
            self.last_version = current_version
        elif self.last_version == current_version:
            return []  # 无变化
        else:
            print(f"[INFO] 版本变化: {self.last_version} -> {current_version}")
            self.last_version = current_version
        
        # 3. 版本变化时获取快照
        snapshot_data = await self.get_snapshot()
        if not snapshot_data:
            print("[WARN] 快照获取失败")
            return []
        
        # 4. 解析快照数据
        current_parsed = self.parse_snapshot_data(snapshot_data)
        print(f"[INFO] 解析到 {len(current_parsed)} 场足球1X2比赛")
        
        # 5. 对比并获取变化
        changes = self.diff_and_print(self.last_snapshot, current_parsed)
        
        # 6. 更新缓存
        self.last_snapshot = current_parsed
        
        # 7. 调用回调函数
        if callback and changes:
            try:
                await callback(changes)
            except Exception as e:
                print(f"[ERROR] 回调函数执行失败: {e}")
        
        return changes
    
    async def run_continuous_monitoring(self, callback=None):
        """
        持续监控模式
        """
        print("[INFO] 开始监控 BC.Game 足球1X2赔率变化...")
        
        try:
            while True:
                await self.monitor_odds_changes(callback)
                await asyncio.sleep(self.POLL_INTERVAL)
        except asyncio.CancelledError:
            print("[INFO] 监控已停止")
        except Exception as e:
            print(f"[ERROR] 监控异常: {e}")
    
    async def get_current_odds(self) -> Dict[str, Dict]:
        """
        获取当前所有足球1X2赔率
        """
        snapshot_data = await self.get_snapshot()
        if not snapshot_data:
            return {}
        
        return self.parse_snapshot_data(snapshot_data)

# 兼容旧版本的函数
async def run_monitor_async(callback=None):
    """异步运行监控"""
    async with BCGameMonitor() as monitor:
        await monitor.run_continuous_monitoring(callback)

def run_watch_loop():
    """同步运行监控（兼容旧版本）"""
    asyncio.run(run_monitor_async())

if __name__ == "__main__":
    run_watch_loop()
