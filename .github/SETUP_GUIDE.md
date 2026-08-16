# GitHub 仓库配置指引

## 1. 创建私有仓库

1. 登录 GitHub → 点击 New repository
2. 仓库名称：`low-altitude-intel`
3. 可见性：**Private**（私有）
4. 不要勾选 "Add a README file"（已有 README）
5. 点击 Create repository

## 2. 上传项目代码

```bash
# 初始化 Git 仓库
cd low-altitude-intel
git init
git add .
git commit -m "feat: Phase 1C 初始化 — 采集流水线 + GitHub Actions"

# 关联远程仓库（替换为你的仓库地址）
git remote add origin https://github.com/YOUR_USERNAME/low-altitude-intel.git
git branch -M main
git push -u origin main
```

## 3. 配置 GitHub Secrets

进入仓库 Settings → Secrets and variables → Actions → New repository secret

| Secret 名称 | 值 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 你的 DeepSeek API Key | 用于高级 AI 分析（可选） |
| `NOTIFICATION_WEBHOOK` | 企业微信/飞书/钉钉 Webhook URL | 采集完成后发送通知（可选） |

### DeepSeek API Key 获取方式
1. 访问 https://platform.deepseek.com/
2. 注册并登录
3. API Keys → Create New Key
4. 复制 Key 填入 GitHub Secret

## 4. 验证 GitHub Actions

1. 进入仓库 Actions 页面
2. 应能看到两个工作流：
   - `每日低空经济情报采集`
   - `每周情报报告生成`
3. 点击 `每日低空经济情报采集` → Run workflow → 选择 `test` 模式 → Run
4. 查看运行日志确认无报错

## 5. 定时任务说明

| 工作流 | Cron 表达式 | 运行时间（北京时间） | 说明 |
|--------|------------|-------------------|------|
| 每日采集 | `0 8 * * *` | 每天 16:00 | RSS 采集 + 解析 + NER + 清洗 |
| 每周报告 | `0 9 * * 1` | 每周一 17:00 | 生成周报数据 |

> GitHub Actions cron 使用 UTC 时间，北京时间 = UTC + 8

## 6. 手动触发

在 Actions 页面选择工作流 → 点击 "Run workflow" → 选择模式：
- `full`：完整流水线（采集 + 解析 + NER + 清洗 + 报告）
- `collect`：仅采集（快速模式）
- `test`：测试模式（采集1个源验证连通性）
