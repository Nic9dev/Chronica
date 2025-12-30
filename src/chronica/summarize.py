"""
Summarize - Summary Pack v0.1.2 実装
Chronicaが返す"材料"を構造化
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from zoneinfo import ZoneInfo

from .store import Store

JST = ZoneInfo("Asia/Tokyo")


def summarize(
    mode: str,
    range_start: str,
    range_end: str,
    thread_type: str,
    store: Store
) -> Dict[str, Any]:
    """
    サマリーパックを生成
    
    Args:
        mode: モード（daily/weekly/decision）
        range_start: 範囲開始時刻（ISO文字列、JST）
        range_end: 範囲終了時刻（ISO文字列、JST）
        thread_type: スレッドタイプ（normal/project）
        store: Storeインスタンス
    
    Returns:
        Summary Pack v0.1.2 構造
    """
    # エントリを取得
    entries = store.timeline(
        start_time=range_start,
        end_time=range_end,
        thread_type=thread_type
    )
    
    # 統計情報
    stats = {
        "total_entries": len(entries),
        "by_kind": {}
    }
    for entry in entries:
        kind = entry.get("kind", "unknown")
        stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
    
    # timeline_items
    timeline_items = []
    for entry in entries:
        item = {
            "entry_id": entry["entry_id"],
            "saved_time": entry["saved_time"],
            "kind": entry["kind"],
            "title": entry.get("title"),
            "text": entry.get("text", "")[:200]  # 先頭200文字
        }
        if "event_time" in entry:
            item["event_time"] = entry["event_time"]
        timeline_items.append(item)
    
    # decisions, actions, open_questions の抽出
    decisions = []
    actions = []
    open_questions = []
    
    for entry in entries:
        kind = entry.get("kind", "")
        text = entry.get("text", "")
        title = entry.get("title", "")
        
        # decision_log から decisions を抽出
        if kind == "decision_log" or "decision" in kind.lower():
            decisions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
        
        # action や todo から actions を抽出
        if kind in ["action", "todo", "task"] or "action" in kind.lower():
            actions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
        
        # question や open_question から open_questions を抽出
        if kind in ["question", "open_question"] or "question" in kind.lower():
            open_questions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
    
    # digest_candidates の生成
    digest_candidates = _generate_digest_candidates(
        entries, thread_type, mode
    )
    
    # meta の構築
    meta = {
        "mode": mode,
        "range": {
            "start": range_start,
            "end": range_end
        },
        "thread": {
            "type": thread_type,
            "opening_style": "normal_default" if thread_type == "normal" else "project_default"
        },
        "stats": stats
    }
    
    return {
        "meta": meta,
        "timeline_items": timeline_items,
        "decisions": decisions,
        "actions": actions,
        "open_questions": open_questions,
        "digest_candidates": digest_candidates
    }


def _generate_digest_candidates(
    entries: List[Dict[str, Any]],
    thread_type: str,
    mode: str
) -> Dict[str, Any]:
    """
    digest_candidates を生成（v0.1.2）
    
    Args:
        entries: エントリリスト
        thread_type: スレッドタイプ
        mode: モード
    
    Returns:
        digest_candidates 構造
    """
    highlights = []
    blockers = []
    next_priorities = []
    memory_keep = []
    next_talk_seed = None
    
    # highlights（最大10）
    # 重要そうなエントリを選ぶ（decision_log, summary など）
    for entry in entries:
        kind = entry.get("kind", "")
        if kind in ["decision_log", "summary", "daily_summary", "weekly_review"]:
            highlights.append({
                "entry_id": entry["entry_id"],
                "title": entry.get("title", entry.get("text", "")[:100]),
                "saved_time": entry["saved_time"]
            })
            if len(highlights) >= 10:
                break
    
    # blockers（最大5）
    # blocker や issue を含むエントリ
    for entry in entries:
        text = entry.get("text", "").lower()
        if "blocker" in text or "阻害" in text or "問題" in text or "issue" in text:
            blockers.append({
                "entry_id": entry["entry_id"],
                "title": entry.get("title", entry.get("text", "")[:100]),
                "saved_time": entry["saved_time"]
            })
            if len(blockers) >= 5:
                break
    
    # next_priorities（最大5）
    # action や priority を含むエントリ
    for entry in entries:
        kind = entry.get("kind", "")
        text = entry.get("text", "").lower()
        if kind in ["action", "todo", "task"] or "priority" in text or "優先" in text:
            next_priorities.append({
                "entry_id": entry["entry_id"],
                "title": entry.get("title", entry.get("text", "")[:100]),
                "saved_time": entry["saved_time"]
            })
            if len(next_priorities) >= 5:
                break
    
    # memory_keep と next_talk_seed（通常スレッド向け）
    if thread_type == "normal":
        # memory_keep（最大5）
        # 最近の重要なエントリや興味深いエントリ
        for entry in entries[-10:]:  # 最近10件から選ぶ
            kind = entry.get("kind", "")
            if kind in ["memory", "insight", "note"] or "覚えて" in entry.get("text", ""):
                memory_keep.append({
                    "entry_id": entry["entry_id"],
                    "title": entry.get("title", entry.get("text", "")[:100]),
                    "saved_time": entry["saved_time"]
                })
                if len(memory_keep) >= 5:
                    break
        
        # next_talk_seed（1行）
        # 最近のエントリから話題の種を抽出
        if entries:
            latest = entries[-1]
            text = latest.get("text", "")
            if text:
                # 先頭100文字を種として使う
                next_talk_seed = text[:100].replace("\n", " ").strip()
    
    return {
        "highlights": highlights[:10],
        "blockers": blockers[:5],
        "next_priorities": next_priorities[:5],
        "memory_keep": memory_keep[:5] if thread_type == "normal" else [],
        "next_talk_seed": next_talk_seed if thread_type == "normal" else None
    }

