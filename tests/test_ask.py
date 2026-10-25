# CLI引数をテスト中に差し替えるために使う。
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types

import app.ask as ask_module


# ask()の外部依存をテスト用に差し替え、質問を実際のGemini APIへ送らないようにする補助関数。
def _patch_client(monkeypatch, response):
    # Mock(return_value=値) は、呼び出すとその値を返す偽物の関数を作る。
    generate_content = Mock(return_value=response)
    count_tokens = Mock(return_value=SimpleNamespace(total_tokens=0))

    # SimpleNamespace(名前=値) は、受け取ったキーワード引数を同名の属性として持つオブジェクトを作る。
    # 内側で models 属性を作り、その中に generate_content 属性を設定する。
    # そのため client.models.generate_content とたどると、上で作ったMockに到達する。
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=generate_content,
            count_tokens=count_tokens,
        )
    )

    # app.ask.ask() の `genai.Client(api_key=get_api_key())` に対応する差し替え。
    # get_api_key() は引数なしなので、lambdaも引数なしでテスト用キーを返す。
    # genai.Client(...) は偽クライアントを返すMockに置き換え、実際のAPI通信を防ぐ。
    # monkeypatch.setattr(対象, "属性名", 置き換える値) は、テスト終了時に元へ自動で戻る。
    monkeypatch.setattr(ask_module, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(ask_module.genai, "Client", Mock(return_value=client))

    # ask()が使う生成APIとトークン計数APIのMockを返し、呼び出しを検証できるようにする。
    return generate_content, count_tokens


def test_ask_prints_input_and_output_token_counts(monkeypatch, capsys):
    """利用量がある応答では、入力・出力のトークン数が表示される。"""
    # ask() がGeminiから受け取る応答の代わりに、テスト用の応答を作る。
    # GenerateContentResponseUsageMetadataは、Gemini SDKが利用量情報用に定義しているデータ型。
    # prompt_token_countは入力、candidates_token_countは生成された回答のトークン数を表す。
    # SimpleNamespaceで回答本文(text)と利用量(usage_metadata)をひとまとめにし、
    # ask()から response.text / response.usage_metadata と読める形にする。
    response = SimpleNamespace(
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=12,
            candidates_token_count=8,
        ),
        text="回答",
    )
    # 補助関数が偽クライアントを設定し、呼び出しを検証するためのMockを返す。
    generate_content, count_tokens = _patch_client(monkeypatch, response)

    assert ask_module.ask("質問") == "回答"
    # モデル名と質問文を指定して、生成処理が1回呼ばれたことを確認する。
    generate_content.assert_called_once_with(model=ask_module.MODEL, contents="質問")
    # capsysはpytestの標準出力・標準エラーを捕まえるfixture名（capture system）。
    # 公式ドキュメントでは略称の展開ではなく、出力を捕捉する機能として説明されている。
    # readouterr().outで捕まえた標準出力を読み、入力12・出力8と表示されたことを確認する。
    assert "[トークン] 履歴: 0 / 入力全体: 12 / 出力: 8" in capsys.readouterr().out
    count_tokens.assert_not_called()


def test_ask_reports_unavailable_token_counts(monkeypatch, capsys):
    """利用量メタデータがない応答では、トークン数を「不明」と表示する。"""
    # 利用量情報がない応答を再現し、「不明」と表示されることを確かめる。
    # text属性は通常の応答と同様に残し、usage_metadataだけをNoneにする。
    response = SimpleNamespace(usage_metadata=None, text="回答")
    # 利用量がない応答でも、同じ偽クライアントでAPI通信なしにテストする。
    generate_content, count_tokens = _patch_client(monkeypatch, response)

    assert ask_module.ask("質問") == "回答"
    generate_content.assert_called_once_with(model=ask_module.MODEL, contents="質問")
    assert "[トークン] 履歴: 0 / 入力全体: 不明 / 出力: 不明" in capsys.readouterr().out
    count_tokens.assert_not_called()


def test_ask_passes_temperature_in_generate_content_config(monkeypatch):
    """temperature が指定された場合、GenerateContentConfig 経由で SDK に渡す。"""
    # 実API応答の代わりを用意し、通信しない偽クライアントを設定する。
    response = SimpleNamespace(usage_metadata=None, text="回答")
    generate_content, _ = _patch_client(monkeypatch, response)

    # 指定温度でも回答文を返すことを確認する。
    assert ask_module.ask("質問", temperature=0.7) == "回答"

    # SDKが1回だけ呼ばれ、モデル・質問・温度設定が正しく渡ることを確認する。
    generate_content.assert_called_once()
    call = generate_content.call_args
    assert call.kwargs["model"] == ask_module.MODEL
    assert call.kwargs["contents"] == "質問"
    assert isinstance(call.kwargs["config"], types.GenerateContentConfig)
    assert call.kwargs["config"].temperature == 0.7


def test_main_passes_temperature_option_to_ask(monkeypatch, capsys):
    """CLI の --temperature が ask() に渡され、設定値が表示される。"""
    # API通信なしでCLIの呼び出しを検証するため、ask()を偽物へ置き換える。
    ask = Mock(return_value="回答")
    monkeypatch.setattr(ask_module, "ask", ask)
    # main()が受け取るコマンドライン引数をテスト用の値にする。
    monkeypatch.setattr(sys, "argv", ["app.ask", "--temperature", "0.7", "質問"])

    # 模擬した引数でCLIの入口を実行する。
    ask_module.main()

    # CLIから質問と数値化した温度が渡され、温度も画面に表示されることを確認する。
    ask.assert_called_once_with("質問", temperature=0.7)
    output = capsys.readouterr().out
    assert "[temperature] 0.7" in output
    assert "[mode] 単発質問（会話履歴なし）" in output


