import json
import logging
from openai import OpenAI
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokXAIAPI:
    """
    封装 Grok (xAI) 的接口
    负责通过 X (Twitter) 的流量和情绪来交叉验证链上代币
    """

    def __init__(self):
        # Grok 官方全面兼容 OpenAI SDK，只需替换 api_key 和 base_url
        self.client = OpenAI(
            api_key=config.GROK_API_KEY,
            base_url=config.GROK_BASE_URL
        )
        # 指定使用的模型，建议使用最新的 grok 模型以获取最好的联网搜索能力
        self.model = "grok-beta"

    def analyze_token_traffic(self, token_data: dict) -> dict:
        """
        利用 Grok 分析特定代币在 X 上的实时热度与情绪
        """
        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        progress = token_data.get("progress", "Unknown")

        # 精心设计的 Prompt，引导 Grok 查数据并输出固定格式
        prompt = f"""
        你是一个顶级的 Web3 Meme 币投研专家。我刚在链上发现了一个早期的优质代币。

        【代币基本信息】
        - 代币名称: ${symbol}
        - 合约地址(CA): {ca}
        - 内盘进度: {progress}% (即将上线DEX)

        【你的任务】
        请立刻利用你的 X (Twitter) 搜索能力，查验这个合约地址（{ca}）或代币名称（${symbol}）目前的真实热度：
        1. 过去 2 小时内的推文讨论量大吗？
        2. 有没有粉丝量较大的 KOL 在提及或喊单？
        3. 评论区和推文情绪是真实的 FOMO，还是明显的机器号刷评论？
        4. 是否有用户在提示 rug、scam 等负面预警？

        【输出格式要求】
        请严格以 JSON 格式输出你的分析结果，不要包含任何 markdown 标记（如 ```json），直接输出 JSON 字符串。
        必须包含以下两个字段：
        {{
            "rating": "S 或 A 或 B 或 F",
            "summary": "100字以内的推特流量分析和一句话最终点评"
        }}

        【评级标准】
        S: 流量爆炸，有知名 KOL 喊单，情绪真实 FOMO，无软跑路迹象。
        A: 有一定的真实用户讨论度，处于早期酝酿阶段。
        B: 讨论寥寥无几，几乎无人关注。
        F: 纯机器号刷屏，或者出现大量 rug/scam 的负面预警。
        """

        try:
            logging.info(f"正在请求 Grok 分析代币 ${symbol} 的推特流量...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "你是一个严谨的 Web3 数据分析师，你必须强制使用纯 JSON 格式输出结果，拒绝任何其他废话。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # 保持较低温度，让输出更客观、格式更稳定
            )

            result_text = response.choices[0].message.content.strip()

            # 清理大模型可能不听话带上的 Markdown 标记
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[-1]
            if result_text.endswith("```"):
                result_text = result_text.rsplit("\n", 1)[0]
            result_text = result_text.replace("```json", "").replace("```", "").strip()

            analysis_result = json.loads(result_text)
            logging.info(f"代币 ${symbol} 的 Grok 评级为: {analysis_result.get('rating')}")

            return analysis_result

        except json.JSONDecodeError:
            logging.error(f"Grok 返回了非预期的 JSON 格式: {result_text}")
            return {"rating": "Error", "summary": "解析 Grok 返回数据失败，返回格式不规范。"}
        except Exception as e:
            logging.error(f"Grok API 请求异常: {e}")
            return {"rating": "Error", "summary": f"请求 Grok 异常: {str(e)}"}


# 实例化提供给其他模块使用
grok_api = GrokXAIAPI()