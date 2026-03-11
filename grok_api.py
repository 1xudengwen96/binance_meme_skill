import requests
import json
import logging
import time
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokAPI:
    """
    对接 xAI Grok 的接口，专职负责 Meme 币的社交潜力与病毒式传播分析
    猎人实战版 V4：引入多维 Degen 审美（Ticker浓度、PvP防身、聪明钱与市值上下文感知）
    """

    def __init__(self):
        self.api_key = config.GROK_API_KEY
        self.base_url = config.GROK_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def analyze_meme_potential(self, token: dict, max_retries=2) -> dict:
        """
        调用 Grok 分析代币的社交热度与病毒潜质
        返回格式: {"rating": "S/A/Neutral/F", "summary": "分析摘要"}
        """
        if not self.api_key or self.api_key.startswith("xai-your"):
            logging.warning("⚠️ GROK_API_KEY 未配置，跳过 AI 分析，默认返回 S 级(测试模式)")
            return {"rating": "S", "summary": "[测试模式] 默认放行"}

        symbol = token.get('symbol', 'Unknown')
        ca = token.get('contractAddress', 'Unknown')
        progress = token.get('progress', 0)

        # 获取由主引擎注入的上下文数据
        mcap = token.get('marketCap', 0)
        sm_count = token.get('smart_money_count', 0)
        sm_inflow = token.get('smart_money_inflow', 0.0)

        # [核心优化] 顶级猎人 Prompt：加入市值上下文、Ticker 浓度、PvP 防身与突发新闻一票否决/通过
        prompt = f"""
        你现在是一名顶级的 Web3 Degen 和 Meme 币星探，你的嗅觉极其敏锐。
        你的任务是分析该链上的 Meme 代币：${symbol} 
        合约地址(CA): {ca}
        当前进度: {progress}%
        当前市值(MCAP): ${mcap}
        聪明钱雷达: {sm_count} 个聪明钱地址已介入，净流入 ${sm_inflow}

        【分析焦点】
        请忽略常规的合约安全审计，专注于 X (Twitter) 上的社交数据与纯粹的 Meme 基因：
        1. 病毒潜质 (Virality)：该代币的概念是否好玩、易于传播、具备做成表情包(Meme)的魔力？
        2. Ticker 浓度 (Ticker Quality)：代号（${symbol}）是否简洁有力、朗朗上口（如 $POPCAT, $WIF 等经典风格）？
        3. 真实社区讨论：搜索推特，是否有真实的 Web3 玩家或 KOL 在讨论？还是全是 0 粉丝的 Bot 账号在刷屏？结合当前市值 ${mcap} 评估，如果极低市值却有异常高频的讨论，需警惕刷量。
        4. PvP 与仿盘判定 (Copycat Check)：它是否是已经烂大街的“第 N 个某某龙”或“第 N 个马斯克宠物”？如果是劣质的蹭热度仿盘，必须严厉降级！

        【评级标准 - 极度重要】
        - S级 (全仓抢入)：必须满足 Ticker 优质且概念新颖，同时有知名 KOL 讨论或社区有自发二创。⚠️【特权规则】：如果 ${symbol} 精准命中了最近 24 小时内的突发大新闻（如马斯克新推文、重大政治/科技事件），且 Ticker 具有唯一性，请无视社交粉丝量，直接提升至 S 级！配合聪明钱底仓，这是绝佳胜率。
        - A级 (半仓尝试)：有一定热度，概念不错，非明显劣质仿盘，且有部分聪明钱 ({sm_count}人) 在建仓，社区文化在初期酝酿中。
        - Neutral级 (中立观察)：【防误杀保护机制！】如果这是一个市值较低的纯新币，X (Twitter) 上暂时搜不到太多有效信息，这是极其正常的！只要 Ticker 顺口、概念不引起反感、没有明显的烂大街仿盘特征，请务必给它 Neutral 评级，给它发育的时间！
        - F级 (放弃)：能搜到大量内容但全是僵尸号在机械发推(Rug前兆)；或者名字完全是对知名项目的劣质拼凑和拙劣模仿（明显的烂大街 PvP 盘）。

        【必须严格遵守的返回格式】
        你只能返回纯 JSON，不能有任何多余的解释。
        示例: {{"rating": "Neutral", "summary": "纯新币，X上暂无有效讨论，但 Ticker($WUF) 简洁，无劣质仿盘特征，聪明钱已介入，给予发育时间。"}}
        """

        payload = {
            "model": config.GROK_MODEL,
            "messages": [
                {"role": "system",
                 "content": "You are a highly analytical AI that outputs ONLY strict JSON formatted data. Do not use markdown blocks."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 300
        }

        retries = 0
        while retries <= max_retries:
            try:
                logging.info(
                    f"🧠 [Grok] 开始对 {symbol} 进行社交体检 (模型: {config.GROK_MODEL}) (第 {retries + 1} 次尝试)...")
                response = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload,
                                         timeout=15)

                if response.status_code != 200:
                    logging.warning(f"⚠️ [Grok] 服务器驳回请求: HTTP {response.status_code} | 详情: {response.text}")

                response.raise_for_status()

                result_json = response.json()
                content = result_json['choices'][0]['message']['content'].strip()

                # 增强版：清洗 Markdown 标记，防止 JSON 解析报错
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                parsed_data = json.loads(content)

                # 规范化评级，把默认兜底从 F 改为 Neutral，保护初生牛犊
                rating = str(parsed_data.get("rating", "Neutral")).capitalize()
                if rating not in ["S", "A", "Neutral", "F"]:
                    rating = "Neutral"

                return {
                    "rating": rating,
                    "summary": parsed_data.get("summary", "Grok 返回了格式无法解析的摘要。")
                }

            except requests.exceptions.RequestException as e:
                logging.warning(f"⚠️ [Grok] API 网络请求失败: {e}")
                retries += 1
                time.sleep(2)
            except json.JSONDecodeError as e:
                logging.error(f"❌ [Grok] 返回格式解析失败，非合法 JSON: {e} | 返回内容: {content}")
                # 熔断保护时，返回 Neutral 而不是 F
                return {"rating": "Neutral", "summary": "AI 返回格式异常，进入防误杀保护机制。"}
            except Exception as e:
                logging.error(f"❌ [Grok] 发生未知错误: {e}")
                # 熔断保护
                return {"rating": "Neutral", "summary": f"系统错误: {str(e)}"}

        logging.error(f"❌ [Grok] 对 {symbol} 的分析在重试 {max_retries} 次后彻底失败。")
        return {"rating": "Neutral", "summary": "API 请求持续超时或失败，默认中性放行。"}


# 实例化单例
grok_api = GrokAPI()