#!/usr/bin/env python3
"""
低空经济情报服务 — 环境验证脚本
验证 Phase 1 所有配置是否正确完成
"""

import sys
import os
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# ANSI 颜色
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

def ok(msg):
    print(f"  {GREEN}✓{RESET} {msg}")

def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")

def warn(msg):
    print(f"  {YELLOW}⚠{RESET} {msg}")

def header(msg):
    print(f"\n{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  {msg}{RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")


def check_directories():
    """检查目录结构"""
    header("1. 目录结构检查")

    dirs = [
        'raw/gov', 'raw/associations',
        'processed/company_profiles',
        'reports', 'templates', 'scripts', 'config',
        'backup/ima-export'
    ]

    all_ok = True
    for d in dirs:
        path = PROJECT_ROOT / d
        if path.exists():
            ok(f"目录存在: {d}")
        else:
            fail(f"目录缺失: {d}")
            all_ok = False

    return all_ok


def check_python_deps():
    """检查 Python 依赖"""
    header("2. Python 依赖检查")

    deps = {
        'trafilatura': '网页内容提取',
        'hanlp': '中文 NER',
        'spacy': '中文 NER (备用)',
        'yaml': '配置文件解析',
        'requests': 'HTTP 请求',
    }

    all_ok = True
    for module, desc in deps.items():
        try:
            if module == 'yaml':
                import yaml
            else:
                __import__(module)
            ok(f"{module} ({desc})")
        except ImportError:
            fail(f"{module} 未安装 ({desc})")
            all_ok = False

    return all_ok


def check_spacy_model():
    """检查 spaCy 中文模型"""
    header("3. spaCy 中文模型检查")

    try:
        import spacy
        nlp = spacy.load('zh_core_web_sm')
        ok("zh_core_web_sm 模型已加载")

        # 测试 NER
        test_text = "张三是北京大学教授"
        doc = nlp(test_text)
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        if entities:
            ok(f"NER 测试: {entities}")
        else:
            warn("NER 测试未提取到实体（可能需要更大模型）")
        return True
    except OSError:
        fail("zh_core_web_sm 模型未下载")
        fail("请运行: python -m spacy download zh_core_web_sm")
        return False
    except ImportError:
        fail("spaCy 未安装")
        return False
    except Exception as e:
        warn(f"spaCy 初始化异常: {e}")
        return False


def check_hanlp():
    """检查 HanLP"""
    header("4. HanLP 检查")

    try:
        import hanlp
        ok("HanLP 已安装")
        # 尝试加载预训练模型
        try:
            model = hanlp.load(hanlp.pretrained.mtl.CLOSE_TOK_POS_NER_SRL_DEP_SDP_CON_ELECTRA_BASE_ZH)
            ok("HanLP 预训练模型已加载")
            return True
        except Exception as e:
            warn(f"HanLP 模型加载需要下载（首次使用会自动下载）: {e}")
            return True  # 不阻塞，首次使用会下载
    except ImportError:
        fail("HanLP 未安装")
        fail("请运行: pip install hanlp --break-system-packages")
        return False


def check_config():
    """检查配置文件"""
    header("5. 配置文件检查")

    configs = [
        ('config/sources.yaml', '数据源配置'),
        ('config/industry_dict.yaml', '行业词典'),
    ]

    all_ok = True
    for filepath, desc in configs:
        path = PROJECT_ROOT / filepath
        if path.exists():
            size = path.stat().st_size
            ok(f"{filepath} ({desc}, {size} bytes)")
        else:
            fail(f"{filepath} 缺失 ({desc})")
            all_ok = False

    # 验证 sources.yaml 内容
    try:
        import yaml
        with open(PROJECT_ROOT / 'config' / 'sources.yaml', 'r', encoding='utf-8') as f:
            sources = yaml.safe_load(f)

        gov_count = len(sources.get('gov_sources', []))
        assoc_count = len(sources.get('association_sources', []))

        if gov_count >= 9:
            ok(f"政府数据源: {gov_count} 个（目标 ≥9）")
        else:
            warn(f"政府数据源: {gov_count} 个（目标 ≥9）")

        if assoc_count >= 5:
            ok(f"协会数据源: {assoc_count} 个（目标 ≥5）")
        else:
            warn(f"协会数据源: {assoc_count} 个（目标 ≥5）")

    except Exception as e:
        fail(f"配置文件解析失败: {e}")
        all_ok = False

    return all_ok


def check_scripts():
    """检查脚本框架"""
    header("6. 脚本框架检查")

    scripts = [
        ('scripts/collector.py', '采集器'),
        ('scripts/parser.py', '解析器'),
        ('scripts/ner_extractor.py', 'NER 提取器'),
        ('scripts/cleaner.py', '数据清洗器'),
        ('scripts/report_generator.py', '报告生成器'),
    ]

    all_ok = True
    for filepath, desc in scripts:
        path = PROJECT_ROOT / filepath
        if path.exists():
            # 检查语法
            import py_compile
            try:
                py_compile.compile(str(path), doraise=True)
                ok(f"{filepath} ({desc}) — 语法正确")
            except py_compile.PyCompileError as e:
                fail(f"{filepath} 语法错误: {e}")
                all_ok = False
        else:
            fail(f"{filepath} 缺失 ({desc})")
            all_ok = False

    return all_ok


def check_trafilatura():
    """检查 Trafilatura 功能"""
    header("7. Trafilatura 功能测试")

    try:
        import trafilatura

        # 测试提取功能
        test_html = """
        <html><head><title>测试政策文件</title></head>
        <body>
        <article>
        <h1>关于促进低空经济发展的指导意见</h1>
        <p>2026年8月15日，国家发展和改革委员会发布关于促进低空经济发展的指导意见。</p>
        <p>为推动低空经济高质量发展，经国务院同意，现提出以下意见。</p>
        </article>
        </body></html>
        """

        result = trafilatura.extract(test_html, output_format='json', with_metadata=True)
        if result:
            data = json.loads(result) if isinstance(result, str) else result
            ok(f"Trafilatura 提取成功: {data.get('title', 'N/A')[:40]}")
            return True
        else:
            warn("Trafilatura 提取返回空结果")
            return True
    except Exception as e:
        fail(f"Trafilatura 测试失败: {e}")
        return False


def main():
    """运行所有检查"""
    print(f"\n{BOLD}低空经济情报服务 — Phase 1 环境验证{RESET}")
    print(f"项目路径: {PROJECT_ROOT}\n")

    results = {
        '目录结构': check_directories(),
        'Python 依赖': check_python_deps(),
        'spaCy 模型': check_spacy_model(),
        'HanLP': check_hanlp(),
        '配置文件': check_config(),
        '脚本框架': check_scripts(),
        'Trafilatura': check_trafilatura(),
    }

    # 汇总
    header("验证结果汇总")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = f"{GREEN}通过{RESET}" if result else f"{RED}失败{RESET}"
        print(f"  {name}: {status}")

    print(f"\n  总计: {passed}/{total} 项通过")

    if passed == total:
        print(f"\n  {GREEN}{BOLD}✓ Phase 1 环境配置全部完成！{RESET}")
        print(f"  {GREEN}可以进入 Phase 2: 情报采集管线{RESET}")
        return 0
    else:
        print(f"\n  {YELLOW}{BOLD}⚠ 部分检查未通过，请按上述提示修复{RESET}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
