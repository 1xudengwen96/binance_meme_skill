import requests
import uuid
import logging

# 配置基础的日志输出
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BinanceWeb3API:
    """
    封装 Binance Web3 相关的 API 接口
    主要用于 Meme 币扫盘和合约安全审计
    """

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"
        }

    def get_finalizing_memes(self, chain_id: str = "CT_501", limit: int = 5) -> list:
        """
        获取即将打满（Finalizing）的 Meme 币列表
        """
        url = "[https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list](https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list)"

        payload = {
            "chainId": chain_id,
            "rankType": 20,
            "progressMin": "80",
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
                clean_tokens.append({
                    "symbol": token.get("symbol"),
                    "contractAddress": token.get("contractAddress"),
                    "progress": token.get("progress"),
                    "marketCap": token.get("marketCap"),
                    "holdersTop10Percent": token.get("holdersTop10Percent"),
                    "devSellPercent": token.get("devSellPercent"),
                    "devPosition": token.get("devPosition")
                })

            return clean_tokens

        except Exception as e:
            logging.error(f"Meme 扫盘请求异常: {e}")
            return []

    def audit_token_security(self, chain_id: str, contract_address: str) -> dict:
        """
        调用币安底层安全审计接口
        """
        url = "[https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit](https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit)"
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
                logging.error(f"代币 {contract_address} 审计请求失败: {data.get('message')}")
                return {"is_safe": False, "reason": "审计接口请求失败"}

            audit_data = data.get("data", {})

            if not isinstance(audit_data, dict) or not audit_data.get("hasResult") or not audit_data.get("isSupported"):
                return {"is_safe": False, "reason": "该代币尚无审计数据或不支持"}

            risk_level = audit_data.get("riskLevel", 5)

            extra_info = audit_data.get("extraInfo", {})
            buy_tax = float(extra_info.get("buyTax", 100)) if extra_info.get("buyTax") else 0.0
            sell_tax = float(extra_info.get("sellTax", 100)) if extra_info.get("sellTax") else 0.0

            # --- 优化风控逻辑 ---
            # 原逻辑 risk_level > 1 (LOW) 就过滤掉太严了。
            # 修改为 risk_level > 2 (即允许 LOW，只拦截 MEDIUM 及以上)
            if risk_level > 2:
                return {"is_safe": False, "reason": f"风险等级过高 ({audit_data.get('riskLevelEnum')})"}

            if buy_tax > 10 or sell_tax > 10:
                return {"is_short": False, "reason": f"税率过高 (买: {buy_tax}%, 卖: {sell_tax}%)"}

            for item in audit_data.get("riskItems", []):
                if item.get("id") == "CONTRACT_RISK":
                    for detail in item.get("details", []):
                        if detail.get("isHit") and detail.get("riskType") == "RISK":
                            return {"is_safe": False, "reason": f"致命合约风险: {detail.get('title')}"}

            return {"is_safe": True, "reason": "安全"}

        except Exception as e:
            logging.error(f"代币审计请求异常: {e}")
            return {"is_safe": False, "reason": f"网络或解析异常: {str(e)}"}


# 实例化提供给其他模块使用
binance_api = BinanceWeb3API()