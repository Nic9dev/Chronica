"""
Chronica Logic: Opening & Context
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any

from .store import Store, get_store

JST = ZoneInfo("Asia/Tokyo")
logger = logging.getLogger("chronica.logic.opening")


def get_season_context(now: datetime) -> str:
    """季節・時間帯のコンテキストを生成"""
    month = now.month
    hour = now.hour
    
    # 季節判定
    if month in [12, 1, 2]:
        season = "冬"
    elif month in [3, 4, 5]:
        season = "春"
    elif month in [6, 7, 8]:
        season = "夏"
    else:
        season = "秋"
    
    # 時間帯判定
    if 5 <= hour < 12:
        time_of_day = "朝"
    elif 12 <= hour < 17:
        time_of_day = "午後"
    elif 17 <= hour < 22:
        time_of_day = "夕方・夜"
    else:
        time_of_day = "深夜"
    
    return f"{season}の{time_of_day}"


def get_time_gap_description(last_time_str: Optional[str], now: datetime) -> str:
    """時間差の説明文を生成"""
    if not last_time_str:
        return "初対面またはリセット"
    
    try:
        last_time = datetime.fromisoformat(last_time_str.replace("Z", "+00:00"))
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=JST)
        else:
            last_time = last_time.astimezone(JST)
        
        delta = now - last_time
        hours = delta.total_seconds() / 3600
        
        if hours < 2:
            return "さっき（2時間以内）"
        elif hours < 24:
            return "久しぶり（24時間以内）"
        elif hours < 24 * 7:
            return "お久しぶり（1週間以内）"
        else:
            days = int(hours / 24)
            return f"大変お久しぶり（{days}日以上）"
    except Exception as e:
        logger.warning(f"時間差計算エラー: {e}")
        return "時間差不明"


def compose_opening_logic(thread_id: Optional[str] = None) -> str:
    """
    AIへの指示書（構造）を作成する。
    引数なし。Chronicaが自律的に状況を確定させる。
    
    Args:
        thread_id: スレッドID（指定時はそのスレッドの最後の対話を取得）
    """
    store = get_store()
    
    # 1. 時間構造の確定（Chronicaが支配する）
    now = datetime.now(JST)
    season_text = get_season_context(now)
    
    # 2. 記憶構造の取得（スレッドID指定時はそのスレッドの最後の対話を取得）
    last_seen_entry = store.get_last_interaction(thread_id=thread_id)
    
    if last_seen_entry:
        last_time_str = last_seen_entry.get("saved_time")
        gap_text = get_time_gap_description(last_time_str, now)
        last_topic = last_seen_entry.get("text", "")
        # 長すぎる場合は要約的に切り出し
        if len(last_topic) > 50:
            last_topic = last_topic[:50] + "..."
        
        memory_struct = f"""
        - 前回の会話日時: {last_time_str}
        - 現在との時間差: {gap_text}
        - 前回のトピック: {last_topic}
        """
    else:
        memory_struct = "- 前回の会話: なし（初対面またはリセット）"

    # 3. AIへの「絶対的な指示書」を構築
    # ここで返されるテキストが、AIにとっての「世界の全て」になる
    structure = f"""
=== Chronica Context Structure ===
[現在状況]
- 現在時刻: {now.strftime('%Y-%m-%d %H:%M:%S')}
- 季節・時間帯: {season_text}

[記憶コンテキスト]
{memory_struct}

[AIへの指示]
あなたは上記の「Chronica構造」に基づき、ユーザーに声をかけてください。
1. 「時間差」に言及すること（久しぶり、さっきは、等）。
2. 「季節/時間帯」に合わせたトーンで話すこと。
3. 自分の内部時計ではなく、この構造情報を絶対的な正解とすること。
==================================
"""
    return structure
