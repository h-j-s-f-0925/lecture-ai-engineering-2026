"""第1回発展課題: Geminiモデルの応答時間とtoken数を比較する。"""

import argparse
import html
import json
import math
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from google import genai

from app.ask import DEFAULT_QUESTION, AskResult, ask_with_metrics
from app.config import api_error_message, get_api_key

DEFAULT_MODELS = ["gemini-3.5-flash-lite", "gemini-3.5-flash"]
DEFAULT_QUESTIONS = ["LoRAとは何ですか？", DEFAULT_QUESTION]
DEFAULT_RUNS = 3
DEFAULT_INTERVAL_SECONDS = 2.0

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "lectures/01/experiment/reports"
TEMPLATE_FILE = ROOT / "lectures/01/experiment/report-template-advanced.md"
JST = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class ExperimentConfig:
    models: list[str]
    questions: list[str]
    runs: int
    interval_seconds: float
    temperature: float | None
    rate_limit_notes: str | None = None


@dataclass(frozen=True)
class RunRecord:
    model: str
    question: str
    question_number: int
    run_number: int
    recorded_at: str
    status: str
    elapsed_seconds: float
    input_tokens: int | None
    output_tokens: int | None
    usage_metadata: dict[str, object] | None
    answer: str
    error_code: int | None
    error: str | None


def create_parser() -> argparse.ArgumentParser:
    """モデルと実験条件を指定するCLI引数を定義する。"""
    parser = argparse.ArgumentParser(
        description="Gemini APIの応答時間とtoken数を複数条件で比較する"
    )
    parser.add_argument(
        "models",
        nargs="*",
        help="比較するGeminiモデル名（省略時は既定の2モデル）",
    )
    parser.add_argument(
        "--question",
        action="append",
        dest="questions",
        help="比較する質問。複数回指定できます",
    )
    parser.add_argument(
        "--runs",
        type=int,
        help="モデル・質問ごとの試行回数（環境変数 AIE_RUNS でも指定可能）",
    )
    parser.add_argument(
        "--interval",
        type=float,
        help=(
            "APIリクエスト間の待機秒数"
            "（環境変数 AIE_REQUEST_INTERVAL_SECONDS でも指定可能）"
        ),
    )
    parser.add_argument(
        "--rate-limit-notes",
        help="Google AI Studioで確認したtierや適用制限のメモ",
    )
    return parser


