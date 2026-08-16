#!/usr/bin/env python3
"""
低空经济情报服务 — 采集流程主入口
编排 RSS采集 → 网页解析 → NER提取 → 数据清洗 → 报告生成 完整流程
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# 日志配置
LOG_DIR = PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

BJT = timezone(timedelta(hours=8))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f'pipeline_{datetime.now(BJT).strftime("%Y%m%d")}.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class IntelPipeline:
    """情报采集流水线"""

    def __init__(self):
        self.feed_collector = None
        self.parser = None
        self.ner_extractor = None
        self.cleaner = None
        self.report_generator = None
        self.stats = {
            'collected': 0,
            'parsed': 0,
            'entities_extracted': 0,
            'cleaned': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None,
        }

    def step_1_collect_feeds(self):
        """步骤1：RSS/Atom 采集"""
        logger.info("=" * 60)
        logger.info("步骤 1/4：RSS/Atom 采集")
        logger.info("=" * 60)

        try:
            from feed_collector import FeedCollector
            self.feed_collector = FeedCollector()
            results = self.feed_collector.run()
            self.stats['collected'] = len(results)
            logger.info(f"采集完成：{len(results)} 条")
            return results
        except Exception as e:
            logger.error(f"采集失败: {e}")
            self.stats['errors'] += 1
            return []

    def step_2_parse_content(self, raw_records):
        """步骤2：网页正文解析（对 RSS 摘要补充全文）
        
        优化：
        - 使用 requests + BeautifulSoup 先解析出真实 URL（跳过 Google News 重定向）
        - 使用 Trafilatura 提取正文
        - 并发抓取加速（ThreadPoolExecutor）
        - 限制最多处理 80 篇，避免超时
        """
        logger.info("=" * 60)
        logger.info("步骤 2/4：网页正文解析")
        logger.info("=" * 60)

        try:
            import trafilatura
            from parser import WebPageParser
            self.parser = WebPageParser()
        except Exception as e:
            logger.warning(f"解析器不可用，跳过: {e}")
            return raw_records

        import requests as req
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # 筛选需要全文提取的记录
        to_parse = []
        for record in raw_records:
            # 已有足够内容，跳过
            if len(record.get('content', '')) > 500:
                continue
            url = record.get('url', '')
            if not url:
                continue
            to_parse.append(record)

        logger.info(f"需要全文提取: {len(to_parse)} 条（已跳过 {len(raw_records) - len(to_parse)} 条内容充足）")

        # 限制并发数量，避免超时（GitHub Actions 30分钟限制）
        MAX_PARSE = 80
        if len(to_parse) > MAX_PARSE:
            logger.info(f"数量超过 {MAX_PARSE}，仅处理前 {MAX_PARSE} 条（按采集顺序）")
            to_parse = to_parse[:MAX_PARSE]

        session = req.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        session.verify = False

        def fetch_and_parse(record):
            """单条记录的全文提取"""
            url = record.get('url', '')
            try:
                # 如果 URL 仍然是 Google News 跳转链接，先解析真实 URL
                if 'news.google.com' in url:
                    try:
                        resp = session.get(url, timeout=15, allow_redirects=True)
                        final_url = resp.url
                        if 'news.google.com' in final_url:
                            import re as _re
                            # 尝试多种方式从 HTML 中提取真实 URL
                            url_match = _re.search(r'data-n-au="([^"]+)"', resp.text)
                            if not url_match:
                                url_match = _re.search(r'window\.location\.replace\(["\']([^"\']+)', resp.text)
                            if not url_match:
                                url_match = _re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+url=([^"\'>\s]+)', resp.text, _re.IGNORECASE)
                            if not url_match:
                                url_match = _re.search(r'og:url["\']\s+content=["\'](https?://[^"\']+)', resp.text)
                            if not url_match:
                                url_match = _re.search(r'<a[^>]+class=["\'][^"]*article[^"]*["\'][^>]+href=["\'](https?://[^"\']+)', resp.text)
                            if not url_match:
                                url_match = _re.search(r'<a[^>]+href=["\'](https?://[^"\']+)["\']', resp.text)
                            if url_match:
                                final_url = url_match.group(1)
                            else:
                                return ('gn_unresolved', record)
                        url = final_url
                        record['url'] = final_url
                    except Exception:
                        return ('gn_error', record)

                resp = session.get(url, timeout=15, allow_redirects=True)
                final_url = resp.url
                resp.encoding = resp.apparent_encoding or 'utf-8'
                html_content = resp.text

                text = trafilatura.extract(
                    html_content, include_comments=False,
                    include_tables=True, favor_precision=True, url=final_url
                )

                if text and len(text) > 100:
                    record['content'] = text[:8000]
                    record['url'] = final_url
                    metadata = trafilatura.extract(
                        html_content, output_format='json',
                        with_metadata=True, url=final_url
                    )
                    if metadata:
                        import json as _json
                        if isinstance(metadata, str):
                            metadata = _json.loads(metadata)
                        if metadata.get('date'):
                            record['publish_date'] = self.parser._normalize_date(metadata.get('date', ''))
                        if metadata.get('sitename'):
                            record['publisher'] = self.parser._normalize_org_name(metadata.get('sitename', ''))
                    return ('ok', record)
                else:
                    # Trafilatura 失败，用 BeautifulSoup 回退
                    from bs4 import BeautifulSoup as _bs
                    soup = _bs(html_content, 'html.parser')
                    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
                        tag.decompose()
                    body_text = soup.get_text(separator='\n', strip=True)
                    if len(body_text) > 200:
                        record['content'] = body_text[:8000]
                        return ('bs4_ok', record)
                    return ('empty', record)
            except req.exceptions.Timeout:
                return ('timeout', record)
            except req.exceptions.ConnectionError:
                return ('conn_error', record)
            except Exception:
                return ('error', record)

        # 并发抓取（5 线程）
        MAX_WORKERS = 5
        success_count = 0
        fail_count = 0
        status_counts = {}

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_and_parse, r): r for r in to_parse}
            for i, future in enumerate(as_completed(futures, timeout=300)):
                try:
                    status, record = future.result(timeout=60)
                    status_counts[status] = status_counts.get(status, 0) + 1
                    if status in ('ok', 'bs4_ok'):
                        success_count += 1
                        self.stats['parsed'] += 1
                    else:
                        fail_count += 1
                    if (i + 1) % 10 == 0:
                        logger.info(f"  进度: {i+1}/{len(to_parse)} | 成功: {success_count} 失败: {fail_count}")
                except Exception as e:
                    fail_count += 1
                    status_counts['exception'] = status_counts.get('exception', 0) + 1
                    logger.warning(f"  并发异常: {type(e).__name__}: {e}")

        logger.info(f"  状态分布: {status_counts}")
        logger.info(f"解析完成：{success_count} 成功 / {fail_count} 失败 / {len(to_parse)} 总计")
        return raw_records

    def step_3_extract_entities(self, records):
        """步骤3：NER 实体提取"""
        logger.info("=" * 60)
        logger.info("步骤 3/4：NER 实体提取")
        logger.info("=" * 60)

        try:
            from ner_extractor import NERExtractor
            self.ner_extractor = NERExtractor()
        except Exception as e:
            logger.warning(f"NER 引擎不可用，跳过: {e}")
            return records

        intel_dir = PROJECT_ROOT / 'processed'
        intel_dir.mkdir(parents=True, exist_ok=True)

        intel_records = []
        for i, record in enumerate(records):
            # 合并标题和内容用于 NER（标题通常包含关键实体）
            title = record.get('title', '')
            content = record.get('content', '')
            ner_text = f"{title} {content}".strip() if content else title

            if len(ner_text) < 20:
                intel_records.append(record)
                continue

            try:
                entities = self.ner_extractor.extract(ner_text)
                record['entities'] = entities
                self.stats['entities_extracted'] += 1

                if i < 5 or (i + 1) % 10 == 0:
                    persons = [e['text'] for e in entities.get('persons', [])[:3]]
                    orgs = [e['text'] for e in entities.get('orgs', [])[:3]]
                    logger.info(f"  [{i+1}/{len(records)}] {record['title'][:30]}... | 人物:{persons} 机构:{orgs}")

            except Exception as e:
                logger.warning(f"  [{i+1}/{len(records)}] NER 失败: {e}")

            intel_records.append(record)

        # 保存情报记录
        output_file = intel_dir / 'intel_records.jsonl'
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in intel_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        logger.info(f"NER 完成：{self.stats['entities_extracted']}/{len(records)} 条已提取实体")
        return intel_records

    def step_4_clean_and_report(self, records):
        """步骤4：数据清洗 + 报告生成"""
        logger.info("=" * 60)
        logger.info("步骤 4/4：数据清洗与报告生成")
        logger.info("=" * 60)

        # 数据清洗
        try:
            from cleaner import DataCleaner
            self.cleaner = DataCleaner()

            # 将 RSS 采集结果写入 cleaner 期望的格式
            gov_dir = PROJECT_ROOT / 'raw' / 'gov'
            gov_dir.mkdir(parents=True, exist_ok=True)

            for record in records:
                url_hash = record.get('doc_id', '')
                filename = f"{record.get('publish_date', 'unknown')}_{url_hash}.json"
                filepath = gov_dir / filename
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(record, f, ensure_ascii=False, indent=2)

            cleaned = self.cleaner.clean_all()
            self.stats['cleaned'] = len(cleaned)
            logger.info(f"清洗完成：{len(cleaned)} 条")
        except Exception as e:
            logger.warning(f"数据清洗失败: {e}")
            self.stats['errors'] += 1

        # 报告生成
        try:
            from report_generator import ReportGenerator
            self.report_generator = ReportGenerator()

            today = datetime.now(BJT).strftime('%Y-%m-%d')
            self.report_generator.generate_weekly(today)
            logger.info("周报数据已生成")
        except Exception as e:
            logger.warning(f"报告生成失败: {e}")
            self.stats['errors'] += 1

    def run_full(self):
        """运行完整流水线"""
        self.stats['start_time'] = datetime.now(BJT).isoformat()
        logger.info("=" * 60)
        logger.info("低空经济情报采集流水线 — 完整模式")
        logger.info(f"开始时间: {self.stats['start_time']}")
        logger.info("=" * 60)

        # Step 1
        raw_records = self.step_1_collect_feeds()

        if not raw_records:
            logger.warning("未采集到新内容，流水线结束")
            self._print_summary()
            return

        # Step 2
        enriched = self.step_2_parse_content(raw_records)

        # Step 3
        intel_records = self.step_3_extract_entities(enriched)

        # Step 4
        self.step_4_clean_and_report(intel_records)

        self.stats['end_time'] = datetime.now(BJT).isoformat()
        self._print_summary()

    def run_test(self):
        """测试模式：仅采集1个源，不执行NER"""
        self.stats['start_time'] = datetime.now(BJT).isoformat()
        logger.info("=" * 60)
        logger.info("低空经济情报采集流水线 — 测试模式")
        logger.info("=" * 60)

        # 测试 RSS 采集
        try:
            from feed_collector import FeedCollector, SOURCES
            self.feed_collector = FeedCollector()

            # 只采集第一个源（Google News RSS）
            source = SOURCES[0]
            stype = source.get('type', 'rss')
            if stype == 'rss':
                results = self.feed_collector.collect_rss(source)
            elif stype == 'bing_rss':
                results = self.feed_collector.collect_bing_rss(source)
            elif stype == 'gov_html':
                results = self.feed_collector.collect_gov_html(source)
            else:
                results = []

            self.stats['collected'] = len(results)
            logger.info(f"测试采集完成：{len(results)} 条")

            if results:
                # 打印前3条
                for r in results[:3]:
                    logger.info(f"  - [{r['publish_date']}] {r['title'][:50]}")
                    logger.info(f"    URL: {r['url']}")

            self.feed_collector._save_state()

        except Exception as e:
            logger.error(f"测试失败: {e}")
            self.stats['errors'] += 1

        self.stats['end_time'] = datetime.now(BJT).isoformat()
        self._print_summary()

    def run_collect_only(self):
        """仅采集模式（不解析、不NER）"""
        self.stats['start_time'] = datetime.now(BJT).isoformat()
        logger.info("=" * 60)
        logger.info("低空经济情报采集流水线 — 仅采集模式")
        logger.info("=" * 60)

        raw_records = self.step_1_collect_feeds()
        self.stats['end_time'] = datetime.now(BJT).isoformat()
        self._print_summary()

    def _print_summary(self):
        """打印执行摘要"""
        logger.info("")
        logger.info("=" * 60)
        logger.info("执行摘要")
        logger.info("=" * 60)
        for key, val in self.stats.items():
            logger.info(f"  {key}: {val}")
        logger.info("=" * 60)

        # 保存摘要到文件
        summary_file = PROJECT_ROOT / 'processed' / 'pipeline_summary.json'
        summary_file.parent.mkdir(parents=True, exist_ok=True)
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description='低空经济情报采集流水线')
    parser.add_argument('--mode', choices=['full', 'test', 'collect'],
                        default='full', help='运行模式: full=完整流水线, test=测试模式, collect=仅采集')
    args = parser.parse_args()

    pipeline = IntelPipeline()

    if args.mode == 'test':
        pipeline.run_test()
    elif args.mode == 'collect':
        pipeline.run_collect_only()
    else:
        pipeline.run_full()


if __name__ == '__main__':
    main()
