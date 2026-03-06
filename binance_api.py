import requests
import time
import logging
from functools import wraps
from config import config

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def retry_request(max_retries=3, backoff_factor=1.5):
    """
    指数级退避重试装饰器：处理极端网络与接口限频
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    retries += 1
                    wait_time = backoff_factor ** retries
                    logging.warning(
                        f"⚠️ {func.__name__} 接口请求异常，{wait_time:.1f}秒后进行第 {retries}/{max_retries} 次重试...")
                    time.sleep(wait_time)
            logging.error(f"❌ {func.__name__} 接口请求失败，已达到最大重试次数 {max_retries}")
            return None

        return wrapper

    return decorator


class BinanceAPI:
    """
    基于官方 binance-skills-hub 仓库标准的 Web3 API 客户端
    自带动态路由降级 (Fallback) 机制，彻底杜绝 404 崩溃
    """

    def __init__(self):
        # 使用 Session 复用底层的 TCP 连接，提升高频请求速度
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Clienttype": "web",
            "Content-Type": "application/json"
        })

    def _smart_post(self, skill_name: str, payload: dict) -> dict:
        """
        智能路由发送器：根据官方 binance-skills-hub 规范请求，并附带容错降级
        """
        # 路由优先级：1. 官方 Skill 端点 -> 2. 传统 Explorer 端点 -> 3. Token 子端点
        urls_to_try = [
            f"https://www.binance.com/bapi/web3/v1/public/web3-skill/{skill_name}",
            f"https://www.binance.com/bapi/web3/v1/public/web3/explorer/{skill_name}",
            f"https://www.binance.com/bapi/web3/v1/public/web3/explorer/token/{skill_name}"
        ]

        for url in urls_to_try:
            try:
                resp = self.session.post(url, json=payload, timeout=8)
                # 如果遇到 404，静默跳过，尝试下一个备用路由
                if resp.status_code == 404:
                    continue

                resp.raise_for_status()
                data = resp.json()

                if data.get("code") == "000000":
                    return data
            except requests.exceptions.RequestException as e:
                # 记录调试日志，继续尝试备用地址
                logging.debug(f"尝试端点 {url} 失败: {e}")
                continue

        # 所有路由都失败则抛出异常，交给外层的 @retry_request 处理
        raise requests.exceptions.RequestException(f"无法访问 {skill_name} 的任何已知端点 (均返回 404 或超时)")

    @retry_request(max_retries=3)
    def get_memes(self, chain_id="CT_501", rank_type=10):
        """
        Skill: meme-rush (获取土狗打满榜单)
        rank_type: 10(New), 20(Finalizing), 30(Migrated)
        """
        payload = {"chainId": chain_id, "rankType": rank_type}
        data = self._smart_post("meme-rush", payload)
        if data and data.get("data"):
            return data["data"]
        return []

    @retry_request(max_retries=3)
    def get_token_info(self, chain_id, contract_address):
        """
        Skill: query-token-info (获取代币物理指标)
        """
        payload = {"chainId": chain_id, "contractAddress": contract_address}
        data = self._smart_post("query-token-info", payload)
        if data and data.get("data"):
            return data["data"]
        return {}

    @retry_request(max_retries=3)
    def get_token_audit(self, chain_id, contract_address):
        """
        Skill: query-token-audit (深度安全审计)
        """
        payload = {"chainId": chain_id, "contractAddress": contract_address}

        # 默认的高风险防御状态
        result = {"is_safe": False, "risk_level": 5, "detail": {}}

        try:
            data = self._smart_post("query-token-audit", payload)
            if data and data.get("data"):
                audit_data = data["data"]
                result["is_safe"] = audit_data.get("isSafe", False)
                result["risk_level"] = audit_data.get("riskLevel", 5)
                result["detail"] = audit_data
        except Exception as e:
            logging.warning(f"⚠️ 审计接口获取异常，默认返回高风险 ({contract_address}): {e}")

        return result

    @retry_request(max_retries=2)
    def get_smart_money_info(self, chain_id, contract_address):
        """
        Skill: trading-signal (聪明钱雷达追踪)
        """
        payload = {"chainId": chain_id, "contractAddress": contract_address}
        try:
            data = self._smart_post("trading-signal", payload)
            if data and data.get("data"):
                return data["data"]
        except Exception:
            pass
        # 若获取失败，返回默认空数据，避免阻断主引擎的算分流
        return {"smartMoneyCount": 0, "smartMoneyInflow": 0.0}

    @retry_request(max_retries=2)
    def get_trending_topics(self, chain_id="CT_501"):
        """
        Skill: crypto-market-rank (获取大盘热门叙事)
        """
        payload = {"chainId": chain_id}
        try:
            data = self._smart_post("crypto-market-rank", payload)
            if data and data.get("data"):
                # 兼容不同的返回结构
                if isinstance(data["data"], list):
                    return [item.get("topic") for item in data["data"] if "topic" in item]
                elif isinstance(data["data"], dict) and "topics" in data["data"]:
                    return [item.get("topic") for item in data["data"]["topics"] if "topic" in item]
        except Exception:
            pass
        return []


# 实例化单例
binance_api = BinanceAPI()