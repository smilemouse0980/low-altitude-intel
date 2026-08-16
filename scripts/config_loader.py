#!/usr/bin/env python3
"""
低空经济情报服务 — 配置加载工具
"""

import os
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def load_config(config_name='sources'):
    """加载配置文件"""
    config_path = PROJECT_ROOT / 'config' / f'{config_name}.yaml'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_gov_sources():
    """获取政府数据源列表"""
    config = load_config('sources')
    return config.get('gov_sources', [])


def get_association_sources():
    """获取行业协会数据源列表"""
    config = load_config('sources')
    return config.get('association_sources', [])


def get_industry_dict():
    """获取行业词典"""
    return load_config('industry_dict')


def get_collection_config():
    """获取采集配置"""
    config = load_config('sources')
    return config.get('collection', {})


def get_ner_config():
    """获取 NER 配置"""
    config = load_config('sources')
    return config.get('ner', {})


if __name__ == '__main__':
    # 测试配置加载
    print("数据源配置:")
    sources = load_config('sources')
    print(f"  政府源: {len(sources.get('gov_sources', []))} 个")
    print(f"  协会源: {len(sources.get('association_sources', []))} 个")

    print("\n行业词典:")
    dicts = load_config('industry_dict')
    print(f"  企业名: {len(dicts.get('companies', []))} 个")
    print(f"  职务名: {len(dicts.get('titles', []))} 个")
    print(f"  会议类型: {len(dicts.get('meeting_types', []))} 个")
    print(f"  技术领域: {len(dicts.get('tech_domains', []))} 个")
    print(f"  政策关键词: {len(dicts.get('policy_keywords', []))} 个")
