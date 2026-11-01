from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import errors

import app.benchmark as benchmark
from app.ask import AskResult


def _parse_args(*argv):
    return benchmark.create_parser().parse_args(list(argv))


def _result(
    answer="回答",
    elapsed_seconds=1.0,
    input_tokens=10,
    output_tokens=5,
    api_error=None,
):
    return AskResult(
        answer=answer,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        history_tokens=0,
        elapsed_seconds=elapsed_seconds,
        usage_metadata={"prompt_token_count": input_tokens or 0},
        api_error=api_error,
    )


def test_resolve_config_uses_defaults_and_cli_values_override_environment():
    """未指定時の既定条件と、CLI値が環境変数より優先されることを確認する。"""
    defaults = benchmark.resolve_config(_parse_args(), environ={})
    assert defaults.models == benchmark.DEFAULT_MODELS
    assert defaults.questions == benchmark.DEFAULT_QUESTIONS
    assert defaults.runs == 3
    assert defaults.interval_seconds == 2.0

    configured = benchmark.resolve_config(
        _parse_args(
            "model-a",
            "--question",
            " 質問A ",
            "--question",
            "質問B",
            "--runs",
            "2",
            "--interval",
            "0.5",
            "--rate-limit-notes",
            "Free tier",
        ),
        environ={
            "AIE_RUNS": "9",
            "AIE_REQUEST_INTERVAL_SECONDS": "4",
            "AIE_TEMPERATURE": "0.2",
        },
    )
    assert configured.models == ["model-a"]
    assert configured.questions == ["質問A", "質問B"]
    assert configured.runs == 2
    assert configured.interval_seconds == 0.5
    assert configured.temperature == 0.2
    assert configured.rate_limit_notes == "Free tier"


def test_resolve_config_reads_questions_file(tmp_path):
    """環境変数で指定した質問ファイルをUTF-8で読み込む。"""
    question_file = tmp_path / "questions.txt"
    question_file.write_text("質問A\n\n 質問B \n", encoding="utf-8")

    config = benchmark.resolve_config(
        _parse_args(),
        environ={"AIE_QUESTIONS_FILE": str(question_file)},
    )

    assert config.questions == ["質問A", "質問B"]


@pytest.mark.parametrize(
    ("argv", "environ", "message"),
    [
        (("--question", "A"), {"AIE_QUESTIONS_FILE": "questions.txt"}, "同時"),
        (("--runs", "0"), {}, "1以上"),
        (("--interval", "-1"), {}, "0以上"),
        (("--question", "   "), {}, "質問"),
        (("model-a", "model-a"), {}, "重複"),
        (("--question", "A", "--question", "A"), {}, "重複"),
        ((), {"AIE_RUNS": "bad"}, "AIE_RUNS"),
    ],
)
def test_resolve_config_rejects_invalid_or_conflicting_values(
    argv, environ, message
):
    """矛盾する条件や不正値はAPI実行前にエラーにする。"""
    with pytest.raises(ValueError, match=message):
        benchmark.resolve_config(_parse_args(*argv), environ=environ)


def test_run_experiment_executes_every_model_question_and_run(monkeypatch):
    """質問・試行・モデルの全組み合わせを順に実行し、間隔を空ける。"""
    config = benchmark.ExperimentConfig(
        models=["model-a", "model-b"],
        questions=["question-a", "question-b"],
        runs=2,
        interval_seconds=0.25,
        temperature=None,
    )
    ask = Mock(side_effect=[_result() for _ in range(8)])
    monkeypatch.setattr(benchmark, "ask_with_metrics", ask)
    sleeps = []

    records = benchmark.run_experiment(
        config,
        client=SimpleNamespace(),
        sleep=sleeps.append,
    )

    assert len(records) == 8
    assert [
        (call.args[0], call.kwargs["model"])
        for call in ask.call_args_list
    ] == [
        ("question-a", "model-a"),
        ("question-a", "model-b"),
        ("question-a", "model-a"),
        ("question-a", "model-b"),
        ("question-b", "model-a"),
        ("question-b", "model-b"),
        ("question-b", "model-a"),
        ("question-b", "model-b"),
    ]
    assert sleeps == [0.25] * 7


