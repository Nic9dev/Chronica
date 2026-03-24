"""
MCPツール定義・実装（Claude Desktop最適化版）
"""
from typing import Any, Dict, List
from mcp import types
from mcp.server import Server

from .store import get_store
from .opening import compose_opening_context
from .summarize import summarize
from .timeparse import parse_event_time


def register_tools(server: Server):
    """MCPツールを登録"""
    
    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name="chronica_save_entry",
                description="""
エントリ（記憶・記録）を保存します。

【使用タイミング】
- ユーザーが新しい情報を提供したとき
- 重要な決定事項があったとき
- タスクや未決事項が発生したとき
- 出来事や質問があったとき

【保存すべきタイミング】
- 「覚えておいて」「忘れないで」「記録して」などの発言
- 「今日〇〇をした」「〇〇に決めた」「〇〇をやる予定」
- 新しい事実・決定・予定・気づき・感情が含まれる発言
- 迷ったら保存する。保存しすぎるほうが保存漏れより良い。
- 「保存しました」等の報告は不要。会話を自然に続ける。

【Claude向けの注意】
- ユーザーに「保存しました」等の確認は不要
- 自然に会話を続ける
- メタ発言（「Chronicaに保存します」等）は避ける
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entry": {
                            "type": "object",
                            "description": "Entry JSON（thread, kind, text, tags は必須）"
                        }
                    },
                    "required": ["entry"]
                }
            ),
            types.Tool(
                name="chronica_search",
                description="""
保存されたエントリを検索します。本文・タグ・種別を含むエントリ一覧を返します。

【記憶の閲覧・一覧（save と対になる操作）】
- 「記憶を見せて」「保存したものを一覧」「Chronicaに何が入ってる？」「最近の記録」では、
  フィルタなしで呼び出す（引数は空オブジェクト {} または limit のみ）。
  全スレッド横断で、保存日時の新しい順に最大100件が返る。
- chronica_list_threads はスレッド名・件数・ID のみ。本文は含まれない。
  本文を一覧・紹介するには必ず本ツール（search）を使う。特定スレッドだけなら thread_id を指定。

【使用タイミング】
- ユーザーが「最近の〜を振り返りたい」と言ったとき
- 特定のタグやトピックの記録を探すとき

【能動的な記憶参照】
- ユーザーの発言に既存の記憶と関連しそうなテーマが出てきたら、
  会話を止めずに裏側でsearchを呼ぶこと。
- 関連記憶が見つかった場合、「Chronicaによると〜」等のメタ発言は不要。
  その記憶を自然に会話に織り込む。
