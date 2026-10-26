# 第1回 実験スクリプト

このフォルダーには、基礎課題向けのシェルスクリプトと、発展課題向けのPython runnerを起動するシェルスクリプトがあります。どちらもリポジトリのルートから実行してください。

## どのコマンドを実行するか

| 目的 | 実行コマンド | 何を記録するか |
|---|---|---|
| 基礎課題・temperature比較 | `bash lectures/01/experiment/run.sh` | モデルごとの回答・token数 |
| 発展課題・応答時間と複数質問の比較 | `bash lectures/01/experiment/run-advanced.sh` | 応答時間・token数・試行結果 |

`run.sh` は従来どおりBashで書かれた基礎用スクリプトです。シェルの配列、ループ、条件分岐、コマンド置換やレポート組み立てを学びたい場合はこちらを使ってください。発展用Python runnerは `run-advanced.sh` から実行します。スクリプト名を取り違えないよう、以下にそれぞれの既定動作と指定方法を記載します。

## 実行前の確認

どちらのコマンドもGemini APIを呼び出します。実行前に次を確認してください。

- `GEMINI_API_KEY` が環境変数に設定されていること
- リポジトリのルートで `uv` が使えること
- 比較に使うモデルがGemini APIで利用できること
- Google AI Studioで対象projectの現在の利用tier、無料対象モデル、レート制限、課金状態を確認したこと

APIキーはスクリプト、質問ファイル、ログ、レポートへ書き込まないでください。無料枠の制限値はモデルやprojectの利用状況によって異なり、既定の待機時間は制限回避を保証しません。

## 基礎用 `run.sh`

このスクリプトはBashでモデルごとに3回実行し、token数と回答全文をMarkdownに記録します。既定では2モデル×3回、合計6回の生成API呼び出しです。質問は講座の「3レベル」についての1問です。

```bash
bash lectures/01/experiment/run.sh
```

比較するモデルを変える場合は、モデル名を引数で渡します。temperature比較では環境変数 `AIE_TEMPERATURE` を設定します。

```bash
bash lectures/01/experiment/run.sh gemini-3.5-flash-lite gemini-3.5-flash
AIE_TEMPERATURE=0.2 bash lectures/01/experiment/run.sh
AIE_TEMPERATURE=1.0 bash lectures/01/experiment/run.sh
```

基礎用スクリプトは応答時間を計測しません。temperature比較の詳細は[temperature比較実験の手順](../temperature-experiment.md)を参照してください。

## 発展用 `run-advanced.sh`

この入口からPython runnerを起動し、複数の質問・モデル・試行をまとめて実行します。既定では2モデルに2質問を各3回送り、合計12回の生成API呼び出しを行います。リクエスト間には2秒待機します。

```bash
bash lectures/01/experiment/run-advanced.sh
```

既定の質問は次の2つです。

- `LoRAとは何ですか？`
- `AIE2026の講座の宿題にある「3レベル」とは何ですか？`

モデル名は位置引数、質問は `--question` を繰り返して指定します。

```bash
bash lectures/01/experiment/run-advanced.sh gemini-3.5-flash-lite gemini-3.5-flash \
  --question "LoRAとは何ですか？" \
  --question "AIE2026の講座の宿題にある「3レベル」とは何ですか？" \
  --runs 3 \
  --interval 2
```

`--runs` はモデル・質問ごとの試行回数、`--interval` はAPIリクエスト間の待機秒数です。待機を0にすると間隔を空けずに実行します。レート制限を意図的に試すために短い間隔を使わないでください。

| CLI引数 | 環境変数 | 既定値 |
|---|---|---|
| `--question`（複数回指定可） | `AIE_QUESTIONS_FILE`（1行に1つの質問を書いたUTF-8ファイル） | 上記2質問 |
| `--runs` | `AIE_RUNS` | `3` |
| `--interval` | `AIE_REQUEST_INTERVAL_SECONDS` | `2` 秒 |
| — | `AIE_TEMPERATURE` | モデル既定値 |
| `--rate-limit-notes` | `AIE_RATE_LIMIT_NOTES` | 未記録 |

CLIで指定した試行回数・待機時間・制限メモは対応する環境変数より優先されます。質問は `--question` または `AIE_QUESTIONS_FILE` のどちらか一方で指定してください。両方を指定すると、API呼び出し前にエラーになります。試行回数は1以上、待機時間は0以上の有限な数値を指定します。

質問ファイルでは、1行に1つの質問を書き、空行は読み飛ばします。

```bash
AIE_QUESTIONS_FILE=questions.txt AIE_RUNS=3 \
  bash lectures/01/experiment/run-advanced.sh gemini-3.5-flash-lite gemini-3.5-flash
```

Google AI Studioで確認した利用tierやレート制限をレポートへ残す場合は、制限メモを指定します。APIキー、project ID、個人情報などの秘密情報は入力しないでください。

```bash
bash lectures/01/experiment/run-advanced.sh \
  --rate-limit-notes "Free tier。実行前にAI Studioで表示されたモデル別上限を確認"
```

temperatureの比較では、すべてのモデル・質問・試行に同じ `AIE_TEMPERATURE` が適用されます。利用可能な温度範囲はモデルによって異なります。

```bash
AIE_TEMPERATURE=0.2 bash lectures/01/experiment/run-advanced.sh
AIE_TEMPERATURE=1.0 bash lectures/01/experiment/run-advanced.sh
```

## 発展用レポートの読み方

実行ごとに `reports/YYYYMMDD_HHMM_experiment-<一意な文字列>.md` が作られます。ファイル名と時刻はJSTです。レポートには実験条件、質問・モデルごとの集計、各試行の生データ、回答全文を記録します。

- **応答時間**はAPI呼び出し直前からresponseが返るまでのクライアント側経過時間です。ネットワークやSDK処理を含み、モデル内部だけの推論時間ではありません。
- **token数**はGemini API responseのusage metadataから得ます。usageが返らない場合は「不明」とし、0とみなしません。
- **集計**は成功した応答時間を対象に平均・中央値・最小・最大を表示します。失敗回数は別に数え、失敗の所要時間は成功時間の統計に含めません。
- **失敗**は各試行とレポートに残します。残りの試行も続け、レポート保存後にコマンドは失敗終了します。自動再試行はしません。

Gemini APIはRPM（1分あたりの要求数）、TPM（1分あたりのtoken数）、RPD（1日あたりの要求数）などの制限を適用します。429などが発生した場合は、モデル、project、現在の利用tier、実行時の待機条件を確認してください。503は混雑などの一時的な問題を示す場合があります。少数の成功・失敗から無料枠の上限やモデルの一般的な性能を断定せず、Google AI Studioで確認した適用制限と実験で観測した事実を分けて考察します。

## `answer.md` に書くこと

[第1回の解答](../answer.md)には、実験条件、各質問・モデルの観測結果、モデル回答の内容評価、応答時間とtoken数の傾向、レート制限との関係、実験回数や混雑などの限界を記録します。実測値は発展用レポートから転記し、レポートへの相対パスを記載してください。観測した事実と考察を区別し、各条件3回の結果だけでモデル全体の性能を断定しないでください。