def resolve_config(
    args: argparse.Namespace,
    environ: dict[str, str] | None = None,
    questions_file: Path | None = None,
) -> ExperimentConfig:
    """CLI引数、環境変数、既定値の順に実験条件を決めて検証する。"""
    environment = environ if environ is not None else dict(os.environ)

    # モデル名が1つ以上指定された場合
    if args.models:
        models = [model.strip() for model in args.models]
    # モデル名が省略された場合
    else:
        models = DEFAULT_MODELS.copy()
    # モデル名が空の場合
    if any(not model for model in models):
        raise ValueError("モデル名に空の値は指定できません。")
    # 同じモデル名が複数回指定された場合
    if len(set(models)) != len(models):
        raise ValueError("同じモデル名を重複して指定できません。")

    questions_path_value = environment.get("AIE_QUESTIONS_FILE")
    # 質問をCLIとファイルの両方から指定した場合
    if args.questions and questions_path_value:
        raise ValueError(
            "--question と AIE_QUESTIONS_FILE は同時に指定できません。"
        )
    # CLIから質問が指定された場合
    if args.questions:
        # CLIの質問に空文字が含まれる場合
        if any(not question.strip() for question in args.questions):
            raise ValueError("空の質問は指定できません。")
        questions = [question.strip() for question in args.questions]
    # 質問ファイルが環境変数で指定された場合
    elif questions_path_value:
        path = questions_file or Path(questions_path_value)
        try:
            questions = path.read_text(encoding="utf-8").splitlines()
        except OSError as error:
            raise ValueError(f"質問ファイルを読み込めません: {path}: {error}") from error
        questions = [question.strip() for question in questions if question.strip()]
    # 質問が指定されていない場合
    else:
        questions = [question.strip() for question in DEFAULT_QUESTIONS]
    # 有効な質問が1つもない場合
    if not questions:
        raise ValueError("質問を1つ以上指定してください。")
    # 同じ質問が複数回指定された場合
    if len(set(questions)) != len(questions):
        raise ValueError("同じ質問を重複して指定できません。")

    runs = args.runs
    # CLIで試行回数が指定されていない場合
    if runs is None:
        try:
            runs = int(environment.get("AIE_RUNS", DEFAULT_RUNS))
        except ValueError as error:
            raise ValueError("AIE_RUNS は1以上の整数で指定してください。") from error
    # 試行回数が1未満の場合
    if runs < 1:
        raise ValueError("試行回数は1以上で指定してください。")

    interval_seconds = args.interval
    # CLIでリクエスト間隔が指定されていない場合
    if interval_seconds is None:
        try:
            interval_seconds = float(
                environment.get(
                    "AIE_REQUEST_INTERVAL_SECONDS",
                    str(DEFAULT_INTERVAL_SECONDS),
                )
            )
        except ValueError as error:
            raise ValueError(
                "AIE_REQUEST_INTERVAL_SECONDS は0以上の秒数で指定してください。"
            ) from error
    # リクエスト間隔が負数または有限でない場合
    if not math.isfinite(interval_seconds) or interval_seconds < 0:
        raise ValueError("リクエスト間隔は0以上の有限な秒数で指定してください。")

    temperature_value = environment.get("AIE_TEMPERATURE")
    # temperatureが環境変数に指定された場合
    if temperature_value:
        try:
            temperature = float(temperature_value)
        except ValueError as error:
            raise ValueError("AIE_TEMPERATURE は数値で指定してください。") from error
        # temperatureが有限でない場合
        if not math.isfinite(temperature):
            raise ValueError("AIE_TEMPERATURE は有限な数値で指定してください。")
    # temperatureが指定されていない場合
    else:
        temperature = None

    # 制限メモがCLIから指定された場合
    if args.rate_limit_notes is not None:
        rate_limit_notes = args.rate_limit_notes
    # 制限メモがCLIで省略された場合
    else:
        rate_limit_notes = environment.get("AIE_RATE_LIMIT_NOTES")

    return ExperimentConfig(
        models=models,
        questions=questions,
        runs=runs,
        interval_seconds=interval_seconds,
        temperature=temperature,
        rate_limit_notes=rate_limit_notes,
    )


def run_experiment(
    config: ExperimentConfig,
    client: genai.Client,
    sleep=time.sleep,
) -> list[RunRecord]:
    """モデル・質問・試行の全組み合わせを順に実行して記録する。"""
    total_runs = len(config.models) * len(config.questions) * config.runs
    records: list[RunRecord] = []

    # 同じ質問・試行番号のモデルを続けて呼び、時間帯の偏りを小さくする。
    for question_index, question in enumerate(config.questions, start=1):
        for run_number in range(1, config.runs + 1):
            for model in config.models:
                run_index = len(records) + 1
                print(
                    f"実行中: {run_index}/{total_runs} "
                    f"model={model} / 質問{question_index} / {run_number}回目",
                    file=sys.stderr,
                )
                result: AskResult = ask_with_metrics(
                    question,
                    temperature=config.temperature,
                    model=model,
                    client=client,
                )
                # Gemini API呼び出しが成功した場合
                if result.api_error is None:
                    status = "成功"
                    error_message = None
                # Gemini API呼び出しがAPIErrorになった場合
                else:
                    status = "失敗"
                    error_message = api_error_message(
                        result.api_error.code, result.api_error.message
                    )

                records.append(
                    RunRecord(
                        model=model,
                        question=question,
                        question_number=question_index,
                        run_number=run_number,
                        recorded_at=datetime.now(JST).isoformat(timespec="seconds"),
                        status=status,
                        elapsed_seconds=result.elapsed_seconds,
                        input_tokens=result.input_tokens,
                        output_tokens=result.output_tokens,
                        usage_metadata=result.usage_metadata,
                        answer=result.answer,
                        error_code=(
                            result.api_error.code
                            if result.api_error is not None
                            else None
                        ),
                        error=error_message,
                    )
                )

                # 最後のリクエスト以外は指定された秒数だけ間隔を空ける。
                if run_index < total_runs and config.interval_seconds:
                    sleep(config.interval_seconds)

    return records


