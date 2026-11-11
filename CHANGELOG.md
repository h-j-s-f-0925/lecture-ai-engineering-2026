# 変更履歴

教材の運用ルールや使い方（手順、環境設定、利用するサービスなど）を変更した場合は、このファイルに追記してください。各項目には変更日、変更内容、利用者への影響や必要な対応を記録します。

## 2026-11-11

- Gemini API で `402 Payment Required` が出た場合は、前払いクレジット残高が不足している状態です。カード登録や「有料 1・請求先アカウントの階層の上限（例: ¥39,971）」の表示は、利用可能なクレジット残高を意味しません。この金額は請求額や現在の利用額ではなく、階層に設定された上限です。AI Studio の Billing で残高・購入履歴・自動チャージ設定を確認してください。残高不足は `--wait 2` で解消しないため、API キーが紐づく請求先アカウントにクレジットを追加するか、残高のある別の請求先アカウントの API キーを使ってください。
- Gemini API キーを `AIE_API_TIER` で選択できるように変更。省略時または `free` は `GEMINI_API_KEY`、`paid` は `GEMINI_API_KEY_PAID` を使用します。既存の無料用 Secret はそのまま利用でき、有料用 Secret を追加すればコマンドごとに切り替えられます。
- README の教材向け既定手順は変更していません。有料キーを使う場合だけ、実行コマンドに `AIE_API_TIER=paid` を付けます。

  ```bash
  # 既定（無料用キー）
  uv run python -m app.ask "LoRAとは何ですか？"

  # 有料用キーを使う
  AIE_API_TIER=paid uv run python -m app.ask "LoRAとは何ですか？"

  # モデルと有料用キーを指定する
  AIE_MODEL=gemini-3.5-flash AIE_API_TIER=paid uv run python -m app.ask "LoRAとは何ですか？"
  ```
