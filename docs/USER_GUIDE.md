# 低空经济情报系统 — 用户指南

> **版本**: v3.0 | **更新日期**: 2026-08-17 | **适用对象**: 系统使用者、运维人员、情报分析人员

---

## 目录

1. [系统概述](#1-系统概述)
2. [功能模块](#2-功能模块)
3. [操作指南](#3-操作指南)
4. [报告目录结构](#4-报告目录结构)
5. [IMA 知识库使用](#5-ima-知识库使用)
6. [配置说明](#6-配置说明)
7. [常见问题 (FAQ)](#7-常见问题-faq)
8. [技术支持](#8-技术支持)

---

## 1. 系统概述

### 1.1 系统简介

低空经济情报系统是一套自动化情报采集、NLP 分析与知识库交付一体化平台，专注于低空经济领域（eVTOL、无人机、通用航空、低空空域管理等）的动态监测与情报分析。系统通过 RSS 订阅、网页抓取、实体识别、知识图谱构建等技术，将分散的低空经济信息汇聚为结构化的情报产品，为政策研究者、投资人和产业决策者提供数据支撑。

### 1.2 系统目标

- **实时监测**：每日自动采集低空经济相关新闻、政策、企业动态
- **智能分析**：通过 NER 实体识别、知识图谱、竞争格局分析挖掘情报价值
- **便捷交付**：生成 Markdown 报告、GitHub Pages 预览站点、IMA 知识库，多渠道触达用户

### 1.3 系统架构（双轨制）

系统采用 **TraeWork（生产端）+ IMA（交付端）** 双轨架构：

```
┌─────────────────────────────────────────────────────────────────┐
│                        生产端：TraeWork                          │
│                                                                 │
│   GitHub Actions 定时触发                                        │
│   ├── daily-collect.yml  (每日 16:00 BJT)                       │
│   ├── weekly-report.yml  (每周一 17:00 BJT)                     │
│   └── deploy-pages.yml   (push 触发)                            │
│                                                                 │
│   IntelPipeline 采集流水线 (main.py)                             │
│   Step1 RSS采集 → Step2 全文解析 → Step3 NER实体提取             │
│   → Step4 数据清洗+报告生成 → Step5 深度分析                     │
│         │                                                       │
│   ┌─────▼──────────────────────────────────────────┐            │
│   │  数据存储 (Git 仓库)                            │            │
│   │  raw/ · processed/ · reports/ · ima-export/    │            │
│   └──────┬───────────────────────┬─────────────────┘            │
└──────────┼───────────────────────┼─────────────────────────────┘
           │                       │
     ┌─────▼─────┐          ┌─────▼──────┐
     │ GitHub    │          │   IMA      │
     │  Pages    │          │  知识库    │
     │ 报告预览  │          │ (交付端)   │
     └──────────┘          └────────────┘
```

| 轨道 | 平台 | 职责 | 产出物 |
|------|------|------|--------|
| **生产端** | TraeWork + GitHub Actions | 情报采集、NLP 分析、报告生成 | 日报、周报、企业画像、知识图谱、竞争格局分析 |
| **交付端** | IMA 知识库 | 知识管理、智能问答、内容交付 | 企业卡片、情报摘要、Copilot 问答、知识索引 |

### 1.4 数据流

```
政府/协会网站 + 新闻 RSS → RSS采集 → googlenewsdecoder URL解码
→ Trafilatura 全文解析 → HanLP+spaCy NER实体提取 → 数据清洗标准化
→ 报告生成 → 企业画像 → 知识图谱 → 竞争格局分析 → IMA知识库导出
```

---

## 2. 功能模块

### 2.1 每日情报采集 (`daily-collect.yml`)

| 属性 | 说明 |
|------|------|
| **触发时间** | 每天 16:00 BJT（北京时间），即 UTC 08:00 |
| **Cron 表达式** | `0 8 * * *` |
| **执行内容** | 完整 5 步流水线（采集 → 解析 → NER → 清洗 → 深度分析）+ Markdown 日报生成 |
| **超时限制** | 45 分钟 |
| **产出物** | `reports/YYYY-MM/daily-YYYY-MM-DD.md`（每日情报日报） |
| **支持模式** | `full`（完整流水线）、`collect`（仅采集）、`test`（测试模式） |

每日 16:00 自动运行，采集 Google News、Bing News 等 RSS 源的低空经济新闻，使用 `googlenewsdecoder` 解码 Google News 跳转链接获取真实 URL，通过 Trafilatura 提取全文，经 HanLP + spaCy 双引擎 NER 提取实体后清洗标准化，最终生成结构化 Markdown 日报并自动提交到 Git 仓库。

### 2.2 每周情报报告 (`weekly-report.yml`)

| 属性 | 说明 |
|------|------|
| **触发时间** | 每周一 17:00 BJT（北京时间），即 UTC 09:00 |
| **Cron 表达式** | `0 9 * * 1` |
| **执行内容** | 周报数据生成 + Phase 2 深度分析 + Markdown 周报 + IMA 导出 |
| **超时限制** | 15 分钟 |
| **产出物** | `reports/YYYY-Www/weekly-report.md`、企业画像、知识图谱、竞争格局报告、IMA 交付文件 |

每周一自动生成上周情报汇总，并执行 Phase 2 深度分析模块：

- **企业画像** (`company_profiler.py`)：构建 6 家企业深度画像
- **知识图谱** (`knowledge_graph.py`)：构建企业-人物-地点-政策-技术关系图谱
- **竞争格局分析** (`competitive_analysis.py`)：分析 4 个赛道 8 家企业的竞争态势
- **增强报告** (`enhanced_reporter.py`)：生成月度趋势报告与高管摘要
- **IMA 导出** (`ima_exporter.py`)：生成 IMA 知识库交付文件

### 2.3 GitHub Pages 报告预览

| 属性 | 说明 |
|------|------|
| **访问地址** | https://smilemouse0980.github.io/low-altitude-intel/ |
| **触发条件** | push 到 main 分支（`docs/`、`reports/` 或摘要数据有变更时） |
| **工作流** | `deploy-pages.yml` |
| **部署内容** | 报告预览站点（含首页、日报、周报、企业报告、竞争格局等） |

报告站点自动部署，无需手动操作。当 `reports/` 目录有新报告提交时，会自动触发重新部署。站点包含 `.nojekyll` 文件以确保下划线开头的文件不被忽略。

### 2.4 企业画像系统

基于情报数据为每家重点企业构建深度画像，包含：

- 企业基本信息与分类（eVTOL 整机、无人机整机、通航运营等）
- 情报提及次数与时间跨度
- 关键人物识别
- 业务地理分布
- 合作伙伴关系（共现分析）
- 核心事件分类（产品发布、融资动态、合作签约、适航认证、市场拓展等）
- 近期动态时间线

系统当前构建 **6 家企业**深度画像，数据存储于 `processed/company_profiles/` 目录，并以 Markdown 格式导出至 `ima-export/company-cards/`。

### 2.5 知识图谱

| 属性 | 数值 |
|------|------|
| **总节点数** | 88 |
| **总边数** | 318 |
| **节点类型** | 企业(8)、人物(1)、地点(67)、政策(1)、技术(11) |
| **边类型** | 提及人物(5)、位于(227)、合作(18)、受影响(3)、运营于(65) |

知识图谱将情报中的实体关系结构化，支持企业合作关系分析、地理分布分析、技术关联分析。数据存储于 `processed/knowledge_graph/knowledge_graph.json`。

### 2.6 竞争格局分析

对 **4 个赛道**的 **8 家企业**进行竞争态势分析：

| 赛道 | 代表企业 |
|------|----------|
| eVTOL 整机 | 亿航智能、小鹏汇天、峰飞航空、沃兰特、沃飞长空 |
| 通航运营 | 中信海直 |
| 无人机整机 | 大疆创新 |
| 军工航空 | 中国商飞 |

分析维度包括：企业活跃度评分、事件分布（产品/融资/合作/国际/认证）、地理分布、合作伙伴关系、最新动态时间线、投资信号识别。产出物为 `reports/competitive-landscape-YYYY-MM.md`。

### 2.7 IMA 知识库交付

系统自动生成 IMA 知识库可导入的交付文件，包含四大模块：

| 模块 | 内容 | 文件路径 |
|------|------|----------|
| **企业卡片** | 每家企业的核心信息卡片 | `ima-export/company-cards/*.md` |
| **情报摘要** | 按主题分类的情报摘要（8 个主题） | `ima-export/intel-digest/*.md` |
| **Copilot QA** | 预设问答示例（6 对） | `ima-export/copilot-qa.md` |
| **知识索引** | 全部内容的索引文件 | `ima-export/knowledge-index.json` |

详细使用方法见 [第 5 节](#5-ima-知识库使用)。

---

## 3. 操作指南

### 3.1 手动触发 GitHub Actions

当需要立即执行采集或报告生成时，可手动触发工作流：

**步骤：**

1. 打开 GitHub 仓库页面：`https://github.com/smilemouse0980/low-altitude-intel`
2. 点击顶部标签栏的 **Actions**
3. 在左侧工作流列表中选择目标工作流：
   - `每日低空经济情报采集`（daily-collect.yml）
   - `每周情报报告生成`（weekly-report.yml）
   - `部署报告站点到 GitHub Pages`（deploy-pages.yml）
4. 点击右侧的 **Run workflow** 按钮
5. 在弹出的对话框中选择运行参数：
   - 对于每日采集工作流，选择运行模式：
     - `full` — 完整流水线（采集 + 解析 + NER + 清洗 + 报告）
     - `collect` — 仅采集（快速模式，不执行 NER 和报告生成）
     - `test` — 测试模式（仅采集 1 个源验证连通性）
6. 点击绿色的 **Run workflow** 按钮确认执行
7. 在工作流列表中点击运行记录，查看实时日志

> **提示**：手动触发产生的结果会自动提交到 Git 仓库，无需额外操作。

### 3.2 本地运行采集流水线

如需在本地环境运行采集流水线（调试或开发用途）：

**第一步：安装依赖**

```bash
# 进入项目目录
cd low-altitude-intel

# 安装 Python 依赖
pip install -r requirements.txt

# 下载 spaCy 中文模型（NER 引擎依赖）
python -m spacy download zh_core_web_sm
```

**第二步：运行流水线**

```bash
# 测试模式：仅采集第一个源，验证连通性（推荐首次运行）
python scripts/main.py --mode test

# 仅采集模式：只采集不解析/NER（快速获取原始数据）
python scripts/main.py --mode collect

# 完整模式：完整 5 步流水线（采集 + 解析 + NER + 清洗 + 深度分析）
python scripts/main.py --mode full
```

**三种模式说明：**

| 模式 | 执行步骤 | 耗时（参考） | 适用场景 |
|------|----------|-------------|----------|
| `test` | 仅采集第一个数据源 | < 1 分钟 | 验证环境连通性 |
| `collect` | Step 1：RSS 采集 | 5-10 分钟 | 快速获取原始数据 |
| `full` | Step 1-5：完整流水线 | 10-45 分钟 | 完整情报生产 |

**第三步：查看结果**

```bash
# 查看采集的原始数据
ls raw/feeds/

# 查看清洗后的情报记录
cat processed/intel_records.jsonl

# 查看流水线执行摘要
cat processed/pipeline_summary.json

# 查看运行日志
ls logs/
```

> **注意**：本地运行 NER 需要先安装 HanLP 和 spaCy 模型。如未安装，NER 步骤会自动跳过，不影响采集和报告生成。

### 3.3 查看 GitHub Pages 报告站点

**步骤：**

1. 在浏览器中访问：**https://smilemouse0980.github.io/low-altitude-intel/**
2. 首页展示系统概览与最新情报摘要
3. 通过导航可查看：
   - **日报**：每日情报列表（按来源分布、实体标注）
   - **周报**：每周情报汇总与趋势分析
   - **企业报告**：各企业深度分析报告
   - **竞争格局**：赛道竞争态势分析
   - **月度趋势**：月度情报趋势报告
   - **高管摘要**：面向决策层的核心发现摘要

> **提示**：如果站点未更新，检查 `deploy-pages.yml` 工作流是否执行成功。报告站点在 `reports/` 目录有新提交时自动重新部署。

### 3.4 查看和下载报告文件

所有报告文件存储在仓库的 `reports/` 目录中，可通过以下方式查看和下载：

**方式一：GitHub 网页直接查看**

1. 打开仓库页面，进入 `reports/` 目录
2. 点击任意 `.md` 文件即可在线预览（GitHub 原生支持 Markdown 渲染）
3. 点击文件右上角的下载按钮可下载原始文件

**方式二：通过 GitHub Pages 查看**

访问 https://smilemouse0980.github.io/low-altitude-intel/ ，在站点中浏览报告。

**方式三：克隆仓库到本地**

```bash
git clone https://github.com/smilemouse0980/low-altitude-intel.git
cd low-altitude-intel/reports
```

**`reports/` 目录结构说明：**

| 路径 | 内容 | 说明 |
|------|------|------|
| `reports/YYYY-MM/` | 按月归档的日报 | 如 `2026-08/daily-2026-08-17.md` |
| `reports/YYYY-Www/` | 按周归档的周报 | 如 `2026-W33/weekly-report.md` |
| `reports/company-reports/` | 企业深度报告 | 如 `亿航智能_深度报告.md` |
| `reports/competitive-landscape-YYYY-MM.md` | 竞争格局分析 | 按月生成 |
| `reports/monthly-YYYY-MM.md` | 月度趋势报告 | 按月生成 |
| `reports/executive-summary.md` | 高管摘要 | 面向决策层的核心发现 |

详细目录结构见 [第 4 节](#4-报告目录结构)。

### 3.5 IMA 知识库使用方法

#### 导入企业卡片

1. 在 IMA 知识库管理后台，选择「内容导入」功能
2. 选择 `ima-export/company-cards/` 目录下的 Markdown 文件
3. 每个文件对应一家企业的情报卡片，包含分类、提及次数、关键人物、地理分布、合作伙伴、核心事件等
4. 批量导入后，企业卡片将作为知识库的基础内容

#### 使用 Copilot 问答

1. 在 IMA 知识库中配置 Copilot（系统提示词见 `ima-config/copilot-system-prompt.txt`）
2. 导入预设问答对（`ima-export/copilot-qa.md`）作为 Few-shot 示例
3. 用户可直接向 Copilot 提问，例如：
   - 「低空经济领域最活跃的企业有哪些？」
   - 「低空经济有哪些细分市场？」
   - 「低空经济的技术热点是什么？」
   - 「低空经济在中国哪些地区发展最快？」
   - 「近期有哪些值得关注的投资信号？」

> 详细使用方法见 [第 5 节](#5-ima-知识库使用)。

---

## 4. 报告目录结构

系统生成的所有报告文件统一存储在 `reports/` 目录下，按照时间维度和内容类型分类归档：

```
reports/
├── 2026-08/                          # 按月归档日报
│   ├── daily-2026-08-16.md           # 8月16日情报日报
│   └── daily-2026-08-17.md           # 8月17日情报日报
├── 2026-W33/                         # 按周归档周报
│   ├── weekly-report-data.json       # 周报原始数据（JSON）
│   └── weekly-report.md              # 周报 Markdown 报告
├── company-reports/                  # 企业深度报告
│   ├── 亿航智能_深度报告.md
│   ├── 峰飞航空_深度报告.md
│   ├── 沃兰特_深度报告.md
│   ├── 小鹏汇天_深度报告.md
│   ├── 大疆创新_深度报告.md
│   └── ...
├── competitive-landscape-2026-08.md  # 竞争格局分析（按月）
├── monthly-2026-08.md                 # 月度趋势报告（按月）
└── executive-summary.md               # 高管摘要（最新一期）
```

### 目录说明

| 目录/文件 | 命名规则 | 生成频率 | 内容描述 |
|-----------|----------|----------|----------|
| `YYYY-MM/` | 年-月 | 每日 | 按月归档的每日情报日报，包含当日采集的新闻、来源分布、实体标注 |
| `YYYY-Www/` | 年-周序号 | 每周 | 按周归档的周报，含 JSON 数据和 Markdown 报告 |
| `company-reports/` | 企业名_深度报告.md | 每周 | 每家重点企业的深度分析报告 |
| `competitive-landscape-YYYY-MM.md` | 竞争格局-年-月 | 每月 | 4 赛道 8 企业的竞争态势分析 |
| `monthly-YYYY-MM.md` | 月度-年-月 | 每月 | 月度情报趋势报告（市场细分、企业动态、技术热点、地理动态） |
| `executive-summary.md` | 固定文件名 | 每周 | 面向决策层的核心发现摘要（市场细分、企业活跃度、投资信号） |

### 日报文件内容示例

每份日报包含以下结构：

- **标题与元信息**：报告日期、情报条数
- **来源分布表**：各信息来源及条数统计
- **情报列表**：每条情报包含标题、日期、来源、机构实体、人物实体、链接、内容摘要

---

## 5. IMA 知识库使用

IMA 知识库是系统的交付端，将生产端采集和分析的情报以结构化、可问答的形式交付给最终用户。

### 5.1 企业卡片

**文件位置**: `ima-export/company-cards/`

每家企业的核心信息卡片，以独立 Markdown 文件存储。每张卡片包含：

| 字段 | 说明 |
|------|------|
| 分类 | 企业所属赛道（eVTOL 整机、无人机整机、通航运营等） |
| 情报提及次数 | 该企业在情报数据中被提及的总次数 |
| 首次出现 / 最近动态 | 该企业首次和最近出现在情报中的日期 |
| 关键人物 | 情报中识别到的该企业关联人物及提及次数 |
| 业务地理分布 | 该企业业务涉及的主要地区及提及次数 |
| 合作伙伴 | 与该企业共现的其他企业及共现次数 |
| 核心事件 | 按类型分类（产品发布、融资动态、合作签约、政策相关、适航认证、市场拓展）的事件列表 |
| 近期动态时间线 | 按时间倒序排列的近期重要事件 |

**使用方法**：在 IMA 知识库中导入这些 Markdown 文件，即可通过 Copilot 查询特定企业的情报。例如：「亿航智能的合作伙伴有哪些？」「峰飞航空最近有什么融资动态？」

### 5.2 情报摘要

**文件位置**: `ima-export/intel-digest/`

按主题分类的情报摘要，共 8 个主题文件：

| 主题文件 | 内容范围 |
|----------|----------|
| `产品技术.md` | 新产品发布、技术突破、研发进展 |
| `企业融资.md` | 融资事件、投资动态、估值变化 |
| `合作签约.md` | 企业间合作、战略合作、订单签约 |
| `国际动态.md` | 出海动态、国际订单、海外市场拓展 |
| `地方动态.md` | 各地低空经济政策、试点项目、地方产业布局 |
| `应用场景.md` | 低空经济应用场景落地（物流、巡检、应急救援等） |
| `政策法规.md` | 国家及地方政策法规、管理条例、实施方案 |
| `适航认证.md` | 适航审定进展、型号合格证、运营资质 |

**使用方法**：导入 IMA 知识库后，用户可按主题检索情报。例如：「最近有哪些适航认证进展？」「低空经济政策法规有哪些新动态？」

### 5.3 Copilot QA

**文件位置**: `ima-export/copilot-qa.md`

预设的 6 对问答示例，作为 IMA Copilot 的 Few-shot 学习样本：

| 编号 | 问题 | 回答要点 |
|------|------|----------|
| Q1 | 低空经济领域最活跃的企业有哪些？ | 列出活跃度 Top 5 企业及评分 |
| Q2 | 低空经济有哪些细分市场？ | 列出 4 个赛道及企业数量、提及次数 |
| Q3 | 低空经济的技术热点是什么？ | 列出 Top 3 技术领域及关联企业 |
| Q4 | 低空经济在中国哪些地区发展最快？ | 列出活跃度最高的地区 |
| Q5 | 近期有哪些值得关注的投资信号？ | 汇总融资事件和产品里程碑 |
| Q6 | 低空经济有哪些新兴趋势？ | 列出呈现上升趋势的主题 |

**使用方法**：将问答对导入 IMA Copilot 配置，作为回答范本。Copilot 会基于知识库内容，参照这些示例的格式和风格回答用户的类似问题。

### 5.4 知识索引

**文件位置**: `ima-export/knowledge-index.json`

全部 IMA 交付内容的索引文件，包含：

- **元数据**：生成时间、情报总量、企业数、人物数、地区数
- **企业分类**：按赛道分组的企业列表（eVTOL 整机、无人机整机、物流无人机、农业无人机、核心零部件等 12 个分类）
- **高频实体排行**：Top 机构、Top 人物、Top 地区
- **导出文件清单**：企业卡片、情报摘要、Copilot QA 的文件路径
- **市场细分概览**：各赛道的企业和提及次数

**使用方法**：作为 IMA 知识库的目录导航文件，帮助用户快速了解知识库的全貌和内容分布。

### 5.5 IMA Copilot 系统提示词

**文件位置**: `ima-config/copilot-system-prompt.txt`

定义了 Copilot 的角色定位、知识范围、回答规范和典型场景：

- **角色**：低空经济情报分析师
- **知识范围**：法规政策库、行业标准库、企业情报库、会议情报库、行业研报库
- **回答规范**：优先引用知识库文档、准确引用法规文号和标准号、表格呈现对比、不编造数据
- **限制**：不提供法律意见、不做投资建议

### 5.6 IMA 知识库种子内容

**文件位置**: `ima-seed-content/`

知识库的种子内容，包含法规政策库和行业标准库的结构化文档：

| 子目录 | 内容 |
|--------|------|
| `01-法规政策库/` | 17 份政策法规文档（国家条例、地方实施方案、产业政策） |
| `02-行业标准库/` | 16 份行业标准文档（GB 国标、MH/T 民航行标、团体标准） |

此外，`ima-config/batch-url-import.txt` 提供了 33 条外部 URL 的批量导入清单，分 4 组（每组 ≤10 条），可在 IMA 知识库中使用「网页链接」导入功能批量导入。

---

## 6. 配置说明

### 6.1 数据源配置 (`config/sources.yaml`)

该文件定义了系统的所有数据源，分为三个优先级：

| 优先级 | 数据源类型 | 数量 | 说明 |
|--------|------------|------|------|
| **P0** | 九部委政府网站 | 9 个 | 发改委、民航局、工信部、交通部、科技部、公安部、应急部、市场监管总局、气象局 |
| **P1** | 行业协会 | 5 个 | AOPA 中国、无人机联盟、航协、深圳低空协会、低空联盟 |

**配置字段说明：**

```yaml
gov_sources:
  - name: "国家发展和改革委员会"    # 数据源全称
    short_name: "发改委"             # 简称（用于报告标注）
    url: "https://www.ndrc.gov.cn"  # 网站 URL
    search_paths:                    # 采集路径
      - "/xxgk/zcfb/"
    keywords:                        # 关键词过滤
      - "低空经济"
      - "通用航空"
    update_frequency: "daily"        # 采集频率
    priority: "P0"                   # 优先级
```

**采集配置**部分还包含请求间隔、重试策略、超时设置、User-Agent、NER 引擎选择等参数。

### 6.2 行业词典 (`config/industry_dict.yaml`)

该文件是 NER 实体识别的增强词典，包含以下模块：

| 词典模块 | 用途 | 示例 |
|----------|------|------|
| `companies` | 企业名词典（NER 增强） | 大疆创新、亿航智能、峰飞航空... |
| `ner_blocklist_persons` | 非人物实体黑名单（NER 消歧） | 波音、空客、北斗、戴姆勒... |
| `policy_entities` | 政策法规实体关键词 | 型号合格证、TC 证、AOC... |
| `titles` | 职务词典 | 董事长、CEO、总工程师... |
| `meeting_types` | 会议类型词典 | 峰会、论坛、博览会... |
| `tech_domains` | 技术领域关键词 | eVTOL、适航认证、复合材料... |
| `policy_keywords` | 政策法规关键词 | 低空经济、空域改革、适航... |

> **提示**：添加新的监测企业时，需在 `companies` 列表中添加该企业的所有名称变体（中文名、英文名、简称）。

### 6.3 GitHub Secrets

在 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret** 中配置：

| Secret 名称 | 用途 | 是否必填 |
|-------------|------|----------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥，用于高级 AI 分析 | 可选 |
| `NOTIFICATION_WEBHOOK` | 通知 Webhook URL（飞书/钉钉/企业微信），采集完成后推送通知 | 可选 |

**配置通知 Webhook 的效果**：当每日采集任务完成（无论成功或失败），系统会自动向配置的 Webhook 发送通知消息，包含任务状态和完成时间。

**DeepSeek API Key 获取方式**：
1. 访问 https://platform.deepseek.com/
2. 注册并登录
3. 进入 API Keys → Create New Key
4. 复制 Key 填入 GitHub Secret

### 6.4 运行模式配置

`main.py` 支持三种运行模式，通过 `--mode` 参数控制：

| 模式 | 命令 | 执行步骤 |
|------|------|----------|
| `full` | `python scripts/main.py --mode full` | 采集 → 解析 → NER → 清洗+报告 → 深度分析 |
| `collect` | `python scripts/main.py --mode collect` | 仅采集 |
| `test` | `python scripts/main.py --mode test` | 仅采集第一个源 |

---

## 7. 常见问题 (FAQ)

### Q1: 如何添加新的数据源？

**A**: 新数据源需在 `scripts/feed_collector.py` 的 `SOURCES` 列表中添加配置：

```python
{
    "name": "新源名称",
    "type": "direct_html",      # 类型：rss / bing_rss / gov_html / direct_html
    "url": "https://example.com/news",
    "keywords": ["低空经济", "无人机"],  # 关键词过滤
    "priority": "P1",           # 优先级
    "parser": "generic",        # 解析器：generic / yuanxiangsky
    "max_articles": 30,         # 每次最多采集文章数
}
```

同时，如果新数据源涉及新的企业或术语，需在 `config/industry_dict.yaml` 的 `companies` 或 `tech_domains` 中补充对应词条，以提升 NER 识别准确率。添加后建议先用 `--mode test` 验证连通性。

### Q2: 如何添加新的监测企业？

**A**: 需要修改以下文件：

1. **`config/industry_dict.yaml`**：在 `companies` 列表中添加该企业的所有名称变体（中文名、英文名、简称），例如：
   ```yaml
   - "新企业名"
   - "NewCorp"
   - "新企"
   ```
2. **`config/sources.yaml`**：如需专门监测该企业官网，可在 `association_sources` 中添加
3. **`scripts/company_profiler.py`**：在企业画像配置中添加该企业，确保其被纳入深度画像范围

修改后运行 `python scripts/main.py --mode full`，新企业将出现在情报报告和知识图谱中。

### Q3: 采集结果为空怎么办？

**A**: 按以下步骤排查：

1. **检查 `googlenewsdecoder` 是否安装**：执行 `pip install googlenewsdecoder`，该库用于解码 Google News 跳转链接
2. **检查网络连通性**：GitHub Actions runner 网络正常即可访问 Google News RSS；本地运行需确保能访问 `news.google.com`
3. **查看运行日志**：检查 `logs/pipeline_YYYYMMDD.log` 中采集器的输出，确认 RSS 源是否返回数据
4. **检查关键词过滤**：确认 `config/sources.yaml` 和 `config/industry_dict.yaml` 中的关键词配置正确
5. **尝试测试模式**：运行 `python scripts/main.py --mode test`，确认第一个数据源能否正常采集
6. **检查 feed_state**：查看 `raw/feeds/feed_state.json`，确认采集状态是否异常（如时间戳过期）

### Q4: GitHub Actions 超时怎么办？

**A**: 每日采集工作流的超时限制为 45 分钟，可通过以下方式优化：

1. **减少数据源数量**：在 `scripts/feed_collector.py` 的 `SOURCES` 列表中暂时注释掉低优先级数据源
2. **降低 `max_articles` 参数**：减少每个数据源单次采集的文章数量上限
3. **使用分步执行**：先用 `collect` 模式采集数据，再手动触发 `full` 模式处理（已采集的数据不会重复采集）
4. **检查网络延迟**：某些政府网站响应较慢，可调整 `config/sources.yaml` 中 `collection.timeout` 参数
5. **优化并发**：全文解析步骤使用 ThreadPoolExecutor（5 线程并发），如需可调整 `main.py` 中的 `MAX_WORKERS` 参数

### Q5: 如何修改采集频率？

**A**: 采集频率通过 GitHub Actions 的 Cron 表达式控制，修改对应工作流文件即可：

- **每日采集** (`daily-collect.yml`)：修改 `on.schedule.cron` 字段
  ```yaml
  schedule:
    - cron: '0 8 * * *'    # 当前：每天 UTC 08:00（北京 16:00）
    - cron: '0 0,12 * * *' # 示例：每天 UTC 00:00 和 12:00（北京 08:00 和 20:00）
  ```
- **每周报告** (`weekly-report.yml`)：修改 `on.schedule.cron` 字段
  ```yaml
  schedule:
    - cron: '0 9 * * 1'    # 当前：每周一 UTC 09:00（北京 17:00）
  ```

> **注意**：GitHub Actions Cron 使用 UTC 时间，北京时间 = UTC + 8。GitHub 对定时任务的实际触发时间可能有数分钟延迟，属正常现象。

### Q6: 如何配置通知？

**A**: 通知通过 GitHub Secrets 中的 `NOTIFICATION_WEBHOOK` 配置：

1. 在目标群聊（飞书/钉钉/企业微信）中添加自定义机器人，获取 Webhook URL
2. 在 GitHub 仓库 **Settings → Secrets and variables → Actions → New repository secret** 中：
   - Name: `NOTIFICATION_WEBHOOK`
   - Value: 粘贴 Webhook URL
3. 配置完成后，每日采集任务结束时（无论成功或失败）会自动发送通知

通知消息格式为 JSON：`{"text": "低空经济情报采集任务完成\n状态: success\n时间: 2026-08-17 08:00 UTC"}`。如需自定义通知格式，可修改 `daily-collect.yml` 中的「发送通知」步骤。

### Q7: NER 实体识别不准确怎么办？

**A**: NER 使用 HanLP + spaCy 双引擎，通过以下方式提升准确率：

1. **检查模型加载**：确认 `python -m spacy download zh_core_web_sm` 已执行，HanLP 模型已正确安装
2. **完善企业词典**：在 `config/industry_dict.yaml` 的 `companies` 中补充遗漏的企业名称变体
3. **更新消歧黑名单**：如发现非人物实体被误识别为人物（如「波音」「北斗」），将其添加到 `ner_blocklist_persons` 列表中
4. **调整置信策略**：在 `config/sources.yaml` 的 `ner` 配置中，将 `confidence_threshold` 从 `intersection`（取交集，高精度）改为 `union`（取并集，高召回），或反之
5. **查看 NER 日志**：运行日志中会打印每条记录的 NER 结果（前 5 条和每 10 条打印一次），可用于诊断识别质量

### Q8: 如何更新 IMA 知识库内容？

**A**: IMA 知识库内容由 `ima_exporter.py` 自动生成，更新流程如下：

1. **触发更新**：手动运行 `python scripts/main.py --mode full`，或在 GitHub Actions 页面手动触发「每周情报报告生成」工作流
2. **生成交付文件**：流水线的 Step 5 会自动调用 IMA 导出器，生成以下文件：
   - `ima-export/company-cards/*.md`（企业卡片）
   - `ima-export/intel-digest/*.md`（情报摘要）
   - `ima-export/copilot-qa.md`（Copilot 问答对）
   - `ima-export/knowledge-index.json`（知识索引）
3. **导入 IMA 知识库**：在 IMA 管理后台中，将更新后的 `ima-export/` 目录文件重新导入，替换旧版本内容
4. **更新种子内容**（如需）：如需更新法规政策或行业标准库，编辑 `ima-seed-content/` 目录下的对应文件，并使用 `ima-config/batch-url-import.txt` 中的 URL 清单补充外部链接
5. **验证 Copilot**：导入后向 Copilot 提问验证回答质量，确保新内容已生效

> **提示**：IMA 知识库内容建议每周更新一次（与周报生成同步），以保持情报的时效性。

---

## 8. 技术支持

### 8.1 文档资源

| 文档 | 路径 | 说明 |
|------|------|------|
| 本用户指南 | `docs/USER_GUIDE.md` | 系统使用与操作指南 |
| 运维手册 | `docs/OPERATIONS.md` | 系统架构、工作流、故障排查、性能指标 |
| GitHub 配置指引 | `.github/SETUP_GUIDE.md` | 仓库创建、Secrets 配置、Actions 验证 |
| 项目说明 | `README.md` | 项目概述与快速开始 |

### 8.2 关键文件索引

| 文件 | 路径 | 用途 |
|------|------|------|
| 采集流水线主入口 | `scripts/main.py` | 流水线编排（5 步流程） |
| RSS 采集引擎 | `scripts/feed_collector.py` | RSS/Atom 采集 + URL 解码 |
| 网页解析器 | `scripts/parser.py` | Trafilatura 全文提取 |
| NER 实体提取 | `scripts/ner_extractor.py` | HanLP + spaCy 双引擎 NER |
| 数据清洗 | `scripts/cleaner.py` | 数据清洗与标准化 |
| 报告生成器 | `scripts/report_generator.py` | 周报数据生成 |
| 企业画像 | `scripts/company_profiler.py` | 企业深度画像构建 |
| 知识图谱 | `scripts/knowledge_graph.py` | 实体关系图谱构建 |
| 竞争分析 | `scripts/competitive_analysis.py` | 竞争格局分析 |
| 增强报告 | `scripts/enhanced_reporter.py` | 月度趋势 + 高管摘要 |
| IMA 导出 | `scripts/ima_exporter.py` | IMA 知识库交付文件生成 |
| 数据源配置 | `config/sources.yaml` | 数据源与采集参数 |
| 行业词典 | `config/industry_dict.yaml` | NER 增强词典 |
| 依赖清单 | `requirements.txt` | Python 依赖列表 |

### 8.3 在线资源

| 资源 | 地址 |
|------|------|
| GitHub 仓库 | https://github.com/smilemouse0980/low-altitude-intel |
| 报告预览站点 | https://smilemouse0980.github.io/low-altitude-intel/ |
| GitHub Actions | 仓库 → Actions 标签页 |
| DeepSeek 平台 | https://platform.deepseek.com/ |

### 8.4 性能指标参考

| 指标 | 目标值 |
|------|--------|
| 每日采集量 | 50-200 条 |
| URL 解析率 | > 80% |
| 全文提取率 | > 70% |
| NER 实体覆盖率 | > 90% |
| 流水线耗时 | < 15 分钟 |
| Google News 解码成功率 | > 60% |

### 8.5 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v3.0 | 2026-08-17 | googlenewsdecoder + 圆象网 sitemap + NER 消歧 + GitHub Pages |
| v2.0 | 2026-08-16 | Phase 2 深度分析（企业画像/知识图谱/竞争分析） |
| v1.0 | 2026-08-15 | 初始版本：RSS 采集 + NER + 周报 + GitHub Actions |

---

> **反馈与建议**：如在使用过程中遇到问题或有改进建议，请在 GitHub 仓库提交 Issue，或参考运维手册 (`docs/OPERATIONS.md`) 中的故障排查章节。
