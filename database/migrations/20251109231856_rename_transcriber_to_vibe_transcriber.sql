-- カラム名を命名規則 {domain}_{technology}_result に統一
-- transcriber_result → vibe_transcriber_result

ALTER TABLE audio_features
RENAME COLUMN transcriber_result TO vibe_transcriber_result;

ALTER TABLE audio_features
RENAME COLUMN transcriber_status TO vibe_transcriber_status;

ALTER TABLE audio_features
RENAME COLUMN transcriber_processed_at TO vibe_transcriber_processed_at;
