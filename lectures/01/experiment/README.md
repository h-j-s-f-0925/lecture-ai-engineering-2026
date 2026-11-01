# 第1回 実験用ファイル

このフォルダーには、宿題の実験に使うスクリプトと自動生成レポートがあります。宿題のレベル選択と進め方は[宿題ガイド](../homework/README.md)、各レベルの詳しい実行手順はそれぞれのガイドを確認してください。

| 用途 | 手順 | 実行ファイル | 結果 |
|---|---|---|---|
| 基礎：モデル・temperature比較 | [基礎の手順](../homework/basic.md) | `run.sh` | [`reports/`](./reports/) |
| 発展：応答時間・token数比較 | [発展の手順](../homework/advanced.md) | `run-advanced.sh` | [`reports/`](./reports/) |

両方のスクリプトはリポジトリのルートから実行します。どちらもGemini APIを呼び出すため、事前に `GEMINI_API_KEY` とGoogle AI Studioの利用tier・レート制限・課金状態を確認してください。APIキーやproject IDなどの秘密情報を質問、ログ、レポートへ書き込まないでください。

`run.sh` はBashで実装した基礎用スクリプトです。`run-advanced.sh` は発展用Python runnerを起動します。スクリプトの引数、環境変数、既定の試行数などは、対応する宿題ガイドに記載しています。
