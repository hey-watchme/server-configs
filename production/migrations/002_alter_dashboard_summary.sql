-- =============================================================================
-- Migration: 002_alter_dashboard_summary
-- Description: Add status tracking and timestamp columns to dashboard_summary
-- Author: WatchMe Team
-- Date: 2025-11-09
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Add new columns to dashboard_summary
-- -----------------------------------------------------------------------------
ALTER TABLE dashboard_summary
  -- ステータス追加（累積分析の処理状態）
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending'
    CHECK (status IN ('pending', 'prompt_ready', 'analyzing', 'completed', 'failed')),

  -- タイムスタンプ追加
  ADD COLUMN IF NOT EXISTS prompt_generated_at TIMESTAMP WITH TIME ZONE,
  ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP WITH TIME ZONE;

-- -----------------------------------------------------------------------------
-- 2. Add comments for documentation
-- -----------------------------------------------------------------------------
COMMENT ON COLUMN dashboard_summary.status IS
  '累積分析のステータス（timeblock_vibeのstatusとは独立）
   - pending: 未処理
   - prompt_ready: プロンプト生成完了、ChatGPT分析待ち
   - analyzing: ChatGPT分析中
   - completed: 分析完了
   - failed: 分析失敗';

COMMENT ON COLUMN dashboard_summary.prompt IS
  'Dashboard Summary API が生成した累積プロンプト（入力データ、検証・デバッグ用に保存）';

COMMENT ON COLUMN dashboard_summary.prompt_generated_at IS
  'プロンプト生成完了時刻';

COMMENT ON COLUMN dashboard_summary.analyzed_at IS
  'ChatGPT累積分析完了時刻';

COMMENT ON COLUMN dashboard_summary.overall_summary IS
  'Dashboard Analysis API が生成した1日の総評（出力データ）';

COMMENT ON COLUMN dashboard_summary.average_vibe IS
  '1日の平均気分スコア（レポート画面で使用）
   週次レポート: 7日分のこの値を表示
   月次レポート: 30日分のこの値を表示
   年次レポート: 12ヶ月分をアプリ側で平均';

-- =============================================================================
-- Migration Complete
-- =============================================================================
