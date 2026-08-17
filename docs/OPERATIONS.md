# 低空经济情报系统 — 运维手册

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   GitHub Actions                        │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │ 每日采集     │  │ 每周报告     │  │ Pages 部署   │   │
│  │ 16:00 BJT   │  │ 周一17:00   │  │ push 触发    │   │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┘   │
│         │                │                              │
│  ┌──────▼────────────────▼──────────────────────┐      │
│  │           IntelPipeline (main.py)            │      │
│  │  Step1 采集 → Step2 解析 → Step3 NER        │      │
│  │  → Step4 清洗+报告 → Step5 深度分析          │      │
│  └──────┬──────────────────────────────────────┘      │
│         │                                                │
│  ┌──────▼──────────────────────────────────────┐      │
│  │              数据存储 (Git 仓库)              │      │
│  │  raw/ · processed/ · reports/ · ima-export/ │      │
│  └─────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
         │                              │
    ┌────▼────┐                   ┌─────▼─────┐
    │ GitHub  │                   │   IMA     │
    │  Pages  │                   │  知识库   │
    └─────────┘                   └───────────┘
```

## 数据源配置

| 优先级 | 数据源 | 类型 | 说明 |
|--------|--------|------|------|
| P0 | Google News RSS | RSS × 6 | 使用 googlenewsdecoder 解码真实 URL |
| P1 | 圆象低空经济观察 | HTML 抓取 × 3 | sitemap 发现文章，trafilatura 提取全文 |
| P2 | 国务院政策搜索 | HTML 解析 | 政策法规类情报 |

### 添加新数据源

在 `scripts/feed_collector.py` 的 `SOURCES` 列表中添加：

```python
{
    "name": "新源名称",
    "type": "direct_html",  # 或 rss / gov_html
    "url": "https://example.com/news",
    "keywords": ["低空经济", "无人机"],
    "priority": "P1",
    "parser": "generic",  # 或 yuanxiangsky
    "max_articles": 30,   # 每次最多采集文章数
}
```

## 工作流说明

### 每日采集 (`daily-collect.yml`)

- **触发时间**: 每天 UTC 08:00（北京时间 16:00）
- **执行内容**: 完整 5 步流水线 + Markdown 日报生成
- **超时限制**: 45 分钟
- **手动触发**: GitHub Actions → 选择 `full` / `collect` / `test` 模式

### 每周报告 (`weekly-report.yml`)

- **触发时间**: 每周一 UTC 09:00（北京时间 17:00）
- **执行内容**: 周报 JSON + Phase 2 深度分析 + Markdown 周报 + IMA 导出
- **超时限制**: 30 分钟

### Pages 部署 (`deploy-pages.yml`)

- **触发条件**: push 到 main 分支（docs/ 或 reports/ 有变更时）
- **部署内容**: 报告预览站点

## 报告目录结构

```
reports/
├── 2026-08/                          # 按月归档日报
│   ├── daily-2026-08-16.md
│   └── daily-2026-08-17.md
├── 2026-W33/                         # 按周归档周报
│   ├── weekly-report-data.json
│   └── weekly-report.md
├── company-reports/                  # 企业深度报告
│   ├── 峰飞航空_深度报告.md
│   └── ...
├── competitive-landscape-2026-08.md  # 竞争格局分析
├── monthly-2026-08.md                # 月度趋势
└── executive-summary.md              # 高管摘要
```

## 配置文件

### `config/industry_dict.yaml`

- `companies`: 企业名词典（NER 增强用）
- `ner_blocklist_persons`: 非人物实体黑名单（NER 消歧用）
- `policy_entities`: 政策法规实体关键词
- `titles`: 职务词典
- `tech_domains`: 技术领域关键词
- `policy_keywords`: 政策法规关键词

### `requirements.txt`

所有 Python 依赖。在 GitHub Actions 中自动安装。

## 本地运行

```bash
# 安装依赖
pip install -r requirements.txt
python -m spacy download zh_core_web_sm

# 测试模式（仅采集第一个源）
python scripts/main.py --mode test

# 仅采集模式
python scripts/main.py --mode collect

# 完整流水线
python scripts/main.py --mode full
```

## 通知配置

在 GitHub 仓库 Settings → Secrets 中添加：

| Secret 名称 | 用途 |
|-------------|------|
| `NOTIFICATION_WEBHOOK` | 飞书/钉钉/Slack Webhook URL |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（可选）|

## 故障排查

### 采集内容为空

1. 检查 `googlenewsdecoder` 是否安装：`pip install googlenewsdecoder`
2. 检查 Google News RSS 是否可达（GitHub Actions runner 网络正常即可）
3. 查看日志 `logs/pipeline_YYYYMMDD.log` 中的采集器输出

### NER 实体质量差

1. 检查 `config/industry_dict.yaml` 中 `ner_blocklist_persons` 是否覆盖了误识别实体
2. 检查 HanLP 和 spaCy 模型是否正确加载
3. 查看日志中的 NER 引擎状态

### GitHub Actions 超时

1. 减少 `SOURCES` 中的数据源数量
2. 降低 `max_articles` 参数
3. 使用 `collect` 模式分步执行

### GitHub Pages 部署失败

1. 确认仓库 Settings → Pages → Source 设置为 "GitHub Actions"
2. 检查 `deploy-pages.yml` 权限配置
3. 查看 Actions 运行日志

## 性能指标

| 指标 | 目标值 |
|------|--------|
| 每日采集量 | 50-200 条 |
| URL 解析率 | > 80% |
| 全文提取率 | > 70% |
| NER 实体覆盖率 | > 90% |
| 流水线耗时 | < 15 分钟 |
| Google News 解码成功率 | > 60% |

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v3.0 | 2026-08-17 | googlenewsdecoder + 圆象网 sitemap + NER 消歧 + GitHub Pages |
| v2.0 | 2026-08-16 | Phase 2 深度分析（企业画像/知识图谱/竞争分析） |
| v1.0 | 2026-08-15 | 初始版本：RSS 采集 + NER + 周报 + GitHub Actions |
