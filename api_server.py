from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os

# 初始化 FastAPI 应用
app = FastAPI(title="Meme Hunter Pro API Gateway")

# 配置 CORS 跨域，确保前端 index.html 可以顺利访问接口
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 内存数据存储中心 (DataStore)
# 负责在 Python 引擎和 React 前端之间共享数据
class DataStore:
    def __init__(self):
        # 存储最近扫描到的高评分代币列表
        self.tokens = []
        # 全局统计指标
        self.stats = {
            "scanned": 0,  # 总扫描数
            "hits": 0,     # 发现金狗数
            "rugs": 0      # 拦截风险数
        }

# 实例化全局存储
store = DataStore()

# --- 路由定义 ---

@app.get("/")
async def serve_dashboard():
    """
    根路由：直接托管并返回前端大盘 HTML 文件
    """
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"error": "index.html 尚未生成，请检查根目录"}

@app.get("/api/tokens")
async def get_tokens():
    """
    前端大盘轮询接口：返回最新的代币列表和统计数据
    """
    # 返回最近 15 个命中的信号，确保前端不卡顿
    return {
        "tokens": store.tokens[-15:],
        "stats": store.stats,
        "status": "online"
    }

@app.post("/api/inject_token")
async def inject_token(token: dict):
    """
    内部接口：供 sniper_engine 发现目标后实时注入数据
    """
    # 简单的去重逻辑
    ca_list = [t.get("contractAddress") for t in store.tokens]
    if token.get("contractAddress") not in ca_list:
        store.tokens.append(token)
        store.stats["hits"] += 1
    return {"status": "success"}

def start_server(port: int = 8000):
    """
    启动 Uvicorn 服务器
    """
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")

if __name__ == "__main__":
    start_server()