"""
Summarize - Summary Pack v0.1.2 実装
"""
from typing import List, Dict, Any
from .store import Store


def summarize(
    mode: str,
    range_start: str,
    range_end: str,
    thread_type: str,
    store: Store
) -> Dict[str, Any]:
    """サマリーパックを生成"""
    entries = store.timeline(
        start_time=range_start,
        end_time=range_end,
        thread_type=thread_type
    )
    
    stats = {
        "total_entries": len(entries),
        "by_kind": {}
    }
    for entry in entries:
        kind = entry.get("kind", "unknown")
        stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
    
    timeline_items = []
    for entry in entries:
        item = {
            "entry_id": entry["entry_id"],
            "saved_time": entry["saved_time"],
            "kind": entry["kind"],
            "title": entry.get("title"),
            "text": entry.get("text", "")[:200]
        }
        if "event_time" in entry:
            item["event_time"] = entry["event_time"]
        timeline_items.append(item)
    
    decisions = []
    actions = []
    open_questions = []
    
    for entry in entries:
        kind = entry.get("kind", "")
        text = entry.get("text", "")
        title = entry.get("title", "")
        
        if kind == "decision_log" or "decision" in kind.lower():
            decisions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
        
        if kind in ["action", "todo", "task"] or "action" in kind.lower():
            actions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
        
        if kind in ["question", "open_question"] or "question" in kind.lower():
            open_questions.append({
                "entry_id": entry["entry_id"],
                "saved_time": entry["saved_time"],
                "title": title or text[:100],
                "text": text
            })
    
    digest_candidates = _generate_digest_candidates(entries, thread_type, mode)
    
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
    """digest_candidates を生成"""
    highlights = []
    blockers = []
    next_priorities = []
    memory_keep = []
    next_talk_seed = None
    
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
    
    if thread_type == "normal":
        for entry in entries[-10:]:
            kind = entry.get("kind", "")
            if kind in ["memory", "insight", "note"] or "覚えて" in entry.get("text", ""):
                memory_keep.append({
                    "entry_id": entry["entry_id"],
                    "title": entry.get("title", entry.get("text", "")[:100]),
                    "saved_time": entry["saved_time"]
                })
                if len(memory_keep) >= 5:
                    break
        
        if entries:
            latest = entries[-1]
            text = latest.get("text", "")
            if text:
                next_talk_seed = text[:100].replace("\n", " ").strip()
    
    return {
        "highlights": highlights[:10],
        "blockers": blockers[:5],
        "next_priorities": next_priorities[:5],
        "memory_keep": memory_keep[:5] if thread_type == "normal" else [],
        "next_talk_seed": next_talk_seed if thread_type == "normal" else None
    }
