"""
Chronica MCP Server 起動スクリプト
venv前提: C:\Dev\Chronica\.venv\Scripts\python.exe
"""
import sys
from pathlib import Path

# srcディレクトリをパスに追加（mcp devで実行時もchronica importが通るように）
src_dir = Path(__file__).parent / "src"
sys.path.insert(0, str(src_dir))

from mcp.server.fastmcp import FastMCP
from chronica.store import Store
from chronica.opening import compose_opening
from chronica.summarize import summarize
from chronica.timeparse import parse_event_time
from typing import Optional, List, Dict, Any
import json

# FastMCPインスタンスをグローバル変数として作成
mcp = FastMCP("chronica")

# Storeを初期化
_store = Store()


def get_store() -> Store:
    """Storeインスタンスを取得"""
    return _store


# 6ツールを登録
@mcp.tool(name="chronica.save_entry")
def save_entry(entry: Dict[str, Any]) -> Dict[str, str]:
    """エントリを保存します"""
    # event_time の処理（rawがある場合）
    if "event_time" in entry and isinstance(entry["event_time"], dict):
        event_time_raw = entry["event_time"].get("raw")
        if event_time_raw:
            anchor_time = entry.get("saved_time")
            parsed = parse_event_time(event_time_raw, anchor_time)
            entry["event_time"] = parsed
    
    entry_id = get_store().save_entry(entry)
    return {"entry_id": entry_id}


@mcp.tool(name="chronica.search")
def search(
    thread_type: Optional[str] = None,
    kind: Optional[str] = None,
    tags: Optional[List[str]] = None,
    project: Optional[str] = None,
    limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """エントリを検索します"""
    entries = get_store().search(
        thread_type=thread_type,
        kind=kind,
        tags=tags,
        project=project,
        limit=limit
    )
    return {"entries": entries}


@mcp.tool(name="chronica.timeline")
def timeline(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    thread_type: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 100
) -> Dict[str, List[Dict[str, Any]]]:
    """タイムラインを取得します（期間指定）"""
    entries = get_store().timeline(
        start_time=start_time,
        end_time=end_time,
        thread_type=thread_type,
        kind=kind,
        limit=limit
    )
    return {"entries": entries}


@mcp.tool(name="chronica.get_last_seen")
def get_last_seen(thread_type: str) -> Dict[str, Optional[str]]:
    """最後に見た時刻を取得します"""
    last_seen_time = get_store().get_last_seen(thread_type)
    return {"last_seen_time": last_seen_time} if last_seen_time else {"last_seen_time": None}


@mcp.tool(name="chronica.compose_opening")
def compose_opening_tool(
    anchor_time: str,
    thread_type: str,
    last_seen_time: Optional[str] = None,
    smalltalk_level: str = "normal"
) -> Dict[str, Any]:
    """オープニングパックを生成します"""
    store = get_store()
    
    # last_seen_timeが無ければDBから取得
    if not last_seen_time:
        last_seen_time = store.get_last_seen(thread_type)
    
    opening_pack = compose_opening(
        anchor_time=anchor_time,
        thread_type=thread_type,
        last_seen_time=last_seen_time,
        smalltalk_level=smalltalk_level
    )
    return opening_pack


@mcp.tool(name="chronica.summarize")
def summarize_tool(
    mode: str,
    range_start: str,
    range_end: str,
    thread_type: str
) -> Dict[str, Any]:
    """サマリーパックを生成します（Summary Pack v0.1.2）"""
    summary_pack = summarize(
        mode=mode,
        range_start=range_start,
        range_end=range_end,
        thread_type=thread_type,
        store=get_store()
    )
    return summary_pack


if __name__ == "__main__":
    # STDIOで起動
    mcp.run(transport="stdio")
