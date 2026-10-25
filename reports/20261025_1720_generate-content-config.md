# `generate_content` の `config` 引数と temperature

## 結論

`google-genai` の `client.models.generate_content()` は `config` を受け取り、生成時の設定を指定できます。temperature は `types.GenerateContentConfig` のフィールドなので、たとえば `temperature=0.2` を渡せます。現在の `app.ask.ask()` は `config` を渡していないため、温度を比較するには呼び出しへ明示的に追加する必要があります。

## 調査対象

- リポジトリの依存バージョン: `google-genai==2.31.0`（`pyproject.toml` / `uv.lock`）
- ローカル SDK: `.venv/lib/python3.12/site-packages/google/genai/`
- 対象コード: `app/ask.py` の `client.models.generate_content(...)`

## `config` の型と渡し方

SDK の同期メソッドは、概ね次のシグネチャです。

```python
generate_content(
    *,
    model: str,
    contents: ...,
    config: GenerateContentConfig | GenerateContentConfigDict | None = None,
)
```

つまり `config` は省略可能で、型付きの `types.GenerateContentConfig` または辞書のどちらでも指定できます。読みやすさと型チェックのため、型付きの設定を使う方法が分かりやすいです。

```python
from google.genai import types

response = client.models.generate_content(
    model=MODEL,
    contents=question,
    config=types.GenerateContentConfig(temperature=0.2),
)
```

辞書で指定する場合は、次の形です。

```python
response = client.models.generate_content(
    model=MODEL,
    contents=question,
    config={"temperature": 0.2},
)
```

## temperature の意味と注意点

- temperature は、トークン選択のランダムさを調整します。低くすると回答がより予測しやすくなり、高くすると多様になりやすい設定です。
- 省略時はモデル側の既定値が使われます。既定値や利用できる値の範囲・対応状況はモデルによって異なるため、実験で使うモデルの公式仕様も確認してください。
- temperature を変えても、毎回必ず回答が変わるわけではありません。反対に、同じ設定でも生成結果に揺らぎが出る場合があります。
- 比較ではモデル、質問文、ほかの設定を固定し、temperature だけを変えて各条件を複数回実行してください。値と実行回数を記録し、少数回の観察からモデル全体の性能を断定しないようにします。
- temperature と `top_p` はどちらも生成の多様さに関係します。比較の目的が temperature なら、まず `top_p` などを同時に変えず、条件を一つずつ操作します。

## このリポジトリでの次の手順

現状の `app.ask.ask(question)` は `model` と `contents` のみを渡しており、temperature を引数や環境変数から指定する機能はありません。temperature の比較を `app.ask` で行うには、temperature を設定できるように呼び出しを拡張し、実験レポートへ使用モデル・質問文・temperature・各回答を記録します。外部 API を実際に呼び出す実験は、API キーの設定と利用料金・レート制限を確認してから実行してください。

## 参考資料

- [Google Gen AI Python SDK ドキュメント — Generate Content / System Instructions and Other Configs](https://googleapis.github.io/python-genai/)
- [Google Gen AI Python SDK の型定義 — `GenerateContentConfig`](https://github.com/googleapis/python-genai/blob/main/google/genai/types.py)
- リポジトリ内の固定依存: `pyproject.toml` と `uv.lock` の `google-genai==2.31.0`
