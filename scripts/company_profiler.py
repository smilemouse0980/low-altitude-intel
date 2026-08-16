#!/usr/bin/env python3
"""
低空经济情报服务 — 企业画像引擎
从情报记录中提取企业相关信息，构建结构化企业档案
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

# 企业别名映射（统一名称）
COMPANY_ALIASES = {
    "大疆": "大疆创新",
    "DJI": "大疆创新",
    "亿航": "亿航智能",
    "EHang": "亿航智能",
    "亿航智": "亿航智能",
    "峰飞": "峰飞航空",
    "上海峰飞": "峰飞航空",
    "AutoFlight": "峰飞航空",
    "沃飞": "沃飞长空",
    "小鹏汇天": "小鹏汇天",
    "小鹏飞行汽车": "小鹏汇天",
    "极飞": "极飞科技",
    "XAG": "极飞科技",
    "丰翼科技": "顺丰丰翼",
    "迅蚁": "迅蚁网络",
    "道通": "道通智能",
    "Autel": "道通智能",
    "纵横": "纵横股份",
    "普宙": "普宙科技",
    "云圣": "云圣智能",
    "腾盾": "腾盾科技",
    "海特": "海特高新",
    "航亚": "航亚科技",
    "炼石": "炼石航空",
    "宗申": "宗申动力",
    "航发": "航发动力",
    "成飞": "中航成飞",
    "沈飞": "中航沈飞",
    "西飞": "中航西飞",
    "洪都": "中航洪都",
    "昌飞": "中直股份昌飞",
    "哈飞": "中直股份哈飞",
    "海直": "中信海直",
    "商飞": "中国商飞",
    "沃兰特": "沃兰特",
    "Volant": "沃兰特",
}

# 企业分类
COMPANY_CATEGORIES = {
    "eVTOL整机": ["亿航智能", "沃兰特", "沃飞长空", "小鹏汇天", "峰飞航空", "时的科技", "磐拓航空", "御风未来", "跨界航空", "华羽先翔"],
    "无人机整机": ["大疆创新", "道通智能", "纵横股份", "普宙科技", "腾盾科技", "航天彩虹", "双捷科技"],
    "物流无人机": ["顺丰丰翼", "美团无人机", "京东无人机", "迅蚁网络", "送吧航空"],
    "农业无人机": ["极飞科技"],
    "核心零部件": ["航发动力", "航亚科技", "宗申动力", "赛微电子"],
    "航空材料": ["光威复材", "中航高科", "光启技术", "西部超导", "宝钛", "西部材料", "钢研高纳", "抚顺特钢", "炼石航空", "应流股份"],
    "导航通信": ["北斗星通", "华力创通", "中海达", "合众思壮", "司南导航", "海格通信", "华测导航"],
    "通航运营": ["中信海直", "中航通飞"],
    "军工航空": ["中航成飞", "中航沈飞", "中航西飞", "中航洪都", "中直股份昌飞", "中直股份哈飞", "中国商飞", "航天时代", "航天电子"],
    "雷达电子": ["四创电子", "国睿科技", "雷科防务", "国博电子", "雷电微力", "臻镭科技", "铖昌科技", "振芯科技", "四川九洲", "莱斯信息"],
    "基础设施": ["深城交", "苏交科", "中化岩土", "盛视科技"],
    "投资标的": ["通用航空ETF易方达"],
}


class CompanyProfiler:
    """企业画像引擎"""

    def __init__(self):
        self.data_file = PROJECT_ROOT / 'processed' / 'intel_records.jsonl'
        self.output_dir = PROJECT_ROOT / 'processed' / 'company_profiles'
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def build_all_profiles(self):
        """构建所有企业画像"""
        logger.info("=" * 60)
        logger.info("开始构建企业画像")
        logger.info("=" * 60)

        records = self._load_records()
        company_mentions = self._extract_company_mentions(records)

        profiles = []
        for company_name, mentions in company_mentions.items():
            if len(mentions) < 2:
                continue
            profile = self._build_profile(company_name, mentions, records)
            if profile:
                profiles.append(profile)
                self._save_profile(profile)

        # 生成汇总索引
        self._save_index(profiles)

        logger.info(f"企业画像构建完成: {len(profiles)} 家企业")
        return profiles

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

    def _extract_company_mentions(self, records):
        """从记录中提取企业提及"""
        mentions = defaultdict(list)

        for record in records:
            title = record.get('title', '')
            content = record.get('content', '')
            full_text = f"{title} {content}"

            # 检查行业词典中的企业
            for alias, canonical in COMPANY_ALIASES.items():
                if alias in full_text:
                    mentions[canonical].append(record)

            # 从实体中提取
            entities = record.get('entities', {})
            for org_entity in entities.get('orgs', []):
                org_name = org_entity['text']
                canonical = COMPANY_ALIASES.get(org_name, org_name)
                # 只保留在行业词典中的企业
                if canonical in set(COMPANY_ALIASES.values()):
                    if record not in mentions[canonical]:
                        mentions[canonical].append(record)

        return mentions

    def _build_profile(self, company_name, mentions, all_records):
        """构建单个企业画像"""
        # 基本信息
        category = self._get_category(company_name)

        # 关联人物
        persons = Counter()
        for record in mentions:
            entities = record.get('entities', {})
            for person_entity in entities.get('persons', []):
                person_name = person_entity['text']
                # 过滤掉明显是公司名的误判
                if person_name not in COMPANY_ALIASES and len(person_name) >= 2:
                    persons[person_name] += 1

        # 关联地点
        locations = Counter()
        for record in mentions:
            entities = record.get('entities', {})
            for loc_entity in entities.get('locations', []):
                loc_name = loc_entity['text']
                if loc_name not in ('中国', '美国'):
                    locations[loc_name] += 1

        # 时间线
        timeline = []
        for record in sorted(mentions, key=lambda r: r.get('publish_date', ''), reverse=True):
            timeline.append({
                'date': record.get('publish_date', ''),
                'title': record.get('title', ''),
                'source': record.get('source_site', ''),
                'url': record.get('url', ''),
                'content_snippet': record.get('content', '')[:150],
            })

        # 关键事件分类
        events = self._classify_events(mentions)

        # 合作伙伴
        partners = self._extract_partners(company_name, mentions, all_records)

        profile = {
            'company_name': company_name,
            'category': category,
            'mention_count': len(mentions),
            'first_seen': min((r.get('publish_date', '') for r in mentions if r.get('publish_date')), default=''),
            'last_seen': max((r.get('publish_date', '') for r in mentions if r.get('publish_date')), default=''),
            'key_persons': [{'name': p, 'mentions': c} for p, c in persons.most_common(10)],
            'locations': [{'name': l, 'mentions': c} for l, c in locations.most_common(10)],
            'partners': partners[:10],
            'events': events,
            'timeline': timeline[:20],
            'generated_at': datetime.now(BJT).isoformat(),
        }

        return profile

    def _get_category(self, company_name):
        """获取企业分类"""
        for category, companies in COMPANY_CATEGORIES.items():
            if company_name in companies:
                return category
        return '其他'

    def _classify_events(self, mentions):
        """关键事件分类"""
        events = {
            'product_launch': [],
            'financing': [],
            'cooperation': [],
            'policy_related': [],
            'certification': [],
            'market_expansion': [],
        }

        for record in mentions:
            title = record.get('title', '')
            content = record.get('content', '')
            text = f"{title} {content}"

            event_item = {
                'date': record.get('publish_date', ''),
                'title': title,
                'source': record.get('source_site', ''),
            }

            if any(kw in text for kw in ['发布', '首飞', '下线', '量产', '交付', '首台', '推出']):
                events['product_launch'].append(event_item)
            if any(kw in text for kw in ['融资', '投资', '轮', '估值', '上市', 'IPO']):
                events['financing'].append(event_item)
            if any(kw in text for kw in ['合作', '签约', '战略', '协议', '携手', '联盟']):
                events['cooperation'].append(event_item)
            if any(kw in text for kw in ['政策', '条例', '标准', '规划', '适航', '法规']):
                events['policy_related'].append(event_item)
            if any(kw in text for kw in ['适航', '认证', '审定', '许可证', '资质']):
                events['certification'].append(event_item)
            if any(kw in text for kw in ['出海', '国际', '海外', '出口', '印尼', '东南亚', '欧洲', '北美']):
                events['market_expansion'].append(event_item)

        return events

    def _extract_partners(self, company_name, mentions, all_records):
        """提取合作伙伴"""
        partners = Counter()

        for record in mentions:
            full_text = f"{record.get('title', '')} {record.get('content', '')}"

            # 检查其他企业是否在同一文章中被提及
            for alias, canonical in COMPANY_ALIASES.items():
                if canonical == company_name:
                    continue
                if alias in full_text:
                    partners[canonical] += 1

        return [{'name': p, 'co_occurrences': c} for p, c in partners.most_common(10)]

    def _save_profile(self, profile):
        """保存单个企业画像"""
        filename = profile['company_name'].replace('/', '_')
        output_file = self.output_dir / f'{filename}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        logger.info(f"  企业画像: {profile['company_name']} ({profile['mention_count']} 次提及) → {output_file.name}")

    def _save_index(self, profiles):
        """保存汇总索引"""
        index = {
            'generated_at': datetime.now(BJT).isoformat(),
            'total_companies': len(profiles),
            'companies': [
                {
                    'name': p['company_name'],
                    'category': p['category'],
                    'mention_count': p['mention_count'],
                    'first_seen': p['first_seen'],
                    'last_seen': p['last_seen'],
                    'key_persons': [person['name'] for person in p['key_persons'][:3]],
                    'event_count': sum(len(events) for events in p['events'].values()),
                }
                for p in sorted(profiles, key=lambda x: x['mention_count'], reverse=True)
            ],
        }

        index_file = self.output_dir / '_index.json'
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

        logger.info(f"企业画像索引 → {index_file}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    profiler = CompanyProfiler()
    profiler.build_all_profiles()
