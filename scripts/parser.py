#!/usr/bin/env python3
"""
低空经济情报服务 — 网页解析器
使用 Trafilatura 提取网页正文和元数据
"""

import re
import json
import logging
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class WebPageParser:
    """网页内容解析器"""

    # 机构名称标准化映射
    ORG_NAME_MAP = {
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
        """初始化解析器"""
        try:
            import trafilatura
            self.trafilatura = trafilatura
            logger.info("Trafilatura 加载成功")
        except ImportError:
            logger.error("Trafilatura 未安装，请运行: pip install trafilatura")
            self.trafilatura = None

    def extract_content(self, url, html_content=None):
        """
        从URL或HTML内容中提取结构化信息
        Args:
            url: 网页URL
            html_content: 可选的HTML内容，如果提供则不从URL获取
        Returns:
            dict: {title, content, publish_date, publisher, source_site, url}
        """
        if not self.trafilatura:
            logger.error("Trafilatura 不可用")
            return None

        try:
            # 如果没有提供HTML内容，使用Trafilatura直接从URL获取
            if html_content is None:
                downloaded = self.trafilatura.fetch_url(url)
                if downloaded is None:
                    logger.warning(f"无法下载页面: {url}")
                    return None
                html_content = downloaded

            # 提取元数据
            metadata = self.trafilatura.extract(
                html_content,
                output_format='json',
                with_metadata=True,
                url=url,
                include_comments=False,
                include_tables=True,
                favor_precision=True
            )

            if metadata is None:
                logger.warning(f"无法提取内容: {url}")
                return None

            # 解析JSON
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            # 提取字段
            result = {
                'url': url,
                'title': metadata.get('title', ''),
                'content': metadata.get('text', ''),
                'publish_date': self._normalize_date(metadata.get('date', '')),
                'publisher': self._normalize_org_name(metadata.get('sitename', '')),
                'source_site': self._extract_site_name(url),
                'raw_metadata': metadata
            }

            logger.info(f"提取成功: {result['title'][:50]}...")
            return result

        except Exception as e:
            logger.error(f"提取失败 {url}: {e}")
            return None

    def extract_meeting_info(self, html_content, url=''):
        """
        从会议页面提取会议信息
        Args:
            html_content: HTML内容
            url: 页面URL
        Returns:
            dict: {meeting_name, meeting_date, meeting_location, meeting_organizer, attendees}
        """
        result = {
            'meeting_name': '',
            'meeting_date': '',
            'meeting_location': '',
            'meeting_organizer': '',
            'attendees': [],
            'url': url
        }

        if not html_content:
            return result

        # 先用Trafilatura提取纯文本
        text = self.trafilatura.extract(html_content, include_comments=False) or ''

        # 提取会议名称（匹配常见模式）
        meeting_patterns = [
            r'(第[一二三四五六七八九十百千\d]+届?.*?(?:峰会|论坛|研讨会|交流会|展览会|博览会|大会|年会))',
            r'((?:\d{4})年.*?(?:峰会|论坛|研讨会|交流会|展览会|博览会|大会|年会))',
            r'((?:中国|国际|全国|亚太|全球).*?(?:峰会|论坛|研讨会|交流会|展览会|博览会|大会|年会))',
        ]
        for pattern in meeting_patterns:
            match = re.search(pattern, text)
            if match:
                result['meeting_name'] = match.group(1).strip()
                break

        # 提取会议日期
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)\s*[-—至]\s*(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}-\d{1,2}-\d{1,2})',
            r'(\d{4}\.\d{1,2}\.\d{1,2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                result['meeting_date'] = match.group(0).strip()
                break

        # 提取会议地点
        location_patterns = [
            r'(?:在|地点[：:])\s*([\u4e00-\u9fa5]{2,10}(?:市|区|县|镇|村|酒店|中心|大厦|展馆|会展)).*?(?:举办|召开|举行|开展)',
            r'(?:地点|地址)[：:]\s*([^\n，。]{4,30})',
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text)
            if match:
                result['meeting_location'] = match.group(1).strip()
                break

        # 提取主办方
        organizer_patterns = [
            r'(?:主办[单位]?[：:]|由)([\u4e00-\u9fa5\w]{4,30}?)(?:主办|承办|协办|联合|、|，)',
            r'(?:承办[单位]?[：:])([\u4e00-\u9fa5\w]{4,30})',
        ]
        for pattern in organizer_patterns:
            match = re.search(pattern, text)
            if match:
                result['meeting_organizer'] = match.group(1).strip()
                break

        logger.info(f"会议信息提取: {result['meeting_name'][:30]}...")
        return result

    def _normalize_date(self, date_str):
        """标准化日期格式为 ISO 8601 (YYYY-MM-DD)"""
        if not date_str:
            return ''

        # 尝试解析各种日期格式
        patterns = [
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', r'\1-\2-\3'),
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', r'\1-\2-\3'),
            (r'(\d{4})\.(\d{1,2})\.(\d{1,2})', r'\1-\2-\3'),
            (r'(\d{4})/(\d{1,2})/(\d{1,2})', r'\1-\2-\3'),
        ]

        for pattern, replacement in patterns:
            match = re.search(pattern, date_str)
            if match:
                try:
                    year = int(match.group(1))
                    month = int(match.group(2))
                    day = int(match.group(3))
                    return f"{year:04d}-{month:02d}-{day:02d}"
                except (ValueError, IndexError):
                    continue

        return date_str  # 返回原始字符串

    def _normalize_org_name(self, name):
        """标准化机构名称"""
        if not name:
            return ''
        return self.ORG_NAME_MAP.get(name.strip(), name.strip())

    def _extract_site_name(self, url):
        """从URL提取网站名称"""
        parsed = urlparse(url)
        domain = parsed.netloc.replace('www.', '')
        return domain


def main():
    """测试解析器"""
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    parser = WebPageParser()

    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"\n测试解析: {url}\n")
        result = parser.extract_content(url)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("解析失败")
    else:
        print("用法: python parser.py <url>")
        print("示例: python parser.py https://www.ndrc.gov.cn/xxgk/zcfb/...")


if __name__ == '__main__':
    main()
