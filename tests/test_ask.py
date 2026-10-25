from types import SimpleNamespace
from unittest.mock import Mock

from google.genai import types

import app.ask as ask_module


# ask()の外部依存をテスト用に差し替え、質問を実際のGemini APIへ送らないようにする補助関数。
def _patch_client(monkeypatch, response):
    # Mock(return_value=値) は、呼び出すとその値を返す偽物の関数を作る。
    generate_content = Mock(return_value=response)

    # SimpleNamespace(名前=値) は、受け取ったキーワード引数を同名の属性として持つオブジェクトを作る。
    # 内側で models 属性を作り、その中に generate_content 属性を設定する。
    # そのため client.models.generate_content とたどると、上で作ったMockに到達する。
    client = SimpleNamespace(
        models=SimpleNamespace(generate_content=generate_content)
    )

    # app.ask.ask() の `genai.Client(api_key=get_api_key())` に対応する差し替え。
    # get_api_key() は引数なしなので、lambdaも引数なしでテスト用キーを返す。
    # genai.Client(...) は偽クライアントを返すMockに置き換え、実際のAPI通信を防ぐ。
    # monkeypatch.setattr(対象, "属性名", 置き換える値) は、テスト終了時に元へ自動で戻る。
    monkeypatch.setattr(ask_module, "get_api_key", lambda: "test-key")
    monkeypatch.setattr(ask_module.genai, "Client", Mock(return_value=client))

    # app.ask.ask() 内の client.models.generate_content(...) がこのMockを呼び出す。
    # responseを返す設定にしておき、テスト側で呼び出し引数も検証できるよう返す。
    return generate_content


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
    generate_content = _patch_client(monkeypatch, response)

    assert ask_module.ask("質問") == "回答"
    # モデル名と質問文を指定して、生成処理が1回呼ばれたことを確認する。
    generate_content.assert_called_once_with(model=ask_module.MODEL, contents="質問")
    # capsysはpytestの標準出力・標準エラーを捕まえるfixture名（capture system）。
    # 公式ドキュメントでは略称の展開ではなく、出力を捕捉する機能として説明されている。
    # readouterr().outで捕まえた標準出力を読み、入力12・出力8と表示されたことを確認する。
    assert "[トークン] 入力: 12 / 出力: 8" in capsys.readouterr().out


def test_ask_reports_unavailable_token_counts(monkeypatch, capsys):
    """利用量メタデータがない応答では、トークン数を「不明」と表示する。"""
    # 利用量情報がない応答を再現し、「不明」と表示されることを確かめる。
    # text属性は通常の応答と同様に残し、usage_metadataだけをNoneにする。
    response = SimpleNamespace(usage_metadata=None, text="回答")
    # 利用量がない応答でも、同じ偽クライアントでAPI通信なしにテストする。
    generate_content = _patch_client(monkeypatch, response)

    assert ask_module.ask("質問") == "回答"
    generate_content.assert_called_once_with(model=ask_module.MODEL, contents="質問")
    assert "[トークン] 入力: 不明 / 出力: 不明" in capsys.readouterr().out
