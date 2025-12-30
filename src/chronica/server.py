"""
Chronica MCP Server - エントリーポイント
STDIOで起動
"""
import asyncio
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
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

