#!/usr/bin/env python3
"""
低空经济情报服务 — 增强报告生成器
生成企业深度报告、竞争格局报告、月度趋势报告 (Markdown)
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))

logger = logging.getLogger(__name__)
BJT = timezone(timedelta(hours=8))


class EnhancedReporter:
    """增强报告生成器"""

    def __init__(self):
        self.intel_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.analysis_file = PROJECT_ROOT / 'processed' / 'analysis' / 'competitive_analysis.json'
        self.profiles_dir = PROJECT_ROOT / 'processed' / 'company_profiles'
        self.reports_dir = PROJECT_ROOT / 'reports'
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_all(self):
        """生成全部增强报告"""
        logger.info("=" * 60)
        logger.info("开始生成增强报告")
        logger.info("=" * 60)

        self.generate_monthly_report()
        self.generate_executive_summary()

        logger.info("增强报告生成完成")

    def generate_monthly_report(self, month=None):
        """生成月度趋势报告"""
        if month is None:
            month = datetime.now(BJT).strftime('%Y-%m')

        logger.info(f"生成月度报告: {month}")

        records = self._load_records()
        month_records = [r for r in records if r.get('publish_date', '').startswith(month)]

        analysis = self._load_analysis()

        # 生成 Markdown
        lines = [
            f"# 低空经济月度趋势报告",
            f"",
            f"**报告月份**: {month}",
            f"**生成时间**: {datetime.now(BJT).strftime('%Y-%m-%d %H:%M')} (北京时间)",
            f"**数据来源**: Google News RSS、Bing News RSS、国务院政策搜索",
            f"**本月情报**: {len(month_records)} 条",
            f"",
            f"---",
            f"",
        ]

        # 一、月度概览
        lines.extend(self._monthly_overview(month_records, month))

        # 二、市场细分
        lines.extend(self._monthly_segments(analysis))

        # 三、企业动态
        lines.extend(self._monthly_companies(month_records))

        # 四、技术热点
        lines.extend(self._monthly_tech(analysis))

        # 五、地理动态
        lines.extend(self._monthly_geo(analysis))

        # 六、投资信号
        lines.extend(self._monthly_signals(analysis))

        # 七、趋势研判
        lines.extend(self._monthly_outlook(analysis, month_records))

        content = '\n'.join(lines)
        output_file = self.reports_dir / f'monthly-{month}.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"月度报告 → {output_file}")
        return output_file

    def generate_executive_summary(self):
        """生成高管摘要"""
        logger.info("生成高管摘要")

        analysis = self._load_analysis()
        records = self._load_records()

        lines = [
            f"# 低空经济情报高管摘要",
            f"",
            f"**生成时间**: {datetime.now(BJT).strftime('%Y-%m-%d %H:%M')} (北京时间)",
            f"**情报总量**: {len(records)} 条",
            f"",
            f"---",
            f"",
            f"## 一、核心发现",
            f"",
        ]

        # 市场细分摘要
        segments = analysis.get('market_segments', [])
        lines.append(f"### 市场细分 ({len(segments)} 个领域)")
        lines.append(f"")
        lines.append(f"| 细分领域 | 企业数 | 提及次数 | 关键事件 |")
        lines.append(f"|----------|--------|----------|----------|")
        for seg in segments:
            lines.append(f"| {seg['segment']} | {seg['company_count']} | {seg['mention_count']} | {seg['key_event_count']} |")
        lines.append(f"")

        # 企业排名 Top 5
        landscape = analysis.get('competitive_landscape', [])
        lines.append(f"### 企业活跃度 Top 5")
        lines.append(f"")
        lines.append(f"| 排名 | 企业 | 分类 | 活跃度评分 | 最新动态 |")
        lines.append(f"|------|------|------|------------|----------|")
        for i, company in enumerate(landscape[:5], 1):
            lines.append(f"| {i} | {company['company']} | {company['category']} | {company['activity_score']} | {company['latest_activity']} |")
        lines.append(f"")

        # 投资信号
        signals = analysis.get('investment_signals', [])
        lines.append(f"### 投资信号 ({len(signals)} 条)")
        lines.append(f"")
        financing = [s for s in signals if s['type'] == 'financing']
        milestones = [s for s in signals if s['type'] == 'product_milestone']
        international = [s for s in signals if s['type'] == 'international']

        lines.append(f"- **融资事件**: {len(financing)} 条")
        lines.append(f"- **产品里程碑**: {len(milestones)} 条")
        lines.append(f"- **国际化动态**: {len(international)} 条")
        lines.append(f"")

        # 近期信号
        lines.append(f"### 近期重点信号")
        lines.append(f"")
        for signal in signals[:10]:
            companies = ', '.join(signal.get('companies', []))
            lines.append(f"- [{signal['date']}] **{signal['type']}** | {companies} | {signal['title'][:60]}")
        lines.append(f"")

        # 技术热点
        techs = analysis.get('technology_landscape', [])
        lines.append(f"### 技术热点 Top 5")
        lines.append(f"")
        lines.append(f"| 技术领域 | 提及次数 | 关联企业 |")
        lines.append(f"|----------|----------|----------|")
        for tech in techs[:5]:
            companies = ', '.join([c[0] for c in tech.get('top_companies', [])[:3]])
            lines.append(f"| {tech['tech_area']} | {tech['mention_count']} | {companies} |")
        lines.append(f"")

        # 趋势
        trends = analysis.get('trend_analysis', {})
        emerging = trends.get('emerging_topics', [])
        if emerging:
            lines.append(f"### 新兴主题")
            lines.append(f"")
            for topic in emerging:
                lines.append(f"- **{topic['topic']}** — {topic['trend']}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"")
        lines.append(f"*本摘要由低空经济情报采集系统自动生成，数据来源为公开新闻报道。*")

        content = '\n'.join(lines)
        output_file = self.reports_dir / 'executive-summary.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"高管摘要 → {output_file}")
        return output_file

    def _monthly_overview(self, records, month):
        lines = [
            f"## 一、月度概览",
            f"",
            f"本月共采集低空经济相关情报 **{len(records)}** 条，涵盖政策动态、企业新闻、技术进展、国际合作等多个维度。",
            f"",
        ]

        if not records:
            lines.append(f"本月暂无采集数据。")
            lines.append(f"")
            return lines

        # 按日统计
        from collections import Counter
        daily = Counter(r.get('publish_date', '') for r in records if r.get('publish_date'))
        lines.append(f"### 每日情报量")
        lines.append(f"")
        lines.append(f"| 日期 | 情报数 |")
        lines.append(f"|------|--------|")
        for date in sorted(daily.keys()):
            lines.append(f"| {date} | {daily[date]} |")
        lines.append(f"")

        return lines

    def _monthly_segments(self, analysis):
        segments = analysis.get('market_segments', [])
        lines = [
            f"## 二、市场细分动态",
            f"",
            f"| 细分领域 | 企业数 | 提及次数 | 关键事件数 |",
            f"|----------|--------|----------|------------|",
        ]
        for seg in segments:
            lines.append(f"| {seg['segment']} | {seg['company_count']} | {seg['mention_count']} | {seg['key_event_count']} |")
        lines.append(f"")

        # 各细分近期事件
        for seg in segments[:3]:
            if seg.get('recent_events'):
                lines.append(f"### {seg['segment']} 近期事件")
                lines.append(f"")
                for event in seg['recent_events']:
                    lines.append(f"- [{event['date']}] {event['company']}: {event['title'][:60]}")
                lines.append(f"")

        return lines

    def _monthly_companies(self, records):
        from collections import Counter
        from company_profiler import COMPANY_ALIASES

        company_mentions = Counter()
        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    company_mentions[canonical] += 1

        lines = [
            f"## 三、企业动态",
            f"",
            f"### 企业提及排名",
            f"",
            f"| 排名 | 企业 | 本月提及 |",
            f"|------|------|----------|",
        ]
        for i, (company, count) in enumerate(company_mentions.most_common(10), 1):
            lines.append(f"| {i} | {company} | {count} |")
        lines.append(f"")

        # 近期企业新闻
        lines.append(f"### 近期企业新闻")
        lines.append(f"")
        for record in records[:15]:
            lines.append(f"- [{record.get('publish_date', '')}] {record.get('title', '')[:70]}")
        lines.append(f"")

        return lines

    def _monthly_tech(self, analysis):
        techs = analysis.get('technology_landscape', [])
        lines = [
            f"## 四、技术热点",
            f"",
            f"| 技术领域 | 提及次数 | 主要关联企业 |",
            f"|----------|----------|--------------|",
        ]
        for tech in techs[:8]:
            companies = ', '.join([c[0] for c in tech.get('top_companies', [])[:3]])
            lines.append(f"| {tech['tech_area']} | {tech['mention_count']} | {companies} |")
        lines.append(f"")
        return lines

    def _monthly_geo(self, analysis):
        geos = analysis.get('geographic_distribution', [])
        lines = [
            f"## 五、地理分布",
            f"",
            f"| 区域 | 提及次数 | 关联企业 |",
            f"|------|----------|----------|",
        ]
        for geo in geos[:10]:
            companies = ', '.join([c[0] for c in geo.get('top_companies', [])[:2]])
            lines.append(f"| {geo['location']} | {geo['mention_count']} | {companies} |")
        lines.append(f"")
        return lines

    def _monthly_signals(self, analysis):
        signals = analysis.get('investment_signals', [])
        lines = [
            f"## 六、投资信号",
            f"",
        ]

        if not signals:
            lines.append(f"暂无投资信号。")
            lines.append(f"")
            return lines

        # 按类型分组
        by_type = {}
        for s in signals:
            by_type.setdefault(s['type'], []).append(s)

        type_names = {
            'financing': '融资事件',
            'product_milestone': '产品里程碑',
            'international': '国际化动态',
        }

        for sig_type, type_signals in by_type.items():
            lines.append(f"### {type_names.get(sig_type, sig_type)} ({len(type_signals)} 条)")
            lines.append(f"")
            for s in type_signals[:8]:
                companies = ', '.join(s.get('companies', []))
                lines.append(f"- [{s['date']}] {companies} | {s['title'][:60]}")
            lines.append(f"")

        return lines

    def _monthly_outlook(self, analysis, records):
        trends = analysis.get('trend_analysis', {})
        emerging = trends.get('emerging_topics', [])

        lines = [
            f"## 七、趋势研判",
            f"",
        ]

        if emerging:
            lines.append(f"### 新兴主题")
            lines.append(f"")
            for topic in emerging:
                lines.append(f"- **{topic['topic']}** — 趋势: {topic['trend']}")
            lines.append(f"")

        # 近6月趋势
        recent = trends.get('recent_6_months', [])
        if recent:
            lines.append(f"### 近6月情报量趋势")
            lines.append(f"")
            lines.append(f"| 月份 | 情报数 | 热门主题 |")
            lines.append(f"|------|--------|----------|")
            for m in recent:
                topics = ', '.join([f"{t[0]}({t[1]})" for t in m.get('top_topics', [])[:3]])
                lines.append(f"| {m['month']} | {m['total_articles']} | {topics} |")
            lines.append(f"")

        lines.extend([
            f"### 风险提示",
            f"",
            f"1. **数据局限**: 部分文章全文未能获取，实体提取可能不完整",
            f"2. **来源偏差**: Google News RSS 以标题为主，深度内容有限",
            f"3. **时效性**: 情报采集依赖 RSS 更新频率，可能存在延迟",
            f"",
            f"---",
            f"",
            f"*本报告由低空经济情报采集系统自动生成。*",
        ])

        return lines

    def _load_records(self):
        records = []
        if self.intel_file.exists():
            with open(self.intel_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        return records

    def _load_analysis(self):
        if self.analysis_file.exists():
            with open(self.analysis_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    reporter = EnhancedReporter()
    reporter.generate_all()
