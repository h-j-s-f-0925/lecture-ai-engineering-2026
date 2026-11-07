#!/usr/bin/env bash

# 質問に失敗した場合はエラー終了する。
set -euo pipefail

# このスクリプトが置かれた場所からリポジトリのルートと記録ファイルを求める。
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$SCRIPT_DIR/learning-log-input.md"
cd "$REPO_ROOT"

# 初回だけ記録ファイルを作り、既存の記録は消さずに追記する。
if [[ ! -e "$LOG_FILE" ]]; then
    printf '# 講義・演習・宿題の実行記録\n' > "$LOG_FILE"
fi

# 実行日時・コマンド・回答・traceを画面に表示し、同時に記録ファイルへ追記する。
{
    printf '\n## 第3回 演習\n実行日時: %s\n' "$(date -Is)"
    printf '実行コマンド: %s\n\n実行結果:\n' \
        'uv run python -m app.agent --trace "LoRAとQLoRAの違いは？"'
    uv run python -m app.agent --trace "LoRAとQLoRAの違いは？"
} 2>&1 | tee -a "$LOG_FILE"

printf '\n第3回の質問と結果を %s に追記しました。\n' "$LOG_FILE"
