#!/usr/bin/env python3
"""
低空经济情报服务 — 数据清洗器
对采集的原始数据进行清洗、标准化和质量校验
"""

import os
import re
import json
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)


class DataCleaner:
    """数据清洗器"""

    # 机构名称标准化映射
    ORG_NORMALIZE = {
        "发改委": "国家发展和改革委员会",
        "国家发改委": "国家发展和改革委员会",
        "民航局": "中国民用航空局",
        "中国民航局": "中国民用航空局",
        "工信部": "中华人民共和国工业和信息化部",
        "交通部": "中华人民共和国交通运输部",
        "科技部": "中华人民共和国科学技术部",
        "公安部": "中华人民共和国公安部",
        "应急部": "中华人民共和国应急管理部",
        "市场监管总局": "国家市场监督管理总局",
        "气象局": "中国气象局",
    }

    def __init__(self):
        self.input_dir = PROJECT_ROOT / 'raw'
        self.output_dir = PROJECT_ROOT / 'processed'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def clean_all(self):
        """清洗所有原始数据"""
        logger.info("=" * 60)
        logger.info("开始数据清洗")
        logger.info("=" * 60)

        all_records = []
        gov_dir = self.input_dir / 'gov'
        assoc_dir = self.input_dir / 'associations'

        # 清洗政府数据
        if gov_dir.exists():
            for filepath in gov_dir.glob('*.json'):
                record = self._clean_file(filepath)
                if record:
                    all_records.append(record)

        # 清洗协会数据
        if assoc_dir.exists():
            for filepath in assoc_dir.glob('*.json'):
                record = self._clean_file(filepath)
                if record:
                    all_records.append(record)

        # 保存清洗后数据
        output_file = self.output_dir / 'clean_data.jsonl'
        with open(output_file, 'w', encoding='utf-8') as f:
            for record in all_records:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')

        # 生成统计摘要
        summary = self._generate_summary(all_records)
        summary_file = self.output_dir / 'data_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        logger.info(f"清洗完成: {len(all_records)} 条记录 → {output_file}")
        logger.info(f"统计摘要 → {summary_file}")
        return all_records

    def _clean_file(self, filepath):
        """清洗单个文件"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                record = json.load(f)

            # 清洗标题
            record['title'] = self._clean_text(record.get('title', ''))

            # 清洗正文
            record['content'] = self._clean_text(record.get('content', ''))

            # 标准化日期
            record['publish_date'] = self._normalize_date(record.get('publish_date', ''))

            # 标准化发布机构
            record['publisher'] = self._normalize_org(record.get('publisher', ''))

            # 质量校验
            record['quality_flag'] = self._validate(record)

            return record

        except Exception as e:
            logger.error(f"清洗失败 {filepath}: {e}")
            return None

    def _clean_text(self, text):
        """清洗文本内容"""
        if not text:
            return ''

        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)

        # 移除特殊字符
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

        return text.strip()

    def _normalize_date(self, date_str):
        """标准化日期为 YYYY-MM-DD"""
        if not date_str:
            return ''

        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', lambda m: f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"),
        ]

        for pattern, replacement in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    return replacement(match)
                except (ValueError, IndexError):
                    continue

        return date_str

    def _normalize_org(self, name):
        """标准化机构名称"""
        if not name:
            return ''
        return self.ORG_NORMALIZE.get(name.strip(), name.strip())

    def _validate(self, record):
        """数据质量校验"""
        issues = []

        # 检查必填字段
        if not record.get('title'):
            issues.append('missing_title')
        if not record.get('publish_date'):
            issues.append('missing_date')
        if not record.get('source_url'):
            issues.append('missing_url')

        # 检查内容长度
        content = record.get('content', '')
        if len(content) < 100:
            issues.append('content_too_short')

        # 检查日期合理性
        date_str = record.get('publish_date', '')
        if date_str and re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            try:
                year = int(date_str[:4])
                if year < 2020 or year > 2030:
                    issues.append('date_unreasonable')
            except ValueError:
                issues.append('date_invalid')

        if issues:
            return f"warning: {','.join(issues)}"
        return 'ok'

    def _generate_summary(self, records):
        """生成数据统计摘要"""
        from collections import Counter

        summary = {
            'total_records': len(records),
            'by_source': Counter(r.get('source_site', 'unknown') for r in records),
            'by_type': Counter(r.get('source_type', 'unknown') for r in records),
            'by_quality': Counter(r.get('quality_flag', 'unknown') for r in records),
            'date_range': {
                'earliest': min((r.get('publish_date', '') for r in records if r.get('publish_date')), default=''),
                'latest': max((r.get('publish_date', '') for r in records if r.get('publish_date')), default='')
            },
            'generated_at': datetime.now().isoformat()
        }

        # 转换Counter为普通dict
        summary['by_source'] = dict(summary['by_source'])
        summary['by_type'] = dict(summary['by_type'])
        summary['by_quality'] = dict(summary['by_quality'])

        return summary


def main():
    """主入口"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    cleaner = DataCleaner()
    records = cleaner.clean_all()

    print(f"\n清洗完成: {len(records)} 条记录")
    print(f"输出: {PROJECT_ROOT / 'processed' / 'clean_data.jsonl'}")


if __name__ == '__main__':
    main()
