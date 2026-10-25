# 会話履歴を保つ質問機能の技術調査

調査日: 2026-10-25

## 1. 結論の要点

### まず一言でいうと

違いは、**会話の記憶を誰が持ち、次の質問で誰が前の会話を渡すか**です。

| 方法 | 誰が覚えている？ | たとえると |
|---|---|---|
| `generate_content` + 履歴 | アプリ | 毎回、自分で会話メモを全部添えて質問する |
| SDK の `Chat` | SDK（アプリのメモリ内） | SDK に会話メモを持たせ、質問だけ渡す。SDK がメモを付けて送る |
| Interactions API | Google のサーバー | Google 側に会話を預け、前回の会話 ID で続きを頼む |

**SDK の `Chat` も、Google のサーバーが会話を覚える方式ではありません。** `Chat` オブジェクトがアプリの実行中に履歴を持ち、SDK が履歴を付けて API に送ります。プロセスを終了すると、その履歴も失われます。

今回の機能は、アプリがリストに質問と回答を保存し、次の質問時にまとめて送る **1つ目**です。履歴の流れがコード上で見えるため、学習用途に向いています。実装の詳細や他の選択肢との比較は後の節で説明します。

この機能に新しいパッケージは不要です。リポジトリでは `google-genai==2.31.0` が固定されており、SDK の `models.generate_content` と型 `types.Content` / `types.Part` を使って、会話履歴をリクエストごとに渡せます。引数なしで起動したときだけ対話ループを動かす構成なら、既存の単発質問も維持できます。

実装方法の主な候補は次の3つです。

1. **`models.generate_content` に会話履歴を明示して渡す** — 現在のコードと最も連続性があり、履歴の形式を学習者に見せやすい方法です。
2. **SDK の `client.chats.create()` / `chat.send_message()` を使う** — SDK にターン管理を任せ、対話処理を簡潔にできます。現在の SDK 版にも実装があります。
3. **Interactions API を使う** — 公式ドキュメントで新規開発向けに推奨されている新しい API です。サーバー側で会話を継続する選択肢がありますが、データ保持の扱いと既存コードからの移行を検討する必要があります。

今回の「短い学習用 CLI」「会話はプロセス内だけ」「既存の `generate_content` を維持」という条件なら、**候補1が最小かつ説明しやすい選択**です。SDK に会話管理を任せたいことを優先する場合は候補2も妥当です。候補3は将来、サーバー側の会話管理や新しい API 機能が必要になった段階で、保存方針とあわせて判断するのがよさそうです。

## 2. この機能に必要な技術

### CLI の対話

- `argparse` は既存の引数解析に利用できます。質問引数がある場合は従来どおり単発実行し、引数がない場合だけ `input()` を使うループに入れます。
- `/exit` と `/quit` は CLI 内で判定する文字列であり、Gemini API や追加パッケージは不要です。
- 単発実行・対話実行のどちらでも `--temperature` を維持できます。

### Gemini API と SDK

