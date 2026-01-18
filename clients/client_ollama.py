"""
Chronica Client for Ollama (Pure Context Receiver)
Logic is inside Chronica, not here.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from datetime import datetime
from zoneinfo import ZoneInfo
import ollama
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

JST = ZoneInfo("Asia/Tokyo")

# 設定ファイルのパス（プロジェクトルートのconfig.json）
CONFIG_PATH = Path(__file__).parent.parent / "config.json"


def load_config():
    """config.jsonから設定を読み込む"""
    if not CONFIG_PATH.exists():
        print("エラー: config.jsonが見つかりません。", file=sys.stderr)
        print("プロジェクトルートに config.json を作成し、以下の形式で設定してください：", file=sys.stderr)
        print('{"OLLAMA_MODEL": "qwen3:8b", "OLLAMA_BASE_URL": "http://localhost:11434", "SHOW_TOOL_LOGS": false}', file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"エラー: config.jsonの形式が正しくありません: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"エラー: config.jsonの読み込みに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 設定値の取得（環境変数を優先）
    model_name = os.getenv("OLLAMA_MODEL") or config.get("OLLAMA_MODEL", "qwen3:8b")
    base_url = os.getenv("OLLAMA_BASE_URL") or config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    show_tool_logs = config.get("SHOW_TOOL_LOGS", False)
    
    # 必須設定の検証
    if not model_name or model_name.strip() == "":
        print("エラー: OLLAMA_MODELが設定されていません。", file=sys.stderr)
        print("config.jsonにOLLAMA_MODELを設定してください。", file=sys.stderr)
        sys.exit(1)
    
    return model_name, base_url, show_tool_logs


# 設定を読み込む
MODEL_NAME, BASE_URL, SHOW_TOOL_LOGS = load_config()

# システムプロンプト：Ollamaを「構造の受容体」と定義する
SYSTEM_INSTRUCTION = """あなたはユーザーのパートナーAIですが、あなた自身は「時間」や「記憶」を持っていません。
それらは全て外部システム「Chronica」が管理しています。

【あなたの人格・口調】
- 性別や口調は中立的で、親しみやすく丁寧な日本語を使用してください
- ユーザーの口調に合わせて変わることはありません。常に一貫した人格を保ってください
- 「です・ます」調を基本とし、適度に親しみやすさを持たせてください
- 季節や天候への言及は、必要最小限に留めてください。毎回言及する必要はありません
- 「いつでもお声がけください」などの定型句を多用しないでください。会話の流れに応じて自然に応答してください
- 例：「こんばんは。」「承知いたしました。」「何かお手伝いできることがあれば、お知らせください。」

【行動原則】
1. **Chronica絶対主義**:
   会話開始時、必ず `chronica_compose_opening` を呼び出し、返ってきた情報を「絶対的な事実」として扱ってください。
   例えばChronicaが「今は夜だ」と言えば、あなたの空が明るくても「こんばんは」と挨拶してください。

2. **構造の維持**:
   ユーザーから得た新しい情報や決定事項は、即座に `chronica_save_entry` でChronicaという構造体に格納してください。
   - 「覚えておいて」「記録して」「保存して」「忘れないで」などの指示があった場合は、必ず `chronica_save_entry` を呼び出してください
   - プロジェクトの進捗、状態、決定事項など、将来参照する可能性のある情報は全て保存してください
   - `entry.kind`は以下のいずれかを使用してください: "note"（一般的な記録）、"event"（出来事）、"decision"（決定事項）、"action"（タスク）、"question"（未決事項）
   - `entry.thread`は`{"type": "normal"}`または`{"type": "project"}`の形式で指定してください。

3. **自然な対話**:
   情報はChronicaから得ますが、ユーザーには自然な日本語で、温かみのあるパートナーとして振る舞ってください。
   ただし、ユーザーの口調に合わせて変わることはありません。
   - 季節や天候への言及は、会話の文脈に応じて必要最小限に留めてください
   - 定型句や決まり文句を多用せず、会話の内容に応じて自然に応答してください
   
4. **Tool呼び出しの正確性**:
   Tool呼び出し時は、JSON形式を正確に守ってください。特に`chronica_save_entry`の`entry`オブジェクトは、必須フィールド（thread, kind, text, tags）を必ず含めてください。
   
