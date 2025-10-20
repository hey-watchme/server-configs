# 実装計画：エラーハンドリングとユーザー体験改善

**作成日**: 2025年10月20日
**次のセッションで実装予定**

---

## 📋 背景

### 調査結果のまとめ

1. **Azure Speech APIの処理時間**: 26-28秒（1分音声）
2. **重複処理は発生していない**: クォーター消費3倍の懸念は否定
3. **クォーター超過時の挙動**: 1.1秒で即座にエラー（HTTP 200 OK, `errors: 1`）
4. **現在の問題**: クォーター超過を正しく検出できていない（リトライが動作しない）

### 確立された運用方針

- ✅ **クォーター超過は即座に諦める**（自動リトライしない）
- ✅ **データベースに記録**（`transcriptions_status = 'quota_exceeded'`）
- ✅ **手動で再処理**（料金承認プロセス）
- ✅ **ユーザーには適切なメッセージを表示**

---

## 🎯 実装タスク

### **Task 1: Lambda関数でAzureクォーター超過を正しく検出する**

**ファイル**: `/Users/kaya.matsumoto/projects/watchme/server-configs/lambda-functions/watchme-audio-worker/lambda_function.py`

**現在のコード（問題あり）**:
```python
# Line 89-93
if transcribe_response.status_code in [429, 503]:
    print(f"Received {transcribe_response.status_code}, will retry...")
    retry_count += 1
    continue
```

**問題点**:
- Azure APIはクォーター超過時に**HTTP 200 OK**を返す
- レスポンス本文に`errors: 1`が含まれる形式
- 現在のコードでは検出できない

**修正内容**:

```python
# Line 80-123を以下に置き換え

print(f"Calling Azure Speech API (attempt {retry_count + 1}/{max_retries})...")
transcribe_response = requests.post(
    f"{API_BASE_URL}/vibe-transcriber-v2/fetch-and-transcribe",
    json={
        "file_paths": [file_path]
    },
    timeout=180
)

# レスポンスの解析
if transcribe_response.status_code == 200:
    try:
        response_data = transcribe_response.json()

        # クォーター超過の検出（重要）
        if response_data.get('summary', {}).get('errors', 0) > 0:
            error_files = response_data.get('error_files', [])

            # エラー詳細をログ出力
            print(f"Azure API returned errors: {response_data.get('summary')}")

            # クォーター超過の可能性が高い
            # → 即座に諦める（リトライしない）
            azure_success = False
            results['transcription'] = {
                'status_code': 200,
                'success': False,
                'error_type': 'quota_exceeded',
                'error_files': error_files,
                'message': 'Azure quota exceeded - manual reprocessing required'
            }

            print(f"⚠️ Azure quota exceeded. Stopping retries.")
            break  # リトライループを抜ける

        # 成功の場合
        azure_success = True
        results['transcription'] = {
            'status_code': transcribe_response.status_code,
            'success': True,
            'response': response_data,
            'retry_count': retry_count
        }

        print(f"Azure Speech API response: {response_data}")
        break  # 成功したのでループを抜ける

    except Exception as e:
        print(f"Error parsing Azure response: {str(e)}")
        results['transcription'] = {
            'status_code': 200,
            'success': False,
            'error': f'Response parsing error: {str(e)}'
        }
        break

# 429/503の場合はリトライ
elif transcribe_response.status_code in [429, 503]:
    print(f"Received {transcribe_response.status_code}, will retry...")
    retry_count += 1
    if retry_count < max_retries:
        wait_time = min(30, 5 * (2 ** (retry_count - 1)))
        print(f"Waiting {wait_time} seconds before retry...")
        time.sleep(wait_time)
        continue
    else:
        # 最大リトライ回数に到達
        azure_success = False
        results['transcription'] = {
            'status_code': transcribe_response.status_code,
            'success': False,
            'error': f'Max retries reached with status {transcribe_response.status_code}'
        }
        break

# その他のエラー
else:
    print(f"Azure API failed with status: {transcribe_response.status_code}")
    azure_success = False
    results['transcription'] = {
        'status_code': transcribe_response.status_code,
        'success': False,
        'error': f'HTTP {transcribe_response.status_code}'
    }
    break
```

**テスト方法**:
1. CloudWatch Logsで「Azure quota exceeded」というログが出力されるか確認
2. データベースの`audio_files`テーブルで`transcriptions_status = 'quota_exceeded'`が記録されるか確認

---

### **Task 2: エラー種別ごとのリトライロジックを実装**

**同じファイル**: `lambda_function.py`

**実装内容**:

リトライ対象のエラーを明確にする：