def _escape_cell(value: object) -> str:
    """Markdown表の区切り文字や改行をセル内表示用に変換する。"""
    return str(value).replace("|", r"\|").replace("\n", "<br>")


def _format_seconds(seconds: float) -> str:
    return f"{seconds:.3f}"


def render_summary(records: list[RunRecord]) -> str:
    """モデル・質問ごとの成功数、失敗数、時間とtoken数を集計する。"""
    lines = [
        "| モデル | 質問 | 成功 / 失敗 | 応答時間 平均 / 中央値 / 最小 / 最大（秒） | 平均入力token | 平均出力token |",
        "|---|---|---:|---:|---:|---:|",
    ]
    groups = dict.fromkeys((record.model, record.question) for record in records)
    for model, question in groups:
        group = [
            record
            for record in records
            if record.model == model and record.question == question
        ]
        successful = [record for record in group if record.status == "成功"]
        failed_count = len(group) - len(successful)
        durations = [record.elapsed_seconds for record in successful]
        # 成功した応答時間が1件以上ある場合
        if durations:
            duration_summary = " / ".join(
                _format_seconds(value)
                for value in (
                    statistics.mean(durations),
                    statistics.median(durations),
                    min(durations),
                    max(durations),
                )
            )
        # 成功した応答時間がない場合
        else:
            duration_summary = "不明"

        input_values = [
            record.input_tokens
            for record in successful
            if record.input_tokens is not None
        ]
        output_values = [
            record.output_tokens
            for record in successful
            if record.output_tokens is not None
        ]
        input_average = (
            f"{statistics.mean(input_values):.1f}（{len(input_values)}回分）"
            if input_values
            else "不明"
        )
        output_average = (
            f"{statistics.mean(output_values):.1f}（{len(output_values)}回分）"
            if output_values
            else "不明"
        )
        lines.append(
            f"| {_escape_cell(model)} | {_escape_cell(question)} "
            f"| {len(successful)} / {failed_count} | {duration_summary} "
            f"| {input_average} | {output_average} |"
        )
    return "\n".join(lines)


