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

- 取り組んだレベル：実装
- やったこと：
  - `app/mcp_server.py` に `server.tool()(tools.make_quiz)` を追加し、第3回で作った `make_quiz` を MCP ツールとして公開した。
  - `--list-tools` で、エージェント側を変えずに一覧が9個に増え、`glossary_make_quiz` が表示されることを確認した。説明文は `app/tools.py` の docstring のままで、引数は `{"lecture": {"title": "Lecture", "type": "integer"}}` だった。
  - 用語集の回ごとの用語数を数えると、第1回 26件、第2回 12件、第3回 13件、第4回 7件、第6回 7件で、第5回は0件だった。そこで、存在しない回（第99回）と、講義はあるが用語がない回（第5回）の2つで試した。
  - 範囲外のときの返し方を、`return`（既存の「第○回の用語が見つかりません。」）と `raise ValueError(...)`（同じ文）で比べた。文の中身をそろえ、違いが返し方だけになるようにした。

    ```bash
    # 範囲外の回を質問し、ツールの呼び出しと戻り値を表示する
    AIE_API_TIER=paid uv run --env-file .env python -m app.mcp_agent --trace "第99回のクイズを作って"
    AIE_API_TIER=paid uv run --env-file .env python -m app.mcp_agent --trace "第5回のクイズを作って"
    ```

- 結果：
  - `return` のとき、第99回は次のとおりで、返した文がそのままモデルに渡った。

    ```text
    [tool call]   glossary_make_quiz({'lecture': 99})
    [tool return] glossary_make_quiz -> 第99回の用語が見つかりません。…
    [usage] 入力 5,602 tokens / 出力 50 tokens / モデル応答 2 回
    ```

    最終回答は「第99回は存在しないか、用語集に登録されていません」だった。
  - `return` のとき、第5回は `[tool return] glossary_make_quiz -> 第5回の用語が見つかりません。…`、モデル応答2回だった。最終回答は「他の回（例: 第1回〜第4回など）の確認問題をご希望でしたら…」で、用語がある第6回が抜けていた。
  - `raise` のとき、第99回は次のとおりで、用意した文はモデルに渡らず、決まった文に置き換わった。

    ```text
    [tool call]   glossary_make_quiz({'lecture': 99})
    [tool error]  glossary_make_quiz -> Error executing tool make_quiz
    [usage] 入力 5,604 tokens / 出力 84 tokens / モデル応答 2 回
    ```

    画面にはサーバー側のトレースバック（エラーが起きたときに、どの関数がどの順で呼ばれ、どのファイルの何行目で止まったかを表示する記録）が表示され、最後は `UnexpectedToolError: Error executing tool make_quiz` だった。最終回答は「第1回〜第N回などを指定していただければ…」と、`return` のときよりあいまいになった。
  - どちらの返し方でも、モデルは呼び直さず、`[tool call]` 1回、モデル応答2回で答えた。

  | | `return` | `raise ValueError` |
  |---|---|---|
  | トレースの行 | `[tool return]` | `[tool error]` |
  | モデルに渡った文 | 書いた文そのまま | `Error executing tool make_quiz` だけ |
  | 呼び直し | なし | なし |
  | 最終回答 | 第99回が見つからない理由を案内した | 「第1回〜第N回」とあいまいに案内した |

- 気づき・疑問：
  - トレースバックの `mcp/server/mcpserver/tools/base.py:211-213` で、MCP サーバーはツールの中の普通の例外を `UnexpectedToolError`（予期しないクラッシュ）に変えていた。元の例外の文はサーバー側のログにだけ残り、モデルには渡らない。利用者やモデルに理由を伝えたい範囲外の引数は、`return` で返す方が合っていると分かった。
  - `return` でも、ツールの文に書かれていないことは、モデルが推測で補っていた。第5回の回答の「第1回〜第4回など」は、作れる回の一覧が文に無かったためだと考えられる。作れる回の一覧を文に入れると回答が正しくなるかは、まだ試していない。
  - 同じ「見つかりません」でも、第99回は講義が無い回、第5回は講義はあるが用語が無い回で、意味が違う。今の文では、この違いがモデルに伝わらない。
  - トレースバックの `base.py:210` に `raise ToolError(...)` という別の行があった。SDK の `ToolError` で `raise` すると、文がモデルに渡るのかを確かめたい。

