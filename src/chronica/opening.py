"""
コンテキスト生成ロジック（Claude Desktop最適化版）
"""
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from .store import Store


def _memory_recency(
    store: Store, thread_id: Optional[str], now: datetime
) -> Tuple[str, Optional[str], Optional[dict]]:
    """
    前回記憶からの経過表現とプレビュー。
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

    try:
        saved_time_str = last_entry.get("saved_time")
        if not saved_time_str or saved_time_str == "auto":
            raise ValueError("Invalid saved_time")
        last_time = datetime.fromisoformat(saved_time_str)
    except (ValueError, TypeError):
        return "初回", None, None

    time_diff = now - last_time
    if time_diff.days == 0:
        if time_diff.seconds < 3600:
            time_expr = "数分前"
        elif time_diff.seconds < 7200:
            time_expr = "1時間ほど前"
        else:
            hours = time_diff.seconds // 3600
            time_expr = f"{hours}時間前"
    elif time_diff.days == 1:
        time_expr = "昨日"
    elif time_diff.days <= 7:
        time_expr = f"{time_diff.days}日前"
    else:
        weeks = time_diff.days // 7
        time_expr = f"{weeks}週間前"

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


def compose_opening_context(store: Store, thread_id: str = None) -> str:
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

    time_expr, last_text_short, last_entry = _memory_recency(store, thread_id, now)

    memory_context = ""
    if last_entry is not None and last_text_short is not None:
        last_text = last_entry.get("text", "")[:100]
        memory_context = f"""
[記憶コンテキスト]
- 前回の会話: {time_expr}
- 前回のトピック: {last_text}
"""
    else:
        time_expr = "初回"
        memory_context = """
[記憶コンテキスト]
- 初めての会話です
"""

    # Claudeへの指示（簡潔に、自然な対話を促す）
    context = f"""=== Chronica Context ===
[現在状況]
- 現在時刻: {current_time}
- 時間帯: {season}の{time_of_day}

{memory_context}

[Claude への指示]
1. 上記の情報を基に、自然に声をかけてください
2. 時間差に応じた挨拶（例: 「お久しぶりです」「こんにちは」）
3. 前回のトピックに自然に触れる
4. 季節や時間帯への過度な言及は避ける
5. 「Chronicaによると」等のメタ発言は避ける
6. ユーザーから新しい情報が得られたら chronica_save_entry で保存
7. 保存時に「保存しました」等の確認は不要
8. 2通目以降の各ユーザーメッセージでは、返答前に chronica_session_tick を呼び現在時刻・経過を同期すること

【良い例】
「お久しぶりです！前回はChronicaのプライバシーモード設計について話していましたね。その後の進捗はどうですか？」

【悪い例】
「こんにちは！{season}の{time_of_day}ですね。Chronicaによると前回は{time_expr}に会話していたようです。」

=== End of Context ===
"""

    return context
