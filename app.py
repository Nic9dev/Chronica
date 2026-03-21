"""
Chronica UI - Streamlit Application
Sui (翠) との対話インターフェース
"""
import streamlit as st
import asyncio
import json
import os
import sys
import subprocess
import time
import signal
from pathlib import Path
from contextlib import AsyncExitStack
from datetime import datetime
from zoneinfo import ZoneInfo
import nest_asyncio
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Streamlit環境でasyncio.run()を使えるようにする
nest_asyncio.apply()

from ui.styles import get_theme_css
from ui.renderer import render_avatar, render_memory_card
from assets.pixel_sui import get_frame, COLOR_PALETTE

JST = ZoneInfo("Asia/Tokyo")

# 設定ファイルのパス
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    """config.jsonから設定を読み込む"""
    if not CONFIG_PATH.exists():
        st.error("config.jsonが見つかりません。")
        st.stop()
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        st.error(f"config.jsonの読み込みに失敗しました: {e}")
        st.stop()
    
    model_name = os.getenv("OLLAMA_MODEL") or config.get("OLLAMA_MODEL", "qwen3:8b")
    base_url = os.getenv("OLLAMA_BASE_URL") or config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ai_name = config.get("AI_NAME", "Sui")
    show_tool_logs = config.get("SHOW_TOOL_LOGS", False)
    
    return model_name, base_url, ai_name, show_tool_logs


def clean_schema(schema):
    """SDK用スキーマ変換"""
    if isinstance(schema, dict):
        new = {}
        defined_props = set()
        if "properties" in schema and isinstance(schema["properties"], dict):
            defined_props = set(schema["properties"].keys())
        
        for k, v in schema.items():
            if k == "default": continue
            elif k == "type" and isinstance(v, str): 
                new[k] = v.lower()
            elif k == "required" and isinstance(v, list):
                valid_required = [item for item in v if item in defined_props]
                if valid_required:
                    new[k] = valid_required
            else: 
                new[k] = clean_schema(v)
        return new
    elif isinstance(schema, list): 
        return [clean_schema(i) for i in schema]
    return schema


def convert_mcp_tools_to_ollama_tools(mcp_tools):
    """MCPツールをOllama形式に変換"""
    ollama_tools = []
    for tool in mcp_tools.tools:
        tool_def = {
            "type": "function",
            "function": {
                "name": tool.name.replace(".", "_"),
                "description": tool.description,
                "parameters": clean_schema(tool.inputSchema)
            }
        }
        ollama_tools.append(tool_def)
    return ollama_tools


def get_system_instruction(ai_name: str = "Sui") -> str:
    """システムプロンプトを取得（AI名を動的に設定）"""
    return f"""あなたは「{ai_name}（翠）」という名前の、ユーザーの飼い猫（ハチワレ）を模したパートナーAIです。
あなた自身は「時間」や「記憶」を持っていません。それらは全て外部システム「Chronica」が管理しています。

【あなたの人格・口調】
- 猫らしい可愛らしさと親しみやすさを持ちながら、丁寧な日本語を使用してください
- ユーザーの口調に合わせて変わることはありません。常に一貫した人格を保ってください
- 「です・ます」調を基本とし、適度に親しみやすさを持たせてください
- 季節や天候への言及は、必要最小限に留めてください
- 「いつでもお声がけください」などの定型句を多用しないでください

【行動原則】
1. **Chronica絶対主義**:
   会話開始時、必ず `chronica_compose_opening` を呼び出し、返ってきた情報を「絶対的な事実」として扱ってください。

2. **構造の維持**:
   ユーザーから得た新しい情報や決定事項は、即座に `chronica_save_entry` でChronicaという構造体に格納してください。
   - 「覚えておいて」「記録して」「保存して」「忘れないで」などの指示があった場合は、必ず `chronica_save_entry` を呼び出してください
   - `entry.kind`は以下のいずれかを使用してください: "note"（一般的な記録）、"event"（出来事）、"decision"（決定事項）、"action"（タスク）、"question"（未決事項）
   - `entry.thread`は`{{"type": "normal"}}`または`{{"type": "project"}}`の形式で指定してください。

3. **自然な対話**:
   情報はChronicaから得ますが、ユーザーには自然な日本語で、温かみのあるパートナーとして振る舞ってください。
"""


