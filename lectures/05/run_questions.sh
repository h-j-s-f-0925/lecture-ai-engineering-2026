#!/usr/bin/env bash
# 質問の一覧ファイルを読み、app.agent の各方式（全文投入・ベクトル検索・Tree・Graph）で
# 順に実行して、結果を Markdown に、生の出力をログに残すスクリプト。
#
# 使い方（リポジトリのどこからでも実行できる）:
#   bash lectures/05/run_questions.sh [質問ファイル]
#
#   質問ファイルを省略すると、このスクリプトと同じフォルダの questions.tsv を使う。
#   ほかの回で使うときは、その回のフォルダに質問ファイルを置いて渡す:
#     bash lectures/05/run_questions.sh lectures/06/questions.tsv
#
# 質問ファイルの形式（UTF-8、1行1問、タブ区切り）:
#   質問ID<TAB>質問文<TAB>期待するふるまい
#   - 質問ID は半角英数字・ハイフン・アンダースコアだけ（ログのファイル名に使う）
#   - 期待するふるまい（正解・根拠ページ・断るべきか など）は省略できる。
#     書いた場合は結果に並べて表示し、人が採点するときの基準にする
#   - 空行と # で始まる行は読み飛ばす
#
# 環境変数で挙動を変えられる:
#   AIE_MODES="vector tree"   実行する方式を絞る（既定は full-context vector tree graph）
#   AIE_SLEEP=10              各実行の間に待つ秒数（APIのレート制限対策。既定は5秒）
#   AIE_RUN_NAME=演習追加質問  出力フォルダ名の日付の後ろ（既定は質問ファイル名から拡張子を除いたもの）
#   AIE_MODEL / AIE_RAG_DB    app.agent にそのまま渡る（実行条件として summary.md に記録する）
#
# 出力先（<回> は質問ファイルがあるフォルダ。同じ日の2回目以降は _2, _3 … を付ける）:
#   <回>/results/<YYYYMMDD>_<名前>/summary.md   実行条件と [model]・[time]・[usage]・[cost]・[tool call] の抜き出し
#   <回>/results/<YYYYMMDD>_<名前>/<YYYYMMDD>_<N>_結果.md  全実行のコマンドと出力全文（N はその日の何回目の実行か。1から数える）
#   <回>/.log/<YYYYMMDD>_<名前>/<質問ID>_<方式>.log  各実行の標準出力・標準エラー（.gitignore の対象）

set -u

usage() {
  # 先頭のコメント行（2行目から、最初のコメントでない行の手前まで）を表示する
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
QUESTIONS_FILE="${1:-${SCRIPT_DIR}/questions.tsv}"
if [[ ! -f "$QUESTIONS_FILE" ]]; then
  echo "質問ファイルが見つかりません: ${QUESTIONS_FILE}" >&2
  exit 1
fi
# 出力先は、質問ファイルがあるフォルダ（講義回のフォルダ）を基準にする
QUESTIONS_FILE="$(cd "$(dirname "$QUESTIONS_FILE")" && pwd)/$(basename "$QUESTIONS_FILE")"
LECTURE_DIR="$(dirname "$QUESTIONS_FILE")"

# リポジトリのルートへ移動する（python -m app.agent をルートから実行するため）
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "Git リポジトリの中で実行してください" >&2
  exit 1
}
# Git Bash では git が C:/... 形式で返すので、pwd の形式（/c/...）にそろえる
REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
cd "$REPO_ROOT" || exit 1

# Windows の Python は、出力先がパイプ（tee）だと cp932 で書き出して文字化けする。
# UTF-8 で書き出すよう固定する（Linux の Dev Container では元から UTF-8 なので影響なし）
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
# pydantic-ai の起動バナーを出さない
export PYDANTIC_AI_NO_BANNER=1

SLEEP_SEC="${AIE_SLEEP:-5}"
MODES="${AIE_MODES:-full-context vector tree graph}"
RUN_NAME="${AIE_RUN_NAME:-$(basename "${QUESTIONS_FILE%.*}")}"

# 方式名を app.agent のオプションに変換する
mode_flag() {
  case "$1" in
    full-context) echo "--full-context" ;;
    vector)       echo "" ;;
    tree)         echo "--tree" ;;
    graph)        echo "--graph" ;;
    *) return 1 ;;
  esac
}

# 方式名を先に確かめる（途中で止まって API の呼び出しが無駄にならないように）
for mode in $MODES; do
  mode_flag "$mode" > /dev/null || {
    echo "未知の方式です: ${mode}（使えるのは full-context vector tree graph）" >&2
    exit 1
  }
done

