# 変更履歴

教材の運用ルールや使い方（手順、環境設定、利用するサービスなど）を変更したときの記録です。各項目には変更日、変更内容、影響と反映に必要な作業を記録します。

## 2026-11-19

### Windows にソースを置いて Dev Container を使う場合の対応

Windows の PC にリポジトリを clone し（例: `C:\Users\<名前>\aie-exercises`）、Dev Container で開いている人に関係する変更です。Windows のフォルダをコンテナから使うと、Git の所有者エラー、改行コード（CRLF）、遅さの問題が起きるため、`.devcontainer/devcontainer.json` などを変更しました。Codespaces や WSL の中に clone した場合は、これらの問題は起きません。同じ設定でそのまま動き、対応も不要です。

- **Git の所有者エラー（dubious ownership）への対応**: Git が `fatal: detected dubious ownership in repository` で止まる問題に対応しました。`postCreateCommand` で、ワークスペースを `safe.directory` に登録します（`git config --system`）。
- **`not absolute` の警告への対応**: `warning: safe.directory 'C:/...' not absolute` が出る問題に対応しました。Windows の `~/.gitconfig` がコンテナにコピーされ、そこにある `C:/` で始まるパスを Linux の Git が読めないためです。`postStartCommand` で、コピーされた設定からその項目だけを削除します。Windows 側の `.gitconfig` は変更しません。
- **仮想環境をコンテナ内へ移動**: 仮想環境の場所を、プロジェクトフォルダの `.venv` からコンテナ内の `/home/vscode/.venv` に変更しました（`containerEnv` の `UV_PROJECT_ENVIRONMENT`）。Windows と共有されるフォルダに仮想環境を置くと、`uv sync` や `import` が遅くなるためです。VS Code が使う Python（`python.defaultInterpreterPath`）も `/home/vscode/.venv/bin/python` に変更しました。
  - 反映には `Dev Containers: Rebuild Container` の実行が必要です。`uv run` の使い方は変わりません。プロジェクトフォルダに残った古い `.venv` は使われなくなります。
- **改行コードを LF に統一**: `.gitattributes` を追加し、テキストファイルの改行を LF にそろえるようにしました（`.cmd` と `.bat` だけ CRLF）。Windows で clone すると、シェルスクリプトが CRLF になり、コンテナで実行できなくなるためです。
  - すでに CRLF で展開されたファイルは、作業をすべてコミットしてから次を1回実行すると LF にそろいます（コミットしていない変更は消えます）。

    ```bash
    git rm -r --cached . && git reset --hard
    ```

### 自分の PC での API キーの渡し方

Codespaces ではなく、自分の PC（Windows・WSL・Mac）の Dev Container で演習する人に関係する変更です。

- **API キーは `.env` から読み込む**: 自分の PC のコンテナでは Codespaces の Secret が使われないため、API キーは `.env` に書き、`--env-file .env` で読み込むことにしました。

  ```bash
  uv run --env-file .env python -m app.ask "LoRAとは何ですか？"
  ```

### 設定ファイルの追加

- **`.env.sample` の追加**: 環境変数の設定例 `.env.sample` を追加し、`.gitignore` で Git の管理対象に含めるようにしました（`.env` は引き続き除外）。
- **`devcontainer-lock.json` の追加**: Dev Container の Feature の版を固定する `.devcontainer/devcontainer-lock.json` を追加しました。

## 2026-11-11

### Gemini API の有料キーへの対応

- **`402 Payment Required` が出たときの確認方法**: Gemini API で `402 Payment Required` が出た場合は、前払いクレジット残高が不足している状態です。カード登録や「有料 1・請求先アカウントの階層の上限（例: ¥39,971）」の表示は、利用可能なクレジット残高を意味しません。この金額は請求額や現在の利用額ではなく、階層に設定された上限です。AI Studio の Billing で残高・購入履歴・自動チャージ設定を確認してください。残高不足は `--wait 2` で解消しないため、API キーが紐づく請求先アカウントにクレジットを追加するか、残高のある別の請求先アカウントの API キーを使ってください。
- **`AIE_API_TIER` で無料用・有料用のキーを切り替え**: Gemini API キーを `AIE_API_TIER` で選択できるように変更。省略時または `free` は `GEMINI_API_KEY`、`paid` は `GEMINI_API_KEY_PAID` を使用します。既存の無料用 Secret はそのまま利用でき、有料用 Secret を追加すればコマンドごとに切り替えられます。
- **既定の手順は変更なし**: README の教材向け既定手順は変更していません。有料キーを使う場合だけ、実行コマンドに `AIE_API_TIER=paid` を付けます。

  ```bash
  # 既定（無料用キー）
  uv run python -m app.ask "LoRAとは何ですか？"

  # 有料用キーを使う
  AIE_API_TIER=paid uv run python -m app.ask "LoRAとは何ですか？"

  # モデルと有料用キーを指定する
  AIE_MODEL=gemini-3.5-flash AIE_API_TIER=paid uv run python -m app.ask "LoRAとは何ですか？"
  ```
