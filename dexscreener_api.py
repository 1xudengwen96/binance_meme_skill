import requests
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DexScreenerAPI:
    """
    Level 1 链上雷达：DexScreener API
    金狗专属版：完美适配 Solana (Pump.fun) 与 BSC (Four.meme) 双链不同生态的扫链护城河
    """

    def __init__(self):
        self.base_url = "https://api.dexscreener.com"
        self.session = requests.Session()

    def get_token_social_info(self, ca: str) -> dict:
        """获取 CA 社交资产与建池时间（法证级证据）"""
        result = {"has_socials": False, "social_links": [], "pair_age_minutes": 0, "description": ""}
        try:
            url = f"{self.base_url}/latest/dex/tokens/{ca}"
            resp = self.session.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            pairs = data.get('pairs', [])
            if not pairs: return result

            # 提取存活时间
            main_pair = pairs[0]
            created_at_ms = main_pair.get('pairCreatedAt', 0)
            if created_at_ms > 0:
                result["pair_age_minutes"] = int((time.time() * 1000 - created_at_ms) / 60000)

            # 提取社交媒体
            info = main_pair.get('info', {})
            links = [f"{s.get('type')}: {s.get('url')}" for s in info.get('socials', [])]
            links += [f"website: {w.get('url')}" for w in info.get('websites', [])]

            if links:
                result["has_socials"] = True
                result["social_links"] = links

            result["description"] = info.get('header', '') or info.get('description', '')
            return result
        except Exception as e:
            return result

    def get_latest_safe_pairs(self, chain_id: str):
        """
        获取最新打钱画像代币，动态区分 BSC 和 Solana 策略
        """
        # 将内部 chain_id 映射为 DexScreener 识别的链名
        target_chain = 'solana' if chain_id == "CT_501" else 'bsc'

        try:
            url = f"{self.base_url}/token-profiles/latest/v1"
            resp = self.session.get(url, timeout=10)
            profiles = resp.json()

            if not profiles: return []

            # 过滤出当前正在扫描的目标链代币
            target_cas = [p['tokenAddress'] for p in profiles if p.get('chainId') == target_chain]
            if not target_cas: return []

            cas_str = ",".join(target_cas[:30])
            pair_url = f"{self.base_url}/latest/dex/tokens/{cas_str}"
            pair_resp = self.session.get(pair_url, timeout=10)
            pairs_data = pair_resp.json().get('pairs', [])

            safe_tokens = []
            seen_cas = set()

            for pair in pairs_data:
                ca = pair['baseToken']['address']
                if ca in seen_cas: continue
                seen_cas.add(ca)

                # 获取代币所在的 DEX 名称 (如 pumpfun, fourmeme, pancakeswap)
                dex_id = pair.get('dexId', 'unknown').lower()

                # 【双链差异化防御拦截】
                if target_chain == 'solana':
                    # Solana 强制要求 Pump.fun 出身防撤池
                    if not ca.endswith('pump') and dex_id != 'pumpfun': continue
                    min_liq = 15000
                    min_vol = 5000
                else:
                    # BSC：优先识别 Four.meme，如果是野生池子也先放行（交给主引擎去毙掉）
                    min_liq = 8000  # BSC 四狗开盘池子较小，放宽门槛
                    min_vol = 2000

                liq = pair.get('liquidity', {}).get('usd', 0)
                if liq < min_liq: continue

                vol = pair.get('volume', {}).get('h1', 0)
                if vol < min_vol: continue

                token = {
                    "symbol": pair['baseToken']['symbol'],
                    "contractAddress": ca,
                    "protocol": 1001,
                    "marketCap": float(pair.get('fdv', 0)),
                    "liquidity": float(liq),
                    "progress": 100,
                    # 【关键点】：将 dex_id 注入到 source 中，让主引擎能借此识别出 fourmeme
                    "source": f"DexScreener({dex_id})",
                    "price": float(pair.get('priceUsd', 0)),
                    "rank_type_tracked": 88,
                    "holdersTop10Percent": 0.0
                }
                safe_tokens.append(token)

            logging.info(
                f"🦅 [DexScreener] {target_chain.upper()} 雷达扫描完毕！捕获 {len(safe_tokens)} 个具备基础爆发潜力的标的。")
            return safe_tokens

        except Exception as e:
            logging.error(f"❌ DexScreener API 请求失败: {e}")
            return []


dexscreener_api = DexScreenerAPI()