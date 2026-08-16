#!/usr/bin/env python3
"""
低空经济情报服务 — IMA 知识库交付格式生成器
将情报数据转换为 IMA Copilot 可导入的知识库格式
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


class IMAExporter:
    """IMA 知识库导出器"""

    def __init__(self):
        self.intel_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.analysis_file = PROJECT_ROOT / 'processed' / 'analysis' / 'competitive_analysis.json'
        self.profiles_dir = PROJECT_ROOT / 'processed' / 'company_profiles'
        self.output_dir = PROJECT_ROOT / 'ima-export'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self):
        """导出全部 IMA 格式文件"""
        logger.info("=" * 60)
        logger.info("开始生成 IMA 知识库交付文件")
        logger.info("=" * 60)

        # 1. 导出企业情报卡
        self._export_company_cards()

        # 2. 导出情报摘要
        self._export_intel_digest()

        # 3. 导出知识库索引
        self._export_knowledge_index()

        # 4. 导出 Copilot 问答对
        self._export_copilot_qa()

        logger.info(f"IMA 交付文件生成完成 → {self.output_dir}")

    def _export_company_cards(self):
        """导出企业情报卡（每家企业一个 Markdown 文件）"""
        cards_dir = self.output_dir / 'company-cards'
        cards_dir.mkdir(exist_ok=True)

        if not self.profiles_dir.exists():
            return

        index_data = []
        for profile_file in sorted(self.profiles_dir.glob('*.json')):
            if profile_file.name.startswith('_'):
                continue

            with open(profile_file, 'r', encoding='utf-8') as f:
                profile = json.load(f)

            # 生成 IMA 格式的 Markdown
            md_lines = [
                f"# {profile['company_name']} — 企业情报卡",
                f"",
                f"**分类**: {profile.get('category', '未分类')}",
                f"**情报提及次数**: {profile.get('mention_count', 0)}",
                f"**首次出现**: {profile.get('first_seen', 'N/A')}",
                f"**最近动态**: {profile.get('last_seen', 'N/A')}",
                f"",
                f"## 关键人物",
                f"",
            ]

            for person in profile.get('key_persons', []):
                md_lines.append(f"- {person['name']} (提及 {person['mentions']} 次)")

            md_lines.extend([
                f"",
                f"## 业务地理分布",
                f"",
            ])
            for loc in profile.get('locations', []):
                md_lines.append(f"- {loc['name']} (提及 {loc['mentions']} 次)")

            md_lines.extend([
                f"",
                f"## 合作伙伴",
                f"",
            ])
            for partner in profile.get('partners', []):
                md_lines.append(f"- {partner['name']} (共现 {partner['co_occurrences']} 次)")

            # 事件分类
            events = profile.get('events', {})
            event_labels = {
                'product_launch': '产品发布',
                'financing': '融资动态',
                'cooperation': '合作签约',
                'policy_related': '政策相关',
                'certification': '适航认证',
                'market_expansion': '市场拓展',
            }

            md_lines.extend([f"", f"## 核心事件", f""])
            for event_type, label in event_labels.items():
                event_list = events.get(event_type, [])
                if event_list:
                    md_lines.append(f"### {label} ({len(event_list)} 条)")
                    md_lines.append(f"")
                    for event in event_list[:5]:
                        md_lines.append(f"- [{event['date']}] {event['title'][:60]}")
                    md_lines.append(f"")

            # 时间线
            md_lines.extend([f"## 近期动态时间线", f""])
            for item in profile.get('timeline', [])[:10]:
                md_lines.append(f"- [{item['date']}] {item['title'][:60]}")

            md_lines.extend([
                f"",
                f"---",
                f"*本情报卡由低空经济情报系统自动生成，更新时间: {datetime.now(BJT).strftime('%Y-%m-%d')}*",
            ])

            content = '\n'.join(md_lines)
            filename = profile['company_name'].replace('/', '_')
            output_file = cards_dir / f'{filename}.md'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)

            index_data.append({
                'company': profile['company_name'],
                'category': profile.get('category', ''),
                'mentions': profile.get('mention_count', 0),
                'file': f'company-cards/{filename}.md',
            })

        # 保存索引
        index_file = cards_dir / '_index.json'
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)

        logger.info(f"  企业情报卡: {len(index_data)} 份")

    def _export_intel_digest(self):
        """导出情报摘要（按分类组织）"""
        records = self._load_records()

        # 按主题分类
        categories = {
            '政策法规': ['政策', '条例', '标准', '规划', '办法', '意见', '通知', '法规'],
            '产品技术': ['发布', '首飞', '下线', '量产', '交付', '技术', '研发', '专利', '突破'],
            '企业融资': ['融资', '投资', '上市', 'IPO', '估值', '轮'],
            '合作签约': ['合作', '签约', '协议', '战略', '携手', '联盟', '伙伴'],
            '国际动态': ['国际', '海外', '出口', '关税', '出海', '全球'],
            '适航认证': ['适航', '认证', '审定', '许可证', '资质'],
            '应用场景': ['物流', '配送', '农业', '巡检', '救援', '测绘', '安防', '环境'],
            '地方动态': ['市', '省', '区', '基地', '产业园', '试验区', '示范区'],
        }

        categorized = {cat: [] for cat in categories}
        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            for cat, keywords in categories.items():
                if any(kw in full_text for kw in keywords):
                    categorized[cat].append(record)

        digest_dir = self.output_dir / 'intel-digest'
        digest_dir.mkdir(exist_ok=True)

        for category, cat_records in categorized.items():
            if not cat_records:
                continue

            # 按日期排序
            cat_records.sort(key=lambda r: r.get('publish_date', ''), reverse=True)

            md_lines = [
                f"# {category} — 情报摘要",
                f"",
                f"**情报数量**: {len(cat_records)} 条",
                f"**更新时间**: {datetime.now(BJT).strftime('%Y-%m-%d')}",
                f"",
                f"---",
                f"",
            ]

            for record in cat_records[:50]:
                date = record.get('publish_date', 'N/A')
                title = record.get('title', '无标题')
                source = record.get('source_site', '')
                content = record.get('content', '')[:200]

                md_lines.append(f"## [{date}] {title}")
                md_lines.append(f"")
                if source:
                    md_lines.append(f"**来源**: {source}")
                    md_lines.append(f"")
                if content:
                    md_lines.append(f"{content}")
                md_lines.append(f"")

            content = '\n'.join(md_lines)
            filename = category.replace('/', '_')
            output_file = digest_dir / f'{filename}.md'
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)

        logger.info(f"  情报摘要: {len([c for c in categorized.values() if c])} 个分类")

    def _export_knowledge_index(self):
        """导出知识库总索引"""
        from company_profiler import COMPANY_ALIASES, COMPANY_CATEGORIES

        records = self._load_records()
        analysis = self._load_analysis()

        # 统计信息
        from collections import Counter
        org_counter = Counter()
        person_counter = Counter()
        loc_counter = Counter()

        for r in records:
            entities = r.get('entities', {})
            for e in entities.get('orgs', []):
                org_counter[e['text']] += 1
            for e in entities.get('persons', []):
                person_counter[e['text']] += 1
            for e in entities.get('locations', []):
                loc_counter[e['text']] += 1

        index = {
            'metadata': {
                'generated_at': datetime.now(BJT).isoformat(),
                'total_records': len(records),
                'total_companies': len([c for c in COMPANY_ALIASES.values()]),
                'total_persons': len(person_counter),
                'total_locations': len(loc_counter),
            },
            'company_categories': {cat: companies for cat, companies in COMPANY_CATEGORIES.items()},
            'top_organizations': org_counter.most_common(20),
            'top_persons': person_counter.most_common(15),
            'top_locations': loc_counter.most_common(20),
            'export_files': {
                'company_cards': 'company-cards/',
                'intel_digest': 'intel-digest/',
                'copilot_qa': 'copilot-qa.md',
            },
        }

        # 市场细分摘要
        segments = analysis.get('market_segments', [])
        if segments:
            index['market_segments'] = [
                {'segment': s['segment'], 'companies': s['companies'], 'mentions': s['mention_count']}
                for s in segments
            ]

        output_file = self.output_dir / 'knowledge-index.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        logger.info(f"  知识库索引: {output_file.name}")

    def _export_copilot_qa(self):
        """导出 Copilot 问答对"""
        records = self._load_records()
        analysis = self._load_analysis()

        qa_pairs = []

        # 基于竞争格局的问答
        landscape = analysis.get('competitive_landscape', [])
        if landscape:
            top_companies = ', '.join([c['company'] for c in landscape[:5]])
            qa_pairs.append({
                'q': '低空经济领域最活跃的企业有哪些？',
                'a': f'根据情报系统监测，最活跃的前5家企业分别是：{top_companies}。其中{landscape[0]["company"]}以活跃度评分{landscape[0]["activity_score"]}位居第一，'
                     f'主要涉及{landscape[0]["category"]}领域。'
            })

        # 基于市场细分的问答
        segments = analysis.get('market_segments', [])
        if segments:
            seg_text = '、'.join([f"{s['segment']}({s['company_count']}家企业)" for s in segments[:4]])
            qa_pairs.append({
                'q': '低空经济有哪些细分市场？',
                'a': f'当前监测到的主要细分市场包括：{seg_text}。其中{segments[0]["segment"]}领域企业最为集中，共{segments[0]["company_count"]}家企业，提及次数{segments[0]["mention_count"]}次。'
            })

        # 基于技术领域的问答
        techs = analysis.get('technology_landscape', [])
        if techs:
            top_tech = techs[0]
            companies = '、'.join([c[0] for c in top_tech.get('top_companies', [])[:3]])
            qa_pairs.append({
                'q': '低空经济的技术热点是什么？',
                'a': f'技术热点排名前三的领域是：{techs[0]["tech_area"]}({techs[0]["mention_count"]}次)、{techs[1]["tech_area"] if len(techs)>1 else ""}、{techs[2]["tech_area"] if len(techs)>2 else ""}。'
                     f'其中{top_tech["tech_area"]}领域的主要关联企业包括：{companies}。'
            })

        # 基于地理分布的问答
        geos = analysis.get('geographic_distribution', [])
        if geos:
            top_locations = '、'.join([g['location'] for g in geos[:5]])
            qa_pairs.append({
                'q': '低空经济在中国哪些地区发展最快？',
                'a': f'根据情报监测，低空经济活跃度最高的地区包括：{top_locations}。其中{geos[0]["location"]}以{geos[0]["mention_count"]}次提及位居第一。'
            })

        # 基于投资信号的问答
        signals = analysis.get('investment_signals', [])
        if signals:
            financing = [s for s in signals if s['type'] == 'financing']
            milestones = [s for s in signals if s['type'] == 'product_milestone']
            qa_pairs.append({
                'q': '近期有哪些值得关注的投资信号？',
                'a': f'系统监测到{len(signals)}条投资信号，其中融资事件{len(financing)}条、产品里程碑{len(milestones)}条。'
                     f'最近的重要信号包括：{signals[0]["title"][:50] if signals else "暂无"}。'
            })

        # 基于趋势的问答
        trends = analysis.get('trend_analysis', {})
        emerging = trends.get('emerging_topics', [])
        if emerging:
            emerging_text = '、'.join([f"{t['topic']}({t['trend']})" for t in emerging])
            qa_pairs.append({
                'q': '低空经济有哪些新兴趋势？',
                'a': f'近期监测到的新兴主题包括：{emerging_text}。这些主题在近期情报中呈现出明显的上升趋势，值得关注。'
            })

        # 生成 Markdown 格式
        md_lines = [
            f"# 低空经济情报 Copilot 问答对",
            f"",
            f"**生成时间**: {datetime.now(BJT).strftime('%Y-%m-%d')}",
            f"**问答数量**: {len(qa_pairs)} 对",
            f"",
            f"---",
            f"",
        ]

        for i, qa in enumerate(qa_pairs, 1):
            md_lines.append(f"## Q{i}: {qa['q']}")
            md_lines.append(f"")
            md_lines.append(f"**A**: {qa['a']}")
            md_lines.append(f"")

        content = '\n'.join(md_lines)
        output_file = self.output_dir / 'copilot-qa.md'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"  Copilot 问答对: {len(qa_pairs)} 对")

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
    exporter = IMAExporter()
    exporter.export_all()
