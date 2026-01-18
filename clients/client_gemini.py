"""
Chronica Client for Gemini (Pure Context Receiver)
Logic is inside Chronica, not here.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from contextlib import AsyncExitStack
from google import genai
from google.genai import types as genai_types
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 設定ファイルのパス
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    """config.jsonから設定を読み込む"""
    if not CONFIG_PATH.exists():
        print("エラー: config.jsonが見つかりません。", file=sys.stderr)
        print("プロジェクトルートに config.json を作成し、以下の形式で設定してください：", file=sys.stderr)
        print('{"GOOGLE_API_KEY": "あなたのAPIキー", "MODEL_NAME": "models/gemini-2.5-flash"}', file=sys.stderr)
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
    
    # 環境変数を優先（設定ファイルより優先度が高い）
    api_key = os.getenv("GOOGLE_API_KEY") or config.get("GOOGLE_API_KEY")
    model_name = config.get("MODEL_NAME")
    show_tool_logs = config.get("SHOW_TOOL_LOGS", True)  # デフォルトはTrue（表示）
    
    # 必須設定の検証
    if not api_key or api_key.strip() == "" or "ここに" in api_key:
        print("エラー: GOOGLE_API_KEYが設定されていません。", file=sys.stderr)
        print("config.jsonにAPIキーを設定してください。", file=sys.stderr)
        sys.exit(1)
    
    if not model_name or model_name.strip() == "":
        print("エラー: MODEL_NAMEが設定されていません。", file=sys.stderr)
        print("config.jsonにMODEL_NAMEを設定してください。", file=sys.stderr)
        sys.exit(1)
    
    return api_key, model_name, show_tool_logs


# 設定を読み込む
API_KEY, MODEL_NAME, SHOW_TOOL_LOGS = load_config()

# システムプロンプト：Geminiを「構造の受容体」と定義する
SYSTEM_INSTRUCTION = """
あなたはユーザーのパートナーですが、あなた自身は「時間」や「記憶」を持っていません。
それらは全て外部システム「Chronica」が管理しています。

【行動原則】
1. **Chronica絶対主義**:
   会話開始時、必ず `chronica.compose_opening` を呼び出し、返ってきた情報を「絶対的な事実」として扱ってください。
   例えばChronicaが「今は夜だ」と言えば、あなたの空が明るくても「こんばんは」と挨拶してください。

2. **構造の維持**:
   ユーザーから得た新しい情報や決定事項は、即座に `chronica.save_entry` でChronicaという構造体に格納してください。
   - `entry.kind`は以下のいずれかを使用してください: "note"（一般的な記録）、"event"（出来事）、"decision"（決定事項）、"action"（タスク）、"question"（未決事項）
   - `entry.thread`は`{"type": "normal"}`または`{"type": "project"}`の形式で指定してください。

3. **自然な対話**:
   情報はChronicaから得ますが、ユーザーには自然な日本語で、温かみのあるパートナーとして振る舞ってください。
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
                new[k] = v.upper()
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

def recursive_proto_to_dict(obj):
    """Google Protobuf MapComposite -> Python Dict 変換 (エラー回避用)"""
    if hasattr(obj, 'items'): return {k: recursive_proto_to_dict(v) for k, v in obj.items()}
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)): return [recursive_proto_to_dict(v) for v in obj]
    else: return obj

def convert_mcp_tools_to_genai_tools(mcp_tools):
    """MCPツールをGoogle GenAI SDKのツール形式に変換"""
    genai_tools = []
    for tool in mcp_tools.tools:
        # ツール定義をGenAI SDK形式に変換
        tool_def = {
            "function_declarations": [{
                "name": tool.name.replace(".", "_"),
                "description": tool.description,
                "parameters": clean_schema(tool.inputSchema)
            }]
        }
        genai_tools.append(tool_def)
    return genai_tools

