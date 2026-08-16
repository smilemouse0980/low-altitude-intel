#!/usr/bin/env python3
"""
低空经济情报服务 — 采集器主框架
负责从政府网站和行业协会网站采集低空经济相关信息
"""

import os
import sys
import json
import time
import hashlib
import logging
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(PROJECT_ROOT / 'logs' / 'collector.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# 时区：北京时间
BJT = timezone(timedelta(hours=8))


class LowAltitudeCollector:
    """低空经济情报采集器"""

    def __init__(self, config_path=None):
        """初始化采集器"""
        import yaml
        if config_path is None:
            config_path = PROJECT_ROOT / 'config' / 'sources.yaml'

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        self.raw_dir = PROJECT_ROOT / 'raw'
        self.gov_dir = self.raw_dir / 'gov'
        self.assoc_dir = self.raw_dir / 'associations'

        # 确保目录存在
        self.gov_dir.mkdir(parents=True, exist_ok=True)
        self.assoc_dir.mkdir(parents=True, exist_ok=True)

        # 加载采集状态
        self.state_file = self.raw_dir / 'last_collect.json'
        self.state = self._load_state()

        # 请求配置
        col_cfg = self.config.get('collection', {})
        self.request_interval = col_cfg.get('request_interval', 30)
        self.max_retries = col_cfg.get('max_retries', 3)
        self.retry_interval = col_cfg.get('retry_interval', 30)
        self.timeout = col_cfg.get('timeout', 30)
        self.user_agent = col_cfg.get('user_agent', 'Mozilla/5.0')

        logger.info(f"采集器初始化完成，共 {len(self.config.get('gov_sources', []))} 个政府源，"
                     f"{len(self.config.get('association_sources', []))} 个协会源")

    def _load_state(self):
        """加载上次采集状态"""
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'last_collect_time': None, 'collected_urls': []}

    def _save_state(self):
        """保存采集状态"""
        self.state['last_collect_time'] = datetime.now(BJT).isoformat()
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)

    def _url_hash(self, url):
        """计算URL的MD5哈希"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()

    def _is_collected(self, url):
        """检查URL是否已采集"""
        url_hash = self._url_hash(url)
        return url_hash in [self._url_hash(u) for u in self.state.get('collected_urls', [])]

    def _mark_collected(self, url):
        """标记URL为已采集"""
        if 'collected_urls' not in self.state:
            self.state['collected_urls'] = []
        self.state['collected_urls'].append(url)

    def fetch_page(self, url):
        """
        获取网页内容
        返回: (success: bool, content: str or None, error: str or None)
        """
        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(f"  尝试 {attempt}/{self.max_retries}: {url}")
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    verify=False
                )
                response.encoding = response.apparent_encoding or 'utf-8'

                if response.status_code == 200:
                    logger.info(f"  ✓ 成功获取 ({len(response.text)} 字符)")
                    return True, response.text, None
                else:
                    logger.warning(f"  ✗ HTTP {response.status_code}")
                    if attempt < self.max_retries:
                        time.sleep(self.retry_interval)

            except requests.RequestException as e:
                logger.warning(f"  ✗ 请求异常: {e}")
                if attempt < self.max_retries:
                    time.sleep(self.retry_interval)

        return False, None, f"获取失败，重试 {self.max_retries} 次后仍无法访问"

    def save_raw_article(self, url, title, content, date, publisher, source_site, source_type='gov'):
        """
        保存采集的原始文章
        """
        # 生成文件名
        url_hash = self._url_hash(url)[:12]
        date_str = date if date else datetime.now(BJT).strftime('%Y-%m-%d')
        safe_title = "".join(c for c in title[:30] if c.isalnum() or c in ('_', '-', ' ')).strip()
        filename = f"{date_str}_{safe_title}_{url_hash}.json"

        # 选择保存目录
        save_dir = self.gov_dir if source_type == 'gov' else self.assoc_dir
        filepath = save_dir / filename

        # 构建记录
        record = {
            'doc_id': url_hash,
            'url': url,
            'title': title,
            'content': content,
            'publish_date': date,
            'publisher': publisher,
            'source_site': source_site,
            'source_type': source_type,
            'collected_at': datetime.now(BJT).isoformat(),
            'quality_flag': 'pending'
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        logger.info(f"  ✓ 已保存: {filename}")
        self._mark_collected(url)
        return filepath

    def collect_gov_sources(self, max_per_source=20):
        """
        采集政府数据源
        """
        logger.info("=" * 60)
        logger.info("开始采集政府数据源")
        logger.info("=" * 60)

        gov_sources = self.config.get('gov_sources', [])
        total_collected = 0

        for source in gov_sources:
            name = source['name']
            url = source['url']
            logger.info(f"\n--- 采集: {name} ({url}) ---")

            # TODO: 实现具体的页面列表抓取逻辑
            # 当前为框架，需要针对每个网站定制抓取规则
            logger.info(f"  [框架] 待实现: 需要针对 {name} 网站定制抓取规则")

            time.sleep(self.request_interval)

        logger.info(f"\n政府数据源采集完成，共采集 {total_collected} 篇")
        return total_collected

    def collect_association_sources(self, max_per_source=15):
        """
        采集行业协会数据源
        """
        logger.info("=" * 60)
        logger.info("开始采集行业协会数据源")
        logger.info("=" * 60)

        assoc_sources = self.config.get('association_sources', [])
        total_collected = 0

        for source in assoc_sources:
            name = source['name']
            url = source['url']
            logger.info(f"\n--- 采集: {name} ({url}) ---")

            # TODO: 实现具体的页面列表抓取逻辑
            logger.info(f"  [框架] 待实现: 需要针对 {name} 网站定制抓取规则")

            time.sleep(self.request_interval)

        logger.info(f"\n行业协会数据源采集完成，共采集 {total_collected} 篇")
        return total_collected

    def run(self, source_type='all'):
        """
        运行采集器
        Args:
            source_type: 'gov' | 'association' | 'all'
        """
        logger.info("=" * 60)
        logger.info(f"低空经济情报采集器启动 — 模式: {source_type}")
        logger.info(f"上次采集时间: {self.state.get('last_collect_time', '首次采集')}")
        logger.info("=" * 60)

        total = 0
        if source_type in ('gov', 'all'):
            total += self.collect_gov_sources()

        if source_type in ('association', 'all'):
            total += self.collect_association_sources()

        self._save_state()
        logger.info(f"\n采集完成！总计采集 {total} 篇文档")
        return total


def main():
    """主入口"""
    import argparse
    parser = argparse.ArgumentParser(description='低空经济情报采集器')
    parser.add_argument('--source', choices=['gov', 'association', 'all'],
                        default='all', help='采集源类型')
    parser.add_argument('--max-per-source', type=int, default=20,
                        help='每个源最大采集数量')

    args = parser.parse_args()

    collector = LowAltitudeCollector()
    collector.run(source_type=args.source)


if __name__ == '__main__':
    main()