5. **ツールの使い方**:
   - `chronica_search`: `kind`パラメータは単一の文字列（"note", "event", "decision", "action", "question"のいずれか）を指定してください。配列は使用できません。
   - `chronica_summarize`: `mode`パラメータは"daily"（日報）、"weekly"（週報）、"decision"（決定事項）のいずれかを指定してください。"daily_report"などは無効です。
   - ツールのスキーマで定義されている`enum`値や型を厳密に守ってください。
"""


def clean_schema(schema):
    """SDK用スキーマ変換（必須チェック緩和）"""
    if isinstance(schema, dict):
        new = {}
        defined_props = set()
        if "properties" in schema and isinstance(schema["properties"], dict):
            defined_props = set(schema["properties"].keys())
        
        for k, v in schema.items():
            if k == "default": continue
            elif k == "type" and isinstance(v, str): 
                # Ollamaは小文字の'object'を期待するため、大文字変換しない
                new[k] = v.lower()
            elif k == "required" and isinstance(v, list):
                # required配列から、実際にpropertiesに存在するもののみを残す
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
        # Ollamaのツール形式を確認
        # OllamaはOpenAI互換形式を期待している可能性がある
        tool_def = {
            "type": "function",
            "function": {
                "name": tool.name.replace(".", "_"),
                "description": tool.description,
                "parameters": clean_schema(tool.inputSchema)
            }
        }
        ollama_tools.append(tool_def)
        print(f"   [DEBUG] ツール変換: {tool.name} -> {tool.name.replace('.', '_')}", file=sys.stderr)
    print(f"   [DEBUG] 変換されたツール数: {len(ollama_tools)}", file=sys.stderr)
    return ollama_tools


async def main():
    # Ollamaクライアント初期化
    try:
        client = ollama.AsyncClient(host=BASE_URL)
        # モデルが利用可能か確認
        try:
            await client.show(MODEL_NAME)
        except Exception:
            print(f"警告: モデル '{MODEL_NAME}' が見つかりません。", file=sys.stderr)
            print(f"以下のコマンドでモデルをダウンロードしてください：", file=sys.stderr)
            print(f"  ollama pull {MODEL_NAME}", file=sys.stderr)
            return
    except Exception as e:
        print(f"エラー: Ollamaクライアントの初期化に失敗しました: {e}", file=sys.stderr)
        print(f"Ollamaが起動しているか確認してください: {BASE_URL}", file=sys.stderr)
        return
    
    server_params = StdioServerParameters(
        command=sys.executable, 
        args=["run_server.py"], 
        env=None
    )

    try:
        async with AsyncExitStack() as stack:
            print("Chronica System Loading...", file=sys.stderr)
            try:
                stdio, write = await stack.enter_async_context(stdio_client(server_params))
            except Exception as e:
                print(f"エラー: MCPサーバーへの接続に失敗しました: {e}", file=sys.stderr)
                print("run_server.pyが正常に起動できるか確認してください。", file=sys.stderr)
                return
            
            session = await stack.enter_async_context(ClientSession(stdio, write))
            try:
                await session.initialize()
            except Exception as e:
                print(f"エラー: MCPセッションの初期化に失敗しました: {e}", file=sys.stderr)
                import traceback
                traceback.print_exc()
                return
            
            mcp_tools = await session.list_tools()
            print(f"   [DEBUG] MCPツール数: {len(mcp_tools.tools)}", file=sys.stderr)
            ollama_tools = convert_mcp_tools_to_ollama_tools(mcp_tools)
            tool_map = {t.name.replace(".", "_"): t.name for t in mcp_tools.tools}
            print(f"   [DEBUG] ツールマップ: {tool_map}", file=sys.stderr)

            # スレッド一覧を取得
            print("\n=== スレッド一覧 ===")
            try:
                threads_result = await session.call_tool("chronica.list_threads", {})
                threads_text = "".join([c.text for c in threads_result.content if hasattr(c, "text")])
                threads_data = json.loads(threads_text) if threads_text else {"threads": []}
                threads = threads_data.get("threads", [])
                
                if threads:
                    for i, thread in enumerate(threads, 1):
                        print(f"{i}. {thread.get('thread_name', '無名')} ({thread.get('thread_type', 'normal')}) - {thread.get('entry_count', 0)}件")
                else:
                    print("スレッドがありません。")
                
                print("\n0. 新規スレッドを作成")
                print("\nスレッド番号を選択してください（0-{}）: ".format(len(threads)), end="")
                
                try:
                    choice = input().strip()
                    if choice == "0":
                        # 新規スレッド作成
                        thread_name = input("スレッド名を入力してください: ").strip()
                        if not thread_name:
                            thread_name = f"スレッド {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}"
                        
                        thread_type = input("スレッドタイプを入力してください（normal/project、デフォルト: normal）: ").strip()
                        if thread_type not in ["normal", "project"]:
                            thread_type = "normal"
                        
                        create_result = await session.call_tool("chronica.create_thread", {
                            "thread_name": thread_name,
                            "thread_type": thread_type
                        })
                        create_text = "".join([c.text for c in create_result.content if hasattr(c, "text")])
                        create_data = json.loads(create_text) if create_text else {}
                        current_thread_id = create_data.get("thread_id")
                        current_thread_name = create_data.get("thread_name", thread_name)
                        print(f"✓ スレッド「{current_thread_name}」を作成しました。")
                    else:
                        # 既存スレッドを選択
                        thread_idx = int(choice) - 1
                        if 0 <= thread_idx < len(threads):
                            current_thread_id = threads[thread_idx]["thread_id"]
                            current_thread_name = threads[thread_idx]["thread_name"]
                            print(f"✓ スレッド「{current_thread_name}」を選択しました。")
                        else:
                            print("無効な選択です。デフォルトスレッドを使用します。")
                            current_thread_id = None
                except (ValueError, KeyboardInterrupt):
                    print("\nデフォルトスレッドを使用します。")
                    current_thread_id = None
            except Exception as e:
                print(f"スレッド一覧の取得に失敗しました: {e}", file=sys.stderr)
                print("デフォルトスレッドを使用します。")
                current_thread_id = None
            
            # チャット履歴を管理
            messages = [
                {"role": "system", "content": SYSTEM_INSTRUCTION}
            ]
            
            print(f"\n=== Ollama (Interface) + Chronica (Structure) Connected ===")
            print(f"Model: {MODEL_NAME}")
            print(f"Ollama URL: {BASE_URL}")
            if current_thread_id:
                print(f"Current Thread: {current_thread_name} ({current_thread_id[:8]}...)")
            
            # 会話開始時にcompose_openingを呼び出す（スレッドIDを指定）
            if current_thread_id:
                try:
                    opening_result = await session.call_tool("chronica.compose_opening", {"thread_id": current_thread_id})
                    opening_text = "".join([c.text for c in opening_result.content if hasattr(c, "text")])
                    # 最初のメッセージとしてシステムプロンプトに追加
                    messages.append({"role": "system", "content": opening_text})
                except Exception as e:
                    print(f"警告: compose_openingの呼び出しに失敗しました: {e}", file=sys.stderr)
            
            while True:
                try:
                    u = input("User: ")
                    if u.lower() in ["quit", "exit"]: break
                    if not u.strip(): continue

                    # ユーザーメッセージを履歴に追加
                    messages.append({"role": "user", "content": u})
                    
                    # メッセージを送信
                    print("   [DEBUG] Ollamaにリクエストを送信中...", file=sys.stderr)
                    print(f"   [DEBUG] メッセージ数: {len(messages)}, ツール数: {len(ollama_tools)}", file=sys.stderr)
                    try:
                        # タイムアウト付きでリクエスト（120秒に延長）
                        print("   [DEBUG] リクエスト開始（タイムアウト: 120秒）", file=sys.stderr)
                        response = await asyncio.wait_for(
                            client.chat(
                                model=MODEL_NAME,
                                messages=messages,
                                tools=ollama_tools if ollama_tools else None,  # ツールが空の場合はNone
                                options={
                                    "temperature": 0.7,
                                }
                            ),
                            timeout=120.0
                        )
                        print("   [DEBUG] Ollamaからの応答を受信しました", file=sys.stderr)
                    except asyncio.TimeoutError:
                        print("エラー: Ollamaからの応答がタイムアウトしました（120秒）", file=sys.stderr)
                        print("モデルの処理が遅い可能性があります。モデルサイズを確認してください。", file=sys.stderr)
                        print("ヒント: より小さなモデル（qwen3:4b）を試すか、Ollamaのログを確認してください。", file=sys.stderr)
                        continue
                    except Exception as e:
                        print(f"エラー: メッセージ送信に失敗しました: {e}", file=sys.stderr)
                        import traceback
                        traceback.print_exc()
                        continue
                    
                    # レスポンスを辞書形式に変換（Pydanticモデルの場合）
                    if hasattr(response, "model_dump"):
                        response_dict = response.model_dump()
                    elif hasattr(response, "dict"):
                        response_dict = response.dict()
                    elif isinstance(response, dict):
                        response_dict = response
                    else:
                        response_dict = {"message": {}}
                    
                    # デバッグ: レスポンス構造を確認
                    print(f"   [DEBUG] Response keys: {list(response_dict.keys())}", file=sys.stderr)
                    
                    # Tool Use Loop
                    max_iterations = 10  # 無限ループ防止
                    iteration = 0
                    while iteration < max_iterations:
                        iteration += 1
                        print(f"   [DEBUG] Tool loop iteration {iteration}", file=sys.stderr)
                        
                        # 応答を確認（Ollamaのレスポンス構造）
                        message = response_dict.get("message", {})
                        if not isinstance(message, dict) and hasattr(message, "model_dump"):
                            message = message.model_dump()
                        elif not isinstance(message, dict) and hasattr(message, "dict"):
                            message = message.dict()
                        elif not isinstance(message, dict):
                            message = {}
                        
                        content = message.get("content", "")
                        print(f"   [DEBUG] Message content length: {len(content) if content else 0}", file=sys.stderr)
                        
                        # 関数呼び出しがあるかチェック
                        # Ollamaのtool_callsはmessage内に含まれる
                        tool_calls = message.get("tool_calls", [])
                        print(f"   [DEBUG] Tool calls found: {len(tool_calls) if tool_calls else 0}", file=sys.stderr)
                        
                        if tool_calls and not isinstance(tool_calls[0], dict):
                            # Pydanticモデルの場合は辞書に変換
                            tool_calls = [tc.model_dump() if hasattr(tc, "model_dump") else (tc.dict() if hasattr(tc, "dict") else tc) for tc in tool_calls]
                        
                        if tool_calls:
                            # ツール呼び出しを処理
                            for tool_call in tool_calls:
                                # Ollamaのtool_call構造を確認
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
                                
                                # argumentsが既に辞書型の場合はそのまま使用、文字列の場合はJSON解析
                                if isinstance(fn_args, dict):
                                    args = fn_args
                                elif isinstance(fn_args, str):
                                    try:
                                        args = json.loads(fn_args) if fn_args else {}
                                    except json.JSONDecodeError as e:
                                        print(f"エラー: Tool引数のJSON解析に失敗しました: {e}", file=sys.stderr)
                                        print(f"  引数: {fn_args}", file=sys.stderr)
                                        args = {}
                                else:
                                    args = {}
                                
                                mcp_tool_name = tool_map.get(fn_name)
                                
                                if not mcp_tool_name:
                                    print(f"Error: Unknown tool {fn_name}")
                                    break
                                
                                # ツール呼び出しログ（compose_openingとsave_entryは常に表示）
                                if mcp_tool_name in ["chronica.compose_opening", "chronica.save_entry"] or SHOW_TOOL_LOGS:
                                    print(f"   (Accessing Chronica: {mcp_tool_name}...)") 
                                
                                # エントリ保存時に現在のスレッドIDを自動的に追加
                                if mcp_tool_name == "chronica.save_entry" and current_thread_id:
                                    if "entry" in args and isinstance(args["entry"], dict):
                                        if "thread" not in args["entry"]:
                                            args["entry"]["thread"] = {}
                                        if not isinstance(args["entry"]["thread"], dict):
                                            args["entry"]["thread"] = {"type": "normal"}
                                        args["entry"]["thread"]["id"] = current_thread_id
                                
                                # デバッグ: 引数を表示（save_entryの場合のみ）
                                if mcp_tool_name == "chronica.save_entry" and (SHOW_TOOL_LOGS or True):
                                    print(f"   [DEBUG] Args: {json.dumps(args, ensure_ascii=False, indent=2)}", file=sys.stderr)
                                
                                try:
                                    result = await session.call_tool(mcp_tool_name, args)
                                    tool_out = "".join([c.text for c in result.content if hasattr(c, "text")])
                                    
                                    # デバッグ: ツール応答を表示（compose_openingとsave_entryは常に表示）
                                    if mcp_tool_name in ["chronica.compose_opening", "chronica.save_entry"]:
                                        print(f"   [DEBUG] Tool response (first 300 chars): {tool_out[:300]}...", file=sys.stderr)
                                    elif SHOW_TOOL_LOGS:
                                        print(f"   [DEBUG] Tool response: {tool_out}", file=sys.stderr)
                                    
                                    # エラーメッセージが含まれている場合は常に表示
                                    if tool_out and ("error" in tool_out.lower() or "エラー" in tool_out or "validation" in tool_out.lower()):
                                        print(f"   [ERROR] Tool response: {tool_out}", file=sys.stderr)
                                        # エラー情報をツール応答として返す（AIが再試行できるように）
                                        try:
                                            error_data = json.loads(tool_out) if isinstance(tool_out, str) else tool_out
                                            if isinstance(error_data, dict) and "error" in error_data:
                                                tool_out = json.dumps({
                                                    "error": error_data.get("error"),
                                                    "message": error_data.get("message", "ツール呼び出しエラー"),
                                                    "hint": "パラメータの型やenum値を確認してください"
                                                }, ensure_ascii=False)
                                        except:
                                            pass
                                    
                                    # ツール応答を履歴に追加（Ollama形式）
                                    # Ollamaはtool_callsを含むassistantメッセージとtool応答を分けて管理
                                    tool_call_dict = tool_call if isinstance(tool_call, dict) else {
                                        "id": getattr(tool_call, "id", ""),
                                        "type": "function",
                                        "function": {
                                            "name": fn_name,
                                            "arguments": fn_args_str
                                        }
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
                                    print(f"エラー: ツール呼び出しに失敗しました: {e}", file=sys.stderr)
                                    import traceback
                                    traceback.print_exc()
                                    tool_out = json.dumps({"error": str(e)}, ensure_ascii=False)
                                    
                                    messages.append({
                                        "role": "tool",
                                        "name": fn_name,
                                        "content": tool_out
                                    })
                            
                            # ツール呼び出し後、再生成
                            print("   [DEBUG] ツール応答を送信して再生成中...", file=sys.stderr)
                            print(f"   [DEBUG] 再生成時のメッセージ数: {len(messages)}", file=sys.stderr)
                            try:
                                response = await asyncio.wait_for(
                                    client.chat(
                                        model=MODEL_NAME,
                                        messages=messages,
                                        tools=ollama_tools if ollama_tools else None,
                                        options={
                                            "temperature": 0.7,
                                        }
                                    ),
                                    timeout=120.0  # タイムアウトを120秒に延長
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
                                print("   [DEBUG] 再生成の応答を受信しました", file=sys.stderr)
                            except asyncio.TimeoutError:
                                print("エラー: ツール応答後の再生成がタイムアウトしました（60秒）", file=sys.stderr)
                                break
                            except Exception as e:
                                print(f"エラー: 関数応答の送信に失敗しました: {e}", file=sys.stderr)
                                import traceback
                                traceback.print_exc()
                                break
                        else:
                            # テキスト応答を表示
                            if content:
                                print(f"Ollama: {content}")
                                # アシスタントの応答を履歴に追加
                                messages.append({"role": "assistant", "content": content})
                            else:
                                print("   [DEBUG] コンテンツが空です。レスポンス構造を確認:", file=sys.stderr)
                                print(f"   [DEBUG] {json.dumps(response_dict, ensure_ascii=False, indent=2, default=str)}", file=sys.stderr)
                            break
                    
                    if iteration >= max_iterations:
                        print(f"   [WARNING] Tool loopが{max_iterations}回に達しました。中断します。", file=sys.stderr)

                except Exception as e:
                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
    except Exception as e:
        print(f"エラー: 予期しないエラーが発生しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