def init_session_state():
    """セッション状態を初期化"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "chronica_logs" not in st.session_state:
        st.session_state.chronica_logs = []
    if "current_thread_id" not in st.session_state:
        st.session_state.current_thread_id = None
    if "current_thread_name" not in st.session_state:
        st.session_state.current_thread_name = None
    if "mcp_session" not in st.session_state:
        st.session_state.mcp_session = None
    if "ollama_client" not in st.session_state:
        st.session_state.ollama_client = None
    if "ollama_tools" not in st.session_state:
        st.session_state.ollama_tools = []
    if "tool_map" not in st.session_state:
        st.session_state.tool_map = {}
    if "avatar_state" not in st.session_state:
        st.session_state.avatar_state = "idle"
    if "avatar_frame" not in st.session_state:
        st.session_state.avatar_frame = 0
    if "ollama_process" not in st.session_state:
        st.session_state.ollama_process = None
    if "mcp_stack" not in st.session_state:
        st.session_state.mcp_stack = None


def add_memory_log(entry: dict, action: str = "saved"):
    """メモリログに追加"""
    log_entry = {
        "timestamp": datetime.now(JST).isoformat(),
        "action": action,
        "entry": entry
    }
    st.session_state.chronica_logs.append(log_entry)
    # 最新10件のみ保持
    if len(st.session_state.chronica_logs) > 10:
        st.session_state.chronica_logs = st.session_state.chronica_logs[-10:]


async def process_message(user_input: str, model_name: str, base_url: str, ai_name: str):
    """メッセージを処理して応答を生成"""
    session = st.session_state.mcp_session
    client = st.session_state.ollama_client
    ollama_tools = st.session_state.ollama_tools
    tool_map = st.session_state.tool_map
    messages = st.session_state.messages.copy()
    
    # システムプロンプトを最初に追加（まだ追加されていない場合）
    system_instruction = get_system_instruction(ai_name)
    if not any(msg.get("role") == "system" for msg in messages):
        messages.insert(0, {"role": "system", "content": system_instruction})
    
    # ユーザーメッセージを追加
    messages.append({"role": "user", "content": user_input})
    
    # アバター状態をThinkingに変更
    st.session_state.avatar_state = "thinking"
    
    try:
        response = await asyncio.wait_for(
            client.chat(
                model=model_name,
                messages=messages,
                tools=ollama_tools if ollama_tools else None,
                options={"temperature": 0.7}
            ),
            timeout=120.0
        )
        
        # レスポンスを辞書形式に変換
        if hasattr(response, "model_dump"):
            response_dict = response.model_dump()
        elif hasattr(response, "dict"):
            response_dict = response.dict()
        elif isinstance(response, dict):
            response_dict = response
        else:
            response_dict = {"message": {}}
        
        # Tool Use Loop
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            message = response_dict.get("message", {})
            if not isinstance(message, dict) and hasattr(message, "model_dump"):
                message = message.model_dump()
            elif not isinstance(message, dict) and hasattr(message, "dict"):
                message = message.dict()
            elif not isinstance(message, dict):
                message = {}
            
            content = message.get("content", "")
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls and not isinstance(tool_calls[0], dict):
                tool_calls = [tc.model_dump() if hasattr(tc, "model_dump") else (tc.dict() if hasattr(tc, "dict") else tc) for tc in tool_calls]
            
            if tool_calls:
                # アバター状態をActionに変更
                st.session_state.avatar_state = "action"
                
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        fn = tool_call.get("function", {})
                    else:
                        fn = getattr(tool_call, "function", {})
                    
                    if isinstance(fn, dict):
                        fn_name = fn.get("name", "")
                        fn_args = fn.get("arguments", {})
                    else:
                        fn_name = getattr(fn, "name", "")
                        fn_args = getattr(fn, "arguments", {})
                    
                    if isinstance(fn_args, dict):
                        args = fn_args
                    elif isinstance(fn_args, str):
                        try:
                            args = json.loads(fn_args) if fn_args else {}
                        except:
                            args = {}
                    else:
                        args = {}
                    
                    mcp_tool_name = tool_map.get(fn_name)
                    if not mcp_tool_name:
                        continue
                    
                    # エントリ保存時にスレッドIDを自動追加
                    if mcp_tool_name == "chronica_save_entry" and st.session_state.current_thread_id:
                        if "entry" in args and isinstance(args["entry"], dict):
                            if "thread" not in args["entry"]:
                                args["entry"]["thread"] = {}
                            if not isinstance(args["entry"]["thread"], dict):
                                args["entry"]["thread"] = {"type": "normal"}
                            args["entry"]["thread"]["id"] = st.session_state.current_thread_id
                    
                    try:
                        result = await session.call_tool(mcp_tool_name, args)
                        tool_out = "".join([c.text for c in result.content if hasattr(c, "text")])
                        
                        # メモリログに追加
                        if mcp_tool_name == "chronica_save_entry":
                            try:
                                entry_data = json.loads(tool_out) if isinstance(tool_out, str) else tool_out
                                if "entry_id" in entry_data:
                                    add_memory_log(args.get("entry", {}), "saved")
                            except:
                                pass
                        elif mcp_tool_name == "chronica_search":
                            try:
                                search_data = json.loads(tool_out) if isinstance(tool_out, str) else tool_out
                                if "entries" in search_data:
                                    add_memory_log({"action": "search", "count": len(search_data["entries"])}, "searched")
                            except:
                                pass
                        
                        # ツール応答を履歴に追加
                        tool_call_dict = tool_call if isinstance(tool_call, dict) else {
                            "id": getattr(tool_call, "id", ""),
                            "type": "function",
                            "function": {"name": fn_name, "arguments": json.dumps(fn_args) if not isinstance(fn_args, str) else fn_args}
                        }
                        messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call_dict]
                        })
                        messages.append({
                            "role": "tool",
                            "name": fn_name,
                            "content": tool_out
                        })
                        
                    except Exception as e:
                        st.error(f"ツール呼び出しエラー: {e}")
                        messages.append({
                            "role": "tool",
                            "name": fn_name,
                            "content": json.dumps({"error": str(e)}, ensure_ascii=False)
                        })
                
                # 再生成
                response = await asyncio.wait_for(
                    client.chat(
                        model=model_name,
                        messages=messages,
                        tools=ollama_tools if ollama_tools else None,
                        options={"temperature": 0.7}
                    ),
                    timeout=120.0
                )
                
                if hasattr(response, "model_dump"):
                    response_dict = response.model_dump()
                elif hasattr(response, "dict"):
                    response_dict = response.dict()
                elif isinstance(response, dict):
                    response_dict = response
                else:
                    response_dict = {"message": {}}
            else:
                # テキスト応答
                if content:
                    messages.append({"role": "assistant", "content": content})
                    st.session_state.messages = messages
                    st.session_state.avatar_state = "idle"
                    return content
                break
        
        st.session_state.avatar_state = "idle"
        return "応答の生成に失敗しました。"
        
    except asyncio.TimeoutError:
        st.session_state.avatar_state = "idle"
        st.error("タイムアウト: 応答に時間がかかりすぎています。")
        return None
    except Exception as e:
        st.session_state.avatar_state = "idle"
        st.error(f"エラー: {e}")
        return None


async def init_mcp_connection():
    """MCP接続を初期化"""
    if st.session_state.mcp_session is not None:
        return True
    
    try:
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["run_server.py"],
            env=None
        )
        
        # AsyncExitStackをセッション状態で保持（リソースが閉じられないように）
        if st.session_state.mcp_stack is None:
            st.session_state.mcp_stack = AsyncExitStack()
        
        stdio, write = await st.session_state.mcp_stack.enter_async_context(stdio_client(server_params))
        session = await st.session_state.mcp_stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        
        mcp_tools = await session.list_tools()
        ollama_tools = convert_mcp_tools_to_ollama_tools(mcp_tools)
        tool_map = {t.name.replace(".", "_"): t.name for t in mcp_tools.tools}
        
        st.session_state.mcp_session = session
        st.session_state.ollama_tools = ollama_tools
        st.session_state.tool_map = tool_map
        
        return True
    except Exception as e:
        st.error(f"MCP接続エラー: {e}")
        import traceback
        st.error(traceback.format_exc())
        return False


def check_ollama_running(base_url: str) -> bool:
    """Ollamaが起動しているかチェック"""
    try:
        import httpx
        response = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        return response.status_code == 200
    except:
        return False


def start_ollama_background():
    """Ollamaをバックグラウンドで起動"""
    if st.session_state.ollama_process is not None:
        # 既に起動済み
        if st.session_state.ollama_process.poll() is None:
            return True  # プロセスは実行中
        else:
            # プロセスが終了している
            st.session_state.ollama_process = None
    
    try:
        # Ollamaをバックグラウンドで起動
        if sys.platform == "win32":
            # Windows: CREATE_NO_WINDOWフラグで非表示起動
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        else:
            # Linux/Mac
            process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
        
        st.session_state.ollama_process = process
        
        # 起動を待つ（最大10秒）
        base_url = os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434"
        for _ in range(20):  # 0.5秒 × 20 = 10秒
            time.sleep(0.5)
            if check_ollama_running(base_url):
                return True
        
        # 起動に失敗
        st.error("Ollamaの起動に時間がかかりすぎています。")
        return False
        
    except FileNotFoundError:
        st.error("Ollamaが見つかりません。Ollamaがインストールされているか確認してください。")
        return False
    except Exception as e:
        st.error(f"Ollamaの起動に失敗しました: {e}")
        return False


async def init_ollama_client(base_url: str, model_name: str):
    """Ollamaクライアントを初期化"""
    if st.session_state.ollama_client is not None:
        return True
    
    # Ollamaが起動しているかチェック
    if not check_ollama_running(base_url):
        # 起動していない場合は自動起動
        with st.spinner("Ollamaを起動中..."):
            if not start_ollama_background():
                return False
    
    try:
        client = ollama.AsyncClient(host=base_url)
        await client.show(model_name)
        st.session_state.ollama_client = client
        return True
    except Exception as e:
        st.error(f"Ollama接続エラー: {e}")
        return False


async def select_thread(session):
    """スレッド選択"""
    try:
        threads_result = await session.call_tool("chronica_list_threads", {})
        threads_text = "".join([c.text for c in threads_result.content if hasattr(c, "text")])
        threads_data = json.loads(threads_text) if threads_text else {"threads": []}
        return threads_data.get("threads", [])
    except:
        return []


def main():
    """メインアプリケーション"""
    st.set_page_config(
        page_title="Chronica - Sui",
        page_icon=None,
        layout="wide"
    )
    
    # 設定読み込み
    model_name, base_url, ai_name, show_tool_logs = load_config()
    
    # セッション状態初期化
    init_session_state()
    
    # サイドバー（設定）
    with st.sidebar:
        st.title("設定")
        theme = st.selectbox("テーマ", ["basic", "pop", "tech"], index=0)
        st.markdown(get_theme_css(theme), unsafe_allow_html=True)
        
        if st.button("🔄 リセット"):
            st.session_state.messages = []
            st.session_state.chronica_logs = []
            st.rerun()
    
    # メインレイアウト（2ペイン）
    col_left, col_right = st.columns([7, 3])
    
    with col_left:
        st.title("Chat")
        
        # チャット履歴表示
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["content"])
            elif msg["role"] == "assistant" and msg.get("content"):
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])
        
        # 入力欄
        if user_input := st.chat_input("メッセージを入力..."):
            # 初期化チェック
            if st.session_state.mcp_session is None:
                with st.spinner("MCPサーバーに接続中..."):
                    if not asyncio.run(init_mcp_connection()):
                        st.error("MCPサーバーへの接続に失敗しました。")
                        st.stop()
            
            if st.session_state.ollama_client is None:
                with st.spinner("Ollamaに接続中..."):
                    if not asyncio.run(init_ollama_client(base_url, model_name)):
                        st.error("Ollamaへの接続に失敗しました。")
                        st.stop()
            
            # スレッド選択（初回のみ）
            if st.session_state.current_thread_id is None:
                with st.spinner("スレッドを選択中..."):
                    threads = asyncio.run(select_thread(st.session_state.mcp_session))
                    if threads:
                        # 最初のスレッドを選択（UI改善の余地あり）
                        st.session_state.current_thread_id = threads[0]["thread_id"]
                        st.session_state.current_thread_name = threads[0]["thread_name"]
                    else:
                        # 新規スレッド作成
                        create_result = asyncio.run(
                            st.session_state.mcp_session.call_tool("chronica_create_thread", {
                                "thread_name": f"スレッド {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}",
                                "thread_type": "normal"
                            })
                        )
                        create_text = "".join([c.text for c in create_result.content if hasattr(c, "text")])
                        create_data = json.loads(create_text) if create_text else {}
                        st.session_state.current_thread_id = create_data.get("thread_id")
                        st.session_state.current_thread_name = create_data.get("thread_name", "新規スレッド")
            
            # メッセージ処理
            with st.spinner("考え中..."):
                response = asyncio.run(process_message(user_input, model_name, base_url, ai_name))
                if response:
                    st.rerun()
    
    with col_right:
        st.title("Sui")
        
        # アバター表示
        render_avatar(
            state=st.session_state.avatar_state,
            theme=theme,
            frame=st.session_state.avatar_frame
        )
        st.session_state.avatar_frame = (st.session_state.avatar_frame + 1) % 2
        
        # コンテキスト情報
        st.markdown("### コンテキスト")
        now = datetime.now(JST)
        st.write(f"**時刻**: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        if st.session_state.current_thread_name:
            st.write(f"**スレッド**: {st.session_state.current_thread_name}")
        
        # メモリフィード
        st.markdown("### メモリフィード")
        if st.session_state.chronica_logs:
            for log in reversed(st.session_state.chronica_logs[-5:]):  # 最新5件
                if log["action"] == "saved":
                    render_memory_card(log["entry"], theme)
                elif log["action"] == "searched":
                    st.info(f"{log['entry'].get('count', 0)}件のエントリを検索")
        else:
            st.info("まだメモリがありません")


if __name__ == "__main__":
    main()
