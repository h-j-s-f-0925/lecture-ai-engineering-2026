# 第1回 temperature 比較実験の手順

同じ質問を複数の temperature で実行し、回答の違いを比較する手順です。実行条件と回答全文は自動生成レポートに保存し、要約と考察を [answer.md](./answer.md) にまとめます。

## 1. 実行前の確認

- リポジトリのルートで `uv` を実行できること
- 環境変数 `GEMINI_API_KEY` が設定されていること
- 使用するモデルが Gemini API で利用できること

APIキーはコマンドやレポートに書かないでください。実験ではGemini APIを呼び出すため、利用制限や料金にも注意してください。

## 2. temperature を変えて実行する

リポジトリのルートから、比較したい値ごとにコマンドを実行します。

```bash
AIE_TEMPERATURE=0.2 bash lectures/01/experiment/run.sh
AIE_TEMPERATURE=1.0 bash lectures/01/experiment/run.sh
```

各実行では、既定の `gemini-3.5-flash-lite` と `gemini-3.5-flash` に同じ質問を送り、それぞれ3回ずつ回答を取得します。モデルと質問を揃えてtemperatureを変えることで、温度設定による違いを観察しやすくします。

モデルを変更したい場合は、モデル名をコマンドの後ろに指定します。指定したモデルごとに3回実行されます。

```bash
AIE_TEMPERATURE=0.2 bash lectures/01/experiment/run.sh gemini-3.5-flash-lite gemini-3.1-flash-lite
```

temperatureを指定しない場合は、モデルの既定設定で実行します。

```bash
bash lectures/01/experiment/run.sh
```

## 3. レポートを確認する

各実行のレポートは [`experiment/reports/`](./experiment/reports/) に保存されます。ファイル名と記録される実行日時はJSTです。レポートには実行条件、各試行の成功・失敗とトークン数、回答全文が含まれます。

temperatureが異なるレポートを開き、次の観点で比べてください。

- 回答の内容・構成・表現にどのような違いがあったか
- 同じtemperatureで3回実行したとき、回答にどの程度の揺らぎがあったか
- トークン数や実行失敗に違いがあったか

低いtemperatureでは回答がより予測しやすく、高いtemperatureでは多様になりやすいとされています。ただし、モデルや質問によって結果は異なり、値を変えれば必ず回答が変わるわけではありません。少数回の結果だけで一般的な性能を断定しないでください。

## 4. `answer.md` にまとめる

[answer.md](./answer.md) の宿題欄に、次の内容を記入します。

- 取り組んだレベルと実行した内容
- 比較したモデル、質問、temperature、各条件の実行回数
- 回答の共通点や違い、正確さについての観察
- トークン数など、レポートから分かったこと
- 結果から気づいたことや残った疑問
- 根拠をたどれるよう、確認したレポートへの相対パス

回答全文をそのまま転記する必要はありません。観察した結果と自分の考察を分け、実際のレポートに基づいて記述してください。
