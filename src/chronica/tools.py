"""
MCP Tools - 6ツールの登録と実装
"""
from typing import Any, Dict, List, Optional
from mcp import types
from mcp.server import Server

from .store import Store, set_store, get_store
from .opening import compose_opening_logic
from .summarize import summarize
from .timeparse import parse_event_time


def register_tools(server: Server):
    """MCPツールを登録"""
    
    @server.list_tools()
    async def list_tools() -> List[types.Tool]:
        return [
            types.Tool(
                name="chronica.save_entry",
                description="エントリを保存します",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "entry": {
                            "type": "object",
                            "description": "Entry JSON（version, entry_id, saved_time, thread, kind, text, tags 必須）",
                            "required": ["thread", "kind", "text", "tags"]
                        }
                    },
                    "required": ["entry"]
                }
            ),
            types.Tool(
                name="chronica.search",
                description="エントリを検索します",
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
                            "description": "最大件数",
                            "default": 100
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica.timeline",
                description="タイムラインを取得します（期間指定）",
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
                            "description": "最大件数",
                            "default": 100
                        }
                    }
                }
            ),
            types.Tool(
                name="chronica.get_last_seen",
                description="最後に見た時刻を取得します",
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
                name="chronica.compose_opening",
                description="会話開始時に必ず呼び出すこと。Chronicaから現在時刻や記憶構造を取得する。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "スレッドID（指定時はそのスレッドの最後の対話を取得）"
                        }
                    },
                    "required": []
                }
            ),
            types.Tool(
                name="chronica.summarize",
                description="サマリーパックを生成します（Summary Pack v0.1.2）",
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
                name="chronica.create_thread",
                description="新しいスレッドを作成します",
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
                            "description": "スレッドタイプ",
                            "default": "normal"
                        }
                    },
                    "required": ["thread_name"]
                }
            ),
            types.Tool(
                name="chronica.list_threads",
                description="スレッド一覧を取得します",
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
                name="chronica.get_thread_info",
                description="指定されたスレッドの情報を取得します",
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
            if name == "chronica.save_entry":
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
        
            elif name == "chronica.search":
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
        
            elif name == "chronica.timeline":
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
        
            elif name == "chronica.get_last_seen":
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
        
            elif name == "chronica.compose_opening":
                # スレッドIDが指定されている場合はそれを渡す
                thread_id = arguments.get("thread_id") if arguments else None
                result_text = compose_opening_logic(thread_id=thread_id)
                return [types.TextContent(
                    type="text",
                    text=result_text
                )]
        
            elif name == "chronica.summarize":
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
            
            elif name == "chronica.create_thread":
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
            
            elif name == "chronica.list_threads":
                thread_type = arguments.get("thread_type")
                threads = store.list_threads(thread_type=thread_type)
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"threads": threads}, ensure_ascii=False, indent=2)
                )]
            
            elif name == "chronica.get_thread_info":
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

