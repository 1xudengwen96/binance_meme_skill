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
    采用 wallet-direct 精准路由，彻底杜绝 404 崩溃
    """

    def __init__(self):
        # 使用 Session 复用底层的 TCP 连接，提升高频请求速度
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Accept-Encoding": "identity"  # 官方文档要求的 Header
        })

    def _safe_post(self, url: str, payload: dict):
        """基础的容错 POST 发送器，返回剥离 code 后的真实 data"""
        resp = self.session.post(url, json=payload, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and str(data.get("code")) in ["000000", "0"]:
            return data.get("data")
        return None

    def _safe_get(self, url: str, params: dict = None):
        """[新增] 基础容错 GET 发送器，用于调用 Exclusive 潜力榜等 GET 接口"""
        resp = self.session.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and str(data.get("code")) in ["000000", "0"]:
            return data.get("data")
        return None

    @retry_request(max_retries=3)
    def get_memes(self, chain_id="CT_501", rank_type=10):
        """
        Skill: meme-rush (获取土狗打满榜单)
        官方路由: /pulse/rank/list
        rank_type: 10(New), 20(Finalizing), 30(Migrated)
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/rank/list"
        payload = {"chainId": chain_id, "rankType": rank_type, "limit": 30}

        data = self._safe_post(url, payload)

        # 兼容 Binance 不同的返回结构 (List 或 Dict 嵌套)
        tokens = []
        if isinstance(data, list):
            tokens = data
        elif isinstance(data, dict):
            tokens = data.get("tokens") or data.get("list") or data.get("data") or []

        logging.info(f"📡 [API] 从基础大盘拉取到 {len(tokens)} 个代币 (榜单: {rank_type})")
        return tokens

    @retry_request(max_retries=3)
    def get_exclusive_memes(self, chain_id="56"):
        """
        [新增武器] Skill: crypto-market-rank (Meme Rank 专属潜力榜单)
        官方路由: /pulse/exclusive/rank/list
        这是 Binance 官方算法预先打分筛选出的高爆发潜力 Meme 列表
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/pulse/exclusive/rank/list"
        params = {"chainId": chain_id}

        data = self._safe_get(url, params=params)

        tokens = []
        if isinstance(data, list):
            tokens = data
        elif isinstance(data, dict):
            tokens = data.get("tokens") or data.get("list") or data.get("data") or []

        logging.info(f"🔥 [API] 从官方专属潜力榜拉取到 {len(tokens)} 个高评分代币")
        return tokens

    @retry_request(max_retries=3)
    def get_trending_topics(self, chain_id="CT_501"):
        """
        Skill: crypto-market-rank / topic-rush (获取大盘热门叙事)
        官方路由: /social-rush/rank/list
        """
        url = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/social-rush/rank/list"
        # 猎人实战建议：使用 sort=30 (Viral) 或 sort=20 (Rising)
        payload = {"chainId": chain_id, "rankType": 30, "limit": 20, "sort": 30}

        try:
            data = self._safe_post(url, payload)
            topics = []

            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("tokens") or data.get("topics") or data.get("list") or []

            for item in items:
                if isinstance(item, dict) and "topic" in item:
                    topics.append(item["topic"])

            logging.info(f"📡 [API] 成功拉取到 {len(topics)} 个大盘热门叙事")
            return topics
        except Exception as e:
            logging.debug(f"获取热门叙事失败，跳过: {e}")
            return []

    @retry_request(max_retries=3)
    def get_token_audit(self, chain_id, contract_address):
        """
        Skill: query-token-audit (深度安全审计)
        """
        urls_to_try = [
            "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/security/token/audit",
            "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/security"
        ]
        # 注意: 新版安全审计接口需要 requestId
        import uuid
        payload = {
            "binanceChainId": chain_id,
            "contractAddress": contract_address,
            "requestId": str(uuid.uuid4())
        }
        result = {"is_safe": False, "risk_level": 5, "detail": {}}

        for url in urls_to_try:
            try:
                data = self._safe_post(url, payload)
                if isinstance(data, dict):
                    # 适配新版风险级别 riskLevelEnum (1-5, 1为LOW)
                    risk_level = data.get("riskLevel", 5)
                    result["is_safe"] = (risk_level <= 2)  # 1和2算相对安全
                    result["risk_level"] = risk_level
                    result["detail"] = data
                    return result
            except Exception:
                continue

        logging.debug(f"审计接口获取异常，默认返回高风险 ({contract_address[:6]}...)")
        return result

    @retry_request(max_retries=2)
    def get_smart_money_info(self, chain_id, contract_address):
        """
        Skill: trading-signal (聪明钱雷达追踪)
        """
        urls_to_try = [
            "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/smart-money",
            "https://www.binance.com/bapi/web3/v1/public/web3-skill/trading-signal"
        ]
        payload = {"chainId": chain_id, "contractAddress": contract_address}

        for url in urls_to_try:
            try:
                data = self._safe_post(url, payload)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue

        return {"smartMoneyCount": 0, "smartMoneyInflow": 0.0}

    @retry_request(max_retries=3)
    def get_token_info(self, chain_id, contract_address):
        """
        Skill: query-token-info (获取代币物理指标详情)
        """
        urls_to_try = [
            "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/market/token/info",
            "https://www.binance.com/bapi/web3/v1/public/web3-skill/query-token-info"
        ]
        payload = {"chainId": chain_id, "contractAddress": contract_address}

        for url in urls_to_try:
            try:
                data = self._safe_post(url, payload)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
        return {}


# 实例化单例
binance_api = BinanceAPI()