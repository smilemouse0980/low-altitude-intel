# 低空经济情报系统 — 监控与持续运营计划

> 本文档定义低空经济情报系统的监控体系、告警配置、日常运维任务、故障处理流程、性能优化建议及备份恢复策略，保障系统每日稳定运行与数据质量持续可控。

---

## 1. 监控体系

### 1.1 GitHub Actions 监控

系统通过三个工作流实现自动化运转，需对其运行状态进行持续监控。

| 工作流 | 文件 | 触发方式 | 超时 |
|--------|------|----------|------|
| 每日采集 | `.github/workflows/daily-collect.yml` | `cron: '0 8 * * *'`（北京时间 16:00）+ 手动 | 45 分钟 |
| 每周报告 | `.github/workflows/weekly-report.yml` | `cron: '0 9 * * 1'`（北京时间周一 17:00）+ 手动 | 15 分钟 |
| Pages 部署 | `.github/workflows/deploy-pages.yml` | push 到 main（`docs/`、`reports/` 有变更）+ 手动 | 默认 |

#### 工作流状态检查方法

1. **GitHub Actions 页面检查**
   - 进入仓库 → `Actions` 标签页
   - 查看左侧工作流列表（每日采集 / 每周报告 / Pages 部署）
   - 绿色对勾表示成功，红色叉号表示失败，黄色圆圈表示运行中
   - 点击具体运行记录可查看每个 Step 的详细日志

2. **GitHub API 检查**（适合脚本化监控）

   ```bash
   # 查询最近 5 次每日采集工作流运行状态
   curl -H "Accept: application/vnd.github+json" \
     https://api.github.com/repos/{owner}/{repo}/actions/workflows/daily-collect.yml/runs?per_page=5
   ```

   关键字段：
   - `status`：`queued` / `in_progress` / `completed`
   - `conclusion`：`success` / `failure` / `cancelled` / `timed_out`

#### 失败告警配置

`daily-collect.yml` 已在最后一步配置通知步骤，依赖仓库 Secret `NOTIFICATION_WEBHOOK`：

```yaml
- name: 发送通知
  if: always() && env.NOTIFICATION_WEBHOOK != ''
  env:
    NOTIFICATION_WEBHOOK: ${{ secrets.NOTIFICATION_WEBHOOK }}
  run: |
    STATUS="${{ job.status }}"
    curl -X POST "$NOTIFICATION_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"text\": \"低空经济情报采集任务完成\n状态: $STATUS\n时间: $(date -u '+%Y-%m-%d %H:%M') UTC\"}" || true
```

- 触发条件：`if: always()`，无论成功或失败均发送通知
- 仅当 `NOTIFICATION_WEBHOOK` 已配置时触发，未配置则静默跳过（`!= ''`）
- 通知步骤失败不影响整体任务结果（`|| true`）

