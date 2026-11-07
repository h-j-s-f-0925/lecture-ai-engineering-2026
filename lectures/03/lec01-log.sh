#!/usr/bin/env bash

# 質問が失敗しても残りを実行し、最後に失敗があったことを知らせる。
set -euo pipefail

# このスクリプトが置かれた場所からリポジトリのルートを求める。
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$SCRIPT_DIR/learning-log-input.md"
FAILED=0
cd "$REPO_ROOT"

# 初回だけ記録ファイルを作り、既存の記録は消さずに追記する。
if [[ ! -e "$LOG_FILE" ]]; then
    printf '# 講義・演習・宿題の実行記録\n' > "$LOG_FILE"
fi

# 実行した質問と日時、画面に出る結果を記録ファイルにも残す。
run_and_record() {
    local section="$1"
    local command_text="$2"
    shift 2

    if {
        printf '\n## %s\n' "$section"
        printf '実行日時: %s\n' "$(date -Is)"
        printf '実行コマンド: %s\n\n実行結果:\n' "$command_text"
        "$@"
    } 2>&1 | tee -a "$LOG_FILE"; then
        :
    else
        local exit_code=$?
        printf 'コマンドが終了コード %s で失敗しました。次の質問を続けます。\n' "$exit_code" |
            tee -a "$LOG_FILE"
        FAILED=1
    fi
}

run_and_record \
    "第1回 演習" \
    'uv run python -m app.ask "LoRAとは何ですか？"' \
    uv run python -m app.ask "LoRAとは何ですか？"

run_and_record \
    "第1回 演習" \
    'uv run python -m app.ask "AIE2026の講座の宿題にある「3レベル」とは何ですか？"' \
    uv run python -m app.ask "AIE2026の講座の宿題にある「3レベル」とは何ですか？"

run_and_record \
    "第1回 演習" \
    'uv run python -m app.ask "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？"' \
    uv run python -m app.ask "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？"

run_and_record \
    "第1回 演習" \
    'uv run python -m app.ask "AIE2026の第2回では何を学びますか？"' \
    uv run python -m app.ask "AIE2026の第2回では何を学びますか？"

printf '\n第1回の質問と結果を %s に追記しました。\n' "$LOG_FILE"

# すべての質問を試した後、途中に失敗があったことを終了コードで知らせる。
if ((FAILED != 0)); then
    printf '1つ以上の質問に失敗しました。メモに記録されたエラーを確認してください。\n' >&2
    exit 1
fi
