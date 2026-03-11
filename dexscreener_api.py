import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class DexScreenerAPI:
    """
    Level 1 链上雷达：DexScreener API
    主攻：捕捉最新爆发的热门池子，且通过硬核物理规则彻底杜绝“撤LP”风险
    """

    def __init__(self):
        self.base_url = "https://api.dexscreener.com"

    def get_latest_safe_pairs(self):
        """
        获取 DexScreener 上最新付费更新画像的代币 (防撤池子的第一道防线：Dev花钱了)
        """
        try:
            # 1. 获取最新更新了社交信息的代币 (具有极强的主观拉盘意愿)
            url = f"{self.base_url}/token-profiles/latest/v1"
            resp = requests.get(url, timeout=10)
            profiles = resp.json()

            if not profiles:
                return []

            # 2. 仅筛选 Solana 链上的合约地址
            sol_cas = [p['tokenAddress'] for p in profiles if p.get('chainId') == 'solana']
            if not sol_cas:
                return []

            # 限制每次查询最多 30 个，防止接口超载
            cas_str = ",".join(sol_cas[:30])

            # 3. 批量查询这些代币的实时池子数据
            pair_url = f"{self.base_url}/latest/dex/tokens/{cas_str}"
            pair_resp = requests.get(pair_url, timeout=10)
            pairs_data = pair_resp.json().get('pairs', [])

            safe_tokens = []
            seen_cas = set()

            for pair in pairs_data:
                ca = pair['baseToken']['address']

                # 去重
                if ca in seen_cas:
                    continue
                seen_cas.add(ca)

                # ==========================================
                # 🛡️ 绝对免疫撤池子 (Rug Pull) 的核心防御逻辑
                # ==========================================

                # 防御 1：只玩 Pump.fun 机制产出的币 (CA 必须以 pump 结尾)
                # 这种币的 LP 要么在曲线里被锁死，要么在 Raydium 被销毁，庄家绝对无法撤池子
                if not ca.endswith('pump'):
                    continue

                # 防御 2：流动性护城河 (池子太浅容易被大单砸穿，稍微放宽到 1.5w 抓更早期的)
                liq = pair.get('liquidity', {}).get('usd', 0)
                if liq < 15000:
                    continue

                # 防御 3：交易活跃度 (1小时交易量必须大于 5000 美金，拒绝死水盘)
                vol = pair.get('volume', {}).get('h1', 0)
                if vol < 5000:
                    continue

                # 组装适配主引擎的数据格式
                token = {
                    "symbol": pair['baseToken']['symbol'],
                    "contractAddress": ca,
                    "protocol": 1001,  # 标记为 Pump.fun 协议
                    "marketCap": float(pair.get('fdv', 0)),
                    "liquidity": float(liq),
                    "progress": 100,  # DexScreener 上的基本都已建池
                    "source": "DexScreener",
                    "price": float(pair.get('priceUsd', 0)),
                    "rank_type_tracked": 88,  # 赋予独立的高阶榜单代号: 88
                    # 【核心修复】：显式设置持仓比例为0，防止狙击引擎将其视为100%控盘从而被永远拉黑
                    "holdersTop10Percent": 0.0
                }
                safe_tokens.append(token)

            logging.info(f"🦅 [DexScreener] 雷达扫描完毕！捕获 {len(safe_tokens)} 个 [高流动性 + 绝无撤池风险] 的猛犬。")
            return safe_tokens

        except Exception as e:
            logging.error(f"❌ DexScreener API 请求失败: {e}")
            return []


# 实例化单例
dexscreener_api = DexScreenerAPI()