def test_interactive_mode_sends_previous_turns(monkeypatch, capsys):
    """対話モードの後続質問では、前の質問と回答もモデルへ渡す。"""
    # pytestが引数として渡すmonkeypatchを使い、API通信の代わりになる偽クライアントを設定する。
    generate_content, count_tokens = _patch_client(monkeypatch, None)
    # 2回目の質問前に数える履歴トークン数を、テスト用の値にする。
    count_tokens.return_value = SimpleNamespace(total_tokens=11)
    # side_effectに回答のリストを設定すると、API呼び出しごとに先頭から1件ずつ返す。
    generate_content.side_effect = [
        SimpleNamespace(
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=6,
                candidates_token_count=2,
            ),
            text="最初の回答",
        ),
        SimpleNamespace(
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=20,
                candidates_token_count=4,
            ),
            text="続きの回答",
        ),
    ]
    # 対話で入力する2つの質問と終了コマンドを、入力される順に並べる。
    questions = iter(["最初の質問", "続きの質問", "/exit"])
    # setattr("差し替える場所", "新しい動き")と読み、Python標準のinput()を置き換える。
    # lambda _ は「表示文を1つ受け取る関数」で、その文は使わずnext(questions)の値を返す。
    # つまり app.ask の input("質問> ") が呼ばれるたび、questionsから次の質問が1つ返る。
    monkeypatch.setattr("builtins.input", lambda _: next(questions))
    # main()がコマンドラインから読む値を指定し、対話モードとtemperatureを選ぶ。
    monkeypatch.setattr(sys, "argv", ["app.ask", "--temperature", "0.6"])

    # ここまで用意した入力と偽APIを使って、実際のCLI処理を実行する。
    ask_module.main()

    # 2つの質問でAPIが2回呼ばれ、終了コマンドでは呼ばれないことを確認する。
    assert generate_content.call_count == 2
    # 1回目は履歴がないため、質問文だけがAPIへ渡る。
    first_contents = generate_content.call_args_list[0].kwargs["contents"]
    assert first_contents == "最初の質問"

    # 2回目のAPI呼び出しに渡された会話内容を取り出す。
    second_contents = generate_content.call_args_list[1].kwargs["contents"]
    # 発話者が「利用者、モデル、利用者」の順で記録されていることを確認する。
    assert [content.role for content in second_contents] == [
        "user",
        "model",
        "user",
    ]
    # 発話本文も「最初の質問、最初の回答、続きの質問」の順で渡ることを確認する。
    assert [
        content.parts[0].text for content in second_contents
    ] == ["最初の質問", "最初の回答", "続きの質問"]
    # 履歴の計数APIには、今回の質問を除いた過去の質問と回答だけを渡す。
    count_tokens.assert_called_once()
    count_call = count_tokens.call_args
    assert count_call.kwargs["model"] == ask_module.MODEL
    assert [content.parts[0].text for content in count_call.kwargs["contents"]] == [
        "最初の質問",
        "最初の回答",
    ]
    # 2回ともCLIで指定したtemperatureがAPIへ渡ることを確認する。
    for call in generate_content.call_args_list:
        assert call.kwargs["config"].temperature == 0.6

    # capsysから実行中の画面出力を取り出し、2つの回答が表示されたことを確認する。
    output = capsys.readouterr().out
    assert "最初の回答" in output
    assert "続きの回答" in output
    assert "[トークン] 履歴: 11 / 入力全体: 20 / 出力: 4" in output
    assert "[mode] 対話" in output


# pytest.mark.parametrize("関数の引数名", [値1, 値2])を付けると、
# pytestはテスト関数を値ごとに実行し、その値を同じ名前の引数へ渡す。
# ここではcommandに"/exit"と"/quit"が順番に渡り、同じ終了処理を2通り試す。
@pytest.mark.parametrize("command", ["/exit", "/quit"])
def test_interactive_mode_exits_on_command(monkeypatch, command):
    """終了コマンドはモデルを呼び出さず対話を終了する。"""
    # テスト関数の引数monkeypatchには、pytestが一時的な差し替え機能を渡す。
    # 補助関数でGeminiクライアントを偽物にし、API呼び出しを記録するMockを受け取る。
    generate_content, count_tokens = _patch_client(monkeypatch, None)
    # setattr("差し替える場所", "差し替え後の値")で、Python組み込みのinput()を置き換える。
    # lambda _は引数を1つ受け取る関数で、_にはinput("質問> ")の"質問> "が渡る。
    # 引数_は使わずcommandを返すので、対話処理が開始直後に"/exit"または"/quit"を受け取る。
    # 例えばcommandが"/exit"の回では、input("質問> ")の結果が"/exit"になる。
    monkeypatch.setattr("builtins.input", lambda _: command)
    # main()が読むコマンドライン引数を置き換え、質問文なしの対話モードで起動する。
    monkeypatch.setattr(sys, "argv", ["app.ask"])

    # 差し替えた入力でCLIを実行し、終了コマンドを受け取る一連の処理を確かめる。
    ask_module.main()

    # 終了コマンドでループを抜けるため、質問を送るAPI関数が一度も呼ばれないことを確認する。
    generate_content.assert_not_called()
    count_tokens.assert_not_called()
