"""
Chronica MCP Server - エントリーポイント
STDIOで起動
"""
import asyncio
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server

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


async def main():
    """メインエントリーポイント"""
    server = create_server()
    
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

