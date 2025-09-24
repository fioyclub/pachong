# -*- coding: utf-8 -*-
"""
BC.Game 足球 1X2 批量抓取：列表URL(含version) -> 遍历events -> 输出联赛/队名/赔率
"""

import asyncio
import aiohttp
import json
import time
import gc
import psutil
from datetime import datetime
from typing import Optional, Dict, Any, List
import requests

class BCGameScraper:
    """BC.Game足球1X2批量抓取类"""
    
    def __init__(self):
        self.snapshot_url = "https://bc.game/api/sportsbook/v1/snapshot"
        self.detail_url_template = "https://bc.game/api/sportsbook/v1/events/{event_id}"
        self.session = None
        self.memory_threshold = 80  # 内存使用率阈值
        self._session_created = False
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self._ensure_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def _ensure_session(self):
        """确保session已创建"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            self._session_created = True
    
    async def close(self):
        """关闭session"""
        if self.session and self._session_created:
            await self.session.close()
            self.session = None
            self._session_created = False
            
    def check_memory_usage(self):
        """检查内存使用率"""
        memory_percent = psutil.virtual_memory().percent
        if memory_percent > self.memory_threshold:
            self.cleanup_memory()
            return True
        return False
        
    def cleanup_memory(self):
        """清理内存"""
        # 强制垃圾回收
        gc.collect()
        print(f"内存清理完成，当前使用率: {psutil.virtual_memory().percent}%")
    
    async def get_snapshot(self) -> Optional[Dict[str, Any]]:
        """异步获取快照数据"""
        try:
            await self._ensure_session()
            async with self.session.get(self.snapshot_url) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"快照接口请求失败，状态码: {response.status}")
                    return None
        except Exception as e:
            print(f"快照接口请求异常: {e}")
            return None
    
    async def fetch_events_snapshot(self) -> Optional[Dict[str, Any]]:
        """异步获取事件快照数据"""
        try:
            await self._ensure_session()
            
            print(f"开始请求API: {LIST_URL}")
            print(f"请求头: {HEADERS}")
            
            async with self.session.get(LIST_URL, headers=HEADERS, timeout=15) as response:
                print(f"API响应状态码: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    print(f"成功获取数据，顶级键: {list(data.keys()) if data else 'None'}")
                    
                    # 检查关键数据结构
                    if 'events' in data:
                        events_count = len(data['events'])
                        print(f"事件数量: {events_count}")
                        
                        # 检查是否有足球相关事件
                        football_events = 0
                        for event_id, event_data in data['events'].items():
                            if event_data and isinstance(event_data, dict) and 'markets' in event_data and event_data['markets'] and '1' in event_data['markets']:
                                football_events += 1
                        print(f"有1X2市场的事件数量: {football_events}")
                    else:
                        print("警告: 响应数据中没有'events'键")
                    
                    return data
                else:
                    print(f"获取事件快照失败，状态码: {response.status}")
                    response_text = await response.text()
                    print(f"错误响应内容: {response_text[:500]}...")
                    return None
        except Exception as e:
            print(f"获取事件快照异常: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def get_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        """获取单个事件的详情"""
        url = f"https://bc.game/api/sportsbook/v1/events/{event_id}"
        
        try:
            await self._ensure_session()
            async with self.session.get(url, headers=HEADERS, timeout=10) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    print(f"获取事件 {event_id} 详情失败，状态码: {response.status}")
                    return None
        except Exception as e:
            print(f"获取事件 {event_id} 详情异常: {e}")
            return None
    
    def parse_snapshot_data(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """解析快照数据，提取足球1X2赔率（适配sptpub.com API）"""
        result = []
        
        try:
            events = snapshot.get('events', {})
            tournaments = snapshot.get('tournaments', {})
            categories = snapshot.get('categories', {})
            sports = snapshot.get('sports', {})
            
            print(f"开始解析快照数据，共 {len(events)} 个事件")
            
            # 统计运动类型
            sport_stats = {}
            filtered_events = 0
            
            for event_id, event_data in events.items():
                try:
                    # 检查事件数据是否有效
                    if not event_data or not isinstance(event_data, dict):
                        continue
                    
                    # 获取事件的运动类型信息
                    desc = event_data.get('desc', {})
                    
                    # 初始化变量
                    sport_id = None
                    sport_name = "Unknown Sport"
                    
                    # 首先尝试从desc中直接获取sport信息
                    sport_id = desc.get('sport')
                    
                    if sport_id and str(sport_id) in sports:
                        sport_info = sports.get(str(sport_id), {})
                        sport_name = sport_info.get('name', f'Sport {sport_id}')
                    else:
                        # 如果desc中没有sport，尝试通过tournament -> category -> sport 链条获取
                        tournament_id = desc.get('tournament_id') or desc.get('tournament')
                        
                        if tournament_id:
                            tournament_info = tournaments.get(str(tournament_id), {})
                            category_id = tournament_info.get('category_id')
                            
                            if category_id:
                                category_info = categories.get(str(category_id), {})
                                sport_id = category_info.get('sport_id')
                                
                                if sport_id:
                                    sport_info = sports.get(str(sport_id), {})
                                    sport_name = sport_info.get('name', f'Sport {sport_id}')
                    
                    # 统计运动类型
                    if sport_id:
                        sport_id_str = str(sport_id)
                        if sport_id_str not in sport_stats:
                            sport_stats[sport_id_str] = {'name': sport_name, 'count': 0}
                        sport_stats[sport_id_str]['count'] += 1
                    else:
                        # 没有找到sport_id的事件也要统计
                        if 'unknown' not in sport_stats:
                            sport_stats['unknown'] = {'name': 'Unknown Sport', 'count': 0}
                        sport_stats['unknown']['count'] += 1
                    
                    # 添加调试信息：打印足球事件的详细结构
                    if str(sport_id) == "1":
                        print(f"\n找到足球事件 {event_id}:")
                        print(f"  sport_id: {sport_id}")
                        print(f"  sport_name: {sport_name}")
                        print(f"  desc: {desc}")
                        print(f"  event_data keys: {list(event_data.keys())}")
                    
                    # 只处理真正的足球比赛（sport_id = "1"）
                    if str(sport_id) != "1":
                        filtered_events += 1
                        continue
                    
                    # 进一步过滤：排除虚拟足球/eSoccer
                    # 检查是否为虚拟比赛或eSoccer
                    is_virtual = desc.get('virtual', False)
                    competitors = desc.get('competitors', [])
                    
                    # 检查队伍名称是否包含eSoccer标识
                    is_esoccer = False
                    for competitor in competitors:
                        name = competitor.get('name', '')
                        if '[eSoccer]' in name or 'eSoccer' in name or '[eFootball]' in name:
                            is_esoccer = True
                            break
                    
                    # 如果是虚拟比赛或eSoccer，跳过
                    if is_virtual or is_esoccer:
                        filtered_events += 1
                        print(f"过滤虚拟/eSoccer事件: {event_id} - virtual: {is_virtual}, esoccer: {is_esoccer}")
                        continue
                    
                    # 检查是否有1X2市场（market_id = '1'）
                    markets = event_data.get('markets', {})
                    if not markets or '1' not in markets:
                        continue
                    
                    # 解析1X2赔率
                    market_1 = markets['1']
                    odds_1 = odds_x = odds_2 = None
                    
                    # 遍历所有线路（通常是空字符串""）
                    for line_key, outcomes in market_1.items():
                        if isinstance(outcomes, dict):
                            # 获取1X2赔率
                            odds_1 = outcomes.get('1', {}).get('k')
                            odds_x = outcomes.get('X', {}).get('k')  # 有些API用X表示平局
                            odds_2 = outcomes.get('2', {}).get('k')
                            
                            # 如果没有X，尝试用2作为平局，3作为客胜
                            if not odds_x and '3' in outcomes:
                                odds_x = outcomes.get('2', {}).get('k')
                                odds_2 = outcomes.get('3', {}).get('k')
                            
                            break
                    
                    # 如果没有获取到完整的1X2赔率，跳过
                    if not all([odds_1, odds_2]):
                        continue
                    
                    # 获取事件描述信息（可能为空）
                    desc = event_data.get('desc', {})
                    
                    # 尝试从tournaments中找到联赛信息
                    # 由于API没有提供tournament_id关联，我们只能使用默认值或尝试其他方法
                    league_name = "Unknown League"
                    home_team = "Home Team"
                    away_team = "Away Team"
                    
                    # 使用现有函数解析联赛和队伍信息
                    league_name = league_name_from_maps(tournaments, categories, desc)
                    home_team, away_team = teams_from_desc(desc)
                    
                    result.append({
                        'event_id': event_id,
                        'league': league_name,
                        'home_team': home_team,
                        'away_team': away_team,
                        'odds_1': odds_1,
                        'odds_x': odds_x,
                        'odds_2': odds_2,
                        'need_detail': False  # 已经有赔率了，不需要详情
                    })
                    
                except Exception as e:
                    print(f"解析事件 {event_id} 失败: {e}")
                    continue
            
            # 输出统计信息
            print(f"\n=== 运动类型过滤统计 ===")
            print(f"总事件数: {len(events)}")
            print(f"过滤掉的非足球事件: {filtered_events}")
            print(f"成功解析的足球1X2赔率事件: {len(result)}")
            
            print(f"\n=== 各运动类型事件数量 ===")
            if sport_stats:
                for sport_id, info in sport_stats.items():
                    status = "✓ 已包含" if sport_id == "1" else "✗ 已过滤"
                    print(f"Sport {sport_id} ({info['name']}): {info['count']} 事件 {status}")
            else:
                print("未找到运动类型统计信息")
            
        except Exception as e:
            print(f"解析快照数据失败: {e}")
            import traceback
            traceback.print_exc()
        
        return result
    
    async def fill_missing_odds_from_detail(self, events_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对于缺失赔率的事件，调用详情接口补齐"""
        tasks = []
        
        for event_data in events_list:
            if not event_data['need_detail']:
                continue
            tasks.append(self._fill_single_event_odds(event_data))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        return events_list
    
    async def _fill_single_event_odds(self, event_data: Dict[str, Any]):
        """填充单个事件的赔率"""
        event_id = event_data['event_id']
        print(f"补齐事件 {event_id} 的赔率...")
        
        detail = await self.get_event_detail(event_id)
        if not detail:
            return
            
        # 从详情接口解析1X2赔率
        try:
            markets = detail.get('data', {}).get('markets', [])
            for market in markets:
                if market.get('name') == '1X2':
                    outcomes = market.get('outcomes', [])
                    for outcome in outcomes:
                        outcome_name = outcome.get('name')
                        odds = outcome.get('odds')
                        
                        if outcome_name == '1' and not event_data['odds_1']:
                            event_data['odds_1'] = odds
                        elif outcome_name == 'X' and not event_data['odds_x']:
                            event_data['odds_x'] = odds
                        elif outcome_name == '2' and not event_data['odds_2']:
                            event_data['odds_2'] = odds
                    break
        except Exception as e:
            print(f"解析事件 {event_id} 详情失败: {e}")
        
        # 添加延迟避免请求过快
        await asyncio.sleep(0.1)
    
    async def scrape_all_odds(self) -> List[Dict[str, Any]]:
        """批量抓取所有足球1X2赔率"""
        print("开始批量抓取足球1X2赔率...")
        
        # 获取快照数据
        snapshot_data = await self.fetch_events_snapshot()
        if not snapshot_data:
            print("获取快照数据失败")
            return []
        
        # 解析快照数据
        events_list = self.parse_snapshot_data(snapshot_data)
        print(f"解析到 {len(events_list)} 个足球事件")
        
        # 补齐缺失的赔率
        events_list = await self.fill_missing_odds_from_detail(events_list)
        
        # 过滤掉仍然缺失赔率的事件
        complete_events = []
        for event in events_list:
            if event['odds_1'] and event['odds_x'] and event['odds_2']:
                complete_events.append(event)
        
        print(f"成功获取 {len(complete_events)} 个完整赔率的事件")
        
        # 内存清理
        self.cleanup_memory()
        
        return complete_events
    
    async def get_current_odds(self) -> List[Dict[str, Any]]:
        """获取当前所有足球1X2赔率（别名方法）"""
        return await self.scrape_all_odds()

