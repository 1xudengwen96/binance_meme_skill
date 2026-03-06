🛡️ Meme Hunter Pro V2.0

叙事对齐 & 聪明钱追踪全自动作战系统

Meme Hunter Pro 是一款专为专业 Meme 交易者打造的自动化猎狗工具。它深度集成了 Binance Web3 数据、Grok-4 AI 社交审计以及实时可视化监控大盘，旨在帮助你在极高风险的 Meme 市场中锁定具备“叙事、资金、安全”三合一属性的优质标的。

🚀 核心功能特性

三轨并发探测：

新币榜 (New)：监控进度 > 50% 的高热度早期项目。

打满榜 (Finalizing)：锁定即将打满 Bonding Curve 并迁移至 DEX 的准现货。

已迁移榜 (Migrated)：监控刚完成迁移、流动性已锁定的热点标的。

情报双重交叉验证：

叙事对齐 (Topic Rush)：自动比对币安实时热点话题，识别具备 Viral 病毒潜质的项目。

聪明钱追踪 (Smart Money Inflow)：实时监控币安链上精英地址的买入净流入金额。

多维度安全堡垒：

币安深度审计：利用 Binance Token Audit 接口一票否决代码风险（Honeypot, Mint, 权限未丢弃等）。

Grok-4 社交层反诈：AI 实时检索 X (Twitter) 舆情，识别机器人刷屏和真实社区。

极致交易交互：

赛博作战大盘：单文件 HTML 仪表盘，支持实时跳动数据和 S 级预警。

一键直达交易：推送消息集成 Deeplink，移动端点击按钮直接拉起币安 App Web3 钱包极速成交。

🛠️ 安装与部署

1. 克隆项目并安装依赖

确保你的环境已安装 Python 3.9+。

pip install -r requirements.txt


2. 环境配置

复制 .env.example 并重命名为 .env，填入你的密钥：

GROK_API_KEY: x.ai 官方提供的 API Key。

TG_BOT_TOKEN / FEISHU_WEBHOOK_URL: 用于接收手机端推送。

SCAN_INTERVAL_SECONDS: 建议设为 30，追求极致可设为 5。

3. 文件结构

请确保以下文件处于同一目录下：

main.py 
api_server.py 
sniper_engine.py 
binance_api.py  
grok_api.py 
config.py  
tg_bot.py 
feishu_bot.py
index.html (前端作战大盘)

🎮 如何使用

启动系统

在终端运行：

python main.py


启动后会自动发生：

后台引擎开始轮询链上数据，发现目标后会触发 Grok 审计。

API 网关启动在 http://localhost:8000。

浏览器自动弹出：1.5 秒后会自动打开可视化大盘。

界面解读

红色呼吸灯 (S级)：最高优先级！叙事、资金、安全全部拉满，建议重点关注。

蓝色面板 (A/B级)：有潜力，但可能叙事尚早或资金流入不够集中。

今日战果统计：实时显示今日扫描总量、拦截的 Rug 数量以及发现的金狗数。

📈 交易策略建议

看大买小：如果大盘显示“叙事热点”中出现了相关话题，且“聪明钱”持续净流入，这类币的翻倍概率极高。

拒绝 F 级：机器人拦截的 Rug 比例通常在 80% 以上，严禁手动去买那些被系统跳过的代币。

一键复制：在大盘上点击 CA 右侧的复制图标，即可快速在任何交易工具中使用。

⚠️ 免责声明

Meme 币波动巨大，本项目仅作为数据辅助决策工具。系统无法预知项目方在代码审计之后的恶意行为。请永远用你能承受损失的资金进行博弈！
