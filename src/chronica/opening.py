"""
Opening Pack - compose_opening 実装（v0.1.1）
"""
from datetime import datetime
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def compose_opening(
    anchor_time: str,
    thread_type: str,
    last_seen_time: Optional[str] = None,
    smalltalk_level: str = "normal"
) -> Dict[str, Any]:
    """オープニングパックを生成"""
    anchor = datetime.fromisoformat(anchor_time.replace("Z", "+00:00"))
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=JST)
    else:
        anchor = anchor.astimezone(JST)
    
    # time_bucket
    hour = anchor.hour
    if 5 <= hour < 12:
        time_bucket = "morning"
    elif 12 <= hour < 17:
        time_bucket = "afternoon"
    elif 17 <= hour < 22:
        time_bucket = "evening"
    else:
        time_bucket = "late"
    
    # greeting
    if thread_type == "normal":
        if time_bucket == "morning":
            greeting = "おはようございます"
        elif time_bucket == "afternoon":
            greeting = "こんにちは"
        else:
            greeting = "こんばんは"
    else:
        greeting = "お疲れ様です"
    
    # gap_bucket
    gap_bucket = None
    gap_text = None
    if last_seen_time:
        last_seen = datetime.fromisoformat(last_seen_time.replace("Z", "+00:00"))
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=JST)
        else:
            last_seen = last_seen.astimezone(JST)
        
        delta = anchor - last_seen
        hours = delta.total_seconds() / 3600
        
        if hours < 2:
            gap_bucket = "within_2h"
            if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
                gap_text = "さっきもありがとうございました"
        elif hours < 24:
            gap_bucket = "within_24h"
            if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
                gap_text = "久しぶりです"
        elif hours < 24 * 7:
            gap_bucket = "within_7d"
            if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
                gap_text = "お久しぶりです"
        else:
            gap_bucket = "over_7d"
            if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
                gap_text = "大変お久しぶりです"
    
    # season_key
    month = anchor.month
    if month in [12, 1, 2]:
        season_key = "winter"
    elif month in [3, 4, 5]:
        season_key = "spring"
    elif month in [6, 7, 8]:
        season_key = "summer"
    else:
        season_key = "autumn"
    
    # season_text
    season_text = None
    if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
        if season_key == "winter":
            season_text = "寒い日が続きますね"
        elif season_key == "spring":
            season_text = "暖かくなってきましたね"
        elif season_key == "summer":
            season_text = "暑い日が続きますね"
        else:
            season_text = "涼しくなってきましたね"
    
    # opening_text
    parts_list = [greeting]
    if gap_text:
        parts_list.append(gap_text)
    if season_text:
        parts_list.append(season_text)
    
    opening_text = "、".join(parts_list) + "。"
    
    return {
        "opening_text": opening_text,
        "parts": {
            "greeting": greeting,
            "gap": gap_text,
            "season": season_text
        },
        "meta": {
            "time_bucket": time_bucket,
            "gap_bucket": gap_bucket,
            "season_key": season_key
        }
    }
