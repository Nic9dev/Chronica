"""
Chronica MCP Server 起動スクリプト（HTTP/SSE版）
プロジェクトルートから実行: python run_server_http.py
"""
import sys
from pathlib import Path

# srcディレクトリをパスに追加
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

# サーバーを起動
if __name__ == "__main__":
    from chronica.server_http import main
    import argparse
    
    parser = argparse.ArgumentParser(description="Chronica MCP Server (HTTP/SSE)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    
    args = parser.parse_args()
    
    try:
        main(host=args.host, port=args.port)
    except KeyboardInterrupt:
        print("\nChronica MCP Server (HTTP/SSE) stopped.", file=sys.stderr)
        sys.exit(0)