def test_summary_excludes_failed_request_duration():
    """失敗の時間は記録し、成功時間の統計には含めない。"""
    failure = errors.APIError(429, {"error": {"message": "rate limited"}})
    records = [
        benchmark.RunRecord(
            model="model-a",
            question="質問|A",
            question_number=1,
            run_number=1,
            recorded_at="2026-10-26T10:00:00+09:00",
            status="成功",
            elapsed_seconds=1.0,
            input_tokens=10,
            output_tokens=5,
            usage_metadata={"prompt_token_count": 10},
            answer="回答",
            error_code=None,
            error=None,
        ),
        benchmark.RunRecord(
            model="model-a",
            question="質問|A",
            question_number=1,
            run_number=2,
            recorded_at="2026-10-26T10:00:02+09:00",
            status="失敗",
            elapsed_seconds=100.0,
            input_tokens=None,
            output_tokens=None,
            usage_metadata=None,
            answer="",
            error_code=failure.code,
            error=benchmark.api_error_message(failure.code, failure.message),
        ),
    ]

    summary = benchmark.render_summary(records)
    details = benchmark.render_run_results(records)

    assert "| 成功数 | 失敗数 |" in summary
    assert "| 1 | 1 | 1.000 | 1.000 | 1.000 | 1.000 |" in summary
    assert r"質問\|A" in summary
    assert "回分" not in summary
    assert "成功した応答のみ" in summary
    assert "| 429 |" in details
    assert "100.000" in details


def test_render_report_replaces_template_markers(tmp_path, monkeypatch):
    """既存テンプレートの各差し込み位置に結果を挿入する。"""
    template = tmp_path / "template.md"
    template.write_text(
        "<!-- SUMMARY_TABLE -->\n"
        "<!-- EXPERIMENT_CONDITIONS -->\n"
        "<!-- RUN_RESULTS -->\n"
        "<!-- RESPONSES -->\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(benchmark, "TEMPLATE_FILE", template)
    config = benchmark.ExperimentConfig(
        models=["model-a"],
        questions=["質問"],
        runs=1,
        interval_seconds=0,
        temperature=None,
    )
    records = [
        benchmark.RunRecord(
            model="model-a",
            question="質問",
            question_number=1,
            run_number=1,
            recorded_at="2026-10-26T10:00:00+09:00",
            status="成功",
            elapsed_seconds=1.25,
            input_tokens=10,
            output_tokens=5,
            usage_metadata={"prompt_token_count": 10},
            answer="回答",
            error_code=None,
            error=None,
        )
    ]

    report = benchmark.render_report(config, records)

    assert "<!-- " not in report
    assert "1.250" in report
    assert "回答" in report
    assert "usage metadata" in report


def test_main_saves_report_and_exits_with_failure_after_api_error(
    tmp_path, monkeypatch, capsys
):
    """API失敗の内容をレポートへ保存してから失敗終了する。"""
    template = tmp_path / "template.md"
    template.write_text(
        "<!-- SUMMARY_TABLE -->\n"
        "<!-- EXPERIMENT_CONDITIONS -->\n"
        "<!-- RUN_RESULTS -->\n"
        "<!-- RESPONSES -->\n",
        encoding="utf-8",
    )
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(benchmark, "TEMPLATE_FILE", template)
    monkeypatch.setattr(benchmark, "REPORT_DIR", report_dir)
    monkeypatch.setattr(benchmark, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(
        benchmark.genai,
        "Client",
        Mock(return_value=SimpleNamespace()),
    )
    api_error = errors.APIError(429, {"error": {"message": "rate limited"}})
    monkeypatch.setattr(
        benchmark,
        "ask_with_metrics",
        Mock(return_value=_result(api_error=api_error)),
    )
    monkeypatch.setattr(benchmark.time, "sleep", lambda _: None)

    with pytest.raises(SystemExit) as exit_info:
        benchmark.main(
            ["model-a", "--question", "質問", "--runs", "1", "--interval", "0"]
        )

    assert exit_info.value.code == 1
    reports = list(report_dir.glob("*.md"))
    assert len(reports) == 1
    report = reports[0].read_text(encoding="utf-8")
    assert "| 429 |" in report
    assert "1.000" in report
    assert "レート制限" in report
    capsys.readouterr()


def test_main_rejects_invalid_config_before_creating_client(monkeypatch):
    """入力条件が不正ならAPIクライアントを作る前に終了する。"""
    client = Mock()
    monkeypatch.setattr(benchmark.genai, "Client", client)

    with pytest.raises(SystemExit) as exit_info:
        benchmark.main(["--runs", "0"])

    assert exit_info.value.code == 2
    client.assert_not_called()
