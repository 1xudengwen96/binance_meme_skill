import requests
import uuid
import logging

# 配置基础的日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BinanceWeb3API:
    """
    封装 Binance Web3 相关的 API 接口
    """

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"
        }

    def get_finalizing_memes(self, chain_id: str = "CT_501", limit: int = 5) -> list:
        """
        获取“真正”即将打满（Finalizing）的 Meme 币列表
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list"

        payload = {
            "chainId": chain_id,
            "rankType": 20,  # 20 为 Finalizing 榜单
            "progressMin": "95",  # 严格筛选：进度从 80% 提高到 95%
            "excludeDevWashTrading": 1,
            "limit": limit
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                logging.error(f"获取 Meme 列表失败: {data.get('message')}")
                return []

            res_content = data.get("data")
            if isinstance(res_content, list):
                raw_tokens = res_content
            elif isinstance(res_content, dict):
                raw_tokens = res_content.get("tokens", [])
            else:
                raw_tokens = []

            clean_tokens = []
            for token in raw_tokens:
                if not isinstance(token, dict):
                    continue

                # 【修复核心】：数据脱水时增加 or 运算符作为空值保护
                # 如果 API 返回 None，则强制转为安全的基础值
                clean_tokens.append({
                    "symbol": token.get("symbol") or "Unknown",
                    "contractAddress": token.get("contractAddress") or "Unknown",
                    "progress": token.get("progress") or "0",
                    "marketCap": token.get("marketCap") or "0",
                    "holdersTop10Percent": token.get("holdersTop10Percent") or "0",
                    "devSellPercent": token.get("devSellPercent") or "0",
                    "devPosition": token.get("devPosition") or 0
                })

            return clean_tokens

        except Exception as e:
            logging.error(f"Meme 扫盘请求异常: {e}")
            return []

    def audit_token_security(self, chain_id: str, contract_address: str) -> dict:
        """
        调用币安底层安全审计接口
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"
        request_id = str(uuid.uuid4())
        audit_headers = self.headers.copy()
        audit_headers["source"] = "agent"

        payload = {
            "binanceChainId": chain_id,
            "contractAddress": contract_address,
            "requestId": request_id
        }

        try:
            response = requests.post(url, headers=audit_headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                return {"is_safe": False, "reason": "审计接口异常"}

            audit_data = data.get("data", {})
            if not isinstance(audit_data, dict) or not audit_data.get("hasResult"):
                return {"is_safe": False, "reason": "无审计结果"}

            risk_level = audit_data.get("riskLevel", 5)

            # 严格风控：只接受风险等级 1 (INFO) 或 2 (LOW)
            if risk_level > 2:
                return {"is_safe": False, "reason": f"风险偏高 ({audit_data.get('riskLevelEnum')})"}

            return {"is_safe": True, "reason": "安全"}

        except Exception:
            return {"is_safe": False, "reason": "请求异常"}


# 实例化提供给其他模块使用
binance_api = BinanceWeb3API()