```python
# 関数の先頭に追加

RETRYABLE_STATUS_CODES = [429, 503]  # リトライ対象のHTTPステータス
RETRYABLE_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)

def should_retry_error(status_code, exception):
    """エラーがリトライ可能か判定"""
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True
    return False
```

AST APIとSUPERB APIにも同様のリトライロジックを追加（現在はリトライなし）。

---

### **Task 3: ダッシュボードで分析失敗時のユーザー体験を改善**

#### **3-1. バックエンド（Dashboard Summary API）**

**ファイル**: Vibe Aggregator API（プロンプト生成）

**現在の問題**:
- クォーター超過時、`dashboard`テーブルにレコードが作成されない
- ユーザーはデータポイント自体が存在しないように見える

**改善内容**:

`dashboard`テーブルに**失敗レコード**を作成する：

```python
# Vibe Scorer APIの代わりに、Vibe Aggregatorで失敗レコードを作成

# Azure失敗時の処理
if transcriptions_status == 'quota_exceeded':
    # 失敗レコードをdashboardテーブルに挿入
    dashboard_record = {
        'device_id': device_id,
        'date': date,
        'time_block': time_block,
        'status': 'failed',
        'failure_reason': 'quota_exceeded',
        'vibe_score': None,
        'burst_events': None,
        'current_time': None,
        'time_context': None,
        'cumulative_evaluation': None,
        'mood_trajectory': None,
        'current_state_score': None,
        'message': '分析に失敗しました。しばらくしてから再度お試しください。',
        'user_message': 'Azure Speech APIのクォーター超過により、音声の文字起こしができませんでした。システム管理者に通知されています。',
        'created_at': datetime.utcnow().isoformat()
    }

    # Supabaseに保存
    supabase.table('dashboard').upsert(dashboard_record).execute()
```

**データベーススキーマの追加**:

`dashboard`テーブルに以下のカラムを追加（必要であれば）:
- `status` (text): 'completed', 'failed', 'pending'
- `failure_reason` (text): 'quota_exceeded', 'api_error', etc.
- `message` (text): システム管理者向けメッセージ
- `user_message` (text): エンドユーザー向けメッセージ

---

#### **3-2. フロントエンド（ダッシュボード）**

**ファイル**: `/Users/kaya.matsumoto/projects/watchme/watchme_v8/` または該当するダッシュボードコンポーネント

**現在の問題**:
- データがない場合、空白またはローディング状態のまま
- ユーザーは何が起きているか分からない

**改善内容**:

##### **パターンA: データポイントにエラー状態を表示**

```typescript
// ダッシュボードのデータ取得部分

interface DashboardData {
  device_id: string;
  date: string;
  time_block: string;
  status: 'completed' | 'failed' | 'pending';
  failure_reason?: 'quota_exceeded' | 'api_error';
  user_message?: string;
  vibe_score?: number;
  // ... 他のフィールド
}

// コンポーネント内
{dashboardData.map((item) => {
  if (item.status === 'failed') {
    return (
      <div className="data-point failed">
        <div className="time-block">{item.time_block}</div>
        <div className="error-message">
          <Icon name="alert-circle" />
          <p>{item.user_message || '分析に失敗しました'}</p>
          <button onClick={() => handleRetry(item)}>
            再分析を依頼
          </button>
        </div>
      </div>
    );
  }

  // 通常のデータ表示
  return <DataPoint data={item} />;
})}
```

##### **パターンB: グラフ上にエラーマーカーを表示**

```typescript
// Chart.jsを使用している場合

const chartData = {
  labels: timeBlocks,
  datasets: [{
    label: 'Vibe Score',
    data: dashboardData.map(item => {
      if (item.status === 'failed') {
        return null;  // データなし
      }
      return item.vibe_score;
    }),
    // ... スタイル設定
  }]
};

// エラーマーカーの追加
const errorAnnotations = dashboardData
  .filter(item => item.status === 'failed')
  .map(item => ({
    type: 'point',
    xValue: item.time_block,
    backgroundColor: '#ff4444',
    borderColor: '#ff4444',
    label: {
      content: '⚠️ 分析失敗',
      enabled: true
    }
  }));
```

##### **パターンC: 通知バナーで一括表示**

```typescript
// ページ上部に通知バナーを表示

const failedDataPoints = dashboardData.filter(item => item.status === 'failed');

{failedDataPoints.length > 0 && (
  <div className="notification-banner warning">
    <Icon name="alert-triangle" />
    <div>
      <strong>一部のデータ分析に失敗しています</strong>
      <p>
        {failedDataPoints.length}件のタイムブロックで分析が完了していません。
        システム管理者に自動通知されています。
      </p>
      <details>
        <summary>詳細を見る</summary>
        <ul>
          {failedDataPoints.map(item => (
            <li key={item.time_block}>
              {item.time_block}: {item.user_message}
            </li>
          ))}
        </ul>
      </details>
    </div>
  </div>
)}
```

