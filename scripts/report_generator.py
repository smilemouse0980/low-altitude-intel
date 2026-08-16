#!/usr/bin/env python3
"""
低空经济情报服务 — 报告生成器
根据采集和分析的数据生成周报、月报、企业深度分析等报告
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)

# 北京时间
BJT = timezone(timedelta(hours=8))


class ReportGenerator:
    """情报报告生成器"""

    def __init__(self):
        self.data_file = PROJECT_ROOT / 'processed' / 'clean_data.jsonl'
        self.intel_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.reports_dir = PROJECT_ROOT / 'reports'

    def load_data(self, date_from=None, date_to=None):
        """加载情报数据，支持日期过滤"""
        records = []

        data_file = self.intel_file if self.intel_file.exists() else self.data_file
        if not data_file.exists():
            logger.warning(f"数据文件不存在: {data_file}")
            return records

        with open(data_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    # 日期过滤
                    pub_date = record.get('publish_date', '')
                    if date_from and pub_date and pub_date < date_from:
                        continue
                    if date_to and pub_date and pub_date > date_to:
                        continue
                    records.append(record)
                except json.JSONDecodeError:
                    continue

        logger.info(f"加载 {len(records)} 条记录")
        return records

    def generate_weekly(self, week_date=None):
        """
        生成周报
        Args:
            week_date: 周报日期 (YYYY-MM-DD)，默认为今天
        """
        if week_date is None:
            week_date = datetime.now(BJT).strftime('%Y-%m-%d')

        # 计算本周范围（周一到周日）
        dt = datetime.strptime(week_date, '%Y-%m-%d')
        monday = dt - timedelta(days=dt.weekday())
        sunday = monday + timedelta(days=6)

        date_from = monday.strftime('%Y-%m-%d')
        date_to = sunday.strftime('%Y-%m-%d')

        logger.info(f"生成周报: {date_from} ~ {date_to}")

        records = self.load_data(date_from, date_to)

        # 构建周报数据
        report_data = {
            'report_type': 'weekly',
            'period': f'{date_from} ~ {date_to}',
            'generated_at': datetime.now(BJT).isoformat(),
            'total_items': len(records),
            'sections': {
                'policy_updates': self._filter_by_keywords(records, ['政策', '通知', '办法', '条例', '意见']),
                'industry_news': self._filter_by_keywords(records, ['动态', '签约', '发布', '启动', '开业']),
                'company_intel': self._filter_by_keywords(records, ['融资', '上市', '合作', '量产', '交付']),
                'meeting_preview': self._filter_by_keywords(records, ['峰会', '论坛', '展会', '研讨会'])
            }
        }

        # 保存报告数据
        week_dir = self.reports_dir / f'{datetime.now(BJT).strftime("%Y")}-W{dt.isocalendar()[1]:02d}'
        week_dir.mkdir(parents=True, exist_ok=True)

        output_file = week_dir / 'weekly-report-data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"周报数据已生成: {output_file}")
        logger.info(f"  政策速递: {len(report_data['sections']['policy_updates'])} 条")
        logger.info(f"  行业动态: {len(report_data['sections']['industry_news'])} 条")
        logger.info(f"  企业情报: {len(report_data['sections']['company_intel'])} 条")
        logger.info(f"  会议预告: {len(report_data['sections']['meeting_preview'])} 条")

        return output_file

    def generate_monthly(self, month_date=None):
        """生成月报"""
        if month_date is None:
            month_date = datetime.now(BJT).strftime('%Y-%m')

        logger.info(f"生成月报: {month_date}")

        date_from = f"{month_date}-01"
        # 计算月末
        year, mon = map(int, month_date.split('-'))
        if mon == 12:
            date_to = f"{year+1}-01-01"
        else:
            date_to = f"{year}-{mon+1:02d}-01"

        records = self.load_data(date_from, date_to)

        report_data = {
            'report_type': 'monthly',
            'period': month_date,
            'generated_at': datetime.now(BJT).isoformat(),
            'total_items': len(records),
            'sections': {
                'policy_review': self._filter_by_keywords(records, ['政策', '法规', '标准', '规划']),
                'standard_progress': self._filter_by_keywords(records, ['标准', '规范', '团体标准']),
                'investment': self._filter_by_keywords(records, ['融资', '投资', '轮', '估值']),
                'tech_trends': self._filter_by_keywords(records, ['技术', '研发', '专利', '突破']),
                'meeting_review': self._filter_by_keywords(records, ['峰会', '论坛', '展会', '研讨会'])
            }
        }

        month_dir = self.reports_dir / f'monthly-{month_date}'
        month_dir.mkdir(parents=True, exist_ok=True)

        output_file = month_dir / 'monthly-report-data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"月报数据已生成: {output_file}")
        return output_file

    def generate_company_report(self, company_name):
        """生成企业深度分析报告"""
        logger.info(f"生成企业报告: {company_name}")

        records = self.load_data()
        company_records = [r for r in records if company_name in r.get('content', '') or company_name in r.get('title', '')]

        # 读取企业档案
        profile_file = PROJECT_ROOT / 'processed' / 'company_profiles' / f'{company_name}.json'
        company_profile = {}
        if profile_file.exists():
            with open(profile_file, 'r', encoding='utf-8') as f:
                company_profile = json.load(f)

        report_data = {
            'report_type': 'company_analysis',
            'company_name': company_name,
            'generated_at': datetime.now(BJT).isoformat(),
            'profile': company_profile,
            'related_records': len(company_records),
            'recent_news': company_records[:10]  # 最近10条
        }

        company_dir = self.reports_dir / f'company-{company_name}'
        company_dir.mkdir(parents=True, exist_ok=True)

        output_file = company_dir / 'company-report-data.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, ensure_ascii=False, indent=2)

        logger.info(f"企业报告数据已生成: {output_file}")
        return output_file

    def _filter_by_keywords(self, records, keywords):
        """按关键词筛选记录"""
        filtered = []
        for record in records:
            text = (record.get('title', '') + record.get('content', '')).lower()
            if any(kw in text for kw in keywords):
                filtered.append({
                    'title': record.get('title', ''),
                    'date': record.get('publish_date', ''),
                    'source': record.get('source_site', ''),
                    'url': record.get('url', ''),
                    'summary': record.get('content', '')[:200]
                })
        return filtered


def main():
    """主入口"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    parser = argparse.ArgumentParser(description='低空经济情报报告生成器')
    parser.add_argument('--type', choices=['weekly', 'monthly', 'company'],
                        required=True, help='报告类型')
    parser.add_argument('--date', type=str, help='日期 (周报: YYYY-MM-DD, 月报: YYYY-MM)')
    parser.add_argument('--company', type=str, help='企业名称（企业报告专用）')

    args = parser.parse_args()

    generator = ReportGenerator()

    if args.type == 'weekly':
        generator.generate_weekly(args.date)
    elif args.type == 'monthly':
        generator.generate_monthly(args.date)
    elif args.type == 'company':
        if not args.company:
            print("错误: 企业报告需要指定 --company 参数")
            sys.exit(1)
        generator.generate_company_report(args.company)


if __name__ == '__main__':
    main()
