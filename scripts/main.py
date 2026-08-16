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
        """步骤2：网页正文解析（对 RSS 摘要补充全文）"""
        logger.info("=" * 60)
        logger.info("步骤 2/4：网页正文解析")
        logger.info("=" * 60)

        try:
            from parser import WebPageParser
            self.parser = WebPageParser()
        except Exception as e:
            logger.warning(f"解析器不可用，跳过: {e}")
            return raw_records

        enriched = []
        for i, record in enumerate(raw_records):
            url = record.get('url', '')
            if not url:
                enriched.append(record)
                continue

            # 如果已有足够内容，跳过全文提取
            if len(record.get('content', '')) > 500:
                enriched.append(record)
                continue

            try:
                result = self.parser.extract_content(url)
                if result and result.get('content'):
                    record['content'] = result['content']
                    if result.get('publish_date'):
                        record['publish_date'] = result['publish_date']
                    if result.get('publisher'):
                        record['publisher'] = result['publisher']
                    self.stats['parsed'] += 1
                    logger.info(f"  [{i+1}/{len(raw_records)}] 已提取全文: {record['title'][:40]}...")
                else:
                    logger.warning(f"  [{i+1}/{len(raw_records)}] 全文提取失败: {url}")
            except Exception as e:
                logger.warning(f"  [{i+1}/{len(raw_records)}] 解析异常: {e}")

            enriched.append(record)

        logger.info(f"解析完成：{self.stats['parsed']}/{len(raw_records)} 条已补充全文")
        return enriched

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
            content = record.get('content', '')
            if len(content) < 50:
                intel_records.append(record)
                continue

            try:
                entities = self.ner_extractor.extract(content)
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
