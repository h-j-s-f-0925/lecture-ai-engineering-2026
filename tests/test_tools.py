"""ツールのテスト（LLMもAPIキーも使わない）。"""

import json
import re
from datetime import datetime

from app import tools


def test_glossary_ids_are_unique_and_related_links_exist():
    terms = tools.load_glossary()
    ids = [t["id"] for t in terms]
    assert len(ids) == len(set(ids))
    for t in terms:
        for r in t["related"]:
            assert r in ids, f"{t['id']} の related に存在しない id: {r}"


def test_search_finds_term_by_name_and_alias():
    for query in ["LoRA", "lora", "Low-Rank Adaptation"]:
        hits = json.loads(tools.search_glossary(query))
        assert hits[0]["term"] == "LoRA", query


def test_search_finds_course_specific_term():
    hits = json.loads(tools.search_glossary("lecNN-start"))
    assert hits[0]["term"] == "lecNN-start タグ"


def test_search_limits_number_of_results():
    hits = json.loads(tools.search_glossary("エージェント"))
    assert 1 <= len(hits) <= tools.MAX_RESULTS


def test_search_reports_not_found():
    assert "見つかりませんでした" in tools.search_glossary("存在しない用語xyz")


def test_lecture_summary():
    assert "エージェント" in tools.get_lecture_summary(3)
    assert "まだありません" in tools.get_lecture_summary(99)


def test_make_quiz_selects_a_term_from_requested_lecture(monkeypatch):
    terms = [term for term in tools.load_glossary() if term["lecture"] == 2]
    monkeypatch.setattr(tools.random, "choice", lambda choices: choices[0])

    quiz = json.loads(tools.make_quiz(2))

    assert quiz == {
        "question": f"「{terms[0]['term']}」の意味は？",
        "answer": terms[0]["definition"],
    }


def test_make_quiz_reports_when_lecture_has_no_terms():
    assert "第0回の用語が見つかりません" in tools.make_quiz(0)


def test_save_learning_log_uses_title_for_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")

    result = tools.save_learning_log("# 今日の学び\n内容", title="今日の学び")

    saved_files = list((tmp_path / "learning_log").glob("*.md"))
    assert len(saved_files) == 1
    assert saved_files[0].read_text(encoding="utf-8") == "# 今日の学び\n内容\n"
    assert re.fullmatch(r"\d{8}_\d{4}_今日の学び\.md", saved_files[0].name)
    assert result.startswith("学習記録を ")


def test_save_learning_log_uses_a_descriptive_title(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")

    tools.save_learning_log(
        "# 学習記録\n\n## 学んだこと\n- エージェント / ツール: 基本",
        title="エージェントとツールの基本",
    )

    saved_files = list((tmp_path / "learning_log").glob("*.md"))
    assert len(saved_files) == 1
    assert re.fullmatch(
        r"\d{8}_\d{4}_エージェントとツールの基本\.md",
        saved_files[0].name,
    )


def test_save_learning_log_removes_path_and_filename_separators(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", tmp_path / "learning_log")

    tools.save_learning_log("本文", title="../LoRA: QLoRA?")

    saved_files = list((tmp_path / "learning_log").glob("*.md"))
    assert len(saved_files) == 1
    assert re.fullmatch(r"\d{8}_\d{4}_LoRA-QLoRA\.md", saved_files[0].name)


def test_save_learning_log_does_not_overwrite_existing_file(tmp_path, monkeypatch):
    class FixedDateTime:
        @classmethod
        def now(cls):
            return datetime(2026, 11, 7, 2, 0, 0, 123456)

    log_dir = tmp_path / "learning_log"
    log_dir.mkdir()
    existing_file = log_dir / "20261107_0200_新しい記録.md"
    existing_file.write_text("既存の記録\n", encoding="utf-8")
    monkeypatch.setattr(tools, "LEARNING_LOG_DIR", log_dir)
    monkeypatch.setattr(tools, "datetime", FixedDateTime)

    try:
        tools.save_learning_log("新しい記録", title="新しい記録")
    except FileExistsError as error:
        assert "上書きしない" in str(error)
    else:
        raise AssertionError("同名ファイルを上書きせずエラーにする必要があります")

    assert existing_file.read_text(encoding="utf-8") == "既存の記録\n"


def test_default_question_of_lecture1_is_answerable_from_glossary():
    """第1回の既定の質問（app.ask）は、第3回のエージェントが用語集で正しく答えられること。"""
    from app.ask import DEFAULT_QUESTION

    assert "3レベル" in DEFAULT_QUESTION
    hits = json.loads(tools.search_glossary("3レベル"))
    assert hits[0]["term"] == "宿題の3レベル"
