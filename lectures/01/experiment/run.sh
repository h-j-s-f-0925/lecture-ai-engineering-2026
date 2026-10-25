#!/usr/bin/env bash
# Bash の機能を使ってこのファイルを実行する。
# -e: コマンドが失敗したら終了、-u: 未定義の変数を使ったらエラー、
# pipefail: パイプ途中のコマンドが失敗した場合も失敗として扱う。
set -euo pipefail

# このスクリプトが置かれている場所を基準にリポジトリのルートを求める。
# BASH_SOURCE[0] はこのスクリプト自身のパス、dirname はその親フォルダ、
# ../../.. は experiment → 01 → lectures → リポジトリルートを表す。
# $(...) はコマンドの出力を文字列として取り込む書き方。
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# 以降の相対パスが、呼び出し元の場所によらずリポジトリルート基準になる。
cd "$repo_root"

# 全モデルで共通して使う質問。引用符で囲み、空白や記号を含む質問を1つの引数にする。
question='AIE2026の講座の宿題にある「3レベル」とは何ですか？'
# $# はスクリプトに渡された引数の個数。モデル名が1つ以上渡されたか調べる。
if (($# > 0)); then
  # "$@" は渡された引数をそれぞれ別の要素として保持する（空白を含む名前も壊さない）。
  models=("$@")
else
  # 引数がなければ、この2モデルを既定値として使う。
  models=(gemini-3.5-flash-lite gemini-3.5-flash)
fi

# レポートの保存先。Markdown形式の成果物なので reports フォルダーに保存する。
report_dir="lectures/01/experiment/reports"
# -p は親ディレクトリも作り、既にフォルダがあってもエラーにしない。
# 実験結果を残すフォルダを用意する。
mkdir -p "$report_dir"
# mktemp は実行ごとに異なる一時ファイル名を作る。
# date -u はUTC時刻を使い、XXXXXX は mktemp が一意な文字列に置き換える。
report_file="$(mktemp "$report_dir/experiment-$(date -u +%Y%m%dT%H%M%SZ)-XXXXXX.md")"
# 回答を一時保存する場所。最後にサマリー表を先頭に付けてレポートを組み立てる。
temp_dir="$(mktemp -d "$report_dir/.experiment-XXXXXX")"
# スクリプト終了時（成功・失敗・中断時）に、作成した一時ディレクトリを片付ける。
trap 'rm -rf "$temp_dir"' EXIT

# 固定の見出しや説明を記述した Markdown テンプレート。
template_file="lectures/01/experiment/report-template.md"
# 生成時にテンプレートへ差し込む内容を、それぞれ一時ファイルに作る。
summary_file="$temp_dir/summary.md"
conditions_file="$temp_dir/conditions.md"
responses_file="$temp_dir/responses.md"

# 各実行の条件・トークン数・結果・回答本文を、実行順に配列へ保持する。
run_models=()
run_numbers=()
input_tokens=()
output_tokens=()
run_statuses=()
answers=()
had_error=0

# models 配列に入っているモデルを1つずつ取り出し、同じ質問を3回実行する。
for model in "${models[@]}"; do
  for run in 1 2 3; do
    # API 呼び出し中であることが分かるよう、進捗は標準エラーへ表示する。
    printf '実行中: model=%s / %s回目\n' "$model" "$run" >&2
    output_file="$temp_dir/result-${#run_models[@]}.txt"

    # このコマンドだけ AIE_MODEL に model の値を設定する。
    # 出力を一時ファイルへ保存し、後でサマリーと本文を分けてレポートにまとめる。
    if AIE_MODEL="$model" uv run python -m app.ask "$question" > "$output_file" 2>&1; then
      run_status="成功"
    else
      # 失敗時もエラー出力をレポートに残し、残りの実行は続ける。
      run_status="失敗"
      had_error=1
    fi

    # [トークン] 行から入力・出力トークン数を取り出す。
    tokens="$(sed -n 's/.*\[トークン\] 入力: \([^ ]*\) \/ 出力: \([^ ]*\).*/\1 \2/p' "$output_file")"
    if [[ -n "$tokens" ]]; then
      read -r input_count output_count <<< "$tokens"
      # トークン情報の行より後を回答本文として残し、CLIの重複する見出しは除く。
      answer="$(sed -n '/^\[トークン\]/,$p' "$output_file" | sed '1d')"
    else
      # API エラーなどでトークン情報がなければ、コマンド出力全体を本文欄に残す。
      input_count="不明"
      output_count="不明"
      answer="$(cat "$output_file")"
    fi

    run_models+=("$model")
    run_numbers+=("$run")
    input_tokens+=("$input_count")
    output_tokens+=("$output_count")
    run_statuses+=("$run_status")
    answers+=("$answer")
  done
done

# 先にサマリー表を作る。固定のタイトル・見出しはテンプレート側で管理する。
{
  printf '| モデル | 実行回数 | 成功 / 失敗 | 入力トークン数（1 / 2 / 3回目） | 出力トークン数（1 / 2 / 3回目） | 平均出力トークン数 |\n'
  printf '|---|---:|---:|---|---|---:|\n'
  for model_index in "${!models[@]}"; do
    first_run_index=$((model_index * 3))
    success_count=0
    failure_count=0
    output_token_sum=0
    output_token_count=0
    for offset in 0 1 2; do
      run_index=$((first_run_index + offset))
      if [[ "${run_statuses[$run_index]}" == "成功" ]]; then
        success_count=$((success_count + 1))
      else
        failure_count=$((failure_count + 1))
      fi
      # 数値として取得できた出力トークン数だけを平均の対象にする。
      if [[ "${output_tokens[$run_index]}" =~ ^[0-9]+$ ]]; then
        output_token_sum=$((output_token_sum + output_tokens[$run_index]))
        output_token_count=$((output_token_count + 1))
      fi
    done
    if ((output_token_count > 0)); then
      # 小数第1位まで表示し、何回分の平均かも添える。
      average_output_tokens="$(awk -v sum="$output_token_sum" -v count="$output_token_count" \
        'BEGIN { printf "%.1f", sum / count }')"
      average_display="$average_output_tokens（${output_token_count}回分）"
    else
      average_display="不明（0回分）"
    fi
    printf '| %s | 3 | %s / %s | %s / %s / %s | %s / %s / %s | %s |\n' \
      "${models[$model_index]}" \
      "$success_count" \
      "$failure_count" \
      "${input_tokens[$first_run_index]}" \
      "${input_tokens[$((first_run_index + 1))]}" \
      "${input_tokens[$((first_run_index + 2))]}" \
      "${output_tokens[$first_run_index]}" \
      "${output_tokens[$((first_run_index + 1))]}" \
      "${output_tokens[$((first_run_index + 2))]}" \
      "$average_display"
  done
} > "$summary_file"

# 実行ごとに変わる条件を作る。テンプレートに含めず、ここで値をそのまま出力する。
{
  # date -u -Is はタイムゾーン付きのISO形式で現在時刻を表示する。
  printf -- '- 実行日時（UTC）: %s\n' "$(date -u -Is)"
  printf -- '- 質問: %s\n' "$question"
  printf -- '- 各モデルの実行回数: 3\n'
  printf -- '- モデル: %s\n' "${models[*]}"
} > "$conditions_file"

# モデルの回答は置換コマンドを通さず、折りたたみブロックとしてそのまま書き出す。
{
  for index in "${!run_models[@]}"; do
    # details / summary で回答を折りたたみ、見たい回答だけを開けるようにする。
    printf '\n<details>\n<summary>%s — %s回目（%s）</summary>\n\n' \
      "${run_models[$index]}" "${run_numbers[$index]}" "${run_statuses[$index]}"
    # 4連バッククォートで囲み、回答中に通常の3連バッククォートがあっても
    # 回答の途中でコードブロックが閉じないようにする。
    printf '````text\n'
    printf '%s\n' "${answers[$index]}"
    printf '````\n\n</details>\n'
  done
} > "$responses_file"

# テンプレート内のマーカーを見つけ、それぞれに対応する生成内容を挿入する。
# 回答本文そのものは sed などの置換処理に渡さず、そのまま responses.md からコピーする。
render_template() {
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      '<!-- SUMMARY_TABLE -->')
        cat "$summary_file"
        ;;
      '<!-- EXPERIMENT_CONDITIONS -->')
        cat "$conditions_file"
        ;;
      '<!-- RESPONSES -->')
        cat "$responses_file"
        ;;
      *)
        printf '%s\n' "$line"
        ;;
    esac
  done < "$template_file"
}

# テンプレートに生成内容を差し込み、実行ごとの Markdown レポートを完成させる。
render_template > "$report_file"

# 完成したレポートを画面にも表示する。
cat "$report_file"
printf 'Markdown レポートを保存しました: %s\n' "$report_file"

# 1回でも失敗していた場合、レポートを残したうえで失敗終了にする。
if ((had_error)); then
  exit 1
fi
