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
    # 起動ログ（標準エラー出力に出力）
    print("Chronica MCP Server starting...", file=sys.stderr)
    print("Waiting for MCP client connection...", file=sys.stderr)
    
    server = create_server()
    
    try:
        async with stdio_server() as (read_stream, write_stream):
            print("MCP Server ready. Connected.", file=sys.stderr)
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )
    except KeyboardInterrupt:
        print("\nShutting down server...", file=sys.stderr)
        raise


if __name__ == "__main__":
    asyncio.run(main())

