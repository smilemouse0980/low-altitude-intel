#!/usr/bin/env python3
"""
低空经济情报服务 — 多源采集引擎 v3
核心改进：
1. 使用 googlenewsdecoder 实时解码 Google News URL → 获取真实文章 URL
2. 添加直接新闻源 HTML 抓取（圆象低空经济观察、AOPA 等）
3. 采集阶段即获取全文内容，不再依赖 step 2 延迟解析
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
# 数据源配置
# ============================================================================
SOURCES = [
    # === P0: Google News RSS（使用 googlenewsdecoder 解码真实 URL） ===
    {
        "name": "Google新闻-低空经济",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E4%BD%8E%E7%A9%BA%E7%BB%8F%E6%B5%8E&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-eVTOL中国",
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
        "name": "Google新闻-通用航空低空",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E9%80%9A%E7%94%A8%E8%88%AA%E7%A9%BA+%E4%BD%8E%E7%A9%BA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-复合查询",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E4%BD%8E%E7%A9%BA%E7%BB%8F%E6%B5%8E+OR+eVTOL+OR+%E9%A3%9E%E8%A1%8C%E6%B1%BD%E8%BD%A6+OR+%E5%9F%8E%E5%B8%82%E7%A9%BA%E4%B8%AD%E4%BA%A4%E9%80%9A&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    {
        "name": "Google新闻-适航认证",
        "type": "rss",
        "url": "https://news.google.com/rss/search?q=%E9%80%82%E8%88%AA+%E8%AE%A4%E8%AF%81+%E4%BD%8E%E7%A9%BA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        "keywords": [],
        "priority": "P0",
    },
    # === P1: 直接新闻源 HTML 抓取（提供真实 URL + 正文） ===
    {
        "name": "圆象低空经济观察",
        "type": "direct_html",
        "url": "https://yuanxiangsky.com/A/2.html",
        "keywords": [],
        "priority": "P1",
        "parser": "yuanxiangsky",
    },
    {
        "name": "圆象低空-企业动态",
        "type": "direct_html",
        "url": "https://yuanxiangsky.com/A/3.html",
        "keywords": [],
        "priority": "P1",
        "parser": "yuanxiangsky",
    },
    {
        "name": "圆象低空-政策法规",
        "type": "direct_html",
        "url": "https://yuanxiangsky.com/A/1.html",
        "keywords": [],
        "priority": "P1",
        "parser": "yuanxiangsky",
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

# 关键词过滤白名单
KEYWORD_FILTER = [
    "低空经济", "低空", "eVTOL", "无人机", "通用航空",
    "飞行汽车", "空中交通", "UAM", "UAV", "适航",
    "空域管理", "低空空域", "城市空中交通", "电动垂直起降",
    "峰飞", "亿航", "沃兰特", "小鹏汇天", "大疆",
]


class FeedCollector:
    """多源采集器 v3"""

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
        # googlenewsdecoder 可用性标记
        self._gn_decoder_available = self._check_gn_decoder()

    def _check_gn_decoder(self):
        """检查 googlenewsdecoder 是否可用"""
        try:
            from googlenewsdecoder import gnewsdecoder
            return True
        except ImportError:
            logger.warning("googlenewsdecoder 未安装，Google News URL 将无法解码")
            return False

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
        使用 googlenewsdecoder 解码 Google News URL
        返回真实文章 URL 或 None
        """
        if not self._gn_decoder_available:
            return None

        try:
            from googlenewsdecoder import gnewsdecoder
            result = gnewsdecoder(gn_url, interval=1)
            if result.get('status'):
                decoded_url = result.get('decoded_url', '')
                if decoded_url and 'news.google.com' not in decoded_url:
                    return decoded_url
        except Exception as e:
            logger.debug(f"GN解码失败: {type(e).__name__}: {e}")

        return None

    def _is_relevant(self, text):
        if not text:
            return False
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in KEYWORD_FILTER)

    def _clean_html(self, text):
        if not text:
            return ""
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(strip=True)

    def _parse_date(self, date_str):
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

    def _fetch_article_content(self, url, timeout=15):
        """获取文章全文内容"""
        try:
            resp = self.session.get(url, timeout=timeout, allow_redirects=True)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            html_content = resp.text

            # 尝试 trafilatura 提取
            try:
                import trafilatura
                text = trafilatura.extract(
                    html_content, include_comments=False,
                    include_tables=True, favor_precision=True, url=resp.url
                )
                if text and len(text) > 100:
                    return text[:5000], resp.url
            except Exception:
                pass

            # BeautifulSoup 回退
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                tag.decompose()
            body_text = soup.get_text(separator='\n', strip=True)
            if len(body_text) > 200:
                return body_text[:5000], resp.url

            return None, resp.url
        except Exception:
            return None, url

    # =========================================================================
    # 采集方法 1: Google News RSS（使用 googlenewsdecoder 解码 URL + 获取全文）
    # =========================================================================
    def collect_rss(self, source):
        """采集 Google News RSS，使用 googlenewsdecoder 解码真实 URL"""
        name = source['name']
        url = source['url']
        keywords = source.get('keywords', [])

        logger.info(f"  采集 RSS: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'
            feed = feedparser.parse(resp.content)

            decode_success = 0
            decode_fail = 0

            max_entries = source.get('max_articles', 15)
            processed = 0
            for entry in feed.entries:
                if processed >= max_entries:
                    break
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                summary = entry.get('summary', entry.get('description', '')).strip()
                published = entry.get('published', entry.get('updated', ''))

                if not link:
                    continue

                combined_text = f"{title} {summary}"
                if keywords and not any(kw.lower() in combined_text.lower() for kw in keywords):
                    continue
                if not self._is_relevant(combined_text):
                    continue
                if self._is_collected(link):
                    continue

                # 使用 googlenewsdecoder 解码 Google News URL
                real_url = None
                content = summary if len(summary) > 50 else title
                url_resolved = False

                if 'news.google.com' in link:
                    real_url = self._decode_google_news_url(link)
                    if real_url:
                        # 解码成功，获取文章全文
                        article_text, final_url = self._fetch_article_content(real_url)
                        if article_text:
                            content = article_text
                            real_url = final_url
                        url_resolved = True
                        decode_success += 1
                        # 用真实 URL 去重和记录
                        if self._is_collected(real_url):
                            continue
                        self._mark_collected(real_url)
                    else:
                        decode_fail += 1
                        # 解码失败，用标题作为内容
                        self._mark_collected(link)
                else:
                    # 非 Google News URL，直接获取全文
                    article_text, final_url = self._fetch_article_content(link)
                    if article_text:
                        content = article_text
                        link = final_url
                    url_resolved = True
                    self._mark_collected(link)

                record = self._make_record(
                    real_url or link, title, content, published, name, 'rss',
                    extra={'url_resolved': url_resolved}
                )
                results.append(record)
                processed += 1

            logger.info(f"    获取 {len(results)} 条 | URL解码: 成功={decode_success} 失败={decode_fail}")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 采集方法 2: 直接新闻源 HTML 抓取
    # =========================================================================
    def collect_direct_html(self, source):
        """直接抓取新闻网站 HTML 页面，提取文章列表"""
        name = source['name']
        url = source['url']
        parser_type = source.get('parser', 'generic')

        logger.info(f"  采集直接 HTML: {name}")
        results = []

        try:
            resp = self.session.get(url, timeout=30)
            resp.encoding = resp.apparent_encoding or 'utf-8'

            articles = []
            if parser_type == 'yuanxiangsky':
                articles = self._parse_yuanxiangsky(resp.text, url)
            else:
                articles = self._parse_generic_html(resp.text, url)

            for article in articles[:source.get('max_articles', 15)]:
                title = article.get('title', '').strip()
                link = article.get('url', '').strip()
                date = article.get('date', '')

                if not link:
                    continue
                # 标题为空时跳过相关性检查（标题将从文章页提取）
                if title and not self._is_relevant(title):
                    continue
                if self._is_collected(link):
                    continue

                # 获取文章全文（同时获取标题）
                article_text, final_url = self._fetch_article_content(link)
                content = article_text or title

                # 如果原标题为空，尝试从内容中提取标题
                if not title and article_text:
                    # 使用 trafilatura 提取的标题
                    try:
                        import trafilatura
                        resp = self.session.get(link, timeout=15)
                        meta = trafilatura.extract(resp.text, output_format='json', with_metadata=True, url=link)
                        if meta:
                            import json as _json
                            if isinstance(meta, str):
                                meta = _json.loads(meta)
                            if meta.get('title'):
                                title = meta['title']
                            if meta.get('date'):
                                date = meta['date']
                    except Exception:
                        pass
                    # 如果仍然没有标题，用内容前50字
                    if not title:
                        title = content[:50].replace('\n', ' ').strip()

                if not title:
                    continue

                self._mark_collected(link)
                record = self._make_record(
                    final_url or link, title, content, date, name, 'direct_html',
                    extra={'url_resolved': True}
                )
                results.append(record)

            logger.info(f"    获取 {len(results)} 条")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    def _parse_yuanxiangsky(self, html, base_url):
        """解析圆象低空经济观察网站 — 使用 sitemap 发现文章"""
        articles = []

        # 圆象使用 Nuxt.js SSR，HTML 中可能不包含文章链接
        # 先尝试从 HTML 中提取
        soup = BeautifulSoup(html, 'html.parser')
        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text(strip=True)
            if len(text) < 8 or len(text) > 200:
                continue
            if any(skip in text for skip in ['首页', '下一页', '上一页', '更多', '登录', '搜索', '关于我们', '联系']):
                continue
            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                continue
            if '/N/' in href and href.endswith('.html'):
                articles.append({'url': href, 'title': text, 'date': ''})

        # 如果 HTML 中没有找到文章，使用 sitemap
        if not articles:
            try:
                sitemap_url = 'https://yuanxiangsky.com/sitemap.xml'
                resp = self.session.get(sitemap_url, timeout=15)
                if resp.status_code == 200:
                    all_urls = re.findall(r'<loc>([^<]+)</loc>', resp.text)
                    # 过滤新闻文章 URL (/N/{id}.html)
                    news_urls = [u for u in all_urls if re.search(r'/N/\d+\.html', u)]
                    # 按文章 ID 降序排列（最新的在前）
                    news_urls.sort(key=lambda u: int(re.search(r'/N/(\d+)\.html', u).group(1)), reverse=True)
                    # 取最近 20 篇
                    for u in news_urls[:20]:
                        articles.append({'url': u, 'title': '', 'date': ''})
                    logger.info(f"    Sitemap: 发现 {len(news_urls)} 篇文章，取最近 {len(articles)} 篇")
            except Exception as e:
                logger.warning(f"    Sitemap 获取失败: {e}")

        return articles

    def _parse_generic_html(self, html, base_url):
        """通用 HTML 解析"""
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            href = a_tag.get('href', '')
            text = a_tag.get_text(strip=True)

            if len(text) < 8 or len(text) > 200:
                continue
            if any(skip in text for skip in ['首页', '下一页', '上一页', '更多', '登录', '搜索']):
                continue

            if href.startswith('/'):
                href = urljoin(base_url, href)
            elif not href.startswith('http'):
                continue

            # 尝试查找日期
            parent = a_tag.parent
            date_text = ''
            if parent:
                date_match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', parent.get_text())
                if date_match:
                    date_text = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"

            articles.append({
                'url': href,
                'title': text,
                'date': date_text,
            })

        return articles

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

            found_items = []

            for a_tag in soup.find_all('a', href=True):
                href = a_tag.get('href', '')
                text = a_tag.get_text(strip=True)

                if len(text) < 8 or len(text) > 200:
                    continue
                if any(skip in text for skip in ['首页', '下一页', '上一页', '更多', '登录', '搜索']):
                    continue

                if href.startswith('/'):
                    href = urljoin(url, href)
                elif not href.startswith('http'):
                    continue

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

            seen_urls = set()
            for item in found_items:
                if item['url'] in seen_urls:
                    continue
                seen_urls.add(item['url'])

                if not self._is_relevant(item['title']):
                    continue
                if self._is_collected(item['url']):
                    continue

                self._mark_collected(item['url'])
                record = self._make_record(
                    item['url'], item['title'], item['summary'],
                    item['date'], name, 'gov_html',
                    extra={'url_resolved': True}
                )
                results.append(record)

            logger.info(f"    获取 {len(results)} 条")

        except Exception as e:
            logger.warning(f"    采集失败: {type(e).__name__}: {e}")

        return results

    # =========================================================================
    # 主运行方法
    # =========================================================================
    def run(self):
        """运行所有源的采集"""
        logger.info("=" * 60)
        logger.info("多源采集器 v3 启动")
        logger.info(f"上次运行: {self.state.get('last_run', '首次')}")
        logger.info(f"数据源数量: {len(SOURCES)}")
        logger.info(f"Google News 解码器: {'可用' if self._gn_decoder_available else '不可用'}")
        logger.info("=" * 60)

        all_results = []

        for source in SOURCES:
            source_type = source.get('type', 'rss')

            try:
                if source_type == 'rss':
                    results = self.collect_rss(source)
                elif source_type == 'direct_html':
                    results = self.collect_direct_html(source)
                elif source_type == 'gov_html':
                    results = self.collect_gov_html(source)
                else:
                    logger.warning(f"  未知源类型: {source_type}")
                    continue

                all_results.extend(results)
                logger.info(f"  [{source['name']}] 累计: {len(all_results)} 条")

            except Exception as e:
                logger.error(f"  [{source['name']}] 采集异常: {e}")

            time.sleep(2)

        if all_results:
            output_file = self.raw_dir / f"feed_{datetime.now(BJT).strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            logger.info(f"\n保存 {len(all_results)} 条到 {output_file}")
        else:
            logger.warning("\n未采集到任何内容")

        self._save_state()

        # 统计 URL 解析情况
        resolved = sum(1 for r in all_results if r.get('url_resolved'))
        logger.info(f"采集完成: {len(all_results)} 条 | URL已解析: {resolved} | 未解析: {len(all_results) - resolved}")
        return all_results


# 保持向后兼容
RSS_SOURCES = SOURCES


def main():
    import argparse
    import warnings
    warnings.filterwarnings('ignore')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(description='低空经济情报采集器 v3')
    parser.add_argument('--test', action='store_true', help='测试模式')
    args = parser.parse_args()

    collector = FeedCollector()

    if args.test:
        # 测试模式：采集第一个源
        source = SOURCES[0]
        logger.info(f"测试采集: {source['name']}")
        results = collector.collect_rss(source)
        print(f"\n获取 {len(results)} 条结果")
        for r in results[:5]:
            print(f"  [{r['publish_date']}] {r['title'][:60]}")
            print(f"    URL: {r['url'][:80]}")
            print(f"    内容长度: {len(r.get('content', ''))}")
    else:
        collector.run()


if __name__ == '__main__':
    main()
