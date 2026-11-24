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

- 取り組んだレベル：基礎 / 実装 / 発展
- やったこと：
- 結果：
- 気づき・疑問：
