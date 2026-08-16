# 低空经济情报服务

> 自动化采集、NLP 分析、知识库交付的低空经济情报系统

## 项目架构

```
low-altitude-intel/
├── .github/workflows/     # GitHub Actions 定时任务
├── config/                # 配置文件（数据源、行业词典）
├── scripts/               # 核心脚本
│   ├── main.py            # 采集流程主入口
│   ├── feed_collector.py  # RSS/Atom 采集引擎
│   ├── collector.py       # 网页采集器框架
│   ├── parser.py          # Trafilatura 网页解析器
│   ├── ner_extractor.py   # HanLP + spaCy 双引擎 NER
│   ├── cleaner.py         # 数据清洗与标准化
│   └── report_generator.py# 情报报告生成
├── raw/                   # 原始采集数据（gitignore）
├── processed/             # 清洗后数据（gitignore）
├── reports/               # 生成的报告
├── ima-seed-content/      # IMA 知识库种子内容
├── ima-config/            # IMA Copilot 配置文件
└── requirements.txt       # Python 依赖
```

## 数据流

```
政府/协会网站 → RSS/网页采集 → Trafilatura解析 → NER实体提取 → 数据清洗 → 报告生成 → IMA知识库
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt
python -m spacy download zh_core_web_sm

# 运行采集（本地测试）
python scripts/main.py --mode test

# 运行完整采集流程
python scripts/main.py --mode full
```

## GitHub Actions 自动化

- **每日采集**：每天 08:00 (UTC) 自动运行采集流程
- **每周报告**：每周一 09:00 (UTC) 生成周报
- 采集结果自动提交到 `data/` 目录

## 配置

在 GitHub 仓库 Settings → Secrets 中配置：
- `DEEPSEEK_API_KEY`：DeepSeek API 密钥（用于高级分析）
- `NOTIFICATION_WEBHOOK`：通知 Webhook（可选）