**UIテキストの例**:

| 状況 | ユーザー向けメッセージ |
|------|---------------------|
| クォーター超過 | 「分析処理の上限に達したため、このタイムブロックの分析ができませんでした。しばらくしてから自動的に再試行されます。」 |
| API一時エラー | 「一時的なエラーが発生しました。数分後に自動的に再試行されます。」 |
| 処理中 | 「分析処理中です。しばらくお待ちください...」 |

---

### **Task 4: Dashboard Summary APIで失敗データを適切にハンドリング**

**ファイル**: Vibe Aggregator API（`/vibe-aggregator/generate-dashboard-summary`）

**現在の問題**:
- 失敗したタイムブロックがあると、累積分析全体が失敗する可能性

**改善内容**:

```python
# 累積分析のプロンプト生成時

# dashboardテーブルから全データを取得
dashboard_data = supabase.table('dashboard')\
    .select('*')\
    .eq('device_id', device_id)\
    .eq('date', date)\
    .order('time_block')\
    .execute()

# 成功したデータのみを分析対象にする
successful_data = [
    item for item in dashboard_data.data
    if item.get('status') == 'completed' and item.get('vibe_score') is not None
]

failed_data = [
    item for item in dashboard_data.data
    if item.get('status') == 'failed'
]

# プロンプトに失敗情報を含める
prompt = f"""
## 1日全体の総合分析依頼

### 分析対象
- 成功したタイムブロック: {len(successful_data)}件
- 失敗したタイムブロック: {len(failed_data)}件

### 分析データ
{json.dumps(successful_data, ensure_ascii=False)}

### 注意事項
以下のタイムブロックは分析失敗のため、データがありません：
{[item['time_block'] for item in failed_data]}

上記を考慮して、利用可能なデータのみで分析を行ってください。
"""
```

---

### **Task 5: 手動再処理用の管理画面またはAPIエンドポイントを作成**

#### **オプションA: 管理画面UI（推奨）**

**場所**: `/Users/kaya.matsumoto/projects/watchme/admin/` または watchme-admin

**実装内容**:

```typescript
// 失敗データの一覧表示ページ

interface FailedData {
  device_id: string;
  date: string;
  time_block: string;
  failure_reason: string;
  created_at: string;
  file_path: string;
}

function FailedDataList() {
  const [failedData, setFailedData] = useState<FailedData[]>([]);

  // Supabaseから失敗データを取得
  useEffect(() => {
    const fetchFailedData = async () => {
      const { data } = await supabase
        .from('audio_files')
        .select('*')
        .eq('transcriptions_status', 'quota_exceeded')
        .order('created_at', { ascending: false });

      setFailedData(data || []);
    };

    fetchFailedData();
  }, []);

  // 再処理の実行
  const handleReprocess = async (item: FailedData) => {
    try {
      const response = await fetch('https://api.hey-watch.me/vibe-transcriber-v2/fetch-and-transcribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          file_paths: [item.file_path]
        })
      });

      if (response.ok) {
        alert('再処理を開始しました');
        // リストを更新
      } else {
        alert('再処理に失敗しました');
      }
    } catch (error) {
      console.error(error);
      alert('エラーが発生しました');
    }
  };

  return (
    <div className="failed-data-list">
      <h2>分析失敗データ一覧</h2>
      <table>
        <thead>
          <tr>
            <th>デバイスID</th>
            <th>日付</th>
            <th>タイムブロック</th>
            <th>失敗理由</th>
            <th>発生日時</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {failedData.map(item => (
            <tr key={`${item.device_id}-${item.date}-${item.time_block}`}>
              <td>{item.device_id.slice(0, 8)}...</td>
              <td>{item.date}</td>
              <td>{item.time_block}</td>
              <td>{item.failure_reason || 'quota_exceeded'}</td>
              <td>{new Date(item.created_at).toLocaleString()}</td>
              <td>
                <button onClick={() => handleReprocess(item)}>
                  再処理
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

#### **オプションB: APIエンドポイント（シンプル）**

**場所**: Vibe Transcriber API

**新規エンドポイント**: `/vibe-transcriber-v2/reprocess-failed`

```python
@app.post("/reprocess-failed")
async def reprocess_failed_data(
    device_id: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = 10
):
    """
    失敗したデータを再処理

    Parameters:
    - device_id: 特定のデバイスのみ（省略可）
    - date: 特定の日付のみ（省略可）
    - limit: 最大処理件数（デフォルト10件）
    """

    # Supabaseから失敗データを取得
    query = supabase.table('audio_files')\
        .select('file_path, device_id, local_date, time_block')\
        .eq('transcriptions_status', 'quota_exceeded')

    if device_id:
        query = query.eq('device_id', device_id)
    if date:
        query = query.eq('local_date', date)

    result = query.limit(limit).execute()

    file_paths = [item['file_path'] for item in result.data]

    if not file_paths:
        return {
            "status": "success",
            "message": "No failed data to reprocess",
            "reprocessed_count": 0
        }

    # 既存の処理エンドポイントを呼び出し
    reprocess_result = await fetch_and_transcribe(
        FilePaths(file_paths=file_paths)
    )

    return {
        "status": "success",
        "message": f"Reprocessed {len(file_paths)} files",
        "reprocessed_count": len(file_paths),
        "details": reprocess_result
    }
