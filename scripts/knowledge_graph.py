#!/usr/bin/env python3
"""
低空经济情报服务 — 知识图谱构建引擎
从情报记录中提取实体关系，构建结构化知识图谱
节点: 企业、人物、地点、政策、技术领域
边: 合作、任职、提及、关联
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)

BJT = timezone(timedelta(hours=8))

# 复用企业别名
from company_profiler import COMPANY_ALIASES, COMPANY_CATEGORIES


class KnowledgeGraphBuilder:
    """知识图谱构建器"""

    def __init__(self):
        self.data_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.output_dir = PROJECT_ROOT / 'processed' / 'knowledge_graph'
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.nodes = {}
        self.edges = []
        self._edge_counter = 0

    def build(self):
        """构建知识图谱"""
        logger.info("=" * 60)
        logger.info("开始构建知识图谱")
        logger.info("=" * 60)

        records = self._load_records()

        # 构建各类节点和边
        self._build_company_nodes(records)
        self._build_person_nodes(records)
        self._build_location_nodes(records)
        self._build_policy_nodes(records)
        self._build_tech_nodes(records)

        # 构建关系边
        self._build_company_person_edges(records)
        self._build_company_location_edges(records)
        self._build_company_company_edges(records)
        self._build_company_policy_edges(records)
        self._build_company_tech_edges(records)

        # 保存图谱
        self._save_graph()

        logger.info(f"知识图谱构建完成: {len(self.nodes)} 节点, {len(self.edges)} 边")
        return self._get_summary()

    def _load_records(self):
        """加载情报记录"""
        records = []
        if self.data_file.exists():
            with open(self.data_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        logger.info(f"加载情报记录: {len(records)} 条")
        return records

    def _add_node(self, node_id, node_type, name, **props):
        """添加节点"""
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                'id': node_id,
                'type': node_type,
                'name': name,
                'properties': props,
            }

    def _add_edge(self, source, target, edge_type, **props):
        """添加边（去重，累加权重）"""
        # 查找是否已存在相同边
        for edge in self.edges:
            if edge['source'] == source and edge['target'] == target and edge['type'] == edge_type:
                edge['weight'] = edge.get('weight', 0) + 1
                if 'records' in props:
                    edge.setdefault('records', []).extend(props['records'])
                return

        self._edge_counter += 1
        edge = {
            'id': f'e{self._edge_counter}',
            'source': source,
            'target': target,
            'type': edge_type,
            'weight': props.get('weight', 1),
        }
        if 'records' in props:
            edge['records'] = props['records']
        if 'date' in props:
            edge['date'] = props['date']
        self.edges.append(edge)

    def _build_company_nodes(self, records):
        """构建企业节点"""
        company_mentions = Counter()

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            entities = record.get('entities', {})

            # 从文本中匹配企业
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    company_mentions[canonical] += 1

            # 从实体中提取
            for org_entity in entities.get('orgs', []):
                org_name = org_entity['text']
                canonical = COMPANY_ALIASES.get(org_name, org_name)
                if canonical in set(COMPANY_ALIASES.values()):
                    company_mentions[canonical] += 1

        for company, count in company_mentions.items():
            category = '其他'
            for cat, companies in COMPANY_CATEGORIES.items():
                if company in companies:
                    category = cat
                    break
            self._add_node(
                f'company:{company}', 'company', company,
                category=category, mention_count=count
            )

        logger.info(f"  企业节点: {len(company_mentions)}")

    def _build_person_nodes(self, records):
        """构建人物节点"""
        person_mentions = Counter()

        for record in records:
            entities = record.get('entities', {})
            for person_entity in entities.get('persons', []):
                person_name = person_entity['text']
                # 过滤误判
                if person_name in COMPANY_ALIASES:
                    continue
                if person_name in ('org', 'tan', '揭牌'):
                    continue
                if len(person_name) < 2:
                    continue
                person_mentions[person_name] += 1

        for person, count in person_mentions.items():
            self._add_node(
                f'person:{person}', 'person', person,
                mention_count=count
            )

        logger.info(f"  人物节点: {len(person_mentions)}")

    def _build_location_nodes(self, records):
        """构建地点节点"""
        location_mentions = Counter()

        for record in records:
            entities = record.get('entities', {})
            for loc_entity in entities.get('locations', []):
                loc_name = loc_entity['text']
                location_mentions[loc_name] += 1

        for location, count in location_mentions.items():
            self._add_node(
                f'location:{location}', 'location', location,
                mention_count=count
            )

        logger.info(f"  地点节点: {len(location_mentions)}")

    def _build_policy_nodes(self, records):
        """构建政策节点"""
        policy_keywords = [
            '无人驾驶航空器飞行管理暂行条例', 'CCAR-92', '通用机场管理规定',
            '低空经济标准体系建设指南', '通用航空装备创新应用实施方案',
            '深圳经济特区低空经济产业促进条例', '苏州市低空经济促进条例',
            '低空经济发展司', '低空经济及其核心产业统计分类',
        ]

        policy_mentions = Counter()

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            for policy in policy_keywords:
                if policy in full_text:
                    policy_mentions[policy] += 1

        for policy, count in policy_mentions.items():
            self._add_node(
                f'policy:{policy}', 'policy', policy,
                mention_count=count
            )

        logger.info(f"  政策节点: {len(policy_mentions)}")

    def _build_tech_nodes(self, records):
        """构建技术领域节点"""
        tech_keywords = [
            'eVTOL', '电动垂直起降', '无人驾驶航空器', '通用航空',
            '低空空域', '适航认证', '飞行控制', '北斗导航',
            '电池技术', '复合材料', '空中交通管理', '物流配送',
            '应急救援', '农业植保', '电力巡检', '城市空中交通',
            'UAM', '感知避障', '5G', '集群飞行',
        ]

        tech_mentions = Counter()

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            for tech in tech_keywords:
                if tech in full_text:
                    tech_mentions[tech] += 1

        for tech, count in tech_mentions.items():
            self._add_node(
                f'tech:{tech}', 'tech', tech,
                mention_count=count
            )

        logger.info(f"  技术节点: {len(tech_mentions)}")

    def _build_company_person_edges(self, records):
        """企业-人物关系（提及）"""
        edge_count = 0

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            entities = record.get('entities', {})

            # 找出记录中的企业
            companies_in_record = set()
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            # 找出记录中的人物
            persons_in_record = set()
            for person_entity in entities.get('persons', []):
                person_name = person_entity['text']
                if person_name not in COMPANY_ALIASES and len(person_name) >= 2 and person_name not in ('org', 'tan', '揭牌'):
                    persons_in_record.add(person_name)

            # 建立企业-人物边
            for company in companies_in_record:
                for person in persons_in_record:
                    self._add_edge(
                        f'company:{company}', f'person:{person}',
                        'mentions_person',
                        records=[record.get('title', '')[:60]],
                        date=record.get('publish_date', '')
                    )
                    edge_count += 1

        logger.info(f"  企业-人物边: {edge_count}")

    def _build_company_location_edges(self, records):
        """企业-地点关系"""
        edge_count = 0

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"
            entities = record.get('entities', {})

            companies_in_record = set()
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            locations_in_record = set()
            for loc_entity in entities.get('locations', []):
                locations_in_record.add(loc_entity['text'])

            for company in companies_in_record:
                for location in locations_in_record:
                    self._add_edge(
                        f'company:{company}', f'location:{location}',
                        'located_in',
                        weight=1
                    )
                    edge_count += 1

        logger.info(f"  企业-地点边: {edge_count}")

    def _build_company_company_edges(self, records):
        """企业-企业合作关系"""
        edge_count = 0

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            # 合作关键词
            is_cooperation = any(kw in full_text for kw in ['合作', '签约', '战略', '协议', '携手', '联盟', '伙伴'])

            companies_in_record = set()
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            if is_cooperation and len(companies_in_record) >= 2:
                companies_list = sorted(companies_in_record)
                for i in range(len(companies_list)):
                    for j in range(i + 1, len(companies_list)):
                        self._add_edge(
                            f'company:{companies_list[i]}',
                            f'company:{companies_list[j]}',
                            'cooperates_with',
                            records=[record.get('title', '')[:60]],
                            date=record.get('publish_date', '')
                        )
                        edge_count += 1

        logger.info(f"  企业-企业合作边: {edge_count}")

    def _build_company_policy_edges(self, records):
        """企业-政策关系"""
        edge_count = 0
        policy_keywords = [
            '无人驾驶航空器飞行管理暂行条例', 'CCAR-92', '通用机场管理规定',
            '低空经济标准体系建设指南', '通用航空装备创新应用实施方案',
            '深圳经济特区低空经济产业促进条例', '苏州市低空经济促进条例',
            '低空经济发展司', '低空经济及其核心产业统计分类',
        ]

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            companies_in_record = set()
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            policies_in_record = set()
            for policy in policy_keywords:
                if policy in full_text:
                    policies_in_record.add(policy)

            for company in companies_in_record:
                for policy in policies_in_record:
                    self._add_edge(
                        f'company:{company}', f'policy:{policy}',
                        'affected_by',
                        date=record.get('publish_date', '')
                    )
                    edge_count += 1

        logger.info(f"  企业-政策边: {edge_count}")

    def _build_company_tech_edges(self, records):
        """企业-技术领域关系"""
        edge_count = 0
        tech_keywords = [
            'eVTOL', '电动垂直起降', '无人驾驶航空器', '通用航空',
            '低空空域', '适航认证', '飞行控制', '北斗导航',
            '电池技术', '复合材料', '空中交通管理', '物流配送',
            '应急救援', '农业植保', '电力巡检', '城市空中交通',
            'UAM', '感知避障', '5G', '集群飞行',
        ]

        for record in records:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            companies_in_record = set()
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    companies_in_record.add(canonical)

            techs_in_record = set()
            for tech in tech_keywords:
                if tech in full_text:
                    techs_in_record.add(tech)

            for company in companies_in_record:
                for tech in techs_in_record:
                    self._add_edge(
                        f'company:{company}', f'tech:{tech}',
                        'operates_in',
                        weight=1
                    )
                    edge_count += 1

        logger.info(f"  企业-技术边: {edge_count}")

    def _save_graph(self):
        """保存知识图谱"""
        graph = {
            'metadata': {
                'generated_at': datetime.now(BJT).isoformat(),
                'total_nodes': len(self.nodes),
                'total_edges': len(self.edges),
                'node_types': dict(Counter(n['type'] for n in self.nodes.values())),
                'edge_types': dict(Counter(e['type'] for e in self.edges)),
            },
            'nodes': list(self.nodes.values()),
            'edges': self.edges,
        }

        # 完整图谱
        output_file = self.output_dir / 'knowledge_graph.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(graph, f, ensure_ascii=False, indent=2)
        logger.info(f"知识图谱 → {output_file}")

        # 节点摘要
        nodes_summary = {
            'companies': sorted([
                {'name': n['name'], 'category': n['properties'].get('category', ''),
                 'mentions': n['properties'].get('mention_count', 0)}
                for n in self.nodes.values() if n['type'] == 'company'
            ], key=lambda x: x['mentions'], reverse=True),
            'persons': sorted([
                {'name': n['name'], 'mentions': n['properties'].get('mention_count', 0)}
                for n in self.nodes.values() if n['type'] == 'person'
            ], key=lambda x: x['mentions'], reverse=True),
            'locations': sorted([
                {'name': n['name'], 'mentions': n['properties'].get('mention_count', 0)}
                for n in self.nodes.values() if n['type'] == 'location'
            ], key=lambda x: x['mentions'], reverse=True),
            'policies': sorted([
                {'name': n['name'], 'mentions': n['properties'].get('mention_count', 0)}
                for n in self.nodes.values() if n['type'] == 'policy'
            ], key=lambda x: x['mentions'], reverse=True),
            'techs': sorted([
                {'name': n['name'], 'mentions': n['properties'].get('mention_count', 0)}
                for n in self.nodes.values() if n['type'] == 'tech'
            ], key=lambda x: x['mentions'], reverse=True),
        }

        summary_file = self.output_dir / 'graph_summary.json'
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(nodes_summary, f, ensure_ascii=False, indent=2)
        logger.info(f"图谱摘要 → {summary_file}")

    def _get_summary(self):
        """获取摘要"""
        return {
            'total_nodes': len(self.nodes),
            'total_edges': len(self.edges),
            'node_types': dict(Counter(n['type'] for n in self.nodes.values())),
            'edge_types': dict(Counter(e['type'] for e in self.edges)),
        }


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / 'scripts'))
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    builder = KnowledgeGraphBuilder()
    builder.build()
