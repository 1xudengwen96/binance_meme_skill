import requests
import uuid
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class BinanceWeb3API:
    """
    封装 Binance Web3 相关的 API 接口 - 叙事与聪明钱增强版
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
        获取 Meme 币列表
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

        if rank_type == 20:
            payload["progressMin"] = "80"
        elif rank_type == 10:
            payload["progressMin"] = "50"

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data.get("success"): return []

            res_content = data.get("data")
            raw_tokens = res_content if isinstance(res_content, list) else res_content.get("tokens", [])

            return [{
                "symbol": t.get("symbol") or "Unknown",
                "contractAddress": t.get("contractAddress"),
                "chainId": chain_id,
                "progress": t.get("progress") or "0",
                "marketCap": t.get("marketCap") or "0",
                "holdersTop10Percent": t.get("holdersTop10Percent") or "100",
                "devSellPercent": t.get("devSellPercent") or "0",
                "devMigrateCount": t.get("devMigrateCount") or 0,
                "protocol": t.get("protocol")
            } for t in raw_tokens]
        except Exception as e:
            logging.error(f"Meme 列表请求异常: {e}")
            return []

    def get_trending_topics(self, chain_id: str = "CT_501") -> list:
        """
        获取当前最火的叙事话题 (Topic Rush)
        rankType: 30=Viral, 20=Rising
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/social-rush/rank/list"
        topics = []

        # 同时轮询 Viral (病毒级) 和 Rising (上升级) 话题
        for r_type in [30, 20]:
            params = {
                "chainId": chain_id,
                "rankType": r_type,
                "sort": 30 if r_type == 30 else 10  # Viral 按热度时间排，Rising 按创建时间排
            }
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=10)
                data = response.json()
                if data.get("success"):
                    topics.extend(data.get("data", []))
            except Exception as e:
                logging.error(f"获取叙事话题失败: {e}")

        return topics

    def get_smart_money_inflow(self, chain_id: str = "CT_501") -> list:
        """
        获取聪明钱流入榜单 (Smart Money Inflow Rank)
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/tracker/wallet/token/inflow/rank/query"
        payload = {
            "chainId": chain_id,
            "period": "24h",
            "tagType": 2  # 2 代表聪明钱/精英地址
        }
        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=10)
            data = response.json()
            return data.get("data", []) if data.get("success") else []
        except Exception as e:
            logging.error(f"获取聪明钱榜单失败: {e}")
            return []

    def audit_token_security(self, chain_id: str, contract_address: str) -> dict:
        """
        深度安全审计
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit"
        request_id = str(uuid.uuid4())
        payload = {
            "binanceChainId": chain_id,
            "contractAddress": contract_address,
            "requestId": request_id
        }
        try:
            response = requests.post(url, headers={**self.headers, "source": "agent"}, json=payload, timeout=10)
            data = response.json()
            if not data.get("success"): return {"is_safe": False, "reason": "审计接口故障"}

            audit_data = data.get("data", {})
            risk_level = audit_data.get("riskLevel", 5)
            if risk_level > 2: return {"is_safe": False, "reason": f"高风险: {audit_data.get('riskLevelEnum')}"}
            if not audit_data.get("extraInfo", {}).get("isVerified"): return {"is_safe": False, "reason": "代码未开源"}

            risk_items = audit_data.get("riskItems", [])
            for item in risk_items:
                for d in item.get("details", []):
                    if d.get("isHit") and d.get("riskType") == "RISK":
                        return {"is_safe": False, "reason": f"风险项: {d.get('title')}"}
            return {"is_safe": True, "reason": "安全"}
        except Exception:
            return {"is_safe": False, "reason": "请求失败"}


# 实例化
binance_api = BinanceWeb3API()