---

- 取り組んだレベル：発展
- やったこと：
  - 自分が使っている Claude Code（クロード・コード、Anthropic のコーディング用エージェント）2.1.332 を選び、公式ドキュメントで MCP サーバーの設定方法を調べた。調べた日付は 2026-11-26 である。
  - 参照した公式ドキュメントは、次の2つである。
    - Anthropic「Connect Claude Code to tools via MCP」 https://code.claude.com/docs/en/mcp
    - Anthropic「Configure permissions」 https://code.claude.com/docs/en/permissions
  - problem.md の4項目（設定を書く場所、コマンドで起動する書き方、URL で接続する書き方、有効になる範囲）を調べ、`app/mcp_servers.json` と比べた。
  - ドキュメントの記述を確かめるため、演習の `fetch` と `aws` をそのまま書いた `.mcp.json` を一時フォルダーに置き、`claude mcp list`（登録されたサーバーと接続の状態を表示するコマンド）で、Claude Code が設定をどう読むかを確かめた。
  - 比べるために、ほかの7つのツールの公式ドキュメントも調べた。結果は「気づき・疑問」の最後の表にまとめた。
- 結果：
  - 演習の設定との違いは、主に2つだった。1つは、URL に接続するサーバーに `"type": "http"` を必ず書くことである。もう1つは、設定を置く場所が3つあり、有効になる範囲を選べることである。
  - 前提として、MCP サーバーへのつなぎ方は2種類ある。
    - 1つ目は、コマンドで起動する方式（stdio）である。自分のパソコンでサーバーのプログラムを起動し、そのプログラムの入力と出力（標準入力と標準出力）を通してやりとりする。演習の `glossary` と `fetch` がこの方式である。
    - 2つ目は、URL に接続する方式（HTTP）である。どこかですでに動いているサーバーに、インターネット越しに接続する。演習の `aws` がこの方式である。
  - 4項目を演習の設定と比べると、次のとおりだった。

    | 調べること | 演習（`app/mcp_servers.json`） | Claude Code |
    |---|---|---|
    | 設定を書く場所 | `app/mcp_servers.json` の1つだけ | プロジェクト直下の `.mcp.json`、または `~/.claude.json`。`claude mcp add` でも登録できる |
    | コマンドで起動する書き方 | `command`、`args` | 同じ `command`、`args`（`"type": "stdio"` は省略できる） |
    | URL で接続する書き方 | `url` だけ | `"type": "http"` と `url`。`type` は必ず書く |
    | 有効になる範囲 | このリポジトリだけ | local（自分だけ・そのプロジェクトだけ）、project（`.mcp.json` でチームと共有）、user（自分の全プロジェクト）の3つ |

  - 設定を書く場所と有効になる範囲：Claude Code では、3つの範囲（スコープ）から選んで設定を置ける。
    - project スコープは `.mcp.json` に、local と user スコープは `~/.claude.json` に保存される（[MCP installation scopes](https://code.claude.com/docs/en/mcp#mcp-installation-scopes)）。
    - 同じ名前のサーバーが複数のスコープにあるときは、local、project、user の順に優先される（[Scope hierarchy and precedence](https://code.claude.com/docs/en/mcp#scope-hierarchy-and-precedence)）。
    - 優先された方の設定だけが使われ、スコープの間で中身は混ぜない。同じ節に "fields are not merged across scopes"（スコープの間で項目は混ぜない）とある。
  - コマンドで起動する書き方：キーの名前（`command`、`args`）は演習と同じだった。`"type": "stdio"` は書いても書かなくてもよい。
  - URL で接続する書き方：ここがいちばん大きな違いだった。演習の `"aws": {"url": "..."}` のように `type` を書かないと、Claude Code ではエラーになる。
    - 理由は、どちらの方式かを決めるルールが違うからである。
      - 演習のエージェントは、`url` が書いてあれば、URL に接続する方式と決める。
      - Claude Code は、`type` の値で決め、`type` が書いていなければ、コマンドで起動する方式と決める。
      - そのため、Claude Code は `aws` をコマンドで起動する方式とみなすが、起動するコマンドが書いていないので、正しい設定として扱えない（推論。公式ドキュメントに書かれているのは、次の根拠の内容だけである）。
    - 根拠：公式ドキュメントは、"A JSON entry that has a `url` but no `type` is a configuration error, because Claude Code reads an entry with no `type` as a stdio server."（`url` はあるが `type` が無い設定はエラーになる。Claude Code は、`type` が無い設定を、コマンドで起動する方式のサーバーとして読むため）と書いている。
  - 実際に演習の書き方のまま読み込ませると、`aws` は読み込まれず、`type` を足すように警告が出た。

    ```text
    $ claude mcp list
    fetch: uvx mcp-server-fetch==2026.11.11 --no-readability-js - ⏸ Pending approval (run `claude` to approve)

    MCP config diagnostics ⚠
    [Has warnings] Project config (shared via .mcp.json)
     └ [Warning] [aws] mcpServers.aws: Skipped — MCP server "aws" has a "url" but no "type"; add "type": "http" (or "sse" / "ws") to this entry
    ```

  - `aws` を次のように直すと、警告が消え、URL に接続する方式（HTTP）のサーバーとして認識された。

    ```json
    "aws": {"type": "http", "url": "https://knowledge-mcp.global.api.aws"}
    ```

    ```text
    $ claude mcp list
    fetch: uvx mcp-server-fetch==2026.11.11 --no-readability-js - ⏸ Pending approval (run `claude` to approve)
    aws: https://knowledge-mcp.global.api.aws (HTTP) - ⏸ Pending approval (run `claude` to approve)
    ```

  - 上の `claude mcp list` の出力では、`fetch` と `aws` の両方の行の末尾に `Pending approval`（承認待ち）と表示された。これは、`.mcp.json` に書いた2つのサーバーを、まだ「使ってよい」と許可していないという意味である。
    - Claude Code は、セキュリティ上の理由で、`.mcp.json` のサーバーを許可なしには使わない。`claude` を起動すると、使ってよいかの確認が出る。今回は `claude mcp list` で一覧を見ただけなので、承認待ちのままだった。
    - 根拠：公式ドキュメントの [Project scope](https://code.claude.com/docs/en/mcp#project-scope) の節は、"For security reasons, Claude Code prompts for approval in interactive sessions before using project-scoped servers from `.mcp.json` files."（セキュリティ上の理由で、`claude` を起動して会話するときは、`.mcp.json` のサーバーを使う前に許可を求める）と書いている。
- 気づき・疑問：
  - 演習の `app/mcp_servers.json` は、`type` を足しても演習のエージェントで読めるはずである。[app/mcp_agent.py](../../app/mcp_agent.py#L78-L81) は `url` があるかどうかだけを見て、`type` を読まないためである。`type` を書いておけば、同じ JSON を Claude Code でも演習でも使えると考えられる（演習のエージェントでは試していない）。
  - モデルに見えるツール名の付け方も違った。演習では `glossary_search_glossary` だが、Claude Code では `mcp__サーバー名__ツール名` の形になる。公式ドキュメントの [Configure permissions](https://code.claude.com/docs/en/permissions) は、"To match one tool, write its full name, `mcp__<server>__<tool>`."（1つのツールを指すには、`mcp__<server>__<tool>` の完全な名前を書く）としている。
  - 演習のエージェントには承認の仕組みが無く、書いてあるコマンドを確認せずに起動する。
    - MCP の仕様の [Security Best Practices（2025-11-25 版）](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices) は、設定に悪意のある起動コマンドを入れられると "Attackers can execute any command with MCP client privileges."（攻撃者は、MCP クライアントの権限で任意のコマンドを実行できる）としている。
    - Claude Code がプロジェクトの `.mcp.json` に承認を求めるのは、他人が書いた設定のコマンドがそのまま起動されるのを防ぐためだと考えられる（推論。公式ドキュメントに書かれた理由は「セキュリティ上の理由」だけである）。
  - `mcpServers` という書き方は、MCP の仕様では決まっていなかった。
    - 仕様のリポジトリ [modelcontextprotocol/modelcontextprotocol](https://github.com/modelcontextprotocol/modelcontextprotocol) の全ての版の仕様とスキーマを検索しても、`mcpServers` は見つからなかった。
    - 最初に出てくるのは、MCP のドキュメントのリポジトリの最初のコミット（2024-11-18）の [quickstart.mdx](https://github.com/modelcontextprotocol/docs/blob/2d987afeedd2998a940e228ee29ee70cb53b0d37/quickstart.mdx) で、Claude Desktop（Anthropic のデスクトップアプリ）の設定 `claude_desktop_config.json` の書き方として載っていた。
    - 仕様で決まっていないので、ツールごとに少しずつ書き方が違うと考えられる。
  - ほかのツールも、書き方が少しずつ違った。各ツールの公式ドキュメントで調べた結果は、次のとおりだった（2026-11-26 時点）。

    | ツール（提供元） | 設定ファイル（プロジェクト用） | トップレベルのキー | URL で接続する書き方 | 出典 |
    |---|---|---|---|---|
    | 演習 | `app/mcp_servers.json` | `mcpServers` | `url` | [app/mcp_agent.py](../../app/mcp_agent.py#L78-L81) |
    | Claude Code（Anthropic） | `.mcp.json` | `mcpServers` | `"type": "http"` と `url` | [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp) |
    | Codex（OpenAI） | `.codex/config.toml` | TOML の `[mcp_servers.名前]` | `url` | [Configuration reference](https://developers.openai.com/codex/config-reference) |
    | Gemini CLI（Google） | `.gemini/settings.json` | `mcpServers` | `httpUrl`（`url` は SSE） | [MCP servers with Gemini CLI](https://geminicli.com/docs/tools/mcp-server/) |
    | VS Code（Microsoft） | `.vscode/mcp.json` | `servers` | `"type": "http"` と `url` | [MCP configuration reference](https://code.visualstudio.com/docs/agents/reference/mcp-configuration) |
    | Cursor（Anysphere） | `.cursor/mcp.json` | `mcpServers` | `url` | [Model Context Protocol (MCP)](https://cursor.com/docs/context/mcp) |
    | Copilot CLI（GitHub） | `.mcp.json`、`.github/mcp.json` | `mcpServers` | `"type": "http"` と `url` | [Adding MCP servers for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers) |
    | Kiro（AWS） | `.kiro/settings/mcp.json` | `mcpServers` | `url` | [Configuration](https://kiro.dev/docs/mcp/configuration/) |
    | Antigravity CLI（Google） | `.agents/mcp_config.json` | `mcpServers` | `serverUrl`（`url` も可） | [MCP](https://antigravity.google/docs/mcp/) |

    - 起動するコマンドを `command` と `args` に書く点は、全てのツールで同じだった。違いは、トップレベルのキー、URL のキーの名前、`type` が要るかどうかに集中していた。
    - Codex は JSON ではなく TOML（設定ファイル用の書式）を使う。手元の Codex 0.171.0 で試すと、`url` だけを書いたサーバーは URL に接続する方式（Streamable HTTP）として認識された。
    - VS Code の `.vscode/mcp.json` は、トップレベルのキーが `mcpServers` ではなく `servers` である。ただし同じページは、新しい設定には `mcpServers` を使う `.mcp.json` を勧めている。
    - Gemini CLI では、`url` が古い SSE（Server-Sent Events、サーバーから一方向にデータを流す仕組み）の接続先を意味する。演習の `aws` をそのまま書くと、接続の方式が変わってしまう。
  - 疑問：Claude Code で `type` を省略できるのはコマンドで起動するサーバーだけで、URL のサーバーでは省略できない。Copilot CLI は、2026-04 の版（1.0.29）から、URL のサーバーで `type` を省略できるようにしている（[changelog](https://github.com/github/copilot-cli/blob/main/changelog.md)）。ツールによって `type` の扱いが逆方向に分かれているので、どちらの考え方が主流になるのかを確かめたい。
