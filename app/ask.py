"""第1回: 素のLLMに1回だけ質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする

ツールも会話履歴も持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse

from google import genai
from google.genai import errors
# 生成設定を表すSDKの型を利用する。
from google.genai import types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def ask(question: str, temperature: float | None = None) -> str:
    """質問をモデルへ送り、回答文を返す。temperature は省略可能。"""
    # APIキーを使ってGemini SDKのクライアントを作る。
    client = genai.Client(api_key=get_api_key())
    config = (
        # SDKの型で生成時の設定を作る。
        types.GenerateContentConfig(temperature=temperature)
        if temperature is not None
        # 省略時は設定を作らず、従来のモデル既定動作を保つ。
        else None
    )
    if config is None:
        # temperature未指定時はconfig引数自体を渡さず、モデルの既定値を使う。
        response = client.models.generate_content(model=MODEL, contents=question)
    else:
        # configを使ってtemperatureを生成APIへ渡し、応答を受け取る。
        response = client.models.generate_content(
            # model・質問・生成設定をSDKへ渡す。
            model=MODEL, contents=question, config=config
        )

    # Google Gen AI Python SDK（google-genai）の利用量情報では、入力が prompt、
    # 生成出力が candidates の各トークン数に対応する。
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count if usage is not None else None
    output_tokens = usage.candidates_token_count if usage is not None else None

    # メタデータや個別の値がない場合も、数値と誤解されないよう「不明」と表示する。
    input_display = input_tokens if input_tokens is not None else "不明"
    output_display = output_tokens if output_tokens is not None else "不明"

    # 回答本文とは分けて利用量を表示する。
    print(f"[トークン] 入力: {input_display} / 出力: {output_display}")

    return response.text


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    parser.add_argument(
        # 生成のランダムさを調整するオプション。入力を小数に変換し、不正値はargparseが知らせる。
        "--temperature",
        type=float,
        # CLIのヘルプに、設定の用途とモデルごとの差を説明する。
        help="回答のランダムさを調整する値（モデルで利用可能な範囲は異なります）",
    )
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    print(f"[質問] {args.question}\n")
    if args.temperature is not None:
        # 実験条件が分かるよう、指定値を表示する。
        print(f"[temperature] {args.temperature}")
    try:
        # CLIの質問と温度をask()へ渡し、返された回答を表示する。
        print(ask(args.question, temperature=args.temperature))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
