import requests
import uuid
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BinanceWeb3API:
    """
    封装 Binance Web3 相关的 API 接口 - 探测阈值优化版
    """

    def __init__(self):
        self.headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"
        }
        # 核心发射协议
        self.LAUNCHPAD_PROTOCOLS = {
            "CT_501": [1001],  # Pump.fun
            "56": [2001]  # Four.meme
        }

    def get_memes(self, chain_id: str = "CT_501", rank_type: int = 20, limit: int = 15) -> list:
        """
        获取 Meme 币列表 - 优化进度探测逻辑
        rank_type: 10=New, 20=Finalizing, 30=Migrated
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list"

        target_protocols = self.LAUNCHPAD_PROTOCOLS.get(chain_id, [])

        payload = {
            "chainId": chain_id,
            "rankType": rank_type,
            "protocol": target_protocols,
            "excludeDevWashTrading": 1,
            "limit": limit
        }

        # 优化点：将 95% 下调至 80%，扩大监控窗口
        if rank_type == 20:
            payload["progressMin"] = "80"
        elif rank_type == 10:
            # 对于新币，我们也只看已经有一定热度（进度 > 50%）的
            payload["progressMin"] = "50"

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            if not data.get("success"):
                logging.error(f"获取 Meme 列表失败: {data.get('message')}")
                return []

            res_content = data.get("data")
            raw_tokens = []
            if isinstance(res_content, list):
                raw_tokens = res_content
            elif isinstance(res_content, dict):
                raw_tokens = res_content.get("tokens", [])

            clean_tokens = []
            for token in raw_tokens:
                if not isinstance(token, dict):
                    continue

                clean_tokens.append({
                    "symbol": token.get("symbol") or "Unknown",
                    "contractAddress": token.get("contractAddress"),
                    "chainId": chain_id,  # 显式传递链 ID
                    "progress": token.get("progress") or "0",
                    "marketCap": token.get("marketCap") or "0",
                    "holdersTop10Percent": token.get("holdersTop10Percent") or "100",
                    "devSellPercent": token.get("devSellPercent") or "0",
                    "devMigrateCount": token.get("devMigrateCount") or 0,
                    "migrateStatus": token.get("migrateStatus") or 0,
                    "protocol": token.get("protocol")
                })

            return clean_tokens

        except Exception as e:
            logging.error(f"Meme 扫盘请求异常: {e}")
            return []

    def audit_token_security(self, chain_id: str, contract_address: str) -> dict:
        """
        深度安全审计：基于细节风险项判定
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
                return {"is_safe": False, "reason": "审计接口故障"}

            audit_data = data.get("data", {})
            if not audit_data.get("hasResult") or not audit_data.get("isSupported"):
                return {"is_safe": False, "reason": "无审计数据"}

            # 风险等级校验
            risk_level = audit_data.get("riskLevel", 5)
            if risk_level > 2:
                return {"is_safe": False, "reason": f"风险等级过高 ({audit_data.get('riskLevelEnum')})"}

            # 开源校验
            extra_info = audit_data.get("extraInfo", {})
            if not extra_info.get("isVerified"):
                return {"is_safe": False, "reason": "代码未开源"}

            # 深度风险项扫描
            risk_items = audit_data.get("riskItems", [])
            for item in risk_items:
                details = item.get("details", [])
                for detail in details:
                    if detail.get("isHit") and detail.get("riskType") == "RISK":
                        return {"is_safe": False, "reason": f"命中风险: {detail.get('title')}"}

            return {"is_safe": True, "reason": "安全"}

        except Exception as e:
            logging.error(f"安全审计异常: {e}")
            return {"is_safe": False, "reason": "请求失败"}


# 实例化
binance_api = BinanceWeb3API()