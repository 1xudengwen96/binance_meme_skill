import json
import logging
import httpx
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
        # 修复代理冲突问题：显式创建一个 httpx 客户端
        http_client = httpx.Client(
            follow_redirects=True,
        )

        self.client = OpenAI(
            api_key=config.GROK_API_KEY,
            base_url=config.GROK_BASE_URL,
            http_client=http_client
        )
        # 升级到最新的旗舰推理模型 Grok-4
        # 该模型具备更强的逻辑推理和实时流量分析能力
        self.model = "grok-4"

    def analyze_token_traffic(self, token_data: dict) -> dict:
        """
        利用 Grok 分析特定代币在 X 上的实时热度与情绪
        """
        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        progress = token_data.get("progress", "Unknown")

        # Grok-4 特有的推理引导提示词
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
        请严格以 JSON 格式输出你的分析结果。不要包含任何 markdown 标记。
        必须包含以下两个字段：
        {{
            "rating": "S 或 A 或 B 或 F",
            "summary": "100字以内的推特流量分析和一句话最终点评"
        }}

        【评级标准】
        S: 流量爆炸，情绪真实 FOMO，KOL 密集喊单。
        A: 有一定的真实用户讨论度，处于早期酝酿。
        B: 讨论寥寥无几，不建议参与。
        F: 纯机器号、项目方刷屏或存在致命负面预警。
        """

        try:
            logging.info(f"正在请求 Grok-4 分析代币 ${symbol} 的推特流量...")
            # Grok-4 是原生推理模型，会自动进行思维链分析
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "你是一个严谨的 Web3 数据分析师，必须使用纯 JSON 格式输出结果，严禁返回非 JSON 文本。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
            )

            result_text = response.choices[0].message.content.strip()

            # 清理可能的 Markdown 标记（Grok-4 有时会带上以确格式化）
            if "```" in result_text:
                result_text = result_text.replace("```json", "").replace("```", "").strip()

            analysis_result = json.loads(result_text)
            logging.info(f"代币 ${symbol} 的 Grok-4 评级为: {analysis_result.get('rating')}")

            return analysis_result

        except Exception as e:
            logging.error(f"Grok API 请求异常: {e}")
            return {"rating": "Error", "summary": f"请求 Grok-4 异常: {str(e)}"}


# 实例化提供给其他模块使用
grok_api = GrokXAIAPI()