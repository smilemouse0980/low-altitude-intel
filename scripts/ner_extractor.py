#!/usr/bin/env python3
"""
低空经济情报服务 — NER 实体提取引擎
使用 HanLP + spaCy 双引擎交叉验证提取人名、机构名、地名等实体
"""

import os
import sys
import json
import logging
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
logger = logging.getLogger(__name__)


class NERExtractor:
    """NER 双引擎实体提取器"""

    # 实体类型映射
    LABEL_MAP = {
        # spaCy 标签 → 统一标签
        'PERSON': 'person',
        'ORG': 'org',
        'GPE': 'location',
        'DATE': 'date',
        'LOC': 'location',
        # HanLP 标签 → 统一标签
        'PER': 'person',
        'NR': 'person',
        'ORG': 'org',
        'NT': 'org',
        'GPE': 'location',
        'NS': 'location',
        'DATE': 'date',
        'TIM': 'date',
    }

    def __init__(self, dict_path=None):
        """
        初始化 NER 引擎
        Args:
            dict_path: 行业词典路径 (YAML)
        """
        self.hanlp = None
        self.spacy_nlp = None
        self.industry_dict = {}

        # 加载行业词典
        if dict_path is None:
            dict_path = PROJECT_ROOT / 'config' / 'industry_dict.yaml'
        self._load_industry_dict(dict_path)

        # 初始化 HanLP
        self._init_hanlp()

        # 初始化 spaCy
        self._init_spacy()

    def _load_industry_dict(self, dict_path):
        """加载行业词典"""
        try:
            import yaml
            if os.path.exists(dict_path):
                with open(dict_path, 'r', encoding='utf-8') as f:
                    self.industry_dict = yaml.safe_load(f)
                companies = self.industry_dict.get('companies', [])
                titles = self.industry_dict.get('titles', [])
                blocklist = self.industry_dict.get('ner_blocklist_persons', [])
                policy_entities = self.industry_dict.get('policy_entities', [])
                logger.info(f"行业词典加载: {len(companies)} 企业, {len(titles)} 职务, {len(blocklist)} 消歧黑名单, {len(policy_entities)} 政策实体")
        except Exception as e:
            logger.warning(f"行业词典加载失败: {e}")

    def _init_hanlp(self):
        """初始化 HanLP"""
        try:
            import hanlp
            # 使用 PTB 词法分析 + NER 模型
            self.hanlp = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_BASE_ZH)
            logger.info("HanLP 加载成功")
        except ImportError:
            logger.warning("HanLP 未安装，请运行: pip install hanlp")
        except Exception as e:
            logger.warning(f"HanLP 初始化失败: {e}")

    def _init_spacy(self):
        """初始化 spaCy"""
        try:
            import spacy
            self.spacy_nlp = spacy.load('zh_core_web_sm')
            logger.info("spaCy 中文模型加载成功")
        except ImportError:
            logger.warning("spaCy 未安装，请运行: pip install spacy && python -m spacy download zh_core_web_sm")
        except OSError:
            logger.warning("spaCy 中文模型未下载，请运行: python -m spacy download zh_core_web_sm")
        except Exception as e:
            logger.warning(f"spaCy 初始化失败: {e}")

    def extract(self, text):
        """
        从文本中提取实体
        Args:
            text: 输入文本
        Returns:
            dict: {
                'persons': [{'text', 'start', 'end', 'confidence', 'engine'}],
                'orgs': [...],
                'locations': [...],
                'dates': [...],
                'relations': [{'person', 'title', 'org'}]
            }
        """
        if not text or len(text.strip()) < 10:
            return {'persons': [], 'orgs': [], 'locations': [], 'dates': [], 'policies': [], 'relations': []}

        hanlp_results = self._extract_with_hanlp(text) if self.hanlp else {}
        spacy_results = self._extract_with_spacy(text) if self.spacy_nlp else {}

        # 双引擎交叉验证
        merged = self._merge_results(hanlp_results, spacy_results, text)

        # NER 消歧：过滤误识别的人物实体
        merged = self._filter_false_persons(merged)

        # 基于行业词典增强
        enhanced = self._enhance_with_dict(merged, text)

        # 提取政策实体
        enhanced = self._extract_policy_entities(enhanced, text)

        # 提取人名-企业-职务关系
        relations = self._extract_relations(text, enhanced)

        enhanced['relations'] = relations
        return enhanced

    def _extract_with_hanlp(self, text):
        """使用 HanLP 提取实体"""
        results = {'persons': [], 'orgs': [], 'locations': [], 'dates': []}

        try:
            doc = self.hanlp(text)

            # HanLP 返回多任务结果
            ner_result = doc.get('ner/msra', doc.get('ner', None))

            if ner_result is not None:
                for entity in ner_result:
                    if isinstance(entity, (list, tuple)) and len(entity) >= 2:
                        entity_text = entity[0] if isinstance(entity[0], str) else str(entity[0])
                        entity_label = entity[1] if len(entity) > 1 else ''

                        unified_label = self.LABEL_MAP.get(entity_label, '')

                        entity_item = {
                            'text': entity_text,
                            'label': unified_label,
                            'engine': 'hanlp',
                            'confidence': 'medium'
                        }

                        if unified_label == 'person':
                            results['persons'].append(entity_item)
                        elif unified_label == 'org':
                            results['orgs'].append(entity_item)
                        elif unified_label == 'location':
                            results['locations'].append(entity_item)
                        elif unified_label == 'date':
                            results['dates'].append(entity_item)

        except Exception as e:
            logger.warning(f"HanLP 提取失败: {e}")

        return results

    def _extract_with_spacy(self, text):
        """使用 spaCy 提取实体"""
        results = {'persons': [], 'orgs': [], 'locations': [], 'dates': []}

        try:
            doc = self.spacy_nlp(text)

            for ent in doc.ents:
                unified_label = self.LABEL_MAP.get(ent.label_, '')

                entity_item = {
                    'text': ent.text,
                    'label': unified_label,
                    'start': ent.start_char,
                    'end': ent.end_char,
                    'engine': 'spacy',
                    'confidence': 'medium'
                }

                if unified_label == 'person':
                    results['persons'].append(entity_item)
                elif unified_label == 'org':
                    results['orgs'].append(entity_item)
                elif unified_label == 'location':
                    results['locations'].append(entity_item)
                elif unified_label == 'date':
                    results['dates'].append(entity_item)

        except Exception as e:
            logger.warning(f"spaCy 提取失败: {e}")

        return results

    def _merge_results(self, hanlp_results, spacy_results, text):
        """
        双引擎交叉验证合并
        - 两引擎都识别 → confidence=high
        - 仅一个引擎识别 → confidence=low
        """
        merged = {'persons': [], 'orgs': [], 'locations': [], 'dates': []}

        for entity_type in ['persons', 'orgs', 'locations', 'dates']:
            hanlp_entities = hanlp_results.get(entity_type, [])
            spacy_entities = spacy_results.get(entity_type, [])

            # 提取文本用于比较
            hanlp_texts = {e['text'] for e in hanlp_entities}
            spacy_texts = {e['text'] for e in spacy_entities}

            # 高置信：两引擎都识别
            common_texts = hanlp_texts & spacy_texts
            for text_val in common_texts:
                # 取spaCy的偏移量（更准确）
                spacy_ent = next((e for e in spacy_entities if e['text'] == text_val), {})
                merged[entity_type].append({
                    'text': text_val,
                    'label': hanlp_entities[0]['label'] if hanlp_entities else 'unknown',
                    'start': spacy_ent.get('start', -1),
                    'end': spacy_ent.get('end', -1),
                    'confidence': 'high',
                    'engine': 'hanlp+spacy'
                })

            # 低置信：仅HanLP识别
            for ent in hanlp_entities:
                if ent['text'] not in common_texts:
                    ent['confidence'] = 'low'
                    merged[entity_type].append(ent)

            # 低置信：仅spaCy识别
            for ent in spacy_entities:
                if ent['text'] not in common_texts:
                    ent['confidence'] = 'low'
                    merged[entity_type].append(ent)

        return merged

    def _enhance_with_dict(self, results, text):
        """使用行业词典增强结果"""
        companies = set(self.industry_dict.get('companies', []))
        titles = set(self.industry_dict.get('titles', []))

        # 检查文本中是否包含词典中的企业名
        existing_orgs = {e['text'] for e in results['orgs']}
        for company in companies:
            if company in text and company not in existing_orgs:
                # 找到位置
                start = text.find(company)
                results['orgs'].append({
                    'text': company,
                    'label': 'org',
                    'start': start,
                    'end': start + len(company),
                    'confidence': 'dict',
                    'engine': 'industry_dict'
                })
                existing_orgs.add(company)

        return results

    def _filter_false_persons(self, results):
        """NER 消歧：过滤误识别为人物的实体"""
        import re as _re

        blocklist = set(self.industry_dict.get('ner_blocklist_persons', []))
        companies = set(self.industry_dict.get('companies', []))
        locations = {e['text'] for e in results.get('locations', [])}

        # 非人物术语黑名单（技术词汇、行业术语等）
        non_person_terms = {
            '倾转旋翼', '航空展', '兽门槛', '高密度', '金钥匙', '阿森特',
            '凯瑞鸥', '飞长', '华羽', '中长', '空AE', '瑞鸥',
            '摩根士丹利', '洪泰智造', '南昌智造', '智造',
            'Sky Group', 'Tech', 'UAM', 'VIP',
        }

        # 过滤含这些子串的实体
        bad_substrings = ['旋翼', '航空展', '门槛', '密度', '钥匙', '型号']

        filtered_persons = []
        for person in results.get('persons', []):
            name = person['text']

            # 规则1: 在黑名单中 → 过滤
            if name in blocklist:
                continue

            # 规则2: 在企业词典中 → 过滤
            if name in companies:
                continue

            # 规则3: 在地名中 → 过滤
            if name in locations:
                continue

            # 规则4: 在非人物术语集合中 → 过滤
            if name in non_person_terms:
                continue

            # 规则5: 包含括号、方括号等 → 过滤
            if any(c in name for c in '[]()【】{}<>'):
                continue

            # 规则6: 包含 emoji 或特殊符号 → 过滤
            if any(ord(c) > 0x2000 and c not in '—…' for c in name):
                continue

            # 规则7: 包含数字 → 过滤
            if any(c.isdigit() for c in name):
                continue

            # 规则8: 包含不良子串 → 过滤
            if any(sub in name for sub in bad_substrings):
                continue

            # 规则9: 纯英文大写缩写（如 UAM, VIP, Tech）→ 过滤
            if name.isascii() and len(name) <= 5 and name.isupper():
                continue

            # 规则10: 以 L 开头后跟非ASCII字符 → 过滤（如 L哈萨克斯坦）
            if len(name) > 1 and name[0] == 'L' and any(ord(c) > 127 for c in name[1:]):
                continue

            # 规则11: 包含"何为"等疑问词 → 过滤
            if '何为' in name or '什么是' in name:
                continue

            # 规则12: 中文姓名长度检查（2-4个汉字）
            chinese_chars = [c for c in name if '\u4e00' <= c <= '\u9fff']
            if len(chinese_chars) > 0:
                if len(chinese_chars) < 2 or len(chinese_chars) > 4:
                    continue
                # 混合中英文且长度>6 → 过滤
                if len(name) > 6 and not name.isascii():
                    continue
                # 纯中文但包含常见非姓氏开头 → 可疑，但不强制过滤

            # 规则13: 纯英文姓名长度检查（至少3个字符）
            if name.isascii() and len(name) < 3:
                continue

            # 规则14: 纯英文但首字母未大写 → 可能不是人名
            if name.isascii() and len(name) > 0 and not name[0].isupper():
                continue

            filtered_persons.append(person)

        results['persons'] = filtered_persons
        return results

    def _extract_policy_entities(self, results, text):
        """提取政策法规实体"""
        policy_keywords = self.industry_dict.get('policy_entities', [])
        existing = {e['text'] for e in results.get('policies', [])}

        policies = []
        for kw in policy_keywords:
            if kw in text and kw not in existing:
                start = text.find(kw)
                policies.append({
                    'text': kw,
                    'label': 'policy',
                    'start': start,
                    'end': start + len(kw),
                    'confidence': 'dict',
                    'engine': 'industry_dict'
                })
                existing.add(kw)

        results['policies'] = policies
        return results

    def _extract_relations(self, text, entities):
        """
        提取人名-职务-企业三元组
        例如："亿航智能董事长胡华智" → {"person": "胡华智", "title": "董事长", "org": "亿航智能"}
        """
        relations = []
        persons = entities.get('persons', [])
        orgs = {e['text'] for e in entities.get('orgs', [])}
        titles = self.industry_dict.get('titles', [])

        import re

        for person in persons:
            person_name = person['text']
            person_start = person.get('start', -1)

            if person_start < 0:
                continue

            # 在人名附近查找职务和企业名
            window_start = max(0, person_start - 30)
            window_end = min(len(text), person_start + len(person_name) + 30)
            window = text[window_start:window_end]

            # 查找职务
            matched_title = ''
            for title in titles:
                if title in window:
                    matched_title = title
                    break

            # 查找企业名
            matched_org = ''
            for org in orgs:
                if org in window:
                    matched_org = org
                    break

            if matched_title or matched_org:
                relations.append({
                    'person': person_name,
                    'title': matched_title,
                    'org': matched_org,
                    'context': window.strip()
                })

        return relations


def main():
    """测试 NER 提取器"""
    import argparse
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    parser = argparse.ArgumentParser(description='低空经济 NER 实体提取器')
    parser.add_argument('--text', type=str, help='待提取的文本')
    parser.add_argument('--file', type=str, help='待提取的文件路径')
    parser.add_argument('--output', type=str, help='输出文件路径')

    args = parser.parse_args()

    extractor = NERExtractor()

    # 获取文本
    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    elif args.text:
        text = args.text
    else:
        # 默认测试文本
        text = """
        2026年8月15日，亿航智能董事长胡华智在中国低空经济发展大会上发表演讲，
        介绍了EH216-S型无人驾驶航空器的最新适航认证进展。
        小鹏汇天总裁赵德力也出席了会议，并与大疆创新副总裁就低空经济产业发展进行了交流。
        会议由中国无人机产业创新联盟主办，在深圳市举办。
        """

    print(f"\n输入文本:\n{text.strip()}\n")
    print("提取中...\n")

    result = extractor.extract(text)

    print("提取结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
