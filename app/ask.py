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
import time
from dataclasses import dataclass

from google import genai
from google.genai import errors
# 生成APIの設定値をSDKが受け取れる型で組み立てる。
from google.genai import types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある。
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"


@dataclass(frozen=True)
class AskResult:
    """生成APIの回答、利用量、応答時間をまとめた結果。"""

    answer: str
    input_tokens: int | None
    output_tokens: int | None
    history_tokens: int | None
    elapsed_seconds: float
    usage_metadata: dict[str, object] | None
    api_error: errors.APIError | None = None


def ask_with_metrics(
    question: str,
    temperature: float | None = None,
    history: list[types.Content] | None = None,
    model: str = MODEL,
    client: genai.Client | None = None,
) -> AskResult:
    """質問を送り、回答とAPI利用量・API応答時間を返す。"""
    # client が呼び出し元から渡された場合
    if client is None:
        # Gemini APIキーを使ってSDKクライアントを作る。
        client = genai.Client(api_key=get_api_key())

    history_tokens: int | None = 0
    # 過去の会話がある場合
    if history:
        # Gemini APIのCount tokens APIにモデル名と過去発話を渡し、
        # CountTokensResponse.total_tokensで履歴だけのtoken数を得る。
        history_usage = client.models.count_tokens(model=model, contents=list(history))
        history_tokens = history_usage.total_tokens
        contents: str | list[types.Content] = [
            *history,
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=question)],
            ),
        ]
    # 過去の会話がない場合
    else:
        contents = question

    # temperatureを指定した場合
    if temperature is not None:
        config = types.GenerateContentConfig(temperature=temperature)
    # temperatureを省略した場合
    else:
        config = None

    # 単調時計は時刻修正の影響を受けず、処理にかかった時間を測る。
    started_at = time.perf_counter()
    try:
        # 生成設定がない場合
        if config is None:
            # Gemini APIのGenerateContent APIへモデル名と入力を渡し、生成Responseを受け取る。
            response = client.models.generate_content(model=model, contents=contents)
        # 生成設定がある場合
        else:
            # configにもtemperatureを含めて渡し、生成Responseを受け取る。
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
    # GenerateContent APIがHTTP/APIエラーを返した場合
    except errors.APIError as error:
        elapsed_seconds = time.perf_counter() - started_at
        return AskResult(
            answer="",
            input_tokens=None,
            output_tokens=None,
            history_tokens=history_tokens,
            elapsed_seconds=elapsed_seconds,
            usage_metadata=None,
            api_error=error,
        )
    elapsed_seconds = time.perf_counter() - started_at

    usage = response.usage_metadata
    # API responseにtoken利用量が含まれる場合
    if usage is not None:
        input_tokens = usage.prompt_token_count
        output_tokens = usage.candidates_token_count
        # SDKのmodel_dumpでusage metadataをJSONにできる辞書へ変換して保存する。
        usage_metadata = usage.model_dump(mode="json", exclude_none=True)
    # API responseにtoken利用量が含まれない場合
    else:
        input_tokens = None
        output_tokens = None
        usage_metadata = None

    return AskResult(
        answer=response.text,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        history_tokens=history_tokens,
        elapsed_seconds=elapsed_seconds,
        usage_metadata=usage_metadata,
    )


def _print_token_usage(result: AskResult) -> None:
    """既存CLIと同じ書式で履歴・入力・出力トークン数を表示する。"""
    history_display = (
        result.history_tokens if result.history_tokens is not None else "不明"
    )
    input_display = result.input_tokens if result.input_tokens is not None else "不明"
    output_display = (
        result.output_tokens if result.output_tokens is not None else "不明"
    )
    print(
        f"[トークン] 履歴: {history_display} / "
        f"入力全体: {input_display} / 出力: {output_display}"
    )


def ask(
    question: str,
    temperature: float | None = None,
    history: list[types.Content] | None = None,
) -> str:
    """質問をモデルへ送り、回答文を返す。必要に応じて会話履歴も渡す。"""
    result = ask_with_metrics(question, temperature=temperature, history=history)
    _print_token_usage(result)
    if result.api_error is not None:
        raise result.api_error
    return result.answer


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