> 配置方法详见 [第 2.1 节 飞书/钉钉 Webhook 配置](#21-飞书钉钉-webhook-配置)。

#### 超时处理策略

- `daily-collect.yml` 设置 `timeout-minutes: 45`，超过 45 分钟自动取消
- `weekly-report.yml` 设置 `timeout-minutes: 15`
- 超时取消后，工作流状态显示为 `cancelled`，通知步骤仍会发送（`always()`）
- 超时常见原因及处理：
  1. 数据源响应慢 → 减少 `max_articles` 参数
  2. 网络抖动 → 手动触发 `workflow_dispatch` 重试
  3. 单次采集量过大 → 使用 `collect` 模式分步执行

---

### 1.2 数据质量监控

数据质量是情报系统的核心产出保障，需对采集、解析、提取、实体抽取、知识图谱各环节设定量化指标与告警阈值。

| 监控指标 | 检查方法 | 告警阈值 | 频率 |
|----------|----------|----------|------|
| 每日采集量 | 检查 `processed/intel_records.jsonl` 行数 | < 10 条告警 | 每日 |
| URL 解析率 | 检查原始 URL vs 解析 URL 数量比例 | < 60% 告警 | 每日 |
| 全文提取率 | 检查 `content` 字段非空率 | < 70% 告警 | 每日 |
| NER 实体覆盖率 | 检查 `entities` 字段非空率 | < 80% 告警 | 每日 |
| 知识图谱节点数 | 检查 `processed/knowledge_graph/graph_summary.json` | < 50 告警 | 每周 |

#### 各指标检查方法说明

**每日采集量**

```bash
# 统计当日情报条数
wc -l < processed/intel_records.jsonl
```

- 正常范围参考：`pipeline_summary.json` 中 `collected` 字段（当前样本为 81 条）
- 低于 10 条通常意味着数据源大面积不可达或采集器异常

**URL 解析率**

- 分子：成功解码/解析得到真实 URL 的记录数（依赖 `googlenewsdecoder`）
- 分母：采集到的原始 RSS 条目数
- 参考目标值（见 OPERATIONS.md）：> 80%；低于 60% 告警

**全文提取率**

- 检查 `intel_records.jsonl` 中每条记录的 `content` 字段
- 非空（且非纯空白）计为成功，统计非空率
- 依赖 `trafilatura` 全文提取器；低于 70% 通常因数据源页面结构变更

**NER 实体覆盖率**

- 检查 `entities` 字段（含 `orgs` / `persons` / `locations` 等）非空率
- 依赖 HanLP + spaCy 双引擎；低于 80% 需检查模型加载状态

**知识图谱节点数**

- 检查 `graph_summary.json` 中各类实体节点总数
- 当前样本含企业 8 家、地点 60+、技术 11 项等
- 每周由 `weekly-report.yml` 重建；低于 50 表明周报流水线异常

#### 数据质量检查脚本（建议）

可编写月度数据质量检查脚本（置于 `scripts/` 目录），自动输出上述五项指标报告。运行方式：

```bash
python scripts/data_quality_check.py
```

输出示例：

```
[数据质量检查] 2026-08-17
  每日采集量: 81 条 [OK]
  URL 解析率: 62.9% [WARN, 低于 80% 目标]
  全文提取率: 100.0% [OK]
  NER 实体覆盖率: 100.0% [OK]
  知识图谱节点数: 92 [OK]
```

---

### 1.3 GitHub Pages 监控

报告预览站点通过 `deploy-pages.yml` 部署到 GitHub Pages，需监控其可访问性与内容时效性。

#### 站点可访问性检查

- 访问 GitHub Pages 站点 URL（仓库 `Settings` → `Pages` 中查看）
- 预期响应：HTTP 200，页面正常加载 `docs/index.html`
- 失败表现：404、502 或长时间无响应

检查方法：

```bash
# HTTP 状态检查
curl -I https://{owner}.github.io/{repo}/
```

#### 报告更新检查

- 站点内容来源于 `docs/` 与 `reports/` 目录
- 每日采集提交后，`docs/` 或 `reports/` 变更触发 `deploy-pages.yml`
- 验证站点日报目录 `reports/YYYY-MM/` 中是否存在当日 `daily-YYYY-MM-DD.md`
- 验证站点摘要数据 `processed/pipeline_summary.json` 是否为最新时间戳

---

## 2. 告警配置

### 2.1 飞书/钉钉 Webhook 配置

工作流通知步骤依赖仓库 Secret `NOTIFICATION_WEBHOOK`。配置步骤如下：

1. **获取飞书/钉钉群机器人的 Webhook URL**
   - 飞书：群聊 → 设置 → 群机器人 → 添加机器人 → 自定义机器人 → 复制 Webhook 地址
     （格式：`https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxx`）
   - 钉钉：群聊 → 群设置 → 智能群助手 → 添加机器人 → 自定义 → 复制 Webhook 地址
     （格式：`https://oapi.dingtalk.com/robot/send?access_token=xxxxxxxx`）

2. **在 GitHub 仓库添加 Secret**
   - 进入仓库 `Settings` → `Secrets and variables` → `Actions`
   - 点击 `New repository secret`
   - Name 填写：`NOTIFICATION_WEBHOOK`
   - Secret 填写：上一步获取的完整 Webhook URL
   - 点击 `Add secret` 保存

3. **工作流自动发送运行状态**
   - `daily-collect.yml` 的「发送通知」步骤会在每次运行后自动触发
   - 仅当 `NOTIFICATION_WEBHOOK` 已配置时生效，未配置时静默跳过
   - 通知消息通过 `curl` POST 发送，格式见 [第 2.2 节](#22-告警消息格式)

> 其他相关 Secret：
> - `DEEPSEEK_API_KEY`：DeepSeek API 密钥（深度分析可选，见 OPERATIONS.md）

#### 飞书 Webhook 消息体适配说明

`daily-collect.yml` 当前使用通用 `{"text": "..."}` 格式。飞书自定义机器人默认支持该格式；钉钉自定义机器人需使用 `{"msgtype": "text", "text": {"content": "..."}}` 格式。如使用钉钉，可调整通知步骤中的 JSON 结构。

---

### 2.2 告警消息格式

通知步骤发送的告警消息格式如下：

```
低空经济情报采集任务完成
状态: success/failure
时间: 2026-08-17 16:00 UTC
运行模式: full
采集条数: XX
```

#### 字段说明

| 字段 | 取值 | 来源 |
|------|------|------|
| 状态 | `success` / `failure` / `cancelled` | `${{ job.status }}` |
| 时间 | `YYYY-MM-DD HH:MM UTC` | `$(date -u '+%Y-%m-%d %H:%M')` |
| 运行模式 | `full` / `collect` / `test` | `workflow_dispatch` 输入，默认 `full` |
| 采集条数 | 整数 | `pipeline_summary.json` 中 `collected` 字段 |

#### 完整通知步骤（含采集条数，建议增强版）

当前 `daily-collect.yml` 通知步骤仅含「状态」与「时间」。如需补充「运行模式」与「采集条数」，可改为：

```yaml
- name: 发送通知
  if: always() && env.NOTIFICATION_WEBHOOK != ''
  env:
    NOTIFICATION_WEBHOOK: ${{ secrets.NOTIFICATION_WEBHOOK }}
  run: |
    STATUS="${{ job.status }}"
    MODE="${{ github.event.inputs.mode || 'full' }}"
    COUNT=$(python -c "import json; print(json.load(open('processed/pipeline_summary.json')).get('collected', 0))" 2>/dev/null || echo "N/A")
    curl -X POST "$NOTIFICATION_WEBHOOK" \
      -H "Content-Type: application/json" \
      -d "{\"text\": \"低空经济情报采集任务完成\n状态: $STATUS\n时间: $(date -u '+%Y-%m-%d %H:%M') UTC\n运行模式: $MODE\n采集条数: $COUNT\"}" || true
```

---

## 3. 日常运维任务

| 频率 | 任务 | 操作 | 负责人 |
|------|------|------|--------|
| 每日 | 检查采集结果 | 查看 GitHub Actions 运行状态 | 运维 |
| 每日 | 检查日报 | 查看 `reports/YYYY-MM/daily-YYYY-MM-DD.md` | 运维 |
| 每周 | 检查周报 | 查看 `reports/YYYY-Wxx/weekly-report.md` | 分析师 |
| 每周 | 更新 IMA 知识库 | 导入 `ima-export/` 目录新文件 | 知识管理员 |
| 每月 | 检查数据质量 | 运行数据质量检查脚本 | 运维 |
| 每月 | 更新行业词典 | 添加新企业/术语到 `config/industry_dict.yaml` | 分析师 |
| 每季 | 评估数据源 | 检查数据源可用性和质量 | 运维 |

### 任务说明

**每日 — 检查采集结果**
- 上午查看前一日下午 16:00（北京时间）触发的 `daily-collect.yml` 运行状态
- 确认通知消息状态为 `success`
- 如失败，按 [4.1 采集失败](#41-采集失败) 流程处理

**每日 — 检查日报**
- 路径：`reports/{当前年月}/daily-{当日日期}.md`
- 确认日报已生成，条数合理，来源分布正常

**每周 — 检查周报**
- 路径：`reports/{当前年周}/weekly-report.md`（如 `reports/2026-W33/weekly-report.md`）
- 检查周报数据、企业画像、知识图谱、竞争格局分析、IMA 导出是否均完成

**每周 — 更新 IMA 知识库**
- 将 `ima-export/` 目录下新生成的企业卡片、情报摘要、批量导入文件导入 IMA 知识库
- 参照 `ima-config/batch-url-import.txt` 与 `ima-export/batch-import.txt`

**每月 — 检查数据质量**
- 运行数据质量检查脚本（见 1.2 节）
- 对照五项核心指标阈值，记录趋势

**每月 — 更新行业词典**
- 在 `config/industry_dict.yaml` 中：
  - `companies`：补充新出现的企业
  - `ner_blocklist_persons`：补充误识别为人物的实体
  - `tech_domains`、`policy_entities`：补充新术语与政策实体

**每季 — 评估数据源**
- 检查 `config/sources.yaml` 中各数据源可用性
- 评估采集量、URL 解析率、全文提取率趋势
- 剔除失效源，补充优质源

---

## 4. 故障处理流程

### 4.1 采集失败

1. **检查 GitHub Actions 日志**
   - 进入 `Actions` → 对应运行记录 → 展开失败的 Step
   - 定位失败发生在采集 / 解析 / NER / 清洗 / 提交 哪一步

2. **确认数据源网站可访问**
   - Google News RSS、圆象低空经济观察、国务院政策搜索
   - 本地或 runner 环境手动访问数据源 URL 验证

3. **手动触发 workflow_dispatch 重试**
   - `Actions` → 「每日低空经济情报采集」→ `Run workflow`
   - 选择运行模式：`full`（完整）/ `collect`（仅采集）/ `test`（测试单源）
   - 优先用 `test` 模式快速验证，再用 `full` 完整执行

4. **如持续失败，检查 googlenewsdecoder 依赖**
   ```bash
   pip install googlenewsdecoder
   ```
   - 查看 `logs/pipeline_YYYYMMDD.log` 中采集器输出
   - 确认 `googlenewsdecoder` 解码成功率（目标 > 60%）

### 4.2 NER 质量下降

1. **检查 HanLP 和 spaCy 模型加载状态**
   - 查看 `logs/pipeline_YYYYMMDD.log` 中 NER 引擎初始化日志
   - 确认 `zh_core_web_sm` 模型已安装：
     ```bash
     python -m spacy download zh_core_web_sm
     ```

2. **审查新出现的误识别实体**
   - 检查 `processed/knowledge_graph/graph_summary.json` 中 `persons` 列表
   - 识别明显非人物实体（如地名、技术名词被误判为人物）
   - 当前样本中 `persons` 含 `Tiltrotor`，属误识别典型

3. **添加到 ner_blocklist_persons 或 non_person_terms**
   - 编辑 `config/industry_dict.yaml`
   - 在 `ner_blocklist_persons` 列表下添加误识别实体（如国家名、地名、技术名词）
   - 参考已有条目格式（如 `"戴姆勒"`、`"北斗"`、`"阿联酋"`）

4. **提交并推送更新**
   ```bash
   git add config/industry_dict.yaml
   git commit -m "fix(ner): 屏蔽误识别实体 XXX"
   git push
   ```
   - 下次 `daily-collect.yml` 运行时自动生效

### 4.3 Pages 部署失败

1. **确认仓库为 public**
   - GitHub Pages 私有仓库需 Pro/Team 计划
   - `Settings` → `General` → 末尾 `Danger Zone` 查看可见性

2. **检查 Pages 设置（Source: GitHub Actions）**
   - `Settings` → `Pages` → `Build and deployment`
   - `Source` 必须设置为 `GitHub Actions`（而非 `Deploy from a branch`）

3. **手动触发 deploy-pages.yml**
   - `Actions` → 「部署报告站点到 GitHub Pages」→ `Run workflow`
   - 查看运行日志，确认 `upload-pages-artifact` 与 `deploy-pages` 两步成功
   - 检查 `permissions` 中 `pages: write` 与 `id-token: write` 权限正常

---

## 5. 性能优化建议

- **增量采集**：基于 `raw/feeds/feed_state.json` 记录的已采集 URL 哈希，避免重复采集同一文章，减少无效网络请求与处理开销。

- **并发优化**：使用 `ThreadPoolExecutor` 并行采集多个数据源（Google News RSS × 6、圆象网 HTML × 3、国务院政策搜索），缩短总采集耗时，确保 45 分钟超时内完成。

- **缓存策略**：缓存 `googlenewsdecoder` URL 解析结果，对相同 RSS 条目避免重复解码请求；缓存 `trafilatura` 全文提取结果以应对重试场景。

- **数据归档**：定期归档历史数据（`raw/`、`processed/` 中早期文件）到单独分支或 release，保持主分支仓库体积可控，加速 `actions/checkout` 与 Pages 部署。

---

## 6. 备份与恢复

- **Git 仓库自动备份（GitHub 内置）**：所有采集结果、报告、配置通过 `daily-collect.yml` 与 `weekly-report.yml` 自动提交并推送，GitHub 托管提供版本历史与远端冗余，可通过任意提交回滚恢复。

- **IMA 知识库定期导出**：`weekly-report.yml` 调用 `ima_exporter.py` 生成 `ima-export/` 目录下的企业卡片、情报摘要与批量导入文件，定期将这些文件导入 IMA 知识库作为知识资产的第二份拷贝。

- **配置文件版本控制**：`config/industry_dict.yaml`、`config/sources.yaml`、`ima-config/` 下所有配置均纳入 Git 版本控制，词典与黑名单的每次调整可追溯、可回滚。

- **报告文件永久保存**：日报（`reports/YYYY-MM/`）、周报（`reports/YYYY-Wxx/`）、企业深度报告、竞争格局分析、高管摘要等 Markdown 报告永久保存在 Git 历史中，即使文件被删除仍可通过 commit 历史恢复。

---

## 附：相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| 运维手册 | `docs/OPERATIONS.md` | 系统架构、数据源配置、工作流说明、性能指标 |
| 用户指南 | `docs/USER_GUIDE.md` | 使用说明 |
| 配置指南 | `.github/SETUP_GUIDE.md` | 初始部署配置 |
| 行业词典 | `config/industry_dict.yaml` | 企业词典、NER 消歧黑名单 |
| 数据源配置 | `config/sources.yaml` | 采集数据源列表 |

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v1.0 | 2026-08-17 | 初始版本：监控体系、告警配置、运维任务、故障处理、性能优化、备份恢复 |
