"""
コンテキスト生成ロジック（Claude Desktop最適化版）
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .store import Store


def _recency_expression(now: datetime, saved_time_str: Optional[str]) -> str:
    """saved_time から経過表現（日本語）を返す。不正・欠損時は「初回」。"""
    if not saved_time_str or saved_time_str == "auto":
        return "初回"
    try:
        last_time = datetime.fromisoformat(saved_time_str)
    except (ValueError, TypeError):
        return "初回"

    time_diff = now - last_time
    if time_diff.days == 0:
        if time_diff.seconds < 3600:
            return "数分前"
        if time_diff.seconds < 7200:
            return "1時間ほど前"
        hours = time_diff.seconds // 3600
        return f"{hours}時間前"
    if time_diff.days == 1:
        return "昨日"
    if time_diff.days <= 7:
        return f"{time_diff.days}日前"
    weeks = time_diff.days // 7
    return f"{weeks}週間前"


def _entry_preview_label(entry: dict) -> str:
    title = entry.get("title")
    text = entry.get("text") or ""
    if title:
        label = str(title).strip()
    else:
        label = text[:50].replace("\n", " ").strip()
    if len(label) > 50:
        label = label[:50]
    return label or "（無題）"


def _memory_recency(
    store: Store, thread_id: Optional[str], now: datetime
) -> Tuple[str, Optional[str], Optional[dict]]:
    """
    前回記憶からの経過表現とプレビュー（session_tick 用）。
    Returns: (time_expr, last_topic_preview, last_entry_or_none)
    """
    last_entry = None
    if thread_id:
        entries = store.search(thread_id=thread_id, limit=1)
        if entries:
            last_entry = entries[0]
    else:
        last_entry = store.get_last_interaction(thread_id=None)

    if not last_entry:
        return "初回", None, None

    time_expr = _recency_expression(now, last_entry.get("saved_time"))
    if time_expr == "初回":
        return "初回", None, None

    last_topic = (last_entry.get("text") or "")[:120]
    return time_expr, last_topic, last_entry


def session_tick_payload(store: Store, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """
    各会話ターン用の軽量コンテキスト（JSON）。
    MCP はホストに能動プッシュできないため、モデルが毎ターン呼ぶ前提で提供する。
    """
    now = datetime.now().astimezone()
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    hour = now.hour
    if 5 <= hour < 11:
        time_of_day = "朝"
    elif 11 <= hour < 17:
        time_of_day = "昼"
    elif 17 <= hour < 21:
        time_of_day = "夕方"
    else:
        time_of_day = "夜"
    month = now.month
    if month in [12, 1, 2]:
        season = "冬"
    elif month in [3, 4, 5]:
        season = "春"
    elif month in [6, 7, 8]:
        season = "夏"
    else:
        season = "秋"

    time_expr, last_topic, _ = _memory_recency(store, thread_id, now)

    return {
        "now_local": current_time,
        "season": season,
        "time_of_day": time_of_day,
        "since_last_memory": time_expr,
        "last_topic_preview": last_topic,
    }


def _format_flow_section(recent_entries: List[dict], now: datetime) -> str:
    if not recent_entries:
        return "[プロジェクトの直近の流れ]\n- （エントリーがありません）"
    lines = ["[プロジェクトの直近の流れ]"]
    for entry in recent_entries:
        rec = _recency_expression(now, entry.get("saved_time"))
        kind = entry.get("kind", "note")
        label = _entry_preview_label(entry)
        lines.append(f"- {rec} [{kind}] {label}")
    return "\n".join(lines)


def _format_unresolved_section(recent_entries: List[dict], now: datetime) -> str:
    unresolved = [
        e
        for e in recent_entries
        if e.get("kind") in ("question", "action")
    ]
    lines = ["[継続中・未解決]"]
    if not unresolved:
        lines.append("- （該当なし）")
        return "\n".join(lines)
    for entry in unresolved:
        rec = _recency_expression(now, entry.get("saved_time"))
        kind = entry.get("kind", "note")
        label = _entry_preview_label(entry)
        lines.append(f"- {rec} [{kind}] {label}")
    return "\n".join(lines)


def compose_opening_context(store: Store, thread_id: str = None, project: str = None) -> str:
    """
    会話開始時のコンテキストを生成

    Claude向けに最適化：
    - 定型句を削減
    - メタ発言を避ける指示
    - 自然な日本語への誘導
    """
    now = datetime.now().astimezone()

    # 現在時刻情報
    current_time = now.strftime("%Y-%m-%d %H:%M:%S")
    hour = now.hour

    # 時間帯判定（簡潔に）
    if 5 <= hour < 11:
        time_of_day = "朝"
    elif 11 <= hour < 17:
        time_of_day = "昼"
    elif 17 <= hour < 21:
        time_of_day = "夕方"
    else:
        time_of_day = "夜"

    # 季節判定（過度な言及を避けるため、情報提供のみ）
    month = now.month
    if month in [12, 1, 2]:
        season = "冬"
    elif month in [3, 4, 5]:
        season = "春"
    elif month in [6, 7, 8]:
        season = "夏"
    else:
        season = "秋"

    recent_entries = store.search(thread_type="project", project=project, limit=5)
    flow_block = _format_flow_section(recent_entries, now)
    unresolved_block = _format_unresolved_section(recent_entries, now)

    # Claudeへの指示（簡潔に、自然な対話を促す）
    context = f"""=== Chronica Context ===
[現在状況]
- 現在時刻: {current_time}
- 時間帯: {season}の{time_of_day}

{flow_block}

{unresolved_block}

[Claude への指示]
1. 「プロジェクトの直近の流れ」を把握した上で自然に声をかける
2. 時間差に応じた挨拶（「お久しぶりです」「こんにちは」等）
3. 直近の流れの中で最も会話に繋げやすいトピックに自然に触れる
4. 「Chronicaによると」等のメタ発言は避ける
5. 記憶を探すときは thread_id を指定せず thread_type=\"project\" で横断検索する
6. 「エントリーがありません」となった場合は thread_id なしで再検索する
7. ユーザーから新しい情報が得られたら chronica_save_entry で保存
8. 保存時に「保存しました」等の確認は不要

【良い例】
「お久しぶりです！Glama AAAも取れて、PR #3847のマージ待ちという状態ですね。その後動きはありましたか？」

【悪い例】
「こんにちは！Chronicaによると2日前に会話していたようです。」

=== End of Context ===
"""

    return context
