import json
import logging
import httpx
import re
from openai import OpenAI
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GrokXAIAPI:
    """
    封装 Grok (xAI) 的接口 - 社交安全审计鲁棒版
    针对 Grok-4 返回非标准 JSON 的情况增加了强力解析逻辑
    """

    def __init__(self):
        # 修复可能的代理冲突
        http_client = httpx.Client(
            follow_redirects=True,
        )

        self.client = OpenAI(
            api_key=config.GROK_API_KEY,
            base_url=config.GROK_BASE_URL,
            http_client=http_client
        )
        # 采用旗舰推理模型
        self.model = "grok-4"

    def _extract_json(self, text: str) -> dict:
        """
        鲁棒地从模型返回的杂乱文本中提取并解析 JSON 对象
        """
        try:
            # 1. 尝试直接解析（理想情况）
            return json.loads(text)
        except json.JSONDecodeError:
            # 2. 如果直接解析失败，尝试通过正则表达式匹配第一个 { 到最后一个 }
            logging.warning("直接解析 JSON 失败，尝试正则提取...")
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

            # 3. 如果包含 Markdown 代码块，手动清理后再试
            clean_text = text.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                return None

    def analyze_token_traffic(self, token_data: dict) -> dict:
        """
        利用 Grok 进行社交层面的“反诈”分析，增加解析容错
        """
        symbol = token_data.get("symbol", "Unknown")
        ca = token_data.get("contractAddress", "Unknown")
        progress = token_data.get("progress", "Unknown")

        # 强化提示词：要求 AI 严禁输出无关字符
        prompt = f"""
        你现在是一名顶级的链上安全分析师。请通过 X (Twitter) 实时搜索功能审计以下代币。

        【待审计代币】
        - 符号: ${symbol}
        - 合约地址: {ca}
        - 进度: {progress}%

        【任务清单】
        1. **反诈预警**：搜索 "{ca} rug" 或 "{ca} scam"，确认是否有真实的负面反馈。
        2. **权限透明度**：开发者是否宣布销毁 LP 或丢弃权限？
        3. **推特情绪**：辨别推文是机器人刷屏还是真实的 Web3 社区在讨论。
        4. **KOL 背书**：是否有真实的大 V (50k+ followers) 在提及。

        【输出要求】
        必须严格以 JSON 格式输出，严禁包含任何 Markdown 标记或解释。

        {{
            "rating": "S/A/B/F",
            "summary": "100字内分析"
        }}
        """

        try:
            logging.info(f"正在请求 Grok-4 进行社交防诈审计: ${symbol}...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "你是一个极度严谨的防诈专家。仅输出 JSON，不解释，不输出 Markdown 代码块。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # 极低温度确保输出格式更稳定
            )

            result_text = response.choices[0].message.content.strip()

            # 使用增强的 JSON 提取方法
            analysis_result = self._extract_json(result_text)

            if not analysis_result:
                logging.error(f"Grok 返回内容无法解析为 JSON: {result_text[:200]}...")
                return {"rating": "F", "summary": "社交审计解析异常。出于资金安全考虑，自动判定为 F 级。"}

            # 兜底校验核心字段
            if "rating" not in analysis_result:
                analysis_result["rating"] = "F"

            logging.info(f"代币 ${symbol} 社交审计完成，最终评级: [{analysis_result.get('rating')}]")
            return analysis_result

        except Exception as e:
            logging.error(f"Grok API 请求过程中发生异常: {e}")
            # 任何请求层面的失败都应判定为 F，防止因接口超时漏掉风险
            return {"rating": "F", "summary": f"请求 Grok 失败，为了资金安全判定为 F 级。原因: {str(e)}"}


# 实例化
grok_api = GrokXAIAPI()