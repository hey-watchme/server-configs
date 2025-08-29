# WatchMe Network Architecture

最終更新: 2025年8月28日

## 概要

このドキュメントは、WatchMeプラットフォームのネットワークアーキテクチャと、その管理方針について説明します。

## 基本原則

### 1. Infrastructure as Code (IaC)
- すべてのインフラストラクチャリソースはコードで定義
- `docker-compose.infra.yml`が唯一の真実の源（Single Source of Truth）

### 2. 単一責任の原則
- ネットワークの作成・管理は`watchme-infrastructure`サービスのみが担当
- 各APIサービスは利用者（Consumer）として既存ネットワークを使用

### 3. 明示的な依存関係
- systemdサービスで起動順序を明確に定義
- インフラストラクチャ → 各APIサービスの順で起動

## ネットワークトポロジー

```
┌─────────────────────────────────────────────────┐
│           watchme-network (172.27.0.0/16)        │
├─────────────────────────────────────────────────┤
│                                                  │
│  Gateway: 172.27.0.1                            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ API Manager  │  │   Scheduler   │            │
│  │ 172.27.0.4   │  │  172.27.0.2   │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │  Vault API   │  │  Transcriber  │            │
│  │  172.27.0.6   │  │  172.27.0.3   │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │  Mood Chart  │  │   OpenSMILE   │            │
│  │  172.27.0.7   │  │  172.27.0.12  │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
└─────────────────────────────────────────────────┘
```

### ネットワーク仕様

- **名前**: watchme-network
- **ドライバー**: bridge
- **サブネット**: 172.27.0.0/16
- **ゲートウェイ**: 172.27.0.1
- **作成者**: watchme-infrastructure service
- **管理者**: watchme-server-configs

## サービス追加ガイド

### 新しいAPIサービスを追加する際の手順

#### 1. docker-compose.ymlの設定

**必須**: すべてのサービスは以下の設定を使用してください。

```yaml
version: '3.8'

services:
  your-service:
    # ... サービス設定 ...
    networks:
      - watchme-network

networks:
  watchme-network:
    external: true  # 必ず external: true を使用
```

**禁止事項**:
- `driver: bridge`を使用しない（ネットワーク作成側になってしまう）
- networksセクションを省略しない（デフォルトネットワークになってしまう）

#### 2. systemdサービスの設定

```ini
[Unit]
Description=Your Service Description
After=docker.service watchme-infrastructure.service
Requires=docker.service watchme-infrastructure.service
```

#### 3. 接続確認

サービス起動後、必ず以下のコマンドで接続を確認：

```bash
# ネットワーク接続確認
docker network inspect watchme-network | grep your-container-name

# 他のコンテナとの通信確認
docker exec your-container ping -c 1 api-manager
```

## トラブルシューティング

### 問題: コンテナがwatchme-networkに接続されていない

**症状**:
```
ERROR: API接続エラー - コンテナ名 'xxx' が解決できません
```

**解決方法**:
```bash
# 手動で接続
docker network connect watchme-network [container-name]

# ヘルスチェックスクリプトを実行
/home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh
```

### 問題: watchme-networkが存在しない

**解決方法**:
```bash
# インフラストラクチャを起動
cd /home/ubuntu/watchme-server-configs
docker-compose -f docker-compose.infra.yml up -d

# または systemd経由
sudo systemctl start watchme-infrastructure
```

## 移行計画

### Phase 1: 準備（完了）
- [x] docker-compose.infra.yml作成
- [x] systemdサービス定義
- [x] ヘルスチェックスクリプト作成
- [x] ドキュメント作成

### Phase 2: 新規サービスへの適用
- [ ] 新規追加されるAPIは必ず`external: true`を使用

### Phase 3: 既存サービスの段階的移行
優先度順：
1. [ ] api_gen_prompt_mood_chart（完了）
2. [ ] admin
3. [ ] scheduler
4. [ ] watchme-vault-api
5. [ ] api-transcriber
6. [ ] その他のサービス
7. [ ] api-manager（最後）

### Phase 4: レガシーネットワークの削除
- [ ] 全サービス移行完了後、古いネットワーク定義を削除
- [ ] docker-compose.ymlから`driver: bridge`を削除
- [ ] 不要なネットワークをDockerから削除

## 監視とメンテナンス

### 定期ヘルスチェック

Cronジョブで5分ごとに実行：
```bash
*/5 * * * * /home/ubuntu/watchme-server-configs/scripts/check-infrastructure.sh
```

### ログ確認

```bash
# インフラストラクチャログ
tail -f /var/log/watchme-infrastructure.log

# systemdログ
journalctl -u watchme-infrastructure -f
```

### メトリクス確認

```bash
# 接続コンテナ数
docker network inspect watchme-network | jq '.[0].Containers | length'

# IP割り当て状況
docker network inspect watchme-network | jq -r '.[0].Containers | to_entries[] | "\(.value.Name): \(.value.IPv4Address)"' | sort
```

## セキュリティ考慮事項

1. **内部通信のみ**: watchme-networkは外部からアクセス不可
2. **最小権限の原則**: 各コンテナは必要なポートのみ公開
3. **ネットワーク分離**: 本番と開発環境でネットワークを分離

## 参考リンク

- [Docker Network Documentation](https://docs.docker.com/network/)
- [Docker Compose Networking](https://docs.docker.com/compose/networking/)
- [systemd Service Management](https://www.freedesktop.org/software/systemd/man/systemd.service.html)

## 変更履歴

| 日付 | 変更内容 | 作成者 |
|------|---------|--------|
| 2025-08-28 | 初版作成、インフラストラクチャレイヤー導入 | System |
| 2025-08-28 | api_gen_prompt_mood_chartをwatchme-networkに移行 | System |