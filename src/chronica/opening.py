"""
Opening Pack - compose_opening 実装（v0.1.1）
通常＝親近感 / プロジェクト＝信頼感 の方向性を安定させる
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
    """
    オープニングパックを生成
    
    Args:
        anchor_time: 基準時刻（ISO文字列、JST、必須）
        thread_type: スレッドタイプ（normal/project、必須）
        last_seen_time: 最後に見た時刻（ISO文字列、JST、任意）
        smalltalk_level: 雑談レベル（always/normal/off、推奨：normal=always, project=off）
    
    Returns:
        {
            "opening_text": str,
            "parts": {
                "greeting": str,
                "gap": Optional[str],
                "season": Optional[str]
            },
            "meta": {
                "time_bucket": str,  # morning/afternoon/evening/late
                "gap_bucket": Optional[str],  # within_2h/within_24h/within_7d/over_7d
                "season_key": Optional[str]  # winter/spring/summer/autumn
            }
        }
    """
    anchor = datetime.fromisoformat(anchor_time.replace("Z", "+00:00"))
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=JST)
    else:
        anchor = anchor.astimezone(JST)
    
    # time_bucket の決定
    hour = anchor.hour
    if 5 <= hour < 12:
        time_bucket = "morning"
    elif 12 <= hour < 17:
        time_bucket = "afternoon"
    elif 17 <= hour < 22:
        time_bucket = "evening"
    else:
        time_bucket = "late"
    
    # greeting の生成
    if thread_type == "normal":
        if time_bucket == "morning":
            greeting = "おはようございます"
        elif time_bucket == "afternoon":
            greeting = "こんにちは"
        elif time_bucket == "evening":
            greeting = "こんばんは"
        else:
            greeting = "こんばんは"
    else:  # project
        greeting = "お疲れ様です"
    
    # gap_bucket の計算
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
    
    # season_key の決定（簡易版）
    month = anchor.month
    if month in [12, 1, 2]:
        season_key = "winter"
    elif month in [3, 4, 5]:
        season_key = "spring"
    elif month in [6, 7, 8]:
        season_key = "summer"
    else:
        season_key = "autumn"
    
    # season テキスト（通常スレッドのみ、smalltalk_levelがalways/normalの場合）
    season_text = None
    if thread_type == "normal" and smalltalk_level in ["always", "normal"]:
        if season_key == "winter":
            season_text = "寒い日が続きますね"
        elif season_key == "spring":
            season_text = "暖かくなってきましたね"
        elif season_key == "summer":
            season_text = "暑い日が続きますね"
        else:  # autumn
            season_text = "涼しくなってきましたね"
    
    # opening_text の生成
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

