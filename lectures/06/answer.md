# 第6回 解答

## 演習

<!-- [tool call] の行は、表示された行をそのまま貼り付けてください。終わらなかった STEP は、空欄のままでかまいません。 -->

- STEP 1 のツールの名前：glossary_search_glossary
- STEP 2 の [tool call]：glossary_search_glossary({'query': '3レベル'})
- STEP 3 の [tool call]：fetch_fetch({'url': 'https://modelcontextprotocol.io/'})
- STEP 4 の [tool call]：aws_aws___search_documentation({'search_phrase': 'Amazon S3 versioning overview'})
- 気づき・疑問：
  - `app.agent` と `app.mcp_agent` のツール一覧は、どちらも名前・説明文・引数が同じ形で並んでいた。MCP サーバーのツールには「サーバー名_」が付く。aws のツールは、サーバー自体が `aws___` を付けて公開しているので、`aws_aws___search_documentation` のように二重になっていた。
  - fetch_fetch の説明文は英語で、「インターネットにアクセスできるようになった」という、モデルへの指示のような文が入っていた。サーバーの作者が書いた説明文がそのままモデルに渡るので、足す前に提供元を確かめる理由が分かった。
  - STEP 3 の同じ質問を2回実行すると、1回目は fetch_fetch のあとに glossary_search_glossary も呼ばれた（モデル応答3回）。2回目は fetch_fetch だけだった（モデル応答2回）。同じ質問でも、どのツールを呼ぶかは実行ごとに変わることがある。
  - aws を足したあと、「MCP サーバーに接続できませんでした」や `httpx2.ReadError` のトレースバックが出たり出なかったりした。curl で調べると、手元の PC から AWS へ IPv6 で接続したときだけ、暗号化の準備（TLS）の途中で接続を切られていた（IPv4 は15回中15回成功、IPv6 は15回中9回失敗）。`app/mcp_agent.py` で URL のサーバーへの接続を IPv4 に固定し、`httpx2.HTTPError` も受け止めるようにしたところ、`--list-tools` は10回中10回成功した。同じ PC の開発コンテナ（Linux）では、この修正が無くても成功した。コンテナには IPv6 で外へ出る経路が無く、最初から IPv4 で接続するためだった。
  - 手元の Windows（Git Bash）で実行したので、`uv run --env-file .env` を付けないと `GEMINI_API_KEY` が見つからなかった。「モデルが混み合っています（503）」も出たが、Google 側の一時的な混雑で、少し待てば通った。

## 宿題

<!-- 基礎・実装・発展のどれか1つに取り組めば完了です。 -->

- 取り組んだレベル：基礎
- やったこと：
  - `app/mcp_server.py` に `server.tool()(tools.get_lecture_summary)` を追加し、既存の講義の要点を取得する関数を MCP ツールとして公開した。
  - エージェント側のコードや接続設定は変更せず、次のコマンドでツール一覧を表示した。

    ```bash
    # 有料用キーを選択し、.env を読み込んでツール一覧を表示する
    AIE_API_TIER=paid uv run --env-file .env python -m app.mcp_agent --list-tools
    ```

- 結果：
  - 「モデルに見えているツール: 8 個」と表示され、既存の `glossary_search_glossary` に加え、`glossary_get_lecture_summary` が一覧に表示された。
  - 追加したツールの説明文は「指定した回（1始まりの整数）の講義の要点を返す。」で、引数 `lecture` の型は `integer`（整数）と表示された。
  - 一覧に表示された引数は次のとおり。

    ```json
    {"lecture": {"title": "Lecture", "type": "integer"}}
    ```

  - `glossary` と `fetch` はコマンドで起動し、`aws` は URL に接続するという案内が表示された。
  - 実行途中で仮想環境の再作成と依存パッケージのインストールが行われた。ハードリンクで配置できずファイルのコピーへ切り替える警告も出たが、その後、ツール一覧は表示された。
  - `uv run pytest -q` を実行し、`59 passed in 5.97s` と表示された。既存テスト59件がすべて成功した。
  - `AIE_API_TIER=paid uv run --env-file .env python -m app.mcp_agent --trace "第2回では何を学びますか？"` を実行した。次の記録から、追加したツールに整数の `2` が渡され、第2回の要点が戻ったことを確認できた。

    ```text
    [tool call]   glossary_get_lecture_summary({'lecture': 2})
    [tool return] glossary_get_lecture_summary -> # 第2回 ファインチューニングとLoRA
    ```

  - 最終回答では、第2回の学習内容として、事前学習と追加学習の違い、学習方法、演習などが説明された。実行時のモデルは `gemini-3.5-flash-lite` で、利用状況は次のとおりだった。

    ```text
    [usage] 入力 5,926 tokens / 出力 297 tokens / モデル応答 2 回
    ```
- 気づき・疑問：
  - サーバー側で既存の関数を公開すると、エージェント側を変更しなくても、ツール名・説明文・引数が一覧に反映されることを確認できた。
  - 開発コンテナ内で実行するたびに、作業フォルダーの `.venv` が作成されるのが気になった。コンテナ内の `/home/vscode/.venv` を使う設定なのに、なぜ別の場所に仮想環境が作られるのか。既存の環境を再利用できないのか、サーバー起動時に設定が引き継がれているのかを確認したい。
  - `server.tool()(tools.get_lecture_summary)` を追加すると、サーバー起動時に「この関数をツールとして使える」と登録される。この登録の時点では、講義の要点を読む関数の処理は実行されない。`--list-tools` では、使えるツールの一覧に追加されたことを確認した。
  - その後、「第2回では何を学びますか？」と質問すると、モデルはまず「`glossary_get_lecture_summary` に `lecture=2` を渡して呼び出す」という指示を返した。エージェントがその指示に従ってサーバーへ呼び出しを依頼すると、サーバーが関数を実行し、第2回の要点の本文を返した。ログの `[tool call]` は呼び出すツールと引数、`[tool return]` は返された本文を示している。
  - エージェントは、ツールから返された本文をモデルに渡して、もう一度応答を求めた。モデルはその本文を読んで、利用者向けの回答を返した。つまり「モデル応答2回」は、1回目がツールを呼び出す指示、2回目が質問への回答という意味であり、利用者向けの回答を2つ作ったという意味ではない。
  - 最初の実行では `GEMINI_API_KEY` が見つからないという案内が出た。その後、`AIE_API_TIER=paid` と `--env-file .env` を付けて一覧を表示でき、さらに質問への回答生成も成功した。一覧表示自体は Gemini API を呼び出さないため、回答生成の確認は別に行う必要があった。

---

- 取り組んだレベル：実装 / 発展
- やったこと：
- 結果：
- 気づき・疑問：