def render_run_results(records: list[RunRecord]) -> str:
    """試行ごとの時間・token数・エラーをMarkdown表にする。"""
    lines = [
        "| # | 時刻（JST） | モデル | 質問 | 試行 | 状態 | 応答時間（秒） | 入力token | 出力token | エラーコード | エラー |",
        "|---:|---|---|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for index, record in enumerate(records, start=1):
        lines.append(
            f"| {index} | {record.recorded_at} | {_escape_cell(record.model)} "
            f"| {_escape_cell(record.question)} | {record.run_number} "
            f"| {record.status} | {_format_seconds(record.elapsed_seconds)} "
            f"| {record.input_tokens if record.input_tokens is not None else '不明'} "
            f"| {record.output_tokens if record.output_tokens is not None else '不明'} "
            f"| {record.error_code if record.error_code is not None else '—'} "
            f"| {_escape_cell(record.error or 'なし')} |"
        )
    return "\n".join(lines)


def render_conditions(config: ExperimentConfig, records: list[RunRecord]) -> str:
    """モデルや質問、待機時間など再現に必要な条件を記録する。"""
    lines = [
        f"- 実行日時（JST）: {datetime.now(JST).isoformat(timespec='seconds')}",
        "- API: Gemini GenerateContent API（非ストリーミング）",
        f"- モデル: {', '.join(config.models)}",
        f"- 各モデル・質問の試行回数: {config.runs}",
        f"- 質問数: {len(config.questions)}",
        f"- 生成リクエスト数: {len(records)}",
        f"- APIリクエスト間の待機時間: {config.interval_seconds:g}秒",
        "- temperature: "
        + (
            str(config.temperature)
            if config.temperature is not None
            else "モデル既定値"
        ),
        "- 実行順: 質問ごとに試行番号を進め、各回で指定モデル順に実行",
        "- 応答時間: API呼び出し直前からレスポンス完了直後までのクライアント側経過時間（通信・SDK処理を含む）",
        "- 確認したtier・適用制限: "
        + (
            _escape_cell(config.rate_limit_notes)
            if config.rate_limit_notes
            else "未記録（Google AI Studioで対象projectの制限を確認してください）"
        ),
        "- レート制限の注意: 少数回の結果から上限を推定しない",
        "",
        "### 質問",
    ]
    lines.extend(
        f"{index}. {_escape_cell(question)}"
        for index, question in enumerate(config.questions, start=1)
    )
    return "\n".join(lines)


def _response_fence(answer: str) -> str:
    fence = "```"
    while fence in answer:
        fence += "`"
    return fence


def render_responses(records: list[RunRecord]) -> str:
    """回答を個別に折りたたみ、Markdown構造を壊さないコードブロックにする。"""
    sections: list[str] = []
    for record in records:
        title = html.escape(
            f"質問{record.question_number}: {record.question} — "
            f"{record.model} / {record.run_number}回目（{record.status}）"
        )
        body = record.answer if record.answer else (record.error or "回答なし")
        fence = _response_fence(body)
        sections.append(
            f"<details>\n<summary>{_escape_cell(title)}</summary>\n\n"
            f"{fence}text\n{body}\n{fence}\n\n</details>"
        )
        # API responseに利用量metadataがある場合
        if record.usage_metadata is not None:
            usage_json = json.dumps(
                record.usage_metadata, ensure_ascii=False, sort_keys=True
            )
            usage_fence = _response_fence(usage_json)
            sections.append(
                f"<details>\n<summary>{_escape_cell(title)} — usage metadata</summary>\n\n"
                f"{usage_fence}json\n{usage_json}\n{usage_fence}\n\n</details>"
            )
    return "\n\n".join(sections)


def render_report(config: ExperimentConfig, records: list[RunRecord]) -> str:
    """既存テンプレートのマーカーへ実験結果を差し込む。"""
    replacements = {
        "<!-- SUMMARY_TABLE -->": render_summary(records),
        "<!-- EXPERIMENT_CONDITIONS -->": render_conditions(config, records),
        "<!-- RUN_RESULTS -->": render_run_results(records),
        "<!-- RESPONSES -->": render_responses(records),
    }
    template = TEMPLATE_FILE.read_text(encoding="utf-8")
    for marker, content in replacements.items():
        template = template.replace(marker, content)
    return template


def save_report(config: ExperimentConfig, records: list[RunRecord]) -> Path:
    """JST日時と一意な識別子を付けてMarkdownレポートを保存する。"""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(JST).strftime("%Y%m%d_%H%M")
    report_path = REPORT_DIR / f"{timestamp}_experiment-{uuid.uuid4().hex[:6]}.md"
    report_path.write_text(render_report(config, records), encoding="utf-8")
    return report_path


def main(argv: list[str] | None = None) -> None:
    """CLIの引数を受け取り、実験・レポート保存までを順につなぐ入口。"""
    # CLI引数の定義とヘルプ表示を行う argparse の解析器を用意する。
    parser = create_parser()
    # 呼び出し元から渡された引数、または実行時のコマンドライン引数を解析する。
    args = parser.parse_args(argv)
    # 入力条件に誤りがあれば、APIを呼ぶ前に利用方法とエラーを表示する。
    try:
        # CLI引数・環境変数・既定値から設定を作り、値の妥当性を検証する。
        config = resolve_config(args)
    # 設定値が不正な場合
    except ValueError as error:
        # argparseの標準エラー表示と終了処理で、原因を利用者へ伝える。
        parser.error(str(error))

    # APIキーを読み込み、Gemini APIを呼び出すSDKクライアントを作る。
    client = genai.Client(api_key=get_api_key())
    # 実験のユースケース処理へ条件とクライアントを渡し、各試行の結果を受け取る。
    records = run_experiment(config, client)
    # 各試行の結果を集計・整形し、Markdownレポートを保存してパスを受け取る。
    report_path = save_report(config, records)
    # 保存したレポート本文を標準出力へ表示する。
    print(report_path.read_text(encoding="utf-8"))
    # printのfile引数にsys.stderr（標準エラー出力）を渡し、通常出力のレポート本文と分けて保存先を表示する。
    print(f"Markdown レポートを保存しました: {report_path}", file=sys.stderr)
    # どれか1回でもAPI呼び出しに失敗した場合
    if any(record.status == "失敗" for record in records):
        # レポートを残したうえで、失敗を示す終了コード1でCLIを終了する。
        raise SystemExit(1)


# このファイルをPythonモジュールとして直接実行した場合
if __name__ == "__main__":
    # CLIの入口を呼び出して実験処理を開始する。
    main()
