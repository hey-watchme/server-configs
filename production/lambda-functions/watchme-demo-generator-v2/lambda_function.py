#!/usr/bin/env python3
"""
Demo Data Generator V2 - Spot & Daily Analysis
Generates realistic demo data for spot_results and daily_results tables (hourly)
Version: 2.2.0 - JSON-based data patterns
"""

import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List
import random
import requests

# Environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Path to data files (Lambda compatible)
# In Lambda, __file__ is /var/task/lambda_function.py
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data", "child_5yo_active")

# Device configuration for demo account
DEMO_DEVICE_ID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"  # 5-year-old child


def get_jst_now():
    """Get current JST time"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst)


def load_pattern_data(pattern_type: str) -> Dict:
    """
    Load pattern data from JSON file

    Args:
        pattern_type: "spot" or "daily"

    Returns:
        Dict containing pattern data
    """
    filename = f"{pattern_type}_patterns.json"
    filepath = os.path.join(DATA_DIR, filename)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Pattern file not found: {filepath}")
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {filepath}: {e}")


def get_child_5yo_spot_pattern() -> List[Dict]:
    """
    Load 24-hour spot analysis pattern from JSON file

    Returns:
        List of 24 hourly data points for Monday (default)
    """
    data = load_pattern_data("spot")
    # For now, always use Monday pattern
    # TODO: Implement day-of-week logic
    return data["weekly_data"]["monday"]


def get_child_5yo_spot_pattern_legacy() -> List[Dict]:
    """
    Legacy hardcoded pattern (kept for reference, not used)
    """
    pattern = [
        # 00:00 - Midnight
        {
            "hour": 0,
            "vibe_score": 0,
            "summary": "深夜、ぐっすりと睡眠中。静かな寝息が聞こえる。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 01:00
        {
            "hour": 1,
            "vibe_score": -2,
            "summary": "深い睡眠フェーズ。REM睡眠で体が回復している。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 02:00
        {
            "hour": 2,
            "vibe_score": -3,
            "summary": "夜中、少し寝返りを打った。まだ深い眠りが続く。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 03:00
        {
            "hour": 3,
            "vibe_score": -5,
            "summary": "明け方の静かな時間。最も深い睡眠の時間帯。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 04:00
        {
            "hour": 4,
            "vibe_score": -2,
            "summary": "早朝、少しずつ浅い眠りへ移行し始める。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 05:00
        {
            "hour": 5,
            "vibe_score": 0,
            "summary": "朝が近づき、体が徐々に目覚めの準備を始めている。",
            "behavior": "睡眠",
            "emotion": "中立"
        },

        # 06:00
        {
            "hour": 6,
            "vibe_score": 5,
            "summary": "目覚める時間が近い。まだ布団の中でうとうとしている。",
            "behavior": "睡眠, 起床準備",
            "emotion": "中立"
        },

        # 07:00 - Morning routine
        {
            "hour": 7,
            "vibe_score": 20,
            "summary": "起床。今日も元気に目が覚めた。着替えを始める。",
            "behavior": "起床, 着替え",
            "emotion": "喜び"
        },

        # 08:00 - Breakfast
        {
            "hour": 8,
            "vibe_score": 35,
            "summary": "朝食の時間。パンケーキが大好き。家族と楽しく食事。",
            "behavior": "食事, 家族団らん",
            "emotion": "喜び"
        },

        # 09:00 - Kindergarten arrival
        {
            "hour": 9,
            "vibe_score": 45,
            "summary": "幼稚園に到着。友達と遊び始めて嬉しそう。",
            "behavior": "登園, 友達と遊ぶ",
            "emotion": "喜び, わくわく"
        },

        # 10:00 - Morning activities
        {
            "hour": 10,
            "vibe_score": 40,
            "summary": "午前の活動。お絵かきと工作に夢中になっている。",
            "behavior": "お絵かき, 工作",
            "emotion": "集中, 喜び"
        },

        # 11:00 - Outdoor play
        {
            "hour": 11,
            "vibe_score": 55,
            "summary": "園庭で元気に遊ぶ。かけっこやボール遊びで汗をかいている。",
            "behavior": "外遊び, 運動",
            "emotion": "興奮, 喜び"
        },

        # 12:00 - Lunch time
        {
            "hour": 12,
            "vibe_score": 50,
            "summary": "給食の時間。今日はカレーライス！完食して満足そう。",
            "behavior": "食事, おしゃべり",
            "emotion": "喜び, 満足"
        },

        # 13:00 - After lunch rest
        {
            "hour": 13,
            "vibe_score": 30,
            "summary": "お昼休み。絵本を読んでもらってリラックスしている。",
            "behavior": "休憩, 絵本",
            "emotion": "穏やか"
        },

        # 14:00 - Afternoon activities
        {
            "hour": 14,
            "vibe_score": 42,
            "summary": "午後の活動。音楽に合わせて歌ったり踊ったりしている。",
            "behavior": "歌, ダンス",
            "emotion": "喜び, 楽しい"
        },

        # 15:00 - Going home
        {
            "hour": 15,
            "vibe_score": 35,
            "summary": "降園時間。お迎えが来て、今日の出来事を話している。",
            "behavior": "降園, 会話",
            "emotion": "満足"
        },

        # 16:00 - Snack and play
        {
            "hour": 16,
            "vibe_score": 60,
            "summary": "帰宅後のおやつタイム。その後マインクラフトで遊び始める。",
            "behavior": "おやつ, ゲーム",
            "emotion": "喜び, わくわく"
        },

        # 17:00 - Gaming time
        {
            "hour": 17,
            "vibe_score": 65,
            "summary": "マインクラフトで大きなお城を建築中。集中して楽しんでいる。",
            "behavior": "ゲーム, 集中",
            "emotion": "喜び, 達成感"
        },

        # 18:00 - Evening routine
        {
            "hour": 18,
            "vibe_score": 25,
            "summary": "夕食の準備。お手伝いでテーブルセッティングをしている。",
            "behavior": "お手伝い, 準備",
            "emotion": "協力的"
        },

        # 19:00 - Dinner
        {
            "hour": 19,
            "vibe_score": 45,
            "summary": "家族で夕食。今日一日の出来事を報告している。",
            "behavior": "食事, 家族団らん, 会話",
            "emotion": "喜び, 満足"
        },

        # 20:00 - Bath time
        {
            "hour": 20,
            "vibe_score": 38,
            "summary": "お風呂の時間。お風呂のおもちゃで遊びながら入浴。",
            "behavior": "入浴, 遊び",
            "emotion": "リラックス"
        },

        # 21:00 - Bedtime routine
        {
            "hour": 21,
            "vibe_score": 20,
            "summary": "就寝準備。パジャマに着替えて、寝る前の絵本タイム。",
            "behavior": "就寝準備, 絵本",
            "emotion": "穏やか, 眠い"
        },

        # 22:00 - Sleep
        {
            "hour": 22,
            "vibe_score": 5,
            "summary": "就寝。絵本を読んでもらった後、すぐに眠りについた。",
            "behavior": "睡眠",
            "emotion": "安心"
        },

        # 23:00
        {
            "hour": 23,
            "vibe_score": 0,
            "summary": "深夜、ぐっすりと眠っている。穏やかな寝息。",
            "behavior": "睡眠",
            "emotion": "中立"
        }
    ]

    return pattern


def get_child_5yo_daily_pattern() -> List[Dict]:
    """
    Load 24-hour daily analysis pattern from JSON file

    Returns:
        List of 24 hourly cumulative data points for Monday (default)
    """
    data = load_pattern_data("daily")
    # For now, always use Monday pattern
    # TODO: Implement day-of-week logic
    return data["weekly_data"]["monday"]


def get_child_5yo_daily_pattern_legacy() -> List[Dict]:
    """
    Legacy hardcoded pattern (kept for reference, not used)
    """
    pattern = [
        # 00:00 - Midnight
        {
            "hour": 0,
            "summary": "深夜0時。ぐっすりと眠っている様子。",
            "burst_events": []
        },

        # 01:00
        {
            "hour": 1,
            "summary": "深夜1時。深い睡眠中。",
            "burst_events": []
        },

        # 02:00
        {
            "hour": 2,
            "summary": "深夜2時。睡眠継続中。",
            "burst_events": []
        },

        # 03:00
        {
            "hour": 3,
            "summary": "深夜3時。最も深い睡眠の時間帯。",
            "burst_events": []
        },

        # 04:00
        {
            "hour": 4,
            "summary": "早朝4時。浅い眠りへ移行し始めている。",
            "burst_events": []
        },

        # 05:00
        {
            "hour": 5,
            "summary": "早朝5時。体が目覚めの準備を始めている。",
            "burst_events": []
        },

        # 06:00
        {
            "hour": 6,
            "summary": "朝6時。目覚める時間が近づいている。",
            "burst_events": []
        },

        # 07:00 - Morning routine starts
        {
            "hour": 7,
            "summary": "朝7時に起床。元気に1日がスタート。",
            "burst_events": [
                {"time": "07:00", "event": "元気に目が覚めて、1日が始まった", "score_change": 20}
            ]
        },

        # 08:00 - Breakfast
        {
            "hour": 8,
            "summary": "朝8時。朝食を家族と一緒に楽しんでいる。起床後から良い気分が続いている。",
            "burst_events": [
                {"time": "07:00", "event": "元気に目が覚めて、1日が始まった", "score_change": 20},
                {"time": "08:00", "event": "パンケーキを食べて嬉しそう", "score_change": 15}
            ]
        },

        # 09:00 - Kindergarten arrival
        {
            "hour": 9,
            "summary": "朝9時。幼稚園に到着し、友達と遊び始めた。朝から良好な気分が続いている。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10}
            ]
        },

        # 10:00 - Morning activities
        {
            "hour": 10,
            "summary": "午前10時。お絵かきと工作に集中している。幼稚園での活動を楽しんでいる様子。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10}
            ]
        },

        # 11:00 - Outdoor play
        {
            "hour": 11,
            "summary": "午前11時。園庭で元気に遊んでいる。午前中は活発に活動している。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15}
            ]
        },

        # 12:00 - Lunch time
        {
            "hour": 12,
            "summary": "昼12時。給食のカレーライスを完食。午前中は活発に活動し、昼食も楽しんでいる。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5}
            ]
        },

        # 13:00 - After lunch rest
        {
            "hour": 13,
            "summary": "昼13時。お昼休みで絵本を読んでもらっている。午前の活発な活動から少し落ち着いた様子。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5}
            ]
        },

        # 14:00 - Afternoon activities
        {
            "hour": 14,
            "summary": "午後14時。音楽に合わせて歌ったり踊ったりしている。午後の活動も楽しんでいる。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5}
            ]
        },

        # 15:00 - Going home
        {
            "hour": 15,
            "summary": "午後15時。降園時間。お迎えに来た家族に今日の出来事を報告している。幼稚園での1日を楽しく過ごした様子。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5}
            ]
        },

        # 16:00 - Snack and gaming peak
        {
            "hour": 16,
            "summary": "午後16時。帰宅後のおやつを食べ、マインクラフトで遊び始めた。1日で最も楽しい時間帯に入った。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 17:00 - Gaming time (peak)
        {
            "hour": 17,
            "summary": "午後17時。マインクラフトで大きなお城を建築中。1日で最も高いテンションを記録。幼稚園から帰宅後、ゲームに夢中になっている。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 18:00 - Evening routine
        {
            "hour": 18,
            "summary": "夕方18時。夕食の準備を手伝っている。ゲームタイムが終わり、家族時間へシフト。1日を通して良好な気分が維持されている。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 19:00 - Dinner
        {
            "hour": 19,
            "summary": "夜19時。家族で夕食。今日1日の出来事を報告している。朝の起床から夕食まで、充実した1日を過ごしている。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 20:00 - Bath time
        {
            "hour": 20,
            "summary": "夜20時。お風呂の時間。お風呂のおもちゃで遊びながら入浴している。1日の疲れを癒している様子。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 21:00 - Bedtime routine
        {
            "hour": 21,
            "summary": "夜21時。就寝準備。パジャマに着替えて寝る前の絵本タイム。1日の活動を終え、就寝へ向かっている。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 22:00 - Sleep
        {
            "hour": 22,
            "summary": "夜22時。就寝。絵本を読んでもらった後、すぐに眠りについた。朝7時の起床から幼稚園での活動、夕方のゲームタイム、家族との時間まで、充実した1日を過ごした。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        },

        # 23:00
        {
            "hour": 23,
            "summary": "夜23時。ぐっすりと眠っている。穏やかな寝息。朝7時の起床から夜22時の就寝まで、幼稚園での活動やゲーム、家族との時間を楽しんだ充実した1日だった。",
            "burst_events": [
                {"time": "07:00", "event": "起床", "score_change": 20},
                {"time": "08:00", "event": "朝食", "score_change": 15},
                {"time": "09:00", "event": "登園", "score_change": 10},
                {"time": "11:00", "event": "外遊び", "score_change": 15},
                {"time": "12:00", "event": "給食", "score_change": 5},
                {"time": "16:00", "event": "ゲーム開始", "score_change": 25}
            ]
        }
    ]

    return pattern


def generate_spot_record(device_id: str, date: str, hour: int, pattern_data: Dict) -> Dict:
    """
    Generate a single spot_results record

    Format matches Profiler API output:
    - device_id
    - recorded_at (UTC ISO8601)
    - vibe_score
    - summary (Japanese)
    - behavior (comma-separated)
    - emotion (comma-separated)
    - local_date
    - local_time (JST ISO8601)
    - profile_result (JSONB - full analysis)
    - llm_model
    """

    # Create timestamp for this hour
    recorded_at_jst = datetime(
        int(date.split('-')[0]),
        int(date.split('-')[1]),
        int(date.split('-')[2]),
        hour,
        0,  # minutes = 0 (on the hour)
        0,  # seconds = 0
        tzinfo=timezone(timedelta(hours=9))
    )

    # Convert to UTC for recorded_at
    recorded_at_utc = recorded_at_jst.astimezone(timezone.utc)

    # Add some randomness to vibe_score (±5)
    vibe_score = pattern_data["vibe_score"] + random.randint(-5, 5)
    vibe_score = max(-100, min(100, vibe_score))  # Keep within bounds

    # Profile result (full LLM analysis as JSONB)
    profile_result = {
        "vibe_score": vibe_score,
        "summary": pattern_data["summary"],
        "behavior": pattern_data["behavior"],
        "emotion": pattern_data["emotion"]
    }

    return {
        "device_id": device_id,
        "recorded_at": recorded_at_utc.isoformat(),
        "vibe_score": vibe_score,
        "summary": pattern_data["summary"],
        "behavior": pattern_data["behavior"],
        "emotion": pattern_data["emotion"],
        "local_date": date,
        "local_time": recorded_at_jst.isoformat(),
        "profile_result": profile_result,
        "llm_model": "demo-generator-v2",
    }


def generate_daily_record(device_id: str, date: str, current_hour: int, spot_pattern: List[Dict], daily_pattern: List[Dict]) -> Dict:
    """
    Generate a single daily_results record (cumulative up to current hour)

    Format matches daily_results table:
    - device_id
    - local_date
    - vibe_score (average of all spots up to current hour)
    - summary (cumulative daily summary)
    - burst_events (JSONB array)
    - vibe_scores (JSONB array of {time, score})
    - processed_count (number of recordings up to current hour)
    - llm_model
    """

    # Get daily pattern data for current hour
    daily_data = daily_pattern[current_hour]

    # Generate vibe_scores array from hour 0 to current_hour
    vibe_scores_array = []
    vibe_score_values = []

    for h in range(current_hour + 1):  # 0 to current_hour inclusive
        spot_data = spot_pattern[h]

        # Add randomness to vibe_score (±5)
        vibe_score = spot_data["vibe_score"] + random.randint(-5, 5)
        vibe_score = max(-100, min(100, vibe_score))

        # Create timestamp in ISO 8601 format (YYYY-MM-DDTHH:MM)
        time_str = f"{date}T{h:02d}:00"

        vibe_scores_array.append({
            "time": time_str,
            "score": vibe_score
        })
        vibe_score_values.append(vibe_score)

    # Calculate average vibe_score
    avg_vibe = sum(vibe_score_values) / len(vibe_score_values) if vibe_score_values else 0

    return {
        "device_id": device_id,
        "local_date": date,
        "vibe_score": avg_vibe,
        "summary": daily_data["summary"],
        "burst_events": daily_data["burst_events"],
        "vibe_scores": vibe_scores_array,
        "processed_count": len(vibe_scores_array),
        "llm_model": "demo-generator-v2"
    }


def lambda_handler(event, context):
    """
    Main Lambda handler function
    Generates and saves spot & daily analysis data for current hour
    """

    # Check environment variables
    if not SUPABASE_URL or not SUPABASE_KEY:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Missing SUPABASE_URL or SUPABASE_KEY environment variables'
            })
        }

    try:
        # Get current time and date (JST)
        now = get_jst_now()
        current_date = str(now.date())
        current_hour = now.hour

        # Get the 24-hour patterns
        spot_pattern = get_child_5yo_spot_pattern()
        daily_pattern = get_child_5yo_daily_pattern()

        # Find current hour's data
        current_hour_data = spot_pattern[current_hour]

        # Generate spot record for current hour
        spot_record = generate_spot_record(
            DEMO_DEVICE_ID,
            current_date,
            current_hour,
            current_hour_data
        )

        # Generate daily record (cumulative up to current hour)
        daily_record = generate_daily_record(
            DEMO_DEVICE_ID,
            current_date,
            current_hour,
            spot_pattern,
            daily_pattern
        )

        # Prepare headers for Supabase REST API (UPSERT mode)
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates"
        }

        # Save spot data to spot_results table (UPSERT)
        print(f"💾 Saving spot data for {current_date} {current_hour:02d}:00...")
        spot_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/spot_results",
            headers=headers,
            json=spot_record
        )

        if spot_response.status_code in [200, 201]:
            print(f"✅ Successfully saved to spot_results table")
            spot_save_success = True
        else:
            print(f"⚠️ Warning: spot_results save failed ({spot_response.status_code}): {spot_response.text}")
            spot_save_success = False

        # Save daily data to daily_results table (UPSERT)
        print(f"💾 Saving daily data for {current_date} (hour {current_hour:02d})...")
        daily_response = requests.post(
            f"{SUPABASE_URL}/rest/v1/daily_results",
            headers=headers,
            json=daily_record
        )

        if daily_response.status_code in [200, 201]:
            print(f"✅ Successfully saved to daily_results table")
            daily_save_success = True
        else:
            print(f"⚠️ Warning: daily_results save failed ({daily_response.status_code}): {daily_response.text}")
            daily_save_success = False

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'timestamp': now.isoformat(),
                'device_id': DEMO_DEVICE_ID,
                'current_hour': current_hour,
                'date': current_date,
                'spot_data': {
                    'vibe_score': spot_record["vibe_score"],
                    'summary': spot_record["summary"],
                    'behavior': spot_record["behavior"],
                    'emotion': spot_record["emotion"],
                    'saved': spot_save_success
                },
                'daily_data': {
                    'vibe_score': daily_record["vibe_score"],
                    'summary': daily_record["summary"],
                    'processed_count': daily_record["processed_count"],
                    'saved': daily_save_success
                },
                'message': f'Successfully generated spot & daily data for {current_date} {current_hour:02d}:00'
            }, ensure_ascii=False)
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
        }


# For local testing
if __name__ == "__main__":
    # Test with mock event
    test_event = {}
    test_context = {}
    result = lambda_handler(test_event, test_context)
    print("\n" + "="*60)
    print("Test Result:")
    print("="*60)
    print(json.dumps(json.loads(result['body']), indent=2, ensure_ascii=False))
