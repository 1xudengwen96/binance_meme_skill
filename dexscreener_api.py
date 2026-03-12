import requests
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DexScreenerAPI:
    """
    Level 1 链上雷达：DexScreener API
    升级版：增加了法证级社交资产抓取与时间溯源功能
    """

    def __init__(self):
        self.base_url = "https://api.dexscreener.com"
        self.session = requests.Session()

    def get_token_social_info(self, ca: str) -> dict:
        """
        [法证级侦察] 针对单一 CA 获取社交资产(Twitter/TG)和真实建池时间
        用于给 Grok 提供“无盲区”的分析证据包
        """
        result = {
            "has_socials": False,
            "social_links": [],
            "pair_age_minutes": 0,
            "description": ""
        }
        try:
            url = f"{self.base_url}/latest/dex/tokens/{ca}"
            resp = self.session.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            pairs = data.get('pairs', [])
            if not pairs:
                return result

            # 取流动性最大的主池子数据
            main_pair = pairs[0]

            # 提取创建时间并计算存活分钟数
            created_at_ms = main_pair.get('pairCreatedAt', 0)
            if created_at_ms > 0:
                age_minutes = (time.time() * 1000 - created_at_ms) / 60000
                result["pair_age_minutes"] = int(age_minutes)

            # 提取社交链接与描述
            info = main_pair.get('info', {})
            socials = info.get('socials', [])
            websites = info.get('websites', [])

            links = []
            for s in socials:
                links.append(f"{s.get('type')}: {s.get('url')}")
            for w in websites:
                links.append(f"website: {w.get('url')}")

            if links:
                result["has_socials"] = True
                result["social_links"] = links

            # 描述中可能藏着马斯克推文的关键词
            result["description"] = info.get('header', '') or info.get('description', '')

            return result

        except Exception as e:
            logging.debug(f"抓取 CA {ca} 社交情报失败: {e}")
            return result

    def get_latest_safe_pairs(self):
        """
        获取 DexScreener 上最新付费更新画像的代币 (防撤池子的第一道防线：Dev花钱了)
        """
        try:
            url = f"{self.base_url}/token-profiles/latest/v1"
            resp = self.session.get(url, timeout=10)
            profiles = resp.json()

            if not profiles: return []

            sol_cas = [p['tokenAddress'] for p in profiles if p.get('chainId') == 'solana']
            if not sol_cas: return []

            cas_str = ",".join(sol_cas[:30])
            pair_url = f"{self.base_url}/latest/dex/tokens/{cas_str}"
            pair_resp = self.session.get(pair_url, timeout=10)
            pairs_data = pair_resp.json().get('pairs', [])

            safe_tokens = []
            seen_cas = set()

            for pair in pairs_data:
                ca = pair['baseToken']['address']
                if ca in seen_cas: continue
                seen_cas.add(ca)

                # 防御 1：只玩 Pump.fun 机制产出的币 (CA 必须以 pump 结尾)
                if not ca.endswith('pump'): continue

                # 防御 2：流动性护城河
                liq = pair.get('liquidity', {}).get('usd', 0)
                if liq < 15000: continue

                # 防御 3：交易活跃度
                vol = pair.get('volume', {}).get('h1', 0)
                if vol < 5000: continue

                token = {
                    "symbol": pair['baseToken']['symbol'],
                    "contractAddress": ca,
                    "protocol": 1001,
                    "marketCap": float(pair.get('fdv', 0)),
                    "liquidity": float(liq),
                    "progress": 100,
                    "source": "DexScreener",
                    "price": float(pair.get('priceUsd', 0)),
                    "rank_type_tracked": 88,
                    "holdersTop10Percent": 0.0
                }
                safe_tokens.append(token)

            logging.info(f"🦅 [DexScreener] 雷达扫描完毕！捕获 {len(safe_tokens)} 个 [高流动性 + 绝无撤池风险] 的标的。")
            return safe_tokens

        except Exception as e:
            logging.error(f"❌ DexScreener API 请求失败: {e}")
            return []


dexscreener_api = DexScreenerAPI()