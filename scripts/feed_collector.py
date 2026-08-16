#!/usr/bin/env python3
"""
低空经济情报服务 — 多源采集引擎 v2
使用 Google News RSS + Bing News RSS + HTML 搜索页面解析
确保在 GitHub Actions Ubuntu runner 上可靠运行
"""

import os
import re
import json
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote_plus
import xml.etree.ElementTree as ET

import feedparser
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)

BJT = timezone(timedelta(hours=8))

# ============================================================================
# 数据源配置 — 全部使用经过验证的可靠源
# ============================================================================
SOURCES = [
    # === P0: Google News RSS（用于发现，URL 可能无法解析） ===
    {
        "name": "Google新闻-低空经济",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E4%BD%8E%E7%A9%BA%E7%BB%8F%E6%B5%8E&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-eVTOL",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=eVTOL+%E4%B8%AD%E5%9B%BD&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-无人机政策",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E6%97%A0%E4%BA%BA%E6%9C%BA+%E6%94%BF%E7%AD%96&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-通用航空",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E9%80%9A%E7%94%A8%E8%88%AA%E7%A9%BA+%E4%BD%8E%E7%A9%BA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    # === P1: Bing News RSS（可能包含文章摘要） ===
    {
        "name": "Bing新闻-低空经济",
        "type": "bing_rss",
        "url": "https://www.bing.com/news/search?q=%E4%BD%8E%E7%A9%BA%E7%BB%8F%E6%B5%8E&format=rss",
        "keywords": [],
        "priority": "P1",
    },
    {
        "name": "Bing新闻-eVTOL中国",
        "type": "bing_rss",
        "url": "https://www.bing.com/news/search?q=eVTOL+%E4%B8%AD%E5%9B%BD&format=rss",
        "keywords": [],
        "priority": "P1",
    },
    # === P2: 政府网站 HTML 搜索解析 ===
    {
        "name": "国务院政策-低空经济",
        "type": "gov_html",
        "url": "https://sousuo.www.gov.cn/sousuo/search.shtml?code=17da70961a7&searchWord=%E4%BD%8E%E7%A9%BA%E7%BB%8F%E6%B5%8E&t=zhengcelibrary_gw",
        "keywords": [],
        "priority": "P2",
    },
]

# 关键词过滤白名单（采集后二次过滤用）
KEYWORD_FILTER = [
    "低空经济", "低空", "eVTOL", "无人机", "通用航空",
    "飞行汽车", "空中交通", "UAM", "UAV", "适航",
    "空域管理", "低空空域", "城市空中交通", "电动垂直起降"
]


class FeedCollector:
    """多源采集器 v2"""

    def __init__(self):
        self.raw_dir = PROJECT_ROOT / 'raw' / 'feeds'
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = PROJECT_ROOT / 'raw' / 'feed_state.json'
        self.state = self._load_state()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/rss+xml,application/xml,text/xml,*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.session.verify = False

    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'collected_urls': [], 'last_run': None}

    def _save_state(self):
        self.state['last_run'] = datetime.now(BJT).isoformat()
        self.state['collected_urls'] = self.state['collected_urls'][-1000:]
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

    def _decode_google_news_url(self, gn_url):
        """
        解码 Google News 跳转 URL，提取原始文章 URL
        新版 Google News 使用 JS 跳转，需 HTTP 请求获取真实 URL
        """
        import base64

        # 方法1: HTTP 请求跟随重定向获取真实 URL
        try:
            resp = self.session.get(gn_url, timeout=10, allow_redirects=True)
            final_url = resp.url
            if final_url and 'news.google.com' not in final_url:
                return final_url
        except Exception:
            pass

        # 方法2: base64 + protobuf 解码
        try:
            match = re.search(r'/articles/([A-Za-z0-9_-]+)', gn_url)
            if not match:
                return None
            encoded = match.group(1)
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded_padded = encoded + '=' * padding
            else:
                encoded_padded = encoded
            try:
                decoded_bytes = base64.urlsafe_b64decode(encoded_padded)
            except Exception:
                try:
                    decoded_bytes = base64.b64decode(encoded_padded)
                except Exception:
                    return None
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore')
            url_match = re.search(r'https?://[^\x00-\x1f\x7f-\xff\s<>"]+', decoded_str)
            if url_match:
                return url_match.group(0)
            for i in range(len(decoded_bytes)):
                if decoded_bytes[i:i+4] in (b'http', b'HTTP'):
                    url_end = decoded_bytes.find(b'\x00', i)
                    if url_end == -1:
                        url_end = len(decoded_bytes)
                    found_url = decoded_bytes[i:url_end].decode('utf-8', errors='ignore').strip()
                    if found_url.startswith('http'):
                        return found_url

        except Exception:
            pass

        return None

    def _is_relevant(self, text):
        """检查内容是否与低空经济相关"""
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in KEYWORD_FILTER)

    def _clean_html(self, text):
        """去除 HTML 标签"""
        if not text:
            return ""
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(strip=True)

    def _parse_date(self, date_str):
        """解析日期字符串"""
        if not date_str:
            return datetime.now(BJT).strftime('%Y-%m-%d')
        try:
            from dateutil import parser as date_parser
            dt = date_parser.parse(date_str)
            return dt.strftime('%Y-%m-%d')
        except Exception:
            match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', str(date_str))
            if match:
                return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            return datetime.now(BJT).strftime('%Y-%m-%d')

    def _make_record(self, url, title, content, publish_date, publisher, source_type, extra=None):
        """创建标准化记录"""
        record = {
            'doc_id': self._url_hash(url),
            'url': url,
            'title': title.strip() if title else '',
            'content': self._clean_html(content)[:5000] if content else '',
            'publish_date': self._parse_date(publish_date),
            'publisher': publisher,
            'source_site': urlparse(url).netloc,
            'source_type': source_type,
            'collected_at': datetime.now(BJT).isoformat(),
            'quality_flag': 'pending'
        }
        if extra:
            record.update(extra)
        return record

    # =========================================================================
    # 采集方法 1: 标准 RSS/Atom（Google News）
    # =========================================================================
    def collect_rss(self, source):
        """采集标准 RSS 源"""
        name = source['name']
        url = source['url']
        keywords = source.get('keywords', [])

        logger.info(f"  采集 RSS: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            # Google News RSS 返回的是标准 XML
            feed = feedparser.parse(resp.content)

            for entry in feed.entries:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                published = entry.get('published', entry.get('updated', ''))

                # Google News 的 link 是编码跳转 URL，在采集阶段不解析（太慢）
                # URL 解析推迟到 step 2 的 fetch_and_parse 中进行
                url_resolved = 'news.google.com' not in link

                if not link:
                    continue

                # 关键词过滤（如果有配置）
                combined_text = f"{title} {summary}"
                if keywords and not any(kw.lower() in combined_text.lower() for kw in keywords):
                    continue

                # 相关性过滤
                if not self._is_relevant(combined_text):
                    continue

                # 去重
                if self._is_collected(link):
                    continue

                # 用标题+摘要作为内容（至少有标题可用于 NER）
                content = summary if len(summary) > 50 else title

                record = self._make_record(
                    link, title, content, published, name, 'rss',
                    extra={'url_resolved': url_resolved}
                )
                results.append(record)
                self._mark_collected(link)

            logger.info(f"    获取 {len(results)} 条新内容")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 采集方法 2: 直接新闻源 RSS（真实 URL + 正文摘要）
    # =========================================================================
    def collect_direct_rss(self, source):
        """采集直接新闻源 RSS（如36氪、新浪等，提供真实文章 URL）"""
        name = source['name']
        url = source['url']
        keywords = source.get('keywords', [])

        logger.info(f"  采集直接 RSS: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            feed = feedparser.parse(resp.content)

            for entry in feed.entries:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                published = entry.get('published', entry.get('updated', ''))

                if not link or not title:
                    continue

                # 关键词过滤
                combined_text = f"{title} {summary}"
                if keywords and not any(kw.lower() in combined_text.lower() for kw in keywords):
                    continue

                # 相关性过滤
                if not self._is_relevant(combined_text):
                    continue

                if self._is_collected(link):
                    continue

                # 直接新闻源的 summary 通常包含 HTML，清理后作为内容
                clean_summary = self._clean_html(summary)
                content = clean_summary if len(clean_summary) > 50 else title

                record = self._make_record(
                    link, title, content, published, name, 'direct_rss',
                    extra={'url_resolved': True}
                )
                results.append(record)
                self._mark_collected(link)

            logger.info(f"    获取 {len(results)} 条新内容")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 采集方法 3: Bing News RSS
    # =========================================================================
    def collect_bing_rss(self, source):
        """采集 Bing News RSS"""
        name = source['name']
        url = source['url']

        logger.info(f"  采集 Bing RSS: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            # Bing RSS 也是标准 XML
            feed = feedparser.parse(resp.content)

            for entry in feed.entries:
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                published = entry.get('published', entry.get('updated', ''))

                if not link:
                    continue

                # 相关性过滤
                combined_text = f"{title} {summary}"
                if not self._is_relevant(combined_text):
                    continue

                if self._is_collected(link):
                    continue

                record = self._make_record(
                    link, title, summary, published, name, 'bing_rss'
                )
                results.append(record)
                self._mark_collected(link)

            logger.info(f"    获取 {len(results)} 条新内容")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 采集方法 3: 政府网站 HTML 搜索页面解析
    # =========================================================================
    def collect_gov_html(self, source):
        """采集政府网站 HTML 搜索页面"""
        name = source['name']
        url = source['url']

        logger.info(f"  采集政府网站: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(resp.content, 'html.parser')

            # 通用策略：查找所有包含链接的列表项
            # 政府网站通常用 <li>, <div>, <a> 等元素展示搜索结果
            found_items = []

            # 策略 1: 查找带有标题和日期的链接
            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                text = a_tag.get_text(strip=True)

                # 跳过导航链接等
                if len(text) < 8 or len(text) > 200:
                    continue
                if any(skip in text for skip in ['首页', '下一页', '上一页', '更多', '登录', '搜索']):
                    continue

                # 补全相对 URL
                if href.startswith('/'):
                    href = urljoin(url, href)
                elif not href.startswith('http'):
                    continue

                # 尝试查找同级或父级的日期
                parent = a_tag.parent
                date_text = ''
                if parent:
                    date_match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', parent.get_text())
                    if date_match:
                        date_text = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"

                found_items.append({
                    'url': href,
                    'title': text,
                    'date': date_text,
                    'summary': ''
                })

            # 去重（同一 URL 只保留第一条）
            seen_urls = set()
            for item in found_items:
                if item['url'] in seen_urls:
                    continue
                seen_urls.add(item['url'])

                # 相关性过滤
                if not self._is_relevant(item['title']):
                    continue

                if self._is_collected(item['url']):
                    continue

                record = self._make_record(
                    item['url'], item['title'], item['summary'],
                    item['date'], name, 'gov_html'
                )
                results.append(record)
                self._mark_collected(item['url'])

            logger.info(f"    获取 {len(results)} 条新内容")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 主运行方法
    # =========================================================================
    def run(self):
        """运行所有源的采集"""
        logger.info("=" * 60)
        logger.info("多源采集器 v2 启动")
        logger.info(f"上次运行: {self.state.get('last_run', '首次')}")
        logger.info(f"数据源数量: {len(SOURCES)}")
        logger.info("=" * 60)

        all_results = []

        for source in SOURCES:
            source_type = source.get('type', 'rss')

            try:
                if source_type == 'rss':
                    results = self.collect_rss(source)
                elif source_type == 'direct_rss':
                    results = self.collect_direct_rss(source)
                elif source_type == 'bing_rss':
                    results = self.collect_bing_rss(source)
                elif source_type == 'gov_html':
                    results = self.collect_gov_html(source)
                else:
                    logger.warning(f"  未知源类型: {source_type}")
                    continue

                all_results.extend(results)
                logger.info(f"  [{source['name']}] 累计: {len(all_results)} 条")

            except Exception as e:
                logger.error(f"  [{source['name']}] 采集异常: {e}")

            time.sleep(2)  # 源间礼貌延迟

        # 保存结果
        if all_results:
            output_file = self.raw_dir / f"feed_{datetime.now(BJT).strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            logger.info(f"\n保存 {len(all_results)} 条到 {output_file}")
        else:
            logger.warning("\n未采集到任何内容")

        self._save_state()
        logger.info(f"采集完成，共 {len(all_results)} 条新内容")
        return all_results


# 保持向后兼容
RSS_SOURCES = SOURCES


def main():
    import argparse
    import warnings
    warnings.filterwarnings('ignore')  # 抑制 SSL 警告

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(description='低空经济情报采集器 v2')
    parser.add_argument('--test', action='store_true', help='测试模式（仅采集第一个源）')
    args = parser.parse_args()

    collector = FeedCollector()

    if args.test:
        # 测试模式：只采集第一个 Google News 源
        source = SOURCES[0]
        logger.info(f"测试采集: {source['name']}")
        results = collector.collect_rss(source)
        print(f"\n获取 {len(results)} 条结果")
        for r in results[:5]:
            print(f"  [{r['publish_date']}] {r['title'][:60]}")
            print(f"    URL: {r['url'][:80]}")
    else:
        collector.run()


if __name__ == '__main__':
    main()