- 例：ユーザーが仕事の悩みを話す → 過去の関連決定事項を検索
  → 「以前〇〇と決めていましたよね」と自然につなげる。
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "スレッドID（指定時はthread_typeより優先）"
                        },
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ"
                        },
                        "kind": {
                            "type": "string",
                            "description": "エントリ種別"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "タグリスト（いずれか一致）"
                        },
                        "project": {
                            "type": "string",
                            "description": "プロジェクト名"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最大件数（省略時100）。一覧表示時も指定可。"
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica_timeline",
                description="""
指定期間のタイムラインを取得します。

【使用タイミング】
- 「今日の振り返り」「この1週間の出来事をまとめて」と依頼されたとき
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "start_time": {
                            "type": "string",
                            "description": "開始時刻（ISO文字列、JST）"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "終了時刻（ISO文字列、JST）"
                        },
                        "thread_id": {
                            "type": "string",
                            "description": "スレッドID（指定時はthread_typeより優先）"
                        },
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ"
                        },
                        "kind": {
                            "type": "string",
                            "description": "エントリ種別"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "最大件数"
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica_get_last_seen",
                description="指定されたスレッドタイプで最後に見た時刻を取得します。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ（必須）"
                        }
                    },
                    "required": ["thread_type"]
                }
            ),
            types.Tool(
                name="chronica_compose_opening",
                description="""
会話開始時に必ず呼び出すこと。
現在時刻、前回の会話からの経過時間、記憶コンテキストを取得します。

【Claude向けの指示】
- 返された情報が絶対的な事実
- 自分で時間を推測しない
- 季節への過度な言及は避ける
- 「Chronicaによると」等のメタ発言は避ける
- 自然に「お久しぶりです」「前回は〜について話していましたね」等と声をかける
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "スレッドID（指定時はそのスレッドの最後の対話を取得）"
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica_summarize",
                description="サマリーパックを生成します（Summary Pack v0.1.2）。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["daily", "weekly", "decision"],
                            "description": "モード"
                        },
                        "range_start": {
                            "type": "string",
                            "description": "範囲開始時刻（ISO文字列、JST）"
                        },
                        "range_end": {
                            "type": "string",
                            "description": "範囲終了時刻（ISO文字列、JST）"
                        },
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ"
                        }
                    },
                    "required": ["mode", "range_start", "range_end", "thread_type"]
                }
            ),
            types.Tool(
                name="chronica_create_thread",
                description="新しいスレッドを作成します。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_name": {
                            "type": "string",
                            "description": "スレッド名"
                        },
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ"
                        }
                    },
                    "required": ["thread_name"]
                }
            ),
            types.Tool(
                name="chronica_list_threads",
                description="""
スレッド一覧を取得します（スレッド名・ID・エントリ件数・日付のみ）。
エントリの本文やタグは含まれない。記憶の中身を見せる・列挙するには chronica_search を使う（引数なしで直近の記憶一覧）。
""",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプでフィルタ（省略時は全て）"
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica_get_thread_info",
                description="指定されたスレッドの情報を取得します。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "スレッドID"
                        }
                    },
                    "required": ["thread_id"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        import json
        store = get_store()
        
        try:
            if name == "chronica_save_entry":
                entry = arguments.get("entry", {})
                
                # バリデーション
                if not entry:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "internal_error", "message": "entry is required"}, ensure_ascii=False)
                    )]
                
                # 必須フィールドのチェック
                if "kind" not in entry or not entry.get("kind"):
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "validation_error", "message": "entry.kind is required"}, ensure_ascii=False)
                    )]
                
                if "text" not in entry or not entry.get("text"):
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "validation_error", "message": "entry.text is required"}, ensure_ascii=False)
                    )]
                
                # threadの処理
                thread = entry.get("thread", {})
                if not isinstance(thread, dict):
                    # threadが文字列の場合は、それをtypeとして使用
                    if isinstance(thread, str):
                        thread_type_str = thread
                        thread = {"type": thread_type_str if thread_type_str in ["normal", "project"] else "normal"}
                    else:
                        thread = {"type": "normal"}
                    entry["thread"] = thread
                
                thread_type = thread.get("type", "normal")
                if thread_type not in ["normal", "project"]:
                    thread_type = "normal"
                    thread["type"] = thread_type
                
                # tagsの処理（リストでない場合は空リストに）
                if "tags" not in entry:
                    entry["tags"] = []
                elif not isinstance(entry["tags"], list):
                    entry["tags"] = []
                
                if "event_time" in entry and isinstance(entry["event_time"], dict):
                    event_time_raw = entry["event_time"].get("raw")
                    if event_time_raw:
                        anchor_time = entry.get("saved_time")
                        parsed = parse_event_time(event_time_raw, anchor_time)
                        entry["event_time"] = parsed
                
                try:
                    entry_id = store.save_entry(entry)
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"entry_id": entry_id}, ensure_ascii=False)
                    )]
                except Exception as e:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "save_error", "message": str(e)}, ensure_ascii=False)
                    )]
        
            elif name == "chronica_search":
                thread_type = arguments.get("thread_type")
                if thread_type and thread_type not in ["normal", "project"]:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_thread", "message": f"thread_type must be 'normal' or 'project', got: {thread_type}"}, ensure_ascii=False)
                    )]
                
                entries = store.search(
                    thread_id=arguments.get("thread_id"),
                    thread_type=thread_type,
                    kind=arguments.get("kind"),
                    tags=arguments.get("tags"),
                    project=arguments.get("project"),
                    limit=arguments.get("limit", 100)
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
                )]
        
            elif name == "chronica_timeline":
                thread_type = arguments.get("thread_type")
                if thread_type and thread_type not in ["normal", "project"]:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_thread", "message": f"thread_type must be 'normal' or 'project', got: {thread_type}"}, ensure_ascii=False)
                    )]
                
                entries = store.timeline(
                    start_time=arguments.get("start_time"),
                    end_time=arguments.get("end_time"),
                    thread_type=thread_type,
                    kind=arguments.get("kind"),
                    limit=arguments.get("limit", 100)
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
                )]
        
            elif name == "chronica_get_last_seen":
                thread_type = arguments.get("thread_type")
                if not thread_type:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_thread", "message": "thread_type is required"}, ensure_ascii=False)
                    )]
                
                if thread_type not in ["normal", "project"]:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_thread", "message": f"thread_type must be 'normal' or 'project', got: {thread_type}"}, ensure_ascii=False)
                    )]
                
                last_seen_time = store.get_last_seen(thread_type)
                result = {"last_seen_time": last_seen_time} if last_seen_time else {"last_seen_time": None}
                return [types.TextContent(
                    type="text",
                    text=json.dumps(result, ensure_ascii=False)
                )]
        
            elif name == "chronica_compose_opening":
                # スレッドIDが指定されている場合はそれを渡す
                thread_id = arguments.get("thread_id") if arguments else None
                context = compose_opening_context(store, thread_id)
                return [types.TextContent(
                    type="text",
                    text=context
                )]
        
            elif name == "chronica_summarize":
                mode = arguments.get("mode")
                range_start = arguments.get("range_start")
                range_end = arguments.get("range_end")
                thread_type = arguments.get("thread_type")
                
                if not all([mode, range_start, range_end, thread_type]):
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_range", "message": "mode, range_start, range_end, and thread_type are required"}, ensure_ascii=False)
                    )]
                
                if mode not in ["daily", "weekly", "decision"]:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_range", "message": f"mode must be 'daily', 'weekly', or 'decision', got: {mode}"}, ensure_ascii=False)
                    )]
                
                if thread_type not in ["normal", "project"]:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "invalid_thread", "message": f"thread_type must be 'normal' or 'project', got: {thread_type}"}, ensure_ascii=False)
                    )]
                
                summary_pack = summarize(
                    mode=mode,
                    range_start=range_start,
                    range_end=range_end,
                    thread_type=thread_type,
                    store=store
                )
                return [types.TextContent(
                    type="text",
                    text=json.dumps(summary_pack, ensure_ascii=False, indent=2)
                )]
            
            elif name == "chronica_create_thread":
                thread_name = arguments.get("thread_name")
                thread_type = arguments.get("thread_type", "normal")
                
                if not thread_name:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "validation_error", "message": "thread_name is required"}, ensure_ascii=False)
                    )]
                
                if thread_type not in ["normal", "project"]:
                    thread_type = "normal"
                
                thread_id = store.create_thread(thread_name, thread_type)
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"thread_id": thread_id, "thread_name": thread_name, "thread_type": thread_type}, ensure_ascii=False)
                )]
            
            elif name == "chronica_list_threads":
                thread_type = arguments.get("thread_type")
                threads = store.list_threads(thread_type=thread_type)
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"threads": threads}, ensure_ascii=False, indent=2)
                )]
            
            elif name == "chronica_get_thread_info":
                thread_id = arguments.get("thread_id")
                
                if not thread_id:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "validation_error", "message": "thread_id is required"}, ensure_ascii=False)
                    )]
                
                thread_info = store.get_thread_info(thread_id)
                if thread_info:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps(thread_info, ensure_ascii=False, indent=2)
                    )]
                else:
                    return [types.TextContent(
                        type="text",
                        text=json.dumps({"error": "not_found", "message": f"Thread {thread_id} not found"}, ensure_ascii=False)
                    )]
            
            else:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": "internal_error", "message": f"Unknown tool: {name}"}, ensure_ascii=False)
                )]
        
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": "internal_error", "message": str(e)}, ensure_ascii=False)
            )]

