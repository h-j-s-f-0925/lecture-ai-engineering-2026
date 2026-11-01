#!/usr/bin/env bash
set -euo pipefail

# $(...) は中のコマンドの出力を文字列として使い、ここではリポジトリのルートを求める。
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

# Python runner（実験条件・API呼び出し・結果集計を行うPythonプログラム）を起動する。
# "$@" は引数を個別に保って転送し、exec はこのシェルを起動先のプログラムに置き換える。
exec uv run python -m app.benchmark "$@"
