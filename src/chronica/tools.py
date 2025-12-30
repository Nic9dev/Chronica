"""
MCP Tools - 6ツールの登録と実装
"""
from typing import Any, Dict, List, Optional
from mcp import types
from mcp.server import Server

from .store import Store
from .opening import compose_opening
from .summarize import summarize
from .timeparse import parse_event_time


_store: Optional[Store] = None


def set_store(store: Store):
    """Storeインスタンスを設定"""
    global _store
    _store = store


def get_store() -> Store:
    """Storeインスタンスを取得"""
    if _store is None:
        _store = Store()
    return _store


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
                description="オープニングパックを生成します",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "anchor_time": {
                            "type": "string",
                            "description": "基準時刻（ISO文字列、JST、必須）"
                        },
                        "thread_type": {
                            "type": "string",
                            "enum": ["normal", "project"],
                            "description": "スレッドタイプ（必須）"
                        },
                        "last_seen_time": {
                            "type": "string",
                            "description": "最後に見た時刻（ISO文字列、JST、任意）"
                        },
                        "smalltalk_level": {
                            "type": "string",
                            "enum": ["always", "normal", "off"],
                            "description": "雑談レベル（推奨：normal=always, project=off）",
                            "default": "normal"
                        }
                    },
                    "required": ["anchor_time", "thread_type"]
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
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
        import json
        store = get_store()
        
        if name == "chronica.save_entry":
            entry = arguments.get("entry", {})
            
            if "event_time" in entry and isinstance(entry["event_time"], dict):
                event_time_raw = entry["event_time"].get("raw")
                if event_time_raw:
                    anchor_time = entry.get("saved_time")
                    parsed = parse_event_time(event_time_raw, anchor_time)
                    entry["event_time"] = parsed
            
            entry_id = store.save_entry(entry)
            return [types.TextContent(
                type="text",
                text=json.dumps({"entry_id": entry_id}, ensure_ascii=False)
            )]
        
        elif name == "chronica.search":
            entries = store.search(
                thread_type=arguments.get("thread_type"),
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
            entries = store.timeline(
                start_time=arguments.get("start_time"),
                end_time=arguments.get("end_time"),
                thread_type=arguments.get("thread_type"),
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
                    text=json.dumps({"error": "thread_type is required"}, ensure_ascii=False)
                )]
            
            last_seen_time = store.get_last_seen(thread_type)
            result = {"last_seen_time": last_seen_time} if last_seen_time else {"last_seen_time": None}
            return [types.TextContent(
                type="text",
                text=json.dumps(result, ensure_ascii=False)
            )]
        
        elif name == "chronica.compose_opening":
            anchor_time = arguments.get("anchor_time")
            thread_type = arguments.get("thread_type")
            last_seen_time = arguments.get("last_seen_time")
            smalltalk_level = arguments.get("smalltalk_level", "normal")
            
            if not anchor_time or not thread_type:
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": "anchor_time and thread_type are required"}, ensure_ascii=False)
                )]
            
            if not last_seen_time:
                last_seen_time = store.get_last_seen(thread_type)
            
            opening_pack = compose_opening(
                anchor_time=anchor_time,
                thread_type=thread_type,
                last_seen_time=last_seen_time,
                smalltalk_level=smalltalk_level
            )
            return [types.TextContent(
                type="text",
                text=json.dumps(opening_pack, ensure_ascii=False, indent=2)
            )]
        
        elif name == "chronica.summarize":
            mode = arguments.get("mode")
            range_start = arguments.get("range_start")
            range_end = arguments.get("range_end")
            thread_type = arguments.get("thread_type")
            
            if not all([mode, range_start, range_end, thread_type]):
                return [types.TextContent(
                    type="text",
                    text=json.dumps({"error": "mode, range_start, range_end, and thread_type are required"}, ensure_ascii=False)
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
        
        else:
            return [types.TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
            )]
