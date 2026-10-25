"""第1回: 素のLLMへ質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 対話モード

ツールを持たない「素の」呼び出し。対話モードでは同じプロセス内の会話履歴を保つ。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse

from google import genai
from google.genai import errors
# 生成APIの設定値をSDKが受け取れる型で組み立てる。
from google.genai import types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある。
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


def ask(
    question: str,
    temperature: float | None = None,
    history: list[types.Content] | None = None,
) -> str:
    """質問をモデルへ送り、回答文を返す。必要に応じて会話履歴も渡す。"""
    # APIキーを渡してSDKクライアントを作り、Gemini APIへの窓口として使う。
    client = genai.Client(api_key=get_api_key())
    # 履歴がない最初の質問では、履歴トークン数は0とする。
    history_tokens: int | None = 0
    # 会話履歴がある場合
    if history:
        # len(history)で分かるのは発話数で、モデルが処理するトークン数ではない。
        # 履歴だけのトークン数を得るため、Gemini APIのCount tokens APIを追加で呼び出す。
        # Python SDKではclient.models.count_tokens(...)にモデル名と履歴を渡し、
        # 返されたCountTokensResponseのtotal_tokensから履歴のトークン数を取り出す。
        history_usage = client.models.count_tokens(
            model=MODEL, contents=list(history)
        )
        history_tokens = history_usage.total_tokens
        # 過去の発話を保ち、今回の質問を末尾に追加してターン順を維持する。
        contents: str | list[types.Content] = [
            *history,
            types.Content(
                role="user",
                # 質問文をSDKのテキストPartに変換し、Contentの本文として格納する。
                parts=[types.Part.from_text(text=question)],
            ),
        ]
    # 会話履歴がない場合
    else:
        # 単発質問では従来のリクエスト形式を保つ。
        contents = question
    # temperature が指定された場合
    if temperature is not None:
        # 指定値をSDKの生成設定へ変換する。
        config = types.GenerateContentConfig(temperature=temperature)
    # temperature が省略された場合
    else:
        # 後続処理で設定引数を省略できるようNoneにする。
        config = None
    # 生成設定がない場合
    if config is None:
        # modelにモデル名、contentsに質問を渡すと、生成結果を含むResponseが返る。
        response = client.models.generate_content(model=MODEL, contents=contents)
    # 生成設定がある場合
    else:
        # configも渡すことでtemperatureを適用し、Responseから本文や利用量を読む。
        response = client.models.generate_content(
            model=MODEL, contents=contents, config=config
        )

    # SDKの利用量メタデータではpromptが入力、candidatesが生成出力のトークン数を表す。
    usage = response.usage_metadata
    # 利用量メタデータがある場合
    if usage is not None:
        # SDKの項目名から入力・出力のトークン数を取り出す。
        input_tokens = usage.prompt_token_count
        output_tokens = usage.candidates_token_count
    # 利用量メタデータがない場合
    else:
        # 未取得と0トークンを区別できるようNoneで表す。
        input_tokens = None
        output_tokens = None

    # 入力トークン数が取得できた場合
    if input_tokens is not None:
        input_display = input_tokens
    # 入力トークン数を取得できない場合
    else:
        input_display = "不明"
    # 出力トークン数が取得できた場合
    if output_tokens is not None:
        output_display = output_tokens
    # 出力トークン数を取得できない場合
    else:
        output_display = "不明"
    # 履歴トークン数を計数できた場合
    if history_tokens is not None:
        history_display = history_tokens
    # 履歴トークン数を計数できない場合
    else:
        history_display = "不明"

    # 入力は履歴と今回の質問の合計、履歴は過去の会話だけの数を示す。
    print(
        f"[トークン] 履歴: {history_display} / "
        f"入力全体: {input_display} / 出力: {output_display}"
    )

    return response.text


def run_interactive(temperature: float | None = None) -> None:
    """会話履歴を保ちながら、入力が続く間モデルへ質問する。"""
    # 履歴はプロセス内だけに保持し、次の質問を送るたびにモデルへ渡す。
    history: list[types.Content] = []
    # 対話モードの終了方法を開始時に案内する。
    print("質問を入力してください（終了: /exit または /quit）")

    # 終了コマンドが入力されるまで、質問と回答のターンを繰り返す。
    while True:
        # 次の質問を受け付ける。
        question = input("質問> ")
        # 終了コマンドが入力された場合
        if question.strip() in {"/exit", "/quit"}:
            break
        # 入力が空白だけの場合
        if not question.strip():
            continue

        # 履歴と温度設定を渡してモデルに質問し、回答を受け取る。
        answer = ask(question, temperature=temperature, history=history)
        # 回答と対応する質問を表示する。
        print(f"[質問] {question}\n")
        # APIから返された回答本文を表示する。
        print(answer)
        # 成功したターンだけを保存し、次回も質問と回答の順序で送れるようにする。
        history.extend(
            [
                # userは利用者の発話を表す。
                types.Content(
                    role="user",
                    # 質問文をSDKのテキストPartに変換し、Contentの本文として格納する。
                    parts=[types.Part.from_text(text=question)],
                ),
                # modelはモデルの回答を表す。
                types.Content(
                    role="model",
                    # 回答文も同じ形式にして、次回送信する履歴へ追加する。
                    parts=[types.Part.from_text(text=answer)],
                ),
            ]
        )


def main() -> None:
    # argparseはCLI引数の定義・変換・--help表示をまとめて扱う標準ライブラリ。
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    # nargs="?"で位置引数を省略可能にし、省略時はNoneになる。
    parser.add_argument("question", nargs="?")
    parser.add_argument(
        # --temperatureの後の値をfloatに変換し、args.temperatureから参照できるようにする。
        "--temperature",
        type=float,
        help="回答のランダムさを調整する値（モデルで利用可能な範囲は異なります）",
    )
    # CLI入力を解析してNamespaceを返す。不正な値や--helpではargparseが終了処理を行う。
    args = parser.parse_args()

    # 実行条件が分かるよう、使用モデルを表示する。
    print(f"[model] {MODEL}")
    # temperature が指定された場合
    if args.temperature is not None:
        # 再現に必要な生成条件を表示する。
        print(f"[temperature] {args.temperature}")
    # SDKがAPI失敗時に送出するAPIErrorを捕捉し、利用者向けに整形する。
    try:
        # 質問文が指定されていない場合
        if args.question is None:
            # 前の質問を引き継ぐ対話モードであることをターミナルに示す。
            print("[mode] 対話")
            run_interactive(temperature=args.temperature)
        # 質問文が指定されている場合
        else:
            # この起動だけで完結する単発モードであることをターミナルに示す。
            print("[mode] 単発質問（会話履歴なし）")
            # 単発実行の入力と回答を対応づけて表示する。
            print(f"[質問] {args.question}\n")
            # 指定された条件で1回だけモデルに質問する。
            print(ask(args.question, temperature=args.temperature))
    # Gemini APIエラーが発生した場合
    except errors.APIError as e:
        # エラーコードと詳細を共通の説明形式で表示する。
        print(api_error_message(e.code, e.message))
        # SystemExit(1)でCLIを失敗終了させ、0（成功）と区別できる終了コードを返す。
        raise SystemExit(1)


# Pythonがこのファイルを直接実行すると__name__は"__main__"になる。
if __name__ == "__main__":
    # import時の副作用を避け、直接実行またはpython -m app.askのときだけCLIを起動する。
    main()
