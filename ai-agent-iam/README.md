# AIエージェント用 IAM モデル

AIエージェント（Claude Code 等）にAWSを操作させるための、**他プロジェクト／他アカウントへ横展開できる標準IAM設計**。
「弱い入口ユーザー1つ ＋ 用途別ロール2つ」の assume-role 方式。

## 設計思想

```
[入口ユーザー]  静的アクセスキーを持つが権限はほぼゼロ（AssumeRoleのみ）
     │           → 鍵が漏れても単体では無力
     │ assume
     ├──▶ [ai-agent-readonly ロール]   ReadOnly + Billing        ← 既定（調査・コスト分析の95%）
     └──▶ [ai-agent-operator ロール]   書き込み（ただし権限昇格不可） ← 明示的に昇格したときだけ
```

- **最小権限が既定**：普段は readonly。書き込みは operator を明示 assume した時のみ。
- **短命の一時認証**：CLIが都度STSでロールを assume するため、ディスク上に強い静的鍵を置かない。
- **監査で分離**：`role_session_name` によりCloudTrail上で「AIの操作」と「人間の操作」が区別される。
- **権限昇格の遮断**：operator は `iam:* / organizations:* / account:*` を明示Denyしているため、自分の権限を書き換えられない。

## デプロイ

```bash
# 新規アカウント（入口ユーザーも本スタックで作成する場合）
aws cloudformation deploy \
  --profile admin --region <REGION> \
  --stack-name ai-agent-iam \
  --template-file ai-agent-iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides NamePrefix=ai-agent CreateEntryUser=true

# 既存ユーザーを入口として再利用する場合（WatchMe はこちら）
aws cloudformation deploy \
  --profile admin --region ap-southeast-2 \
  --stack-name ai-agent-iam \
  --template-file ai-agent-iam.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides NamePrefix=ai-agent CreateEntryUser=false \
    ExistingEntryUserArn=arn:aws:iam::<ACCOUNT>:user/<EXISTING_USER>
```

デプロイ後、出力（`ReadonlyRoleArn` / `OperatorRoleArn`）を控える。

## ローカルCLIプロファイル設定

入口ユーザーのアクセスキーを `source_profile`（例: `ai-agent`）に登録済みとして、
`~/.aws/config` に role assume するプロファイルを追加する：

```ini
[profile ai-agent-ro]
role_arn = arn:aws:iam::<ACCOUNT>:role/ai-agent-readonly
source_profile = ai-agent
region = ap-southeast-2
role_session_name = ai-agent-ro

[profile ai-agent-op]
role_arn = arn:aws:iam::<ACCOUNT>:role/ai-agent-operator
source_profile = ai-agent
region = ap-southeast-2
role_session_name = ai-agent-op
```

- 調査／コスト分析：`aws <cmd> --profile ai-agent-ro`
- 書き込み操作　　：`aws <cmd> --profile ai-agent-op`

## MCP との連携

Claude Code の AWS MCP（`awslabs.aws-api-mcp-server`）は **読み取り専用プロファイルを指す**こと。
`.mcp.json` の `AWS_PROFILE` に readonly assume プロファイルを設定し、`READ_OPERATIONS_ONLY=true` も併用する。
IAM（読み取り専用ロール）が最終的な安全弁になる。

## operator ロールの権限レベルについて

本テンプレートの operator は `PowerUserAccess`（IAM/Organizations 以外の全操作）＋ 危険操作の明示Deny。
「便利さ」を優先した広めの既定値。より厳格にしたい場合は、`ai-agent-iam.yaml` の
`OperatorRole` の ManagedPolicyArns をカスタムの許可リストポリシーに差し替える。