# 你刚刚在 Network 里确认到的"列表 URL"（Preview 里有 sports/categories/tournaments/events 的那条）
# 版本号已更新为测试发现的最优版本（包含更多事件数据）
LIST_URL = "https://api-k-c7818b61-623.sptpub.com/api/v3/live/brand/2103509236163162112/en/3517210518874"

# 详情接口的公共部分（当列表里1X2缺失时，用详情接口补一次）
BASE   = "https://api-k-c7818b61-623.sptpub.com"
BRAND  = "2103509236163162112"
LANG   = "en"

HEADERS = {
    "accept": "application/json",
    "origin": "https://bc.game",
    "referer": "https://bc.game/",
    "user-agent": "Mozilla/5.0"
}

# 兼容旧版本的同步函数
def fetch_events_snapshot():
    """获取"整站足球快照"（包含 events / tournaments / categories / sports）"""
    r = requests.get(LIST_URL, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def fetch_event_detail(event_id: str):
    """当列表里某场没有1X2时，调用单场详情接口补齐"""
    url = f"{BASE}/api/v3/live/brand/{BRAND}/{LANG}/{event_id}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()

def league_name_from_maps(tournaments: dict, categories: dict, desc: dict) -> str:
    """用 tournaments + categories 映射出联赛名（带国家）"""
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

def teams_from_desc(desc: dict):
    """从 desc 中解析主客队名，支持新的competitors结构"""
    # 新的数据结构：competitors数组包含队伍信息
    competitors = desc.get("competitors", [])
    if competitors and len(competitors) >= 2:
        home = competitors[0].get("name", "Home Team")
        away = competitors[1].get("name", "Away Team")
        return home, away
    
    # 兼容旧的数据结构
    home = desc.get("home_name") or desc.get("home") or "Home Team"
    away = desc.get("away_name") or desc.get("away") or "Away Team"
    return home, away

def parse_1x2(markets: dict):
    """
    解析 1X2（胜/平/负）赔率：
    - 常见结构：{"1": {"": {"1":{"k":"..."}, "X":{"k":"..."}, "2":{"k":"..."}}}}
    - 也可能是 {"1":{"": {"1":{"k":...}, "2":{"k":...}, "3":{"k":...}}}}（2=平，3=客）
    返回 (home, draw, away) 或 None
    """
    m = markets.get("1")
    if not m or not isinstance(m, dict):
        return None
    for _, outcomes in m.items():  # 取第一条线（通常 key 为 ""）
        if not isinstance(outcomes, dict):
            continue
        if "X" in outcomes:  # 1 / X / 2
            return (
                outcomes.get("1", {}).get("k"),
                outcomes.get("X", {}).get("k"),
                outcomes.get("2", {}).get("k") or outcomes.get("3", {}).get("k"),
            )
        # 1 / 2 / 3 结构
        return (
            outcomes.get("1", {}).get("k"),
            outcomes.get("2", {}).get("k"),  # 作为平的候选
            outcomes.get("3", {}).get("k") or outcomes.get("2", {}).get("k"),
        )
    return None

def main():
    """使用新的足球过滤逻辑的主函数"""
    print("开始获取BC.Game足球赔率数据...")
    
    # 创建爬虫实例
    scraper = BCGameScraper()
    
    # 获取快照数据
    snapshot = fetch_events_snapshot()
    if not snapshot:
        print("获取快照数据失败")
        return
    
    # 使用新的解析方法（包含足球过滤）
    football_events = scraper.parse_snapshot_data(snapshot)
    
    if not football_events:
        print("没有找到任何足球1X2赔率数据")
        return
    
    # 显示结果
    print(f"\n=== 足球赔率数据 ===")
    for event in football_events:
        print(f"Event {event['event_id']} | {event['league']}")
        print(f"{event['home_team']} vs {event['away_team']}")
        print(f"Home: {event['odds_1']}  Draw: {event['odds_x']}  Away: {event['odds_2']}")
        print("-" * 60)

if __name__ == "__main__":
    main()
