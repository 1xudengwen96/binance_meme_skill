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
        并进行“数据脱水”，以节约大模型 Token
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list"

        payload = {
            "chainId": chain_id,
            "rankType": 20,  # 20 表示 Finalizing (即将打满迁移)
            "progressMin": "80",  # 过滤掉进度低于 80% 的垃圾盘
            "excludeDevWashTrading": 1,  # 剔除开发者刷单的代币
            "limit": limit
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                logging.error(f"获取 Meme 列表失败: {data.get('message')}")
                return []

            raw_tokens = data.get("data", {}).get("tokens", [])
            clean_tokens = []

            # 【数据脱水】：只保留核心字段，喂给 Grok 时极其省钱
            for token in raw_tokens:
                clean_tokens.append({
                    "symbol": token.get("symbol"),
                    "contractAddress": token.get("contractAddress"),
                    "progress": token.get("progress"),
                    "marketCap": token.get("marketCap"),
                    "holdersTop10Percent": token.get("holdersTop10Percent"),
                    "devSellPercent": token.get("devSellPercent"),
                    "devPosition": token.get("devPosition")  # 2 代表开发者已卖光
                })

            return clean_tokens

        except Exception as e:
            logging.error(f"Meme 扫盘请求异常: {e}")
            return []

    def audit_token_security(self, chain_id: str, contract_address: str) -> dict:
        """
        调用币安底层安全审计接口，查验代币是否存在貔貅、高税等致命风险
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"

        # 审计接口需要每次请求提供一个唯一的 uuid v4
        request_id = str(uuid.uuid4())

        # 增加安全审计接口特定的 headers
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

            # 如果接口不支持该代币，或者没有审计结果
            if not audit_data.get("hasResult") or not audit_data.get("isSupported"):
                return {"is_safe": False, "reason": "该代币尚无审计数据或不支持"}

            risk_level = audit_data.get("riskLevel", 5)  # 默认极高风险

            # 解析买卖税率 (转换为浮点数处理)
            extra_info = audit_data.get("extraInfo", {})
            buy_tax = float(extra_info.get("buyTax", 100)) if extra_info.get("buyTax") else 0.0
            sell_tax = float(extra_info.get("sellTax", 100)) if extra_info.get("sellTax") else 0.0

            # --- 核心硬性风控逻辑 ---
            # 1. 风险等级大于 1 (LOW) 一律视为不安全
            # 2. 买卖税率超过 10% 视为潜在貔貅或抢钱盘
            if risk_level > 1:
                return {"is_safe": False, "reason": f"风险等级过高 ({audit_data.get('riskLevelEnum')})"}
            if buy_tax > 10 or sell_tax > 10:
                return {"is_safe": False, "reason": f"税率过高 (买: {buy_tax}%, 卖: {sell_tax}%)"}

            # 查验具体风险项中有无 CONTRACT_RISK
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