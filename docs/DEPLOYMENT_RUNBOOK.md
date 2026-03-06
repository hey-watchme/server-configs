# WatchMe Deployment Runbook

最終更新: 2026-03-07
Status: Active  
Source of truth: 変更内容ごとの反映経路

## まず判断すること

変更したものが何かを最初に分類します。

| 変更対象 | 例 | 反映元 |
|---------|----|-------|
| API アプリコード | FastAPI のエンドポイント、LLM ロジック、Dockerfile | 各 API リポジトリ |
| Lambda コード | `production/lambda-functions/` | `server-configs` |
| AWS 配線 | SQS, EventBridge, Lambda trigger | `server-configs` |
| EC2 基盤設定 | Nginx, systemd, docker-compose-files | `server-configs` |
| DB スキーマ | テーブル/カラム追加変更 | Supabase migrations |

## 現在の原則

### API 本体変更

対象例:
- Aggregator API
- Profiler API

反映原則:
- 各 API リポジトリで commit / push
- GitHub Actions workflow により `ECR -> EC2` へ反映
- **手動の `docker build` / `docker push` は原則しない**

やること:
1. API リポジトリの workflow を確認
2. 必要な `Secrets / .env / docker-compose.prod.yml` の整合を見る
3. `main` へ反映して CI/CD を実行
4. EC2 上のコンテナと health endpoint を確認

### Lambda / SQS / EventBridge 変更

対象例:
- Spot pipeline worker
- reconciliation rule
- queue 作成や event source mapping

反映原則:
- `server-configs/production/lambda-functions/` を更新
- AWS に直接デプロイ

やること:
1. 既存 Lambda 設定確認
2. 必要なら ZIP 作成
3. `aws lambda update-function-code` / `create-function`
4. SQS / EventBridge / event source mapping を反映
5. **新規 queue を追加した場合は Lambda 実行ロールの IAM policy も確認**
6. CloudWatch と queue 状態を確認

補足:
- `watchme-lambda-s3-processor` のような共有ロールでは、queue を新設しても自動で `sqs:SendMessage` 権限は増えない
- `watchme-spot-analysis-queue.fifo` 追加時は、`SQSSendMessagePolicy` に対象 ARN を追加しないと `aggregator-checker` で `AccessDenied` が発生する

### EC2 基盤設定変更

対象例:
- Nginx location
- systemd service file
- `production/docker-compose-files/*.yml`

反映原則:
- `server-configs` を更新
- EC2 上の `watchme-server-configs` に反映

やること:
1. `server-configs` で変更
2. EC2 で `git pull`
3. `./setup_server.sh`
4. 必要に応じて `systemctl daemon-reload`, `systemctl restart`, `nginx reload`

## 反映経路の詳細

### A. API リポジトリ経由

フロー:

```text
git push
-> GitHub Actions
-> ECR push
-> EC2 /home/ubuntu/{api-name}/ に反映
-> run-prod.sh
-> Docker container restart
-> health check
```

確認ポイント:
- workflow が存在するか
- ECR repository 名が一致しているか
- `.env` に必要変数が注入されるか
- `docker-compose.prod.yml` が正しいポートと health check を持つか

### B. server-configs 経由

フロー:

```text
server-configs を更新
-> AWS / EC2 に手動反映
-> 反映後に CloudWatch / systemctl / docker / nginx を確認
```

対象:
- Lambda
- queue
- EventBridge
- Nginx
- 集中管理用 systemd / docker-compose files

## 作業時の禁止事項

- API のコード変更を、CI/CD があるのにローカルから手動 `build/push` で先に進めない
- stale な文書 1 本だけを読んで反映経路を決めない
- `systemd` の存在だけを根拠に、そのサービスの source of truth を決めない

## Spot 修正時の見方

Spot 修正では通常、以下を切り分けます。

### API 側

- Aggregator API
- Profiler API

ここは各 API repo の CI/CD で反映。

### AWS 非同期基盤側

- `watchme-aggregator-checker`
- `watchme-spot-analysis-worker`
- Spot queues
- fallback EventBridge

ここは `server-configs` から直接反映。

## 反映後チェックリスト

### API 反映後

- GitHub Actions 成功
- ECR `latest` 更新
- EC2 の対象コンテナ起動確認
- `curl http://localhost:{port}/health`
- 外部 URL health 確認

### Lambda 反映後

- `get-function-configuration`
- event source mapping 確認
- queue attributes 確認
- rule / targets 確認
- Lambda 実行ロールの inline / attached policy 確認
- CloudWatch Logs で新バージョンが実行されていることを確認

Spot 関連の追加確認:
- `watchme-aggregator-checker` が `watchme-spot-analysis-queue.fifo` に enqueue できること
- `watchme-spot-analysis-worker` の log group が作成され、実行ログが出ること
- `daily_aggregator_status` が `queued` のまま取り残されていないこと

## 関連文書

- [CURRENT_STATE.md](./CURRENT_STATE.md)
- [CICD_STANDARD_SPECIFICATION.md](./CICD_STANDARD_SPECIFICATION.md)
- [PROCESSING_ARCHITECTURE.md](./PROCESSING_ARCHITECTURE.md)
