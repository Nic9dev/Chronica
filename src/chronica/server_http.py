"""
Chronica MCP Server - HTTP/SSE エントリーポイント
SSE/HTTPで起動（GPT等のリモート接続用）
"""
import asyncio
import sys
from typing import Optional
from fastapi import FastAPI, Request
import uvicorn

from mcp.server import Server
from mcp.server.sse import SseServerTransport

from .store import Store
from .tools import register_tools, set_store


def create_server() -> Server:
    """MCPサーバーを作成"""
    server = Server("chronica")
    
    # Storeを初期化
    store = Store()
    set_store(store)
    
    # ツールを登録
    register_tools(server)
    
    return server


app = FastAPI(title="Chronica MCP Server")
_server: Optional[Server] = None
_transport: Optional[SseServerTransport] = None


@app.on_event("startup")
async def startup_event():
    """サーバー起動時の初期化"""
    global _server, _transport
    _server = create_server()
    # 認証なし（ローカル開発用）
    _transport = SseServerTransport("/messages")
    print("Chronica MCP Server (HTTP/SSE) initialized", file=sys.stderr)


@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSEエンドポイント"""
    if _server is None or _transport is None:
        return {"error": "Server not initialized"}, 500
    
    # ASGIのscope, receive, sendを取得
    scope = request.scope
    receive = request._receive
    send = request._send
    
    # SSE接続を確立してサーバーを実行
    # connect_sseはASGIアプリケーションとして動作
    async with _transport.connect_sse(scope, receive, send) as streams:
        await _server.run(
            streams[0],
            streams[1],
            _server.create_initialization_options()
        )
    
    # 戻り値は不要（ASGI sendで送信済み）
    return None


@app.post("/messages")
async def messages_endpoint(request: Request):
    """メッセージエンドポイント（POST）"""
    if _server is None or _transport is None:
        return {"error": "Server not initialized"}, 500
    
    # ASGIのscope, receive, sendを取得
    scope = request.scope
    receive = request._receive
    send = request._send
    
    # POSTメッセージを処理（レスポンスはsendで送信される）
    await _transport.handle_post_message(scope, receive, send)
    
    # 戻り値は不要（ASGI sendで送信済み）
    return None


def main(host: str = "127.0.0.1", port: int = 8000):
    """HTTPサーバーを起動"""
    print(f"Chronica MCP Server (HTTP/SSE) starting on http://{host}:{port}", file=sys.stderr)
    print(f"SSE endpoint: http://{host}:{port}/sse", file=sys.stderr)
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Chronica MCP Server (HTTP/SSE)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    
    args = parser.parse_args()
    main(host=args.host, port=args.port)
