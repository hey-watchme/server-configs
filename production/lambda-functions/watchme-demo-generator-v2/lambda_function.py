#!/usr/bin/env python3
"""
Demo Data Generator V2 - Spot Analysis Only
Generates realistic demo data for spot_results table (hourly)
Version: 2.0.0
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

# Device configuration for demo account
DEMO_DEVICE_ID = "a1b2c3d4-e5f6-4a5b-8c9d-0e1f2a3b4c5d"  # 5-year-old child


def get_jst_now():
    """Get current JST time"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst)


def get_child_5yo_spot_pattern() -> List[Dict]:
    """
    24-hour spot analysis pattern for 5-year-old child (hourly data points)
    Returns 24 data points matching Profiler API output format

    Format matches spot_results table:
    - vibe_score: int (-100 to 100)
    - summary: str (Japanese description)
    - behavior: str (comma-separated behaviors)
    - emotion: str (comma-separated emotions)
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


def lambda_handler(event, context):
    """
    Main Lambda handler function
    Generates and saves spot analysis data for current hour
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

        # Get the 24-hour pattern
        spot_pattern = get_child_5yo_spot_pattern()

        # Find current hour's data
        current_hour_data = spot_pattern[current_hour]

        # Generate spot record for current hour
        spot_record = generate_spot_record(
            DEMO_DEVICE_ID,
            current_date,
            current_hour,
            current_hour_data
        )

        # Save to Supabase using REST API
        print(f"💾 Saving spot data for {current_date} {current_hour:02d}:00...")
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }

        response = requests.post(
            f"{SUPABASE_URL}/rest/v1/spot_results",
            headers=headers,
            json=spot_record
        )

        if response.status_code in [200, 201]:
            print(f"✅ Successfully saved to spot_results table")
        else:
            print(f"⚠️ Warning: Supabase returned {response.status_code}: {response.text}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'success': True,
                'timestamp': now.isoformat(),
                'device_id': DEMO_DEVICE_ID,
                'current_hour': current_hour,
                'date': current_date,
                'vibe_score': spot_record["vibe_score"],
                'summary': spot_record["summary"],
                'behavior': spot_record["behavior"],
                'emotion': spot_record["emotion"],
                'message': f'Successfully generated spot data for {current_date} {current_hour:02d}:00'
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
