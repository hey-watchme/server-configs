import json
import boto3
import requests
import os
from datetime import datetime

# 環境変数
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.hey-watch.me')

def lambda_handler(event, context):
    """
    Dashboard Analysis Worker Lambda
    SQSメッセージを処理してChatGPT分析APIを呼び出し、
    結果をデータベースに保存
    """
    
    print(f"Processing Dashboard Analysis: {len(event['Records'])} messages")
    
    for record in event['Records']:
        try:
            # メッセージ本文を解析
            message = json.loads(record['body'])
            
            device_id = message['device_id']
            date = message['date']
            time_slot = message.get('time_slot', '')
            prompt = message.get('prompt', '')
            
            if not prompt:
                raise ValueError("No prompt provided in message")
            
            print(f"Processing dashboard analysis for: {device_id}/{date}")
            print(f"Triggered by timeblock: {time_slot}")
            print(f"Prompt length: {len(prompt)} characters")
            
            # Dashboard Analysis APIを呼び出し（ChatGPT分析）
            analysis_result = call_dashboard_analysis_api(
                device_id, date, prompt
            )
            
            if analysis_result['success']:
                print(f"Dashboard analysis completed successfully")
                print(f"Analysis result saved to database")
                
                # 成功ログ
                log_success_metrics(device_id, date, time_slot, analysis_result)
                
            else:
                print(f"Dashboard analysis API failed: {analysis_result.get('error', 'Unknown error')}")
                # エラーの場合、SQSのリトライ機能により自動的に再試行される
                raise Exception(f"Dashboard analysis failed: {analysis_result.get('error')}")
            
        except Exception as e:
            print(f"Error processing message: {str(e)}")
            # 例外を再発生させてSQSのリトライを有効にする
            raise
    
    return {
        'statusCode': 200,
        'body': json.dumps('Dashboard analysis processing completed')
    }


def call_dashboard_analysis_api(device_id, date, prompt):
    """
    Dashboard Analysis API（ChatGPT分析）を呼び出し
    """
    try:
        print(f"Calling Dashboard Analysis API...")
        print(f"URL: {API_BASE_URL}/vibe-scorer/analyze-dashboard-summary")
        
        # APIを呼び出し
        response = requests.post(
            f"{API_BASE_URL}/vibe-scorer/analyze-dashboard-summary",
            json={
                "device_id": device_id,
                "date": date
            },
            timeout=180
        )
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                
                # 分析結果の確認
                if response_data.get('success'):
                    print(f"Dashboard Analysis API successful")
                    
                    # 分析結果の概要をログ出力
                    analysis_data = response_data.get('analysis_result', {})
                    if analysis_data:
                        print(f"Analysis contains: {list(analysis_data.keys())}")
                        
                        # 主要な分析結果をログ出力
                        if 'overall_summary' in analysis_data:
                            summary = analysis_data['overall_summary']
                            print(f"Overall summary length: {len(str(summary))} characters")
                        
                        if 'hourly_summaries' in analysis_data:
                            hourly_count = len(analysis_data['hourly_summaries'])
                            print(f"Hourly summaries: {hourly_count} entries")
                        
                        if 'emotion_trends' in analysis_data:
                            print("Emotion trends data included")
                        
                        if 'behavioral_patterns' in analysis_data:
                            print("Behavioral patterns data included")
                    
                    return {
                        'success': True,
                        'analysis_result': analysis_data,
                        'status_code': response.status_code
                    }
                else:
                    error_msg = response_data.get('error', 'Analysis indicated failure')
                    print(f"API returned success=false: {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'status_code': response.status_code
                    }
                    
            except Exception as e:
                print(f"Error parsing API response: {str(e)}")
                return {
                    'success': False,
                    'error': f'Response parsing error: {str(e)}',
                    'status_code': response.status_code
                }
                
        else:
            print(f"Dashboard Analysis API failed with status: {response.status_code}")
            try:
                error_detail = response.text
                print(f"Error response: {error_detail}")
            except:
                error_detail = 'No error detail available'
                
            return {
                'success': False,
                'error': f'API returned status {response.status_code}: {error_detail}',
                'status_code': response.status_code
            }
            
    except requests.Timeout:
        print("Dashboard Analysis API timeout")
        return {
            'success': False,
            'error': 'API timeout after 180 seconds'
        }
        
    except Exception as e:
        print(f"Dashboard Analysis API error: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def log_success_metrics(device_id, date, time_slot, analysis_result):
    """
    成功時のメトリクスをログ出力（CloudWatch監視用）
    """
    try:
        metrics = {
            'event': 'dashboard_analysis_completed',
            'device_id': device_id,
            'date': date,
            'triggered_by_timeblock': time_slot,
            'timestamp': datetime.utcnow().isoformat(),
            'status_code': analysis_result.get('status_code', 200)
        }
        
        # 分析結果のサイズ情報を追加
        if 'analysis_result' in analysis_result:
            analysis_data = analysis_result['analysis_result']
            metrics['has_overall_summary'] = 'overall_summary' in analysis_data
            metrics['has_hourly_summaries'] = 'hourly_summaries' in analysis_data
            metrics['has_emotion_trends'] = 'emotion_trends' in analysis_data
            metrics['has_behavioral_patterns'] = 'behavioral_patterns' in analysis_data
            
            # データサイズの概要
            if 'hourly_summaries' in analysis_data:
                metrics['hourly_summaries_count'] = len(analysis_data['hourly_summaries'])
        
        # CloudWatch用のJSON形式でログ出力
        print(f"METRICS: {json.dumps(metrics)}")
        
    except Exception as e:
        print(f"Error logging metrics: {str(e)}")