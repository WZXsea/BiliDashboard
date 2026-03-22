# 🎬 BiliDashboard — B站个人早报看板

一键生成你的**B站每日个人回顾看板**，包含观看历史、全站热门、科技动态、关注UP主更新，并由 AI 撰写趣味每日点评。

![Dashboard Preview](https://img.shields.io/badge/B站-早报看板-00A1D6?style=for-the-badge&logo=bilibili&logoColor=white)

## ✨ 功能特性

- 📊 **每日观看时长统计** — 自动计算昨日观看总时长
- 👀 **历史足迹回顾** — 展示最近观看的视频
- 🔥 **全站热门 & 科技动态** — 一览今日热榜
- 📢 **关注UP主动态追踪** — 自动抓取你关注的UP主/官号近 24h 内的动态和投稿
- 🤖 **AI 每日点评** — 由 Kimi AI 生成幽默风趣的个人观看报告
- 🌙 **深色/浅色主题** — 一键切换
- 📦 **每日快照归档** — 自动保存每天的报告快照
- 🔔 **macOS 原生通知** — 生成完毕自动弹窗提醒

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/BiliDashboard.git
cd BiliDashboard
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置

```bash
# 复制配置模板
cp config.example.yaml config.yaml

# 编辑配置文件，填入你的信息
```

打开 `config.yaml`，填写：

- **`kimi_api_key`** — Kimi AI 的 API Key（[获取地址](https://platform.moonshot.cn/console/api-keys)）
- **`tracked_uids`** — 你想追踪的 UP主列表（格式：`名称: UID`）

> 💡 **如何找到 UP主 的 UID？**  
> 打开 UP主 的空间页，URL 中的数字即为 UID。  
> 例如 `https://space.bilibili.com/401742377` → UID 为 `401742377`

### 4. 运行

```bash
python bili_daily_report.py
```

首次运行时会弹出 B站登录二维码，使用 B站 App 扫码登录。登录凭据会自动保存，后续运行无需重复登录。

运行完成后会**自动在浏览器中打开**你的专属每日看板 🎉

## 📁 项目结构

```
BiliDashboard/
├── README.md              # 本文件
├── requirements.txt       # Python 依赖清单
├── config.example.yaml    # 配置模板（需复制为 config.yaml）
├── .gitignore             # Git 忽略规则
├── bili_daily_report.py   # 🐍 主程序：数据抓取 + AI 总结 + 报告生成
├── index.html             # 🌐 前端页面
├── app.js                 # ⚙️ 前端渲染逻辑
└── styles-v5.css          # 🎨 前端样式
```

运行后会自动生成以下目录（已被 `.gitignore` 忽略）：

```
├── config.yaml            # 你的个人配置
├── data/                  # 登录凭证、趋势缓存
├── daily_notes/           # 每日快照归档
│   └── 2026-03-22/
│       ├── index.html
│       ├── latest_report.js
│       └── ...
├── latest_report.js       # 最新报告数据
└── time_trend.js          # 观看趋势数据
```

## ⏰ 定时运行（可选）

使用 `crontab` 设置每日自动生成：

```bash
crontab -e
```

添加以下行（每天早上 9 点运行）：

```
0 9 * * * cd /path/to/BiliDashboard && /path/to/python bili_daily_report.py >> daily_cron.log 2>> daily_cron.err
```

## 🛠️ 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.10+, bilibili-api-python, httpx |
| AI | Kimi (Moonshot) API |
| 前端 | 原生 HTML/CSS/JS, Chart.js, marked.js, Ionicons |
| 设计 | Glassmorphism, 深色主题, 响应式布局 |

## 📄 License

MIT License