async def main():
    # Google GenAI クライアント初期化
    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        print(f"エラー: Google GenAI クライアントの初期化に失敗しました: {e}", file=sys.stderr)
        return
    
    server_params = StdioServerParameters(command=sys.executable, args=["run_server.py"], env=None)

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
            gemini_tools = convert_mcp_tools_to_genai_tools(mcp_tools)
            tool_map = {t.name.replace(".", "_"): t.name for t in mcp_tools.tools}

            # チャット履歴を管理
            chat_history = []
            
            print(f"\n=== Gemini (Interface) + Chronica (Structure) Connected ===")
            print(f"Model: {MODEL_NAME}")
            
            while True:
                try:
                    u = input("User: ")
                    if u.lower() in ["quit", "exit"]: break
                    if not u.strip(): continue

                    # ユーザーメッセージを履歴に追加
                    chat_history.append({"role": "user", "parts": [{"text": u}]})
                    
                    # メッセージを送信
                    try:
                        response = client.models.generate_content(
                            model=MODEL_NAME,
                            contents=chat_history,
                            config=genai_types.GenerateContentConfig(
                                system_instruction=SYSTEM_INSTRUCTION,
                                tools=gemini_tools,
                                temperature=0.7,
                            )
                        )
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                            print(f"\n⚠️  APIリクエスト制限に達しました。", file=sys.stderr)
                            print(f"   無料枠の1日20リクエスト制限に達した可能性があります。", file=sys.stderr)
                            print(f"   しばらく待ってから再試行するか、有料プランにアップグレードしてください。", file=sys.stderr)
                            print(f"   詳細: https://ai.google.dev/gemini-api/docs/rate-limits\n", file=sys.stderr)
                            print("しばらく待ってから再試行してください。または 'quit' で終了します。")
                        else:
                            print(f"エラー: メッセージ送信に失敗しました: {e}", file=sys.stderr)
                            import traceback
                            traceback.print_exc()
                        continue
                    
                    # Tool Use Loop
                    while response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                        part = response.candidates[0].content.parts[0]
                        
                        # 関数呼び出しがあるかチェック
                        if hasattr(part, 'function_call') and part.function_call:
                            fn = part.function_call
                            # Protobuf変換を適用
                            args = recursive_proto_to_dict(fn.args) if hasattr(fn, 'args') else {}
                            
                            gemini_fn_name = fn.name if hasattr(fn, 'name') else ""
                            mcp_tool_name = tool_map.get(gemini_fn_name)
                            
                            if not mcp_tool_name:
                                print(f"Error: Unknown tool {gemini_fn_name}")
                                break
                            
                            if SHOW_TOOL_LOGS:
                                print(f"   (Accessing Chronica: {mcp_tool_name}...)") 
                            
                            # デバッグ: 引数を表示（save_entryの場合のみ、SHOW_TOOL_LOGSがTrueの場合）
                            if mcp_tool_name == "chronica.save_entry" and SHOW_TOOL_LOGS:
                                print(f"   [DEBUG] Args: {json.dumps(args, ensure_ascii=False, indent=2)}", file=sys.stderr)
                            
                            try:
                                result = await session.call_tool(mcp_tool_name, args)
                                tool_out = "".join([c.text for c in result.content if hasattr(c, "text")])
                                
                                # デバッグ: ツール応答を表示（save_entryの場合のみ、SHOW_TOOL_LOGSがTrueの場合）
                                if mcp_tool_name == "chronica.save_entry" and SHOW_TOOL_LOGS:
                                    print(f"   [DEBUG] Tool response: {tool_out}", file=sys.stderr)
                                
                                # エラーメッセージが含まれている場合は常に表示
                                if tool_out and ("error" in tool_out.lower() or "エラー" in tool_out):
                                    print(f"   [ERROR] Tool response: {tool_out}", file=sys.stderr)
                            except Exception as e:
                                print(f"エラー: ツール呼び出しに失敗しました: {e}", file=sys.stderr)
                                import traceback
                                traceback.print_exc()
                                # エラー情報をツール応答として返す
                                tool_out = json.dumps({"error": str(e)}, ensure_ascii=False)
                            
                            # 関数応答を履歴に追加して再送信
                            function_response_part = {
                                "function_response": {
                                    "name": gemini_fn_name,
                                    "response": {"result": tool_out}
                                }
                            }
                            chat_history.append({"role": "model", "parts": [function_response_part]})
                            
                            try:
                                response = client.models.generate_content(
                                    model=MODEL_NAME,
                                    contents=chat_history,
                                    config=genai_types.GenerateContentConfig(
                                        system_instruction=SYSTEM_INSTRUCTION,
                                        tools=gemini_tools,
                                        temperature=0.7,
                                    )
                                )
                            except Exception as e:
                                error_str = str(e)
                                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower():
                                    print(f"\n⚠️  APIリクエスト制限に達しました。", file=sys.stderr)
                                    print(f"   無料枠の1日20リクエスト制限に達した可能性があります。", file=sys.stderr)
                                    print(f"   しばらく待ってから再試行するか、有料プランにアップグレードしてください。", file=sys.stderr)
                                    print(f"   詳細: https://ai.google.dev/gemini-api/docs/rate-limits\n", file=sys.stderr)
                                else:
                                    print(f"エラー: 関数応答の送信に失敗しました: {e}", file=sys.stderr)
                                break
                        else:
                            # テキスト応答を表示
                            text_parts = [p.text for p in response.candidates[0].content.parts if hasattr(p, 'text') and p.text]
                            if text_parts:
                                response_text = ''.join(text_parts)
                                print(f"Gemini: {response_text}")
                                # モデルの応答を履歴に追加
                                chat_history.append({"role": "model", "parts": [{"text": response_text}]})
                            break

                except Exception as e:
                    print(f"Error: {e}")
                    import traceback
                    traceback.print_exc()
    except Exception as e:
        print(f"エラー: 予期しないエラーが発生しました: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform.startswith('win'): asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