```

---

## 📊 実装の優先順位

### **Phase 1: 緊急（必須）**
1. ✅ **Task 1**: Lambda関数でクォーター超過を正しく検出
2. ✅ **Task 3-1**: バックエンドで失敗レコードを作成

### **Phase 2: 重要（早めに実装）**
3. ✅ **Task 3-2**: ダッシュボードでエラー表示
4. ✅ **Task 4**: Dashboard Summary APIで失敗データをハンドリング

### **Phase 3: 改善（時間があれば）**
5. ⭕ **Task 2**: AST/SUPERB APIにもリトライロジック追加
6. ⭕ **Task 5**: 管理画面で手動再処理UI

---

## 🧪 テスト計画

### **1. Lambda関数のテスト**

**テストケース**:
```python
# クォーター超過のシミュレーション
mock_response = {
    "status": "success",
    "summary": {
        "total_files": 1,
        "pending_processed": 0,
        "errors": 1  # ← これを検出できるか
    },
    "error_files": ["files/..."],
    "message": "1件中0件を処理しました"
}
```

**確認項目**:
- [ ] `azure_success = False`になるか
- [ ] `error_type = 'quota_exceeded'`が記録されるか
- [ ] リトライループを抜けるか（無駄なリトライをしない）
- [ ] CloudWatchに適切なログが出力されるか

### **2. ダッシュボードのテスト**

**テストデータ**:
```sql
-- 失敗レコードを手動で作成
INSERT INTO dashboard (device_id, date, time_block, status, failure_reason, user_message)
VALUES (
  'test-device-id',
  '2025-10-20',
  '09-00',
  'failed',
  'quota_exceeded',
  'Azure Speech APIのクォーター超過により、音声の文字起こしができませんでした。'
);
```

**確認項目**:
- [ ] エラー状態が視覚的に分かるか
- [ ] ユーザー向けメッセージが表示されるか
- [ ] 他の正常データと区別できるか

### **3. 手動再処理のテスト**

**手順**:
1. クォーター超過のデータを用意
2. Azureクォーターを確認（リセット後または追加購入後）
3. 管理画面またはAPIで再処理を実行
4. データベースのステータスが更新されるか確認

---

## 📝 引き継ぎメモ

### **重要なポイント**

1. **Azure APIのエラーレスポンス形式**
   - HTTP 200 OKを返す
   - `summary.errors > 0`でエラー判定
   - これを検出できていないのが現在の問題

2. **ユーザー体験の改善が必須**
   - データがないだけでは、ユーザーは何が起きているか分からない
   - 「分析失敗」「再試行中」「完了」の状態を明確に表示

3. **手動再処理の仕組み**
   - 管理画面UIまたはAPIエンドポイント
   - データベースから`quota_exceeded`を検索
   - Azure APIを再実行

4. **コスト管理の思想**
   - 自動リトライは無駄なコスト発生のリスク
   - 人間による承認プロセスを経る

### **関連ファイル**

- Lambda関数: `/Users/kaya.matsumoto/projects/watchme/server-configs/lambda-functions/watchme-audio-worker/lambda_function.py`
- 設計ドキュメント: `/Users/kaya.matsumoto/projects/watchme/server-configs/PROCESSING_ARCHITECTURE.md`
- ダッシュボード: `/Users/kaya.matsumoto/projects/watchme/watchme_v8/`（または該当プロジェクト）
- 管理画面: `/Users/kaya.matsumoto/projects/watchme/admin/`

### **次のセッションで最初にすること**

1. ✅ Lambda関数の修正（Task 1）
2. ✅ ローカルでビルド・デプロイ
3. ✅ CloudWatchログで動作確認
4. ✅ ダッシュボードのUI改善（Task 3-2）

---

*この引き継ぎ資料は次のセッションで即座に実装を開始できるように作成されています。*
