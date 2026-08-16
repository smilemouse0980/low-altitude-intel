#!/usr/bin/env python3
"""
低空经济情报服务 — 竞争格局分析与趋势研判引擎
基于企业画像和知识图谱，生成竞争格局分析、趋势研判和投资洞察
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))

from company_profiler import COMPANY_ALIASES, COMPANY_CATEGORIES

logger = logging.getLogger(__name__)
BJT = timezone(timedelta(hours=8))


class CompetitiveAnalyzer:
    """竞争格局分析器"""

    def __init__(self):
        self.data_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.profiles_dir = PROJECT_ROOT / 'processed' / 'company_profiles'
        self.output_dir = PROJECT_ROOT / 'processed' / 'analysis'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze(self):
        """执行全部分析"""
        logger.info("=" * 60)
        logger.info("开始竞争格局分析")
        logger.info("=" * 60)

        records = self._load_records()

        results = {
            'generated_at': datetime.now(BJT).isoformat(),
            'market_segments': self._analyze_market_segments(records),
            'competitive_landscape': self._analyze_competitive_landscape(records),
            'trend_analysis': self._analyze_trends(records),
            'geographic_distribution': self._analyze_geography(records),
            'technology_landscape': self._analyze_technology(records),
            'investment_signals': self._extract_investment_signals(records),
        }

        output_file = self.output_dir / 'competitive_analysis.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"竞争格局分析完成 → {output_file}")
        return results

    def _load_records(self):
        records = []
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        logger.info(f"加载情报记录: {len(records)} 条")
        return records

    def _analyze_market_segments(self, records):
        """市场细分分析"""
        segments = defaultdict(lambda: {
            'companies': set(),
            'mention_count': 0,
            'records': [],
            'key_events': [],
        })

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    # 找到企业所属细分
                    for segment, companies in COMPANY_CATEGORIES.items():
                        if canonical in companies:
                            segments[segment]['companies'].add(canonical)
                            segments[segment]['mention_count'] += 1
                            segments[segment]['records'].append(record.get('title', '')[:60])

                            # 关键事件
                            title = record.get('title', '')
                            if any(kw in full_text for kw in ['发布', '首飞', '下线', '量产', '交付']):
                                segments[segment]['key_events'].append({
                                    'date': record.get('publish_date', ''),
                                    'title': title,
                                    'company': canonical,
                                })
                            break

        # 转换为可序列化格式
        result = []
        for segment, data in sorted(segments.items(), key=lambda x: x[1]['mention_count'], reverse=True):
            result.append({
                'segment': segment,
                'company_count': len(data['companies']),
                'companies': sorted(data['companies']),
                'mention_count': data['mention_count'],
                'key_event_count': len(data['key_events']),
                'recent_events': sorted(data['key_events'], key=lambda x: x['date'], reverse=True)[:5],
            })

        logger.info(f"  市场细分: {len(result)} 个")
        return result

    def _analyze_competitive_landscape(self, records):
        """竞争格局分析"""
        company_data = defaultdict(lambda: {
            'mentions': 0,
            'timeline': [],
            'event_types': Counter(),
            'locations': Counter(),
            'partners': Counter(),
        })

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            companies_in_record = set()

            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            for company in companies_in_record:
                company_data[company]['mentions'] += 1
                company_data[company]['timeline'].append({
                    'date': record.get('publish_date', ''),
                    'title': record.get('title', ''),
                })

                # 事件类型分类
                if any(kw in full_text for kw in ['发布', '首飞', '下线', '量产', '交付']):
                    company_data[company]['event_types']['product'] += 1
                if any(kw in full_text for kw in ['融资', '投资', '上市', 'IPO']):
                    company_data[company]['event_types']['financing'] += 1
                if any(kw in full_text for kw in ['合作', '签约', '协议', '战略']):
                    company_data[company]['event_types']['cooperation'] += 1
                if any(kw in full_text for kw in ['出海', '国际', '海外', '出口']):
                    company_data[company]['event_types']['international'] += 1
                if any(kw in full_text for kw in ['适航', '认证', '审定']):
                    company_data[company]['event_types']['certification'] += 1

                # 地点
                entities = record.get('entities', {})
                for loc_entity in entities.get('locations', []):
                    loc = loc_entity['text']
                    if loc not in ('中国', '美国'):
                        company_data[company]['locations'][loc] += 1

                # 合作伙伴
                for other_alias, other_canonical in COMPANY_ALIASES.items():
                    if other_canonical != company and other_alias in full_text:
                        company_data[company]['partners'][other_canonical] += 1

        # 排名
        ranking = []
        for company, data in sorted(company_data.items(), key=lambda x: x[1]['mentions'], reverse=True):
            category = '其他'
            for cat, companies in COMPANY_CATEGORIES.items():
                if company in companies:
                    category = cat
                    break

            ranking.append({
                'company': company,
                'category': category,
                'mention_count': data['mentions'],
                'event_distribution': dict(data['event_types']),
                'top_locations': data['locations'].most_common(5),
                'top_partners': data['partners'].most_common(5),
                'latest_activity': max((t['date'] for t in data['timeline'] if t['date']), default=''),
                'activity_score': self._calc_activity_score(data),
            })

        logger.info(f"  竞争格局: {len(ranking)} 家企业排名")
        return ranking

    def _calc_activity_score(self, data):
        """计算企业活跃度评分"""
        score = data['mentions'] * 1.0
        score += data['event_types'].get('product', 0) * 3.0
        score += data['event_types'].get('financing', 0) * 5.0
        score += data['event_types'].get('cooperation', 0) * 2.0
        score += data['event_types'].get('international', 0) * 4.0
        score += data['event_types'].get('certification', 0) * 3.0
        return round(score, 1)

    def _analyze_trends(self, records):
        """趋势分析"""
        # 按月统计
        monthly = defaultdict(lambda: {
            'total': 0,
            'companies_mentioned': Counter(),
            'topics': Counter(),
        })

        for record in records:
            date = record.get('publish_date', '')
            if not date or len(date) < 7:
                continue
            month = date[:7]
            monthly[month]['total'] += 1

            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    monthly[month]['companies_mentioned'][canonical] += 1

            # 主题分类
            topics = {
                '政策法规': ['政策', '条例', '标准', '规划', '办法', '意见', '通知'],
                '产品发布': ['发布', '首飞', '下线', '量产', '交付', '推出'],
                '融资投资': ['融资', '投资', '上市', 'IPO', '估值'],
                '合作签约': ['合作', '签约', '协议', '战略', '携手'],
                '国际动态': ['国际', '海外', '出口', '关税', '出海'],
                '适航认证': ['适航', '认证', '审定', '许可'],
                '应用场景': ['物流', '农业', '巡检', '救援', '测绘', '安防'],
            }

            for topic, keywords in topics.items():
                if any(kw in full_text for kw in keywords):
                    monthly[month]['topics'][topic] += 1

        # 转换并排序
        trend_data = []
        for month in sorted(monthly.keys()):
            data = monthly[month]
            trend_data.append({
                'month': month,
                'total_articles': data['total'],
                'top_companies': data['companies_mentioned'].most_common(5),
                'top_topics': data['topics'].most_common(5),
            })

        # 近6个月趋势
        recent_trends = trend_data[-6:] if len(trend_data) >= 6 else trend_data

        # 主题热度变化
        topic_trends = defaultdict(list)
        for month_data in recent_trends:
            for topic, count in month_data['top_topics']:
                topic_trends[topic].append({'month': month_data['month'], 'count': count})

        logger.info(f"  趋势分析: {len(trend_data)} 个月, 近6月重点分析")
        return {
            'all_months': trend_data,
            'recent_6_months': recent_trends,
            'topic_trends': dict(topic_trends),
            'emerging_topics': self._find_emerging_topics(topic_trends),
        }

    def _find_emerging_topics(self, topic_trends):
        """发现新兴主题"""
        emerging = []
        for topic, data in topic_trends.items():
            if len(data) >= 2:
                recent = data[-1]['count']
                previous = data[-2]['count'] if len(data) >= 2 else 0
                if recent > 0 and previous == 0:
                    emerging.append({'topic': topic, 'trend': 'new'})
                elif recent > previous * 1.5:
                    emerging.append({'topic': topic, 'trend': 'rising', 'change': f'+{round((recent/previous - 1)*100)}%'})
        return emerging

    def _analyze_geography(self, records):
        """地理分布分析"""
        location_data = defaultdict(lambda: {
            'total': 0,
            'companies': Counter(),
            'topics': Counter(),
        })

        for record in records:
            entities = record.get('entities', {})
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            for loc_entity in entities.get('locations', []):
                loc = loc_entity['text']
                if loc in ('中国', '美国'):
                    continue
                location_data[loc]['total'] += 1

                for alias, canonical in COMPANY_ALIASES.items():
                    if alias in full_text:
                        location_data[loc]['companies'][canonical] += 1

                # 主题
                if any(kw in full_text for kw in ['政策', '条例', '规划']):
                    location_data[loc]['topics']['政策'] += 1
                if any(kw in full_text for kw in ['合作', '签约', '落地', '项目']):
                    location_data[loc]['topics']['项目'] += 1
                if any(kw in full_text for kw in ['基地', '产业园', '试验区']):
                    location_data[loc]['topics']['基建'] += 1

        result = []
        for loc, data in sorted(location_data.items(), key=lambda x: x[1]['total'], reverse=True)[:20]:
            result.append({
                'location': loc,
                'mention_count': data['total'],
                'top_companies': data['companies'].most_common(3),
                'top_topics': data['topics'].most_common(3),
            })

        logger.info(f"  地理分布: {len(result)} 个重点区域")
        return result

    def _analyze_technology(self, records):
        """技术领域分析"""
        tech_keywords = {
            'eVTOL/电动垂直起降': ['eVTOL', '电动垂直起降', '城市空中交通', 'UAM'],
            '无人机系统': ['无人驾驶航空器', '无人机', 'UAV'],
            '通航运营': ['通用航空', '通航', '低空空域'],
            '适航认证': ['适航', '认证', '审定', '许可证'],
            '动力电池': ['电池', '锂电池', '固态电池', '动力系统'],
            '航空材料': ['复合材料', '碳纤维', '钛合金', '材料'],
            '导航通信': ['北斗', '导航', '5G', '通信', '感知'],
            '空中交通管理': ['空管', '空中交通管理', '空域管理', '低空通信'],
            '物流配送': ['物流', '配送', '货运'],
            '应用场景': ['农业', '巡检', '救援', '测绘', '安防', '环境监测'],
        }

        tech_data = defaultdict(lambda: {
            'total': 0,
            'companies': Counter(),
            'timeline': [],
        })

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            for tech_area, keywords in tech_keywords.items():
                if any(kw in full_text for kw in keywords):
                    tech_data[tech_area]['total'] += 1
                    tech_data[tech_area]['timeline'].append(record.get('publish_date', ''))

                    for alias, canonical in COMPANY_ALIASES.items():
                        if alias in full_text:
                            tech_data[tech_area]['companies'][canonical] += 1

        result = []
        for tech, data in sorted(tech_data.items(), key=lambda x: x[1]['total'], reverse=True):
            result.append({
                'tech_area': tech,
                'mention_count': data['total'],
                'top_companies': data['companies'].most_common(5),
                'first_seen': min((d for d in data['timeline'] if d), default=''),
                'last_seen': max((d for d in data['timeline'] if d), default=''),
            })

        logger.info(f"  技术领域: {len(result)} 个")
        return result

    def _extract_investment_signals(self, records):
        """投资信号提取"""
        signals = []

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            # 融资事件
            if any(kw in full_text for kw in ['融资', '投资', '轮', '估值', '上市', 'IPO']):
                companies = set()
                for alias, canonical in COMPANY_ALIASES.items():
                    if alias in full_text:
                        companies.add(canonical)

                if companies:
                    signals.append({
                        'type': 'financing',
                        'date': record.get('publish_date', ''),
                        'title': record.get('title', ''),
                        'companies': sorted(companies),
                        'source': record.get('source_site', ''),
                    })

            # 产品里程碑
            elif any(kw in full_text for kw in ['首飞', '下线', '量产', '交付', '首台']):
                companies = set()
                for alias, canonical in COMPANY_ALIASES.items():
                    if alias in full_text:
                        companies.add(canonical)

                if companies:
                    signals.append({
                        'type': 'product_milestone',
                        'date': record.get('publish_date', ''),
                        'title': record.get('title', ''),
                        'companies': sorted(companies),
                        'source': record.get('source_site', ''),
                    })

            # 国际化
            elif any(kw in full_text for kw in ['出海', '国际', '海外', '出口', '关税']):
                companies = set()
                for alias, canonical in COMPANY_ALIASES.items():
                    if alias in full_text:
                        companies.add(canonical)

                if companies:
                    signals.append({
                        'type': 'international',
                        'date': record.get('publish_date', ''),
                        'title': record.get('title', ''),
                        'companies': sorted(companies),
                        'source': record.get('source_site', ''),
                    })

        signals.sort(key=lambda x: x['date'], reverse=True)
        logger.info(f"  投资信号: {len(signals)} 条")
        return signals[:30]


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    analyzer = CompetitiveAnalyzer()
    analyzer.analyze()