- `google-genai` はリポジトリで既に使っている公式 Python SDK で、依存は `pyproject.toml` と `uv.lock` で固定されています。会話継続だけのために SDK や依存バージョンを追加・更新する必要はありません。
- 既存の `client.models.generate_content(model=..., contents=...)` は1回の生成を行う API です。会話を継続するときは、最新の質問だけではなく、これまでの会話と最新の質問を `contents` として渡します。
- Gemini API の `contents` は単発質問では1つ、複数ターンの会話では「会話履歴と最新の入力を含む繰り返しフィールド」と定義されています。[GenerateContent API リファレンス](https://ai.google.dev/api/generate-content)
- Python SDK では会話ターンを `types.Content(role="user" | "model", parts=[types.Part.from_text(text=...)])` の形で表現できます。Gemini API の応答も `model` 側の発話として次のターンの履歴に加えます。
- API キーは既存どおり `GEMINI_API_KEY` から読み込みます。秘密情報の設定方法やモデル選択はこの機能のために変える必要はありません。

## 3. 実装方法の比較

| 方法 | 履歴を保持する場所 | 次の質問で履歴を渡す人 | メリット | デメリット・注意点 | この機能との相性 |
|---|---|---|---|---|---|
| `models.generate_content` + `types.Content` | アプリのリスト | アプリが毎回、過去の会話と今回の質問をまとめて送る | 現在の呼び出し方を活かせる。履歴が明示的で、テストでも確認しやすい。何ターン残すかをアプリ側で決められる。 | 質問・回答の追加をアプリ側で正しく管理する必要がある。 | 履歴の仕組みを学ぶ今回の機能に適する。 |
| SDK `Chat` (`client.chats.create` / `send_message`) | SDK の Chat オブジェクト（アプリのメモリ内） | SDK が保持している履歴を付けて送る | SDK が質問・回答をターンとして管理するので、呼び出し側のコードが簡潔になる。 | Google 側が履歴を保存するわけではない。Chat オブジェクトを対話中保持する必要があり、履歴の送信内容は明示方式より見えにくい。 | 履歴管理を SDK に任せたい場合に適する。 |
| Interactions API (`client.interactions.create`) | Google のサーバー（サーバー側継続を使う場合） | アプリが前回の Interaction ID を指定して続きを頼む | サーバー側で会話を継続でき、新しい API 機能を利用できる。 | API 移行が必要。既定で Interaction が保存されるため、保存するデータや `store=false` の利用を確認する必要がある。 | サーバー側で会話を再開したい将来の拡張向き。 |
| REST API を直接呼ぶ | アプリのリスト | アプリが毎回、履歴を含む HTTP リクエストを作る | HTTP と JSON の仕組みを直接確認できる。 | 認証、HTTP エラー、JSON 化など SDK が担う処理を自分で実装する必要がある。 | HTTP 層自体を学ぶ場合以外は優先度が低い。 |

### 候補1: アプリが履歴を持つ — `generate_content`

概念上は、各ターンで過去の発話に最新の質問を加えて送ります。

```python
contents = [
    types.Content(
        role="user",
        parts=[types.Part.from_text(text="最初の質問")],
    ),
    types.Content(
        role="model",
        parts=[types.Part.from_text(text="最初の回答")],
    ),
    types.Content(
        role="user",
        parts=[types.Part.from_text(text="続きの質問")],
    ),
]
response = client.models.generate_content(model=MODEL, contents=contents)
```

API は `contents` に会話履歴と最新入力を含める設計です。対話ループでは、モデルが応答した後に質問・回答の両方を履歴へ追加します。応答が失敗したターンを履歴に追加しないようにすると、次の要求へ未完了の会話を混ぜずに済みます。

この方式では会話の保存先はプログラム内のリストです。プロセス終了後に履歴は残らず、再起動時の復元もありません。

### 候補2: SDK が履歴を持つ — `Chat`

SDK の基本形は次のとおりです。

```python
client = genai.Client(api_key=get_api_key())
chat = client.chats.create(model=MODEL)
response = chat.send_message("最初の質問")
print(response.text)
```

温度を指定する場合は `client.chats.create(model=MODEL, config=types.GenerateContentConfig(temperature=temperature))` のように生成設定を作成時に渡せます。SDK の `send_message()` は会話履歴と新しいメッセージを一緒に生成 API へ渡し、応答を Chat の履歴に記録します。SDK 2.31.0 の API には `Chat.get_history()` もあります。

#### 具体的にどこへ、どう保存されるか

`client.chats.create()` が返す `chat` オブジェクトの中に、Python のリストとして保存されます。SDK 2.31.0 の実装では、主に次の2つの履歴を持ちます。

- `_comprehensive_history`: 送受信した全ターンの履歴。
- `_curated_history`: 次のリクエストに使う有効なターンの履歴。

`chat.send_message("続きの質問")` を呼ぶと、SDK は `_curated_history` に新しい質問を追加して `generate_content` に渡し、応答を受け取った後に質問と回答を履歴へ追記します。履歴を確認するには `chat.get_history()` を使えます。既定では全履歴が返り、`chat.get_history(curated=True)` で次の送信に使う履歴を取得できます。

つまり、履歴が置かれるのは**アプリの実行中にメモリ上にある `chat` オブジェクト**です。自動的にファイルやデータベースへ書かれるわけでも、Chat オブジェクトを作っただけでサーバー側セッションに保存されるわけでもありません。プログラムを終了してオブジェクトを破棄すると、そのローカル履歴は失われ、再起動後に `chat` だけから復元できません。

ただし、履歴をモデルに使わせるには、SDK が履歴を含めたリクエストを Google の API に送ります。これは「サーバー側の会話セッションとして保存・再開できる」こととは別です。API へ送信されたデータの保持・利用条件は、SDK 内の履歴管理とは別に、利用する API の公式ポリシーや設定で確認してください。

この動作は、SDK 2.31.0 の `Chat.send_message()` が内部履歴と今回の質問を組み合わせて生成 API を呼び、その後 `record_history()` を呼ぶ実装で確認できます。[SDK 2.31.0 の chats.py](https://github.com/googleapis/python-genai/blob/v2.31.0/google/genai/chats.py)

## 4. トークン量・制限への影響

- 履歴を毎回 `contents` として送る方式では、ターンが増えるほど送信する会話文脈も増えます。入力トークン数が増え、利用量やレイテンシに影響する可能性があります。
- SDK の `Chat` も内部で履歴を含めて生成 API に渡します。Chat を使うだけで、長い履歴のトークン量が自動的に一定になるわけではありません。
- 生成APIの `response.usage_metadata.prompt_token_count` は今回の質問だけではなく送信した会話履歴を含む入力全体の数で、`candidates_token_count` は生成出力の数です。利用量情報がない応答もあるため、未取得値は「不明」として扱います。
- 過去の履歴だけを別表示するには、Geminiの `count_tokens` APIに履歴の `Content` 一覧を渡します。計数APIは入力のトークン数を返し、回答を生成しません。そのため会話生成とは別のAPIリクエストが必要ですが、生成APIの利用量表示は実際の入力全体を示すものとして併記します。
- 長時間の利用でコンテキスト上限や不要な古い会話が問題になる場合は、履歴の上限、古いターンの切り捨て、要約などを別の要件として設計します。今回の短い CLI 機能に先回りして導入する必要はありません。

## 5. 会話履歴の量を管理するパターン

### まず一言でいうと

会話が長くなったときの違いは、**古い会話をそのまま残すか、捨てるか、短くまとめるか、必要な部分だけ探して使うか**です。履歴の保存先（メモリ、ファイル、データベース）とは別の設計判断です。

| パターン | どうする？ | 良い点 | 注意点・失うもの |
|---|---|---|---|
| 全履歴を送る | 最初から現在までの会話を毎回すべて送る。 | 実装が単純。過去の発言をそのまま参照できる。 | ターンごとに入力が増え、トークン量・コスト・応答時間が増える。上限に達する可能性がある。 |
| 直近 N ターンだけ残す（ウィンドウ） | 古いターンを捨て、最近の質問と回答だけ送る。 | 簡単で、履歴量に上限を設けやすい。 | 捨てたターンの固有名詞、決定、前提をモデルが忘れる。質問だけ／回答だけを残さず、ターン単位で扱う必要がある。 |
| トークン予算で切り詰める | モデルへ送れる上限を決め、新しい発言から予算内に収まる範囲を残す。 | メッセージ数ではなく、実際の入力サイズに合わせられる。 | 切り詰めた部分の情報は失われる。システム指示、質問と回答の組、ツール呼び出しと結果を途中で壊さない考慮が必要。 |
| 古い履歴を要約する | 古い発言を短い要約へ置き換え、新しい発言は原文のまま残す。 | 会話の背景や決定事項を、履歴全体より少ないトークンで残せる。 | 要約生成の追加呼び出しが必要。細部が落ちたり、要約が誤ったりする可能性がある。 |
| 要約＋直近 N ターン | 古い部分は要約し、最近の数ターンは原文で残す。 | 過去の重要事項と直近の言い回しの両方を残しやすい。 | 何を要約に残すか、いつ更新するかの設計が必要。要約の誤りや切り詰めも起こり得る。 |
| 必要な情報を検索する（外部メモリ/RAG） | 会話から保存した事実や記録を外部ストアに置き、質問ごとに関連項目だけ検索する。 | 長期の情報を全件プロンプトに入れず、再起動後や別会話でも使える構成にできる。 | ストレージや検索処理が必要。検索漏れ・無関係な取得があり、会話の逐語的な履歴を再現する方式ではない。これは圧縮ではなく「保存して必要な部分を選ぶ」方法。 |

### 履歴の圧縮と混同しやすいもの

- **トークン計数**は、送信する内容の大きさを測る手段であり、それ自体では履歴を削ったり短くしたりしません。Gemini API の `count_tokens` は入力トークン数を数え、レスポンスの利用量情報でも実際の入力・出力トークン数を確認できます。[トークン数の確認方法](https://ai.google.dev/gemini-api/docs/tokens)
- **コンテキストキャッシュ**は、繰り返し送る同じ内容を再利用してコスト・レイテンシを最適化する仕組みです。履歴そのものを要約・削除する機能ではなく、モデルへ渡す文脈の長さを小さくするものでもありません。[Gemini context caching](https://ai.google.dev/gemini-api/docs/caching)
- **大きなコンテキストウィンドウ**は一度に渡せる量を増やしますが、履歴の選別を不要にはしません。Google の長文脈ガイドも、不要な入力は避けること、長文脈では精度やコストにトレードオフがあることを説明しています。[Gemini long context](https://ai.google.dev/gemini-api/docs/long-context)

### LangChain の旧 Memory クラスと現行の考え方

LangChain の旧 `Conversation…Memory` クラス名は、会話履歴の代表的な管理パターンを表しています。現行リファレンスではこれらは `langchain_classic` にあり、いずれも **0.3.1 で非推奨、2.0.0 で削除予定**と記載されています。つまり、概念を学ぶ参考にはなりますが、新規実装でクラスをそのまま採用する前に、現行 API と移行先を確認してください。

| 旧 LangChain クラス | パターン | どのように動く？ | 注意点 |
|---|---|---|---|
| `ConversationBufferMemory` | 全履歴 | 会話全体を加工せず保持する。 | 履歴が長くなると、入力トークン・コストが増え、モデルのコンテキスト上限に近づく。 |
| `ConversationBufferWindowMemory` | 直近ターン（ウィンドウ） | `k` で決めた数の最近のメッセージを残し、古いものを落とす。 | 落とした会話の事実・決定は後続で参照できない。 |
| `ConversationTokenBufferMemory` | トークン予算での切り詰め | 最近のメッセージを優先し、総トークン数が指定上限内に収まるよう古いメッセージを落とす。 | 重要な発言も古ければ消える。メッセージやツール呼び出しの組を壊さない処理が必要。 |
| `ConversationSummaryMemory` | 継続要約 | 会話ターンごとに要約を更新し、会話全体の要約を文脈として使う。 | 更新のためのモデル呼び出しが発生し、細部の欠落や要約の誤りがあり得る。 |
| `ConversationSummaryBufferMemory` | 要約＋直近履歴 | 古い部分を要約し、最近のメッセージを原文で保持してトークン上限内に収める。 | 要約の誤りに加え、要約する境界と残すメッセージ量の設計が必要。 |

各クラスの現行リファレンスは、[Buffer](https://reference.langchain.com/python/langchain-classic/memory/buffer/ConversationBufferMemory)、[BufferWindow](https://reference.langchain.com/python/langchain-classic/memory/buffer_window/ConversationBufferWindowMemory)、[TokenBuffer](https://reference.langchain.com/python/langchain-classic/memory/token_buffer/ConversationTokenBufferMemory)、[Summary](https://reference.langchain.com/python/langchain-classic/memory/summary/ConversationSummaryMemory)、[SummaryBuffer](https://reference.langchain.com/python/langchain-classic/memory/summary_buffer/ConversationSummaryBufferMemory)。

現行の LangChain/LangGraph ドキュメントでは、用途別に次のような部品を案内しています。

- **会話履歴を保存して次の実行に引き継ぐ**: 通常の Runnable では `RunnableWithMessageHistory`、エージェントでは state の `messages` と `checkpointer` を使う短期メモリ。checkpointer はスレッド単位で状態を保持・再開する仕組みで、履歴を圧縮する機能とは別です。
- **モデルに渡すメッセージを減らす**: `trim_messages` でメッセージ数またはトークン数に合わせて切り詰める。履歴ストレージの代替ではありません。
- **古い会話を要約する**: agent 向けの `SummarizationMiddleware` で、トークン閾値に達した履歴を要約し、最近のメッセージを残す。要約にはモデル呼び出しが伴います。
- **会話をまたいで情報を保つ**: long-term memory / Store に保存・検索する。現在の会話履歴を短くする処理とは目的が異なります。

現在の `trim_messages` は、履歴を保存するクラスではなく、モデルへ渡すメッセージ列を指定したメッセージ数・トークン数に切り詰める関数です。公式リファレンスは、直近を残す `strategy="last"`、会話の始まりを人間の発話に合わせる `start_on="human"`、システム指示があれば残す `include_system=True` を例示しています。ツールを使う会話では、ツール呼び出しと結果のような関連メッセージを途中で分断しないようにする必要があります。

したがって、「Memory クラスを使えば自動で最適な圧縮も保存もしてくれる」とは限りません。**会話を保存する部品**と、**モデルへ渡す文脈を選ぶ・要約する部品**、**会話をまたいで情報を検索する部品**は分けて考えます。`RunnableWithMessageHistory` のような Runnable 用履歴ラッパーは履歴の読み書きを担いますが、それだけで履歴を圧縮する機能ではありません。さらに、その公式リファレンスで例示される `InMemoryChatMessageHistory` は `langchain-core` 1.6.4 で非推奨、2.0.0 で削除予定と記載されています。導入時には履歴バックエンドも含め、対象バージョンの文書を確認してください。

### パターン選択の目安

- **短い対話、学習用、全会話を見せたい**: 全履歴。まず挙動が単純で比較の基準になる。
- **古い内容は不要、入力の上限を単純に保ちたい**: 直近ターンを残す。実装が簡単な代わりに、古い情報を明示的に忘れる。
- **モデルの入力上限・費用を確実に守りたい**: トークン予算で切り詰める。残る内容は確実に予算内にしやすいが、重要情報の損失を許容する必要がある。
- **古い会話の背景・決定は必要だが全文はいらない**: 要約＋直近履歴。文脈を残しやすいが、要約品質と追加モデル呼び出しを評価する。
- **ユーザーの好みや過去の事実を別の会話でも使いたい**: 長期メモリ／検索。全履歴の圧縮ではなく、会話をまたぐデータ設計として扱う。

この選択は排他的である必要はありません。例えば「要約＋直近履歴」に厳格なトークン上限を組み合わせることはできます。ただし処理を重ねるほど、どの情報を残すか、検索や要約が失敗したときどうするか、実際のトークン量をどう測るかのテストが必要になります。

参考: [RunnableWithMessageHistory](https://reference.langchain.com/python/langchain-core/runnables/history/RunnableWithMessageHistory)、[LangChain short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[LangChain `trim_messages`](https://reference.langchain.com/python/langchain-core/messages/utils/trim_messages)、[LangChain `SummarizationMiddleware`](https://reference.langchain.com/python/langchain/middleware/SummarizationMiddleware)、[LangGraph memory](https://docs.langchain.com/oss/python/langgraph/add-memory)。旧クラス: [Buffer](https://reference.langchain.com/python/langchain-classic/memory/buffer/ConversationBufferMemory)、[BufferWindow](https://reference.langchain.com/python/langchain-classic/memory/buffer_window/ConversationBufferWindowMemory)、[Summary](https://reference.langchain.com/python/langchain-classic/memory/summary/ConversationSummaryMemory)、[TokenBuffer](https://reference.langchain.com/python/langchain-classic/memory/token_buffer/ConversationTokenBufferMemory)、[SummaryBuffer](https://reference.langchain.com/python/langchain-classic/memory/summary_buffer/ConversationSummaryBufferMemory)。

### 今回の小さな CLI なら

まずは全履歴を保持し、既存のトークン表示でターンごとの入力増加を観察するのが分かりやすい選択です。履歴が実際に長くなって困ることを確認してから、最も簡単な **「直近 N ターンだけ残す」**を追加できます。古い会話の重要な前提も残したい要件が出たら、**「要約＋直近ターン」**を検討します。再起動後も利用者の情報を覚える必要が生じた場合は、履歴圧縮とは別に外部ストアを検討します。

このリポジトリには現在 LangChain は依存していません。会話履歴を数ターン保持するだけなら導入は不要です。LangChain のエージェント・Runnable の機能を使う要件ができた場合に、既存の `pydantic-ai` との役割や依存追加を比較して選ぶのが適切です。

## 6. Google 側に履歴を持たせる — Interactions API

### 「Google 側に履歴を持たせる」とは

ここでいう「Google 側に持たせる」は、Google のモデルが会話を人のように覚えるという意味ではありません。**各ターンの入力・出力を Interaction として Google のサーバーに保存し、次のリクエストではアプリが前回の `interaction.id` を `previous_interaction_id` に指定することで、API がその保存済み会話を続きの文脈として使う**方式です。アプリは会話全文を毎回送り直す代わりに、新しい質問と前回のIDを送ります。

流れの例:

1. 1回目に質問を送る。API は回答と `interaction.id` を返し、既定では Interaction を保存する。
2. 2回目は新しい質問に加え、1回目のIDを `previous_interaction_id` として送る。
3. API はそのIDに結び付く会話の入力・出力を使って回答する。以降も最新の Interaction ID をつないでいく。

```python
first = client.interactions.create(model=MODEL, input="私の名前はアキです")
second = client.interactions.create(
    model=MODEL,
    input="私の名前は？",
    previous_interaction_id=first.id,
)
```

この場合、**アプリ内のリストや SDK の `Chat` オブジェクトに会話全文を保持する必要はありません**。ただしアプリ側は、次のターンへ渡す Interaction ID を保持します。会話データの保存先と、アプリが持つ継続用IDは別です。

### 保存期間と「保存しない」設定の注意

確認時点の公式ガイドでは、Interaction は既定で保存され、無料枠では1日、有料枠では55日保持されると記載されています。`store=false` にすると保存を無効にできますが、その Interaction のIDを使った後続ターン（`previous_interaction_id`）は利用できません。つまり、**サーバーに履歴を保存しないことと、サーバー側の会話継続を使うことは両立しません**。保存したInteractionはIDを使って削除でき、保持期間を有料枠で設定する方法も案内されています。適用条件や期間は変更される可能性があるため、採用時には公式の最新情報を確認してください。[Interactions API 概要: データ保存と保持](https://ai.google.dev/gemini-api/docs/interactions-overview#data-storage-and-retention)

この違いは、SDK `Chat` との比較で重要です。SDK `Chat` はアプリのメモリに履歴を持ち、APIリクエストに含めて送ります。一方、Interactions API のこの使い方では、履歴をサーバーに保持し、アプリはIDで参照します。APIへデータを送ること自体はどちらにもありますが、**履歴を次のターンのために保存・参照する主体が異なります**。

これは長期運用のアプリケーションや、サーバー側に保存した会話をIDで継続したい機能には有力です。一方、今回の要件は「対話プロセス中だけ履歴を保持」であり、既存コードは `generate_content` を使い、利用量表示も同 API のレスポンスに結びついています。そのため現時点で API を移行すると、要求に必要な範囲を超える変更とデータ保持方針の検討が増えます。

**選び方**

- **既存コードの維持、実装内容の見通し、学習で履歴構造を確認することを優先**: `generate_content` + 明示的な `Content` 履歴。
- **ターン管理を SDK に任せて対話処理を簡潔にすることを優先**: `client.chats.create()` + `chat.send_message()`。
- **サーバー側セッション再開、新 API の機能、保存に伴うデータ方針の検討を優先**: Interactions API。

## 7. テスト方法

- Gemini API へ実通信せず、既存テストと同様に `client.models.generate_content` を Mock に置き換えます。
- 2ターン目の呼び出し引数に `user` / `model` の1ターン目の発話と、2ターン目の `user` 発話が順番どおり含まれることを確認します。
- `/exit` と `/quit` は API 呼び出しなしに対話を終了することを確認します。
- 単発質問、温度設定、トークン表示の既存テストを維持します。

この方法なら API キーや外部通信なしで、履歴の引き継ぎと CLI の基本動作を検証できます。

## 8. 参照資料

1. Google AI for Developers, [GenerateContent API リファレンス](https://ai.google.dev/api/generate-content) — `contents` が単発入力または会話履歴と最新入力を含むこと。
2. Google, [google-genai SDK 2.31.0 `google/genai/chats.py`](https://github.com/googleapis/python-genai/blob/v2.31.0/google/genai/chats.py) — Chat の作成、送信時の履歴利用、履歴更新の実装。
3. Google AI for Developers, [Interactions API 概要](https://ai.google.dev/gemini-api/docs/interactions-overview) — 現行 API の推奨、`previous_interaction_id`、保存と `store=false` の説明。
4. リポジトリの `pyproject.toml` / `uv.lock` — 利用中の SDK とバージョン固定。調査時点では `google-genai==2.31.0`。
5. Google AI for Developers, [トークン数の確認方法](https://ai.google.dev/gemini-api/docs/tokens)、[`models.countTokens` API](https://ai.google.dev/api/tokens)、[Gemini long context](https://ai.google.dev/gemini-api/docs/long-context)、[Gemini context caching](https://ai.google.dev/gemini-api/docs/caching) — トークン計数、長文脈のトレードオフ、キャッシュの目的。
6. LangChain, [Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)、[RunnableWithMessageHistory](https://reference.langchain.com/python/langchain-core/runnables/history/RunnableWithMessageHistory)、[InMemoryChatMessageHistory](https://reference.langchain.com/python/langchain-core/chat_history/InMemoryChatMessageHistory)、[trim_messages](https://reference.langchain.com/python/langchain-core/messages/utils/trim_messages)、[SummarizationMiddleware](https://reference.langchain.com/python/langchain/middleware/SummarizationMiddleware) — 現行の履歴保存・検索・切り詰め・要約の考え方。
7. LangChain Classic API Reference, [ConversationBufferMemory](https://reference.langchain.com/python/langchain-classic/memory/buffer/ConversationBufferMemory)、[ConversationBufferWindowMemory](https://reference.langchain.com/python/langchain-classic/memory/buffer_window/ConversationBufferWindowMemory)、[ConversationSummaryMemory](https://reference.langchain.com/python/langchain-classic/memory/summary/ConversationSummaryMemory)、[ConversationTokenBufferMemory](https://reference.langchain.com/python/langchain-classic/memory/token_buffer/ConversationTokenBufferMemory)、[ConversationSummaryBufferMemory](https://reference.langchain.com/python/langchain-classic/memory/summary_buffer/ConversationSummaryBufferMemory) — 旧 Memory クラスの用途と非推奨状況。
8. LangChain, [Release policy](https://docs.langchain.com/oss/python/release-policy) — 1.x 系・0.3 系の保守方針。

Google および LangChain の公式資料は2026-10-25に確認しました。LangChain の現行ドキュメントは固定バージョンではなく確認時点の内容です。旧クラスの非推奨開始は0.3.1、削除予定は2.0.0と各APIリファレンスに記載されています。非推奨・削除予定の時期、API の推奨状況、SDK の機能、モデル対応は更新される可能性があるため、導入時には対象バージョンの最新資料を再確認してください。
