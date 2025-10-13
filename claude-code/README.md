# claude-code CLI トラブルシューティング (最重要手引書)

**`claude-code` を使用する前、または不安定になった際は、必ずこのドキュメントを確認してください。**

このドキュメントは、`claude-code` CLIで頻繁に発生する問題と、その暫定的な運用ルールをまとめたものです。

---

## 現状の運用ルールと最重要事項

1.  **安定バージョン**: `claude-code` は自動更新機能により不安定な最新版がインストールされがちです。現在、安定して動作するバージョンは **`v2.0.5`** です。

2.  **問題の症状**: 使用中に突然フリーズし、文字入力やEnterキーが効かなくなります。この状態になったらプロセスを強制終了するしかありません。

3.  **復旧手順**: 後述の **`clean_reinstall_claude.sh`** スクリプトを実行します。このスクリプトは、不安定なバージョンを完全に削除し、安定版である `v2.0.5` を再インストールします。

4.  **スクリプト実行時の注意**: **スクリプト実行前に、必ず `claude-code` のプロセスを完全に終了させてください。** 起動したまま実行すると、ターミナルごとフリーズする危険性があります。

---

## 状態スナップショット (2025-10-07)

問題の原因を特定するため、安定版 (`v2.0.5`) をクリーンインストールした直後の状態を記録します。
問題が再発した際に、これらの情報と比較することで、変更点を特定できる可能性があります。

- **コマンドパス (`which claude`)**
  ```
  /Users/kaya.matsumoto/.npm-global/bin/claude
  ```

- **バージョン (`claude --version`)**
  ```
  2.0.5 (Claude Code)
  ```

- **実行ファイルのシンボリックリンク (`ls -l ~/.npm-global/bin/claude`)**
  ```
  lrwxr-xr-x  1 kaya.matsumoto  staff  52 10  7 15:48 /Users/kaya.matsumoto/.npm-global/bin/claude -> ../lib/node_modules/@anthropic-ai/claude-code/cli.js
  ```

- **設定ファイル (`cat ~/.claude/settings.json`)**
  ```json
  {
    "env": {
      "DISABLE_AUTOUPDATER": "1"
    },
    "alwaysThinkingEnabled": false
  }
  ```

- **パッケージ情報 (`package.json`)**
  ```json
  {
    "name": "@anthropic-ai/claude-code",
    "version": "2.0.5",
    "main": "sdk.mjs",
    "types": "sdk.d.ts",
    "bin": {
      "claude": "cli.js"
    },
    "engines": {
      "node": ">=18.0.0"
    },
    "type": "module",
    "author": "Anthropic <support@anthropic.com>",
    "license": "SEE LICENSE IN README.md",
    "description": "Use Claude, Anthropic's AI assistant, right from your terminal. Claude can understand your codebase, edit files, run terminal commands, and handle entire workflows for you.",
    "homepage": "https://github.com/anthropics/claude-code",
    "bugs": {
      "url": "https://github.com/anthropics/claude-code/issues"
    },
    "scripts": {
      "prepare": "node -e \"if (!process.env.AUTHORIZED) { console.error('ERROR: Direct publishing is not allowed.\nPlease use the publish-external.sh script to publish this package.'); process.exit(1); }\""
    },
    "dependencies": {},
    "optionalDependencies": {
      "@img/sharp-darwin-arm64": "^0.33.5",
      "@img/sharp-darwin-x64": "^0.33.5",
      "@img/sharp-linux-arm": "^0.33.5",
      "@img/sharp-linux-arm64": "^0.33.5",
      "@img/sharp-linux-x64": "^0.33.5",
      "@img/sharp-win32-x64": "^0.33.5"
    }
  }
  ```

---

## 関連スクリプト: `clean_reinstall_claude.sh`

- **目的**:
  `claude-code` がフリーズする問題が発生した際に、関連ファイルを完全に削除し、安定バージョンである **`v2.0.5`** をクリーンな状態で再インストールするためのスクリプトです。

- **場所**:
  `@/Users/kaya.matsumoto/projects/watchme/server-configs/claude-code/clean_reinstall_claude.sh`

- **使い方 (最重要)**:
  1.  `claude-code` が動作している場合は、**必ずプロセスを強制終了**してください。
  2.  ターミナルで上記スクリプトを実行します。

---

## これまでに解決した問題 (履歴)

過去に発生し、特定の設定変更によって解決した問題の履歴です。

- **問題1：`command not found` エラー**
  - **解決策**: `~/.npm-global` の所有権をユーザーに戻し (`sudo chown -R $(whoami) ~/.npm-global`)、`~/.zshrc` のPATHを修正しました。

- **問題2：自動更新による自己破壊**
  - **解決策**: `~/.claude/settings.json` で `DISABLE_AUTOUPDATER` を設定し、自動更新を無効化しました。

- **問題3：文字化け**
  - **解決策**: `~/.zshrc` で `export LC_ALL="ja_JP.UTF-8"` を設定し、ロケールを統一しました。