#!/usr/bin/env python3
"""
低空经济情报服务 — RSS/Atom 采集引擎
通过 RSS 订阅源采集政府网站和行业协会的最新政策与动态
"""

import os
import re
import json
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)

BJT = timezone(timedelta(hours=8))

# RSS 订阅源配置
# 使用多源策略：政府网站搜索 + 行业媒体 RSS + Google Alerts
RSS_SOURCES = [
    # === P0: 政府网站搜索接口 ===
    {
        "name": "国务院政策搜索",
        "type": "search",
        "url": "https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord={keyword}&t=zhengcelibrary_gw",
        "keywords": ["低空经济", "无人机", "通用航空"],
        "priority": "P0",
    },
    {
        "name": "发改委搜索",
        "type": "search",
        "url": "https://www.ndrc.gov.cn/search-searchPdf?keyword={keyword}&pageNum=1&pageSize=20",
        "keywords": ["低空经济", "通用航空", "无人机"],
        "priority": "P0",
    },
    {
        "name": "民航局搜索",
        "type": "search",
        "url": "http://www.caac.gov.cn/XXGK/XXGK/index_176.html?keywords={keyword}",
        "keywords": ["低空", "无人机", "适航", "通用航空"],
        "priority": "P0",
    },
    # === P1: 行业媒体 RSS ===
    {
        "name": "航空工业-36氪",
        "type": "rss",
        "url": "https://36kr.com/feed",
        "keywords": ["低空经济", "eVTOL", "无人机", "飞行汽车", "通用航空"],
        "priority": "P1",
    },
    {
        "name": "澎湃新闻-科技",
        "type": "rss",
        "url": "https://feedx.net/rss/thepapertech.xml",
        "keywords": ["低空经济", "eVTOL", "无人机", "飞行汽车"],
        "priority": "P1",
    },
    # === P2: 通用搜索聚合 ===
    {
        "name": "百度新闻-低空经济",
        "type": "baidu_news",
        "url": "https://news.baidu.com/ns?word={keyword}&tn=newsdy&from=news",
        "keywords": ["低空经济", "eVTOL", "无人机政策"],
        "priority": "P2",
    },
]


class FeedCollector:
    """RSS/Atom 采集器"""

    def __init__(self):
        self.raw_dir = PROJECT_ROOT / 'raw' / 'feeds'
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = PROJECT_ROOT / 'raw' / 'feed_state.json'
        self.state = self._load_state()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; LowAltitudeIntelBot/1.0; +https://github.com/low-altitude-intel)'
        })

    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'collected_urls': [], 'last_run': None}

    def _save_state(self):
        self.state['last_run'] = datetime.now(BJT).isoformat()
        # 只保留最近 500 条 URL 防止文件过大
        self.state['collected_urls'] = self.state['collected_urls'][-500:]
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _is_collected(self, url):
        return url in self.state.get('collected_urls', [])

    def _mark_collected(self, url):
        if 'collected_urls' not in self.state:
            self.state['collected_urls'] = []
        self.state['collected_urls'].append(url)

    def _url_hash(self, url):
        return hashlib.md5(url.encode('utf-8')).hexdigest()[:12]

    def _matches_keywords(self, text, keywords):
        """检查文本是否包含任一关键词"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def collect_rss(self, source):
        """采集 RSS 源"""
        name = source['name']
        url = source['url']
        keywords = source.get('keywords', [])

        logger.info(f"  采集 RSS: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30, verify=False)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            feed = feedparser.parse(resp.text)

            for entry in feed.entries:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                published = entry.get('published', entry.get('updated', ''))

                # 关键词过滤
                combined_text = f"{title} {summary}"
                if keywords and not self._matches_keywords(combined_text, keywords):
                    continue

                # 去重
                if self._is_collected(link):
                    continue

                record = {
                    'doc_id': self._url_hash(link),
                    'url': link,
                    'title': title,
                    'content': summary,
                    'publish_date': self._parse_date(published),
                    'publisher': name,
                    'source_site': urlparse(url).netloc,
                    'source_type': 'rss',
                    'collected_at': datetime.now(BJT).isoformat(),
                    'quality_flag': 'pending'
                }

                results.append(record)
                self._mark_collected(link)

            logger.info(f"    获取 {len(results)} 条新内容")

        except Exception as e:
            logger.warning(f"    采集失败: {e}")

        return results

    def collect_search(self, source):
        """采集搜索接口"""
        name = source['name']
        base_url = source['url']
        keywords = source.get('keywords', [])

        logger.info(f"  采集搜索: {name}")
        results = []

        for kw in keywords:
            url = base_url.format(keyword=requests.utils.quote(kw))
            try:
                resp = self.session.get(url, timeout=30, verify=False)
                resp.encoding = resp.apparent_encoding or 'utf-8'

                # 尝试解析为 RSS
                feed = feedparser.parse(resp.text)
                if feed.entries:
                    for entry in feed.entries:
                        title = entry.get('title', '').strip()
                        link = entry.get('link', '').strip()
                        summary = entry.get('summary', '').strip()

                        if self._is_collected(link):
                            continue

                        record = {
                            'doc_id': self._url_hash(link),
                            'url': link,
                            'title': title,
                            'content': summary,
                            'publish_date': self._parse_date(entry.get('published', '')),
                            'publisher': name,
                            'source_site': urlparse(url).netloc,
                            'source_type': 'search',
                            'search_keyword': kw,
                            'collected_at': datetime.now(BJT).isoformat(),
                            'quality_flag': 'pending'
                        }
                        results.append(record)
                        self._mark_collected(link)

                time.sleep(2)  # 礼貌延迟

            except Exception as e:
                logger.warning(f"    搜索 '{kw}' 失败: {e}")

        logger.info(f"    获取 {len(results)} 条新内容")
        return results

    def _parse_date(self, date_str):
        """解析日期字符串"""
        if not date_str:
            return datetime.now(BJT).strftime('%Y-%m-%d')

        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            # 尝试正则匹配
            match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_str)
            if match:
                return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            return datetime.now(BJT).strftime('%Y-%m-%d')

    def run(self):
        """运行所有源的采集"""
        logger.info("=" * 60)
        logger.info("RSS/Atom 采集器启动")
        logger.info(f"上次运行: {self.state.get('last_run', '首次')}")
        logger.info("=" * 60)

        all_results = []

        for source in RSS_SOURCES:
            source_type = source.get('type', 'rss')

            if source_type == 'rss':
                results = self.collect_rss(source)
            elif source_type in ('search', 'baidu_news'):
                results = self.collect_search(source)
            else:
                logger.warning(f"  未知源类型: {source_type}")
                continue

            all_results.extend(results)
            time.sleep(3)  # 源间延迟

        # 保存结果
        if all_results:
            output_file = self.raw_dir / f"feed_{datetime.now(BJT).strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            logger.info(f"\n保存 {len(all_results)} 条到 {output_file}")

        self._save_state()
        logger.info(f"采集完成，共 {len(all_results)} 条新内容")
        return all_results


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(description='RSS/Atom 采集器')
    parser.add_argument('--test', action='store_true', help='测试模式（仅采集1个源）')
    args = parser.parse_args()

    collector = FeedCollector()

    if args.test:
        # 测试模式：只采集第一个源
        source = RSS_SOURCES[0]
        if source['type'] == 'rss':
            results = collector.collect_rss(source)
        else:
            results = collector.collect_search(source)
        print(json.dumps(results[:3], ensure_ascii=False, indent=2))
    else:
        collector.run()


if __name__ == '__main__':
    main()
