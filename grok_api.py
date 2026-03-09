import requests
import json
import logging
import time
from config import config

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokAPI:
    """
    对接 xAI Grok 的接口，专职负责 Meme 币的社交潜力与病毒式传播分析
    猎人实战版：修复“冷启动”误杀问题，拥抱零社交数据的新生头矿
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

        # [整改] 核心 Prompt 优化：解决纯新币无数据被误判为垃圾币(F)的问题
        # [修复] 移除硬编码的 Solana/BSC，改为通用的“该链上”，避免 AI 产生跨链幻觉
        prompt = f"""
        你现在是一名顶级的 Web3 Degen 和 Meme 币星探。
        你的任务是分析该链上的 Meme 代币：${symbol} 
        合约地址(CA): {ca}
        当前进度: {progress}%

        【分析焦点】
        请忽略常规的合约安全审计（这部分已有其他系统完成）。你需要专注于 X (Twitter) 上的社交数据：
        1. 病毒潜质 (Virality)：该代币的名称、Logo 或概念是否好玩、易于传播、具备做成表情包(Meme)的潜力？
        2. 真实社区讨论：搜索推特，是否有真实的 Web3 玩家或 KOL 在讨论？还是全是 0 粉丝的机器人(Bot)账号在机械式发推？
        3. 叙事契合度：它是否属于当前最热的叙事（如：AI 代理、热门动物、名流相关）？

        【评级标准 - 极度重要】
        - S级 (全仓抢入)：有知名 KOL 讨论，社区有自发的二创图片/视频，叙事顶级且新颖。
        - A级 (半仓尝试)：有一定热度，概念不错，但社区文化还在初期酝酿中。
        - Neutral级 (中立观察)：由于是刚发射的新币，X (Twitter) 上暂时搜索不到太多有效信息，但这很正常，概念不反感即可。
        - F级 (放弃)：能搜到大量内容，但全是僵尸号/机器人在刷屏(Rug前兆)，或者名字完全是对知名项目的拙劣模仿(貔貅盘特征)。

        【必须严格遵守的返回格式】
        示例: {{"rating": "Neutral", "summary": "纯新币，社交媒体暂无讨论，但概念属近期热门的猫系，需观望。"}}
        """

        # 【破案修复】换回你之前能跑通的确切模型名称
        payload = {
            "model": "grok-2-latest",
            "messages": [
                {"role": "system",
                 "content": "You are a highly analytical AI that outputs ONLY strict JSON formatted data."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.5,
            "max_tokens": 300
        }

        retries = 0
        while retries <= max_retries:
            try:
                logging.info(f"🧠 [Grok] 开始对 {symbol} 进行社交体检 (第 {retries + 1} 次尝试)...")
                response = requests.post(f"{self.base_url}/chat/completions", headers=self.headers, json=payload,
                                         timeout=15)

                # 拦截并打印出真实的报错信息
                if response.status_code != 200:
                    logging.warning(f"⚠️ [Grok] 服务器驳回请求: HTTP {response.status_code} | 详情: {response.text}")

                response.raise_for_status()

                result_json = response.json()
                content = result_json['choices'][0]['message']['content'].strip()

                # 清洗可能带有的 markdown 标记
                if content.startswith("```json"):
                    content = content[7:]
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
                return {"rating": "Neutral", "summary": "AI 返回格式异常，进入防误杀保护。"}
            except Exception as e:
                logging.error(f"❌ [Grok] 发生未知错误: {e}")
                # 熔断保护
                return {"rating": "Neutral", "summary": f"系统错误: {str(e)}"}

        logging.error(f"❌ [Grok] 对 {symbol} 的分析在重试 {max_retries} 次后彻底失败。")
        return {"rating": "Neutral", "summary": "API 请求持续超时或失败，默认中性放行。"}


# 实例化单例
grok_api = GrokAPI()