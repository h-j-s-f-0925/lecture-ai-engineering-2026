"""エージェントの配線テスト。

TestModel は実際のLLMを呼ばない偽モデルで、登録されたツールを全部呼んでから
ダミーの回答を返す。APIキーも利用枠も使わずに、
「ツールが登録され、呼ばれ、結果がモデルに戻るか」を確かめられる。
"""

import pytest
from pydantic_ai import DeferredToolRequests, ToolDenied
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent, request_tool_approvals

BASE_TOOLS = {"search_glossary", "get_lecture_summary", "make_quiz", "save_learning_log"}


def _parts(result, kind):
    return [p for m in result.all_messages() for p in m.parts if isinstance(p, kind)]


def test_base_tools_are_registered_and_called():
    model = TestModel()
    with agent.override(model=model):
        result = agent.run_sync("LoRAとは？")

    offered = {t.name for t in model.last_model_request_parameters.function_tools}
    assert BASE_TOOLS <= offered  # 演習でツールを足しても壊れないよう「含む」で判定

    called = {p.tool_name for p in _parts(result, ToolCallPart)}
    assert BASE_TOOLS <= called
    # 承認が必要なツール（requires_approval=True）は、実行されずに承認待ちになるので戻り値が無い
    waiting = len(result.output.approvals) if isinstance(result.output, DeferredToolRequests) else 0
    assert len(_parts(result, ToolReturnPart)) + waiting == len(_parts(result, ToolCallPart))
    assert result.output


def test_glossary_result_reaches_the_model():
    model = TestModel(call_tools=["search_glossary"])
    with agent.override(model=model):
        result = agent.run_sync("RAGとは？")
    returns = _parts(result, ToolReturnPart)
    assert returns and returns[0].tool_name == "search_glossary"


def test_save_learning_log_waits_for_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")
    model = TestModel(call_tools=["save_learning_log"])

    with agent.override(model=model):
        result = agent.run_sync("学習記録を保存して")

    assert isinstance(result.output, DeferredToolRequests)
    assert [call.tool_name for call in result.output.approvals] == ["save_learning_log"]
    assert not (tmp_path / "learning_log").exists()


def test_approved_learning_log_is_saved(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    first = agent.run_sync(
        "学習記録を保存して",
        model=TestModel(call_tools=["save_learning_log"]),
    )
    assert isinstance(first.output, DeferredToolRequests)

    # monkeypatchで標準のinput()を置き換え、テスト中は利用者がyesと答えた状態にする
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    deferred_results = request_tool_approvals(first.output)
    second = agent.run_sync(
        None,
        message_history=first.all_messages(),
        deferred_tool_results=deferred_results,
        model=TestModel(call_tools=[]),
    )

    saved_files = list(log_dir.glob("*.md"))
    assert len(saved_files) == 1
    assert saved_files[0].read_text(encoding="utf-8") == "a\n"
    assert "保存しました" in second.output


def test_rejected_learning_log_is_not_saved(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    first = agent.run_sync(
        "学習記録を保存して",
        model=TestModel(call_tools=["save_learning_log"]),
    )
    assert isinstance(first.output, DeferredToolRequests)

    monkeypatch.setattr("builtins.input", lambda _: "n")
    deferred_results = request_tool_approvals(first.output)
    assert isinstance(next(iter(deferred_results.approvals.values())), ToolDenied)
    second = agent.run_sync(
        None,
        message_history=first.all_messages(),
        deferred_tool_results=deferred_results,
        model=TestModel(call_tools=[]),
    )

    assert not log_dir.exists()
    assert "拒否" in second.output


def test_interrupted_approval_does_not_save(tmp_path, monkeypatch):
    log_dir = tmp_path / "learning_log"
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    first = agent.run_sync(
        "学習記録を保存して",
        model=TestModel(call_tools=["save_learning_log"]),
    )
    assert isinstance(first.output, DeferredToolRequests)

    def interrupt_input(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", interrupt_input)
    with pytest.raises(SystemExit) as error:
        request_tool_approvals(first.output)

    assert error.value.code == 1
    assert not log_dir.exists()
