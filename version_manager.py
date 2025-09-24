#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BC.Game API版本管理器
自动检测和更新最优版本号
"""

import requests
import time
import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple

class BCGameVersionManager:
    """BC.Game API版本管理器"""
    
    def __init__(self):
        self.base_url = "https://api-k-c7818b61-623.sptpub.com/api/v3/live/brand/2103509236163162112/en"
        self.headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "origin": "https://bc.game",
            "referer": "https://bc.game/",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        self.current_version = "3517210518874"  # 当前最优版本
        self.cache_file = "version_cache.json"
    
    def test_version(self, version: str) -> Optional[Dict]:
        """测试指定版本号是否有效"""
        url = f"{self.base_url}/{version}"
        
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', {})
                return {
                    'version': version,
                    'status': 'success',
                    'event_count': len(events),
                    'timestamp': datetime.now().isoformat(),
                    'data_size': len(str(data))
                }
            else:
                return {
                    'version': version,
                    'status': 'failed',
                    'http_code': response.status_code,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            return {
                'version': version,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def generate_candidate_versions(self, base_version: str = None) -> List[str]:
        """生成候选版本号列表"""
        if not base_version:
            base_version = self.current_version
        
        base_num = int(base_version)
        current_timestamp = int(time.time() * 1000)
        
        candidates = []
        
        # 1. 当前版本
        candidates.append(base_version)
        
        # 2. 基于当前时间戳
        candidates.append(str(current_timestamp))
        
        # 3. 在当前版本基础上的小幅调整
        for offset in [10000, 20000, 50000, 100000, -10000, -20000]:
            candidates.append(str(base_num + offset))
        
        # 4. 最近几小时的时间戳
        for hours_ago in [1, 2, 6, 12]:
            timestamp = current_timestamp - (hours_ago * 60 * 60 * 1000)
            candidates.append(str(timestamp))
        
        # 5. 去重并返回
        return list(set(candidates))
    
    def find_best_version(self, max_candidates: int = 15) -> Optional[Dict]:
        """寻找最佳版本号"""
        print("开始寻找最佳版本号...")
        
        candidates = self.generate_candidate_versions()
        candidates = candidates[:max_candidates]  # 限制测试数量
        
        results = []
        
        for i, version in enumerate(candidates):
            print(f"[{i+1}/{len(candidates)}] 测试版本: {version}")
            
            result = self.test_version(version)
            if result:
                results.append(result)
                
                if result['status'] == 'success':
                    print(f"  ✓ 成功: {result['event_count']} 个事件")
                else:
                    print(f"  ✗ 失败: {result.get('http_code', result.get('error', 'Unknown'))}")
            
            # 避免请求过快
            time.sleep(0.3)
        
        # 找到最佳版本（事件数量最多的成功版本）
        successful_results = [r for r in results if r['status'] == 'success']
        
        if not successful_results:
            print("未找到任何有效版本")
            return None
        
        # 按事件数量排序
        best_result = max(successful_results, key=lambda x: x['event_count'])
        
        print(f"\n找到最佳版本: {best_result['version']}")
        print(f"事件数量: {best_result['event_count']}")
        
        return best_result
    
    def save_version_cache(self, version_info: Dict):
        """保存版本信息到缓存"""
        cache_data = {
            'last_update': datetime.now().isoformat(),
            'best_version': version_info,
            'update_history': []
        }
        
        # 读取现有缓存
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    existing_cache = json.load(f)
                    cache_data['update_history'] = existing_cache.get('update_history', [])
            except:
                pass
        
        # 添加到历史记录
        cache_data['update_history'].append(version_info)
        
        # 保持历史记录不超过10条
        cache_data['update_history'] = cache_data['update_history'][-10:]
        
        # 保存缓存
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, indent=2, ensure_ascii=False)
        
        print(f"版本信息已保存到 {self.cache_file}")
    
    def load_version_cache(self) -> Optional[Dict]:
        """加载版本缓存"""
        if not os.path.exists(self.cache_file):
            return None
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def update_scraper_file(self, new_version: str, scraper_file: str = "bc_game_scraper.py"):
        """更新爬虫文件中的版本号"""
        if not os.path.exists(scraper_file):
            print(f"爬虫文件 {scraper_file} 不存在")
            return False
        
        try:
            # 读取文件
            with open(scraper_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找并替换版本号
            import re
            pattern = r'(LIST_URL = "[^"]+/)\d+(")'
            replacement = f'\\g<1>{new_version}\\g<2>'
            
            new_content = re.sub(pattern, replacement, content)
            
            if new_content != content:
                # 备份原文件
                backup_file = f"{scraper_file}.backup.{int(time.time())}"
                with open(backup_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"原文件已备份为: {backup_file}")
                
                # 写入新内容
                with open(scraper_file, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                
                print(f"已更新 {scraper_file} 中的版本号为: {new_version}")
                return True
            else:
                print("未找到需要更新的版本号")
                return False
                
        except Exception as e:
            print(f"更新文件失败: {e}")
            return False
    
    def auto_update(self, update_scraper: bool = True) -> bool:
        """自动检测并更新到最佳版本"""
        print("BC.Game版本自动更新")
        print("=" * 50)
        
        # 检查缓存
        cache = self.load_version_cache()
        if cache:
            last_update = datetime.fromisoformat(cache['last_update'])
            hours_since_update = (datetime.now() - last_update).total_seconds() / 3600
            
            if hours_since_update < 1:  # 1小时内已更新过
                print(f"最近 {hours_since_update:.1f} 小时前已检查过版本，跳过检查")
                print(f"当前最佳版本: {cache['best_version']['version']}")
                return True
        
        # 寻找最佳版本
        best_version_info = self.find_best_version()
        
        if not best_version_info:
            print("未找到有效版本，保持当前配置")
            return False
        
        # 检查是否需要更新
        if best_version_info['version'] != self.current_version:
            print(f"\n发现更优版本: {best_version_info['version']}")
            print(f"当前版本: {self.current_version}")
            print(f"事件数量差异: +{best_version_info['event_count']}")
            
            # 保存缓存
            self.save_version_cache(best_version_info)
            
            # 更新爬虫文件
            if update_scraper:
                success = self.update_scraper_file(best_version_info['version'])
                if success:
                    self.current_version = best_version_info['version']
                    print("\n✅ 版本更新完成")
                    return True
                else:
                    print("\n❌ 版本更新失败")
                    return False
            else:
                print(f"\n建议手动更新版本号为: {best_version_info['version']}")
                return True
        else:
            print(f"\n✅ 当前版本 {self.current_version} 已是最优版本")
            # 仍然保存缓存以更新检查时间
            self.save_version_cache(best_version_info)
            return True

def main():
    """主函数"""
    manager = BCGameVersionManager()
    
    # 自动更新版本
    success = manager.auto_update(update_scraper=True)
    
    if success:
        print("\n版本管理完成，可以运行爬虫获取最新数据")
    else:
        print("\n版本管理失败，请检查网络连接或手动更新")

if __name__ == "__main__":
    main()