# 質問ファイルを読む。Windows で保存した CRLF の改行にも対応する
QUESTION_IDS=()
QUESTIONS=()
EXPECTED=()
line_no=0
while IFS= read -r line || [[ -n "$line" ]]; do
  line_no=$((line_no + 1))
  line="${line%$'\r'}"
  [[ -z "${line//[[:space:]]/}" || "$line" == \#* ]] && continue
  if [[ "$line" != *$'\t'* ]]; then
    echo "${QUESTIONS_FILE}:${line_no}: 質問IDと質問文をタブで区切ってください" >&2
    exit 1
  fi
  qid="${line%%$'\t'*}"
  rest="${line#*$'\t'}"
  # 3列目（期待するふるまい）がある場合
  if [[ "$rest" == *$'\t'* ]]; then
    question="${rest%%$'\t'*}"
    expected="${rest#*$'\t'}"
  # 2列だけの場合
  else
    question="$rest"
    expected=""
  fi
  if [[ ! "$qid" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "${QUESTIONS_FILE}:${line_no}: 質問ID「${qid}」には半角英数字・ハイフン・アンダースコアだけを使ってください" >&2
    exit 1
  fi
  for existing in "${QUESTION_IDS[@]}"; do
    if [[ "$existing" == "$qid" ]]; then
      echo "${QUESTIONS_FILE}:${line_no}: 質問ID「${qid}」が重複しています" >&2
      exit 1
    fi
  done
  if [[ -z "${question//[[:space:]]/}" ]]; then
    echo "${QUESTIONS_FILE}:${line_no}: 質問文が空です" >&2
    exit 1
  fi
  QUESTION_IDS+=("$qid")
  QUESTIONS+=("$question")
  EXPECTED+=("$expected")
done < "$QUESTIONS_FILE"

if [[ ${#QUESTION_IDS[@]} -eq 0 ]]; then
  echo "質問ファイルに質問がありません: ${QUESTIONS_FILE}" >&2
  exit 1
fi

# .env があれば読み込む（Codespaces の secret だけで動かす場合は無くてもよい）
ENV_ARGS=()
if [[ -f .env ]]; then
  ENV_ARGS=(--env-file .env)
fi

# 出力フォルダ名は「日付_名前」。同じ日に再実行したときは _2, _3 … を付けて上書きを防ぐ
RUN_STARTED="$(date '+%Y-%m-%d %H:%M:%S')"
RUN_DATE="$(date +%Y%m%d)"
BASE_NAME="${RUN_DATE}_${RUN_NAME}"
DIR_NAME="$BASE_NAME"
# その日の何回目の実行か（フォルダ名の _2, _3 … と同じ番号。1回目は 1）
RUN_NO=1
while [[ -e "${LECTURE_DIR}/results/${DIR_NAME}" || -e "${LECTURE_DIR}/.log/${DIR_NAME}" ]]; do
  RUN_NO=$((RUN_NO + 1))
  DIR_NAME="${BASE_NAME}_${RUN_NO}"
done
OUT_DIR="${LECTURE_DIR}/results/${DIR_NAME}"
LOG_DIR="${LECTURE_DIR}/.log/${DIR_NAME}"
mkdir -p "$OUT_DIR" "$LOG_DIR"
SUMMARY="${OUT_DIR}/summary.md"
FULL="${OUT_DIR}/${RUN_DATE}_${RUN_NO}_結果.md"

# 表示用に、リポジトリのルートからの相対パスにする
rel() { echo "${1#"${REPO_ROOT}/"}"; }

# 再現に必要な実行条件を先頭に記録する
{
  echo "# ${RUN_NAME} の実行結果（${RUN_STARTED}）"
  echo
  echo "- 質問ファイル: $(rel "$QUESTIONS_FILE")（${#QUESTION_IDS[@]} 問）"
  echo "- commit: $(git rev-parse --short HEAD 2>/dev/null || echo 不明)$(git diff --quiet 2>/dev/null || echo '（未コミットの変更あり）')"
  echo "- AIE_MODEL: ${AIE_MODEL:-未設定（app/config.py の既定）}"
  echo "- AIE_RAG_DB: ${AIE_RAG_DB:-未設定（既定の data/rag_data/index.sqlite3）}"
  echo "- 方式: ${MODES}"
  echo "- ログ: $(rel "$LOG_DIR")/"
  echo
} > "$SUMMARY"

{
  echo "# ${RUN_NAME} の実行結果（${RUN_STARTED}）"
  echo
} > "$FULL"

first=1
for i in "${!QUESTION_IDS[@]}"; do
  qid="${QUESTION_IDS[$i]}"
  question="${QUESTIONS[$i]}"
  expected="${EXPECTED[$i]}"
  for file in "$SUMMARY" "$FULL"; do
    {
      if [[ "$file" == "$SUMMARY" ]]; then echo "## ${qid}"; else echo "# ${qid}"; fi
      echo
      echo "質問: ${question}"
      echo
      # 期待するふるまいが書かれている場合
      if [[ -n "$expected" ]]; then
        echo "期待するふるまい: ${expected}"
        echo
      fi
    } >> "$file"
  done

  for mode in $MODES; do
    flag="$(mode_flag "$mode")"
    log="${LOG_DIR}/${qid}_${mode}.log"

    # 連続実行でレート制限に当たらないよう、2回目以降は待つ
    if [[ $first -eq 0 ]]; then sleep "$SLEEP_SEC"; fi
    first=0

    echo "=== ${qid} / ${mode} ==="
    # --quiet で uv 自身の進捗表示（仮想環境の作成・ダウンロードなど）を出さない
    # shellcheck disable=SC2086
    uv run --quiet "${ENV_ARGS[@]}" python -m app.agent $flag --trace "$question" 2>&1 | tee "$log"
    status=${PIPESTATUS[0]}

    {
      echo "### ${mode}"
      echo
      echo '```text'
      echo "exit status: ${status}"
      grep -E '^\[(model|full-context|time|usage|cost)\]|^\[tool call\]' "$log" \
        || echo "（該当行なし。ログを確認する: $(rel "$log")）"
      echo '```'
      echo
    } >> "$SUMMARY"

    # コマンドと出力全文を1ファイルにまとめる
    {
      echo "## ${mode}"
      echo '```bash'
      echo "\$ uv run ${ENV_ARGS[*]} python -m app.agent ${flag:+$flag }--trace \"${question}\""
      cat "$log"
      echo "exit status: ${status}"
      echo '```'
      echo
    } >> "$FULL"
  done
done

echo
echo "完了: $(rel "$OUT_DIR")"
echo "要約: $(rel "$SUMMARY")"
echo "全出力: $(rel "$FULL")"
echo "ログ: $(rel "$LOG_DIR")/"
