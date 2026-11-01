# 第1回 宿題（発展）：応答時間とtoken数を比較する

複数のモデル・質問でGemini APIを実行し、応答時間とtoken数を比較します。実験前にGoogle AI Studioで利用tier、対象モデルのレート制限、課金状態を確認してください。実行回数や質問数に応じてAPIを呼び出すため、利用制限や料金にも注意します。

## 1. 実験を実行する

リポジトリのルートから、発展用スクリプトを起動します。

```bash
bash lectures/01/experiment/run-advanced.sh
```

既定では2モデル×2質問×各3回の計12回の生成API呼び出しを行い、リクエスト間に2秒待機します。モデル名・質問・試行回数を指定する例です。

```bash
bash lectures/01/experiment/run-advanced.sh gemini-3.5-flash-lite gemini-3.5-flash \
  --question "LoRAとは何ですか？" \
  --question "AIE2026の講座の宿題にある「3レベル」とは何ですか？" \
  --runs 3 \
  --interval 2
```

質問・試行回数・待機時間などの指定方法は、次のコマンドでも確認できます。

```bash
bash lectures/01/experiment/run-advanced.sh --help
```

| 指定するもの | CLI引数 | 環境変数 | 既定値 |
|---|---|---|---|
| 質問 | `--question`（複数回指定可） | `AIE_QUESTIONS_FILE`（1行に1つの質問を書いたUTF-8ファイル） | 上記2質問 |
| 試行回数 | `--runs` | `AIE_RUNS` | 3回 |
| リクエスト間隔 | `--interval` | `AIE_REQUEST_INTERVAL_SECONDS` | 2秒 |
| temperature | — | `AIE_TEMPERATURE` | モデル既定値 |
| 利用tierや上限のメモ | `--rate-limit-notes` | `AIE_RATE_LIMIT_NOTES` | 未記録 |

質問は `--question` または `AIE_QUESTIONS_FILE` のどちらか一方で指定してください。質問ファイルは1行に1つ質問を書き、空行は読み飛ばします。CLI引数が環境変数より優先されます。Google AI Studioで確認した利用tierや上限を記録する場合は、秘密情報を含めないでください。

```bash
AIE_QUESTIONS_FILE=questions.txt AIE_RUNS=3 \
  bash lectures/01/experiment/run-advanced.sh gemini-3.5-flash-lite gemini-3.5-flash

bash lectures/01/experiment/run-advanced.sh \
  --rate-limit-notes "Free tier。実行前にAI Studioでモデル別上限を確認"
```

レート制限を意図的に試す目的で待機時間を短くしないでください。APIキー、project ID、個人情報などの秘密情報を質問やレポートに含めないでください。

## 2. レポートを確認する

実行ごとに [`experiment/reports/`](../experiment/reports/) にMarkdownレポートが作成されます。実験条件、集計、試行ごとの結果、回答全文を確認してください。

- **応答時間**はAPI呼び出し直前から応答が返るまでのクライアント側の経過時間です。通信やSDK処理も含み、モデル内部だけの推論時間ではありません。
- **token数**はAPI応答のusage metadataに基づきます。値が返されない場合は0ではなく「不明」として扱います。
- **成功応答の統計**には平均・中央値・最小・最大が記録されます。失敗回数と失敗時の所要時間は成功応答の統計と分けて確認してください。
- **エラー**が発生した場合はレポートのエラー情報を確認します。自動再試行は行われません。

Gemini APIにはRPM（1分あたりの要求数）、TPM（1分あたりのtoken数）、RPD（1日あたりの要求数）などの制限があります。429などのエラーは制限との関係を確認する手がかりになりますが、503は一時的な混雑など別の原因の場合があります。AI Studioで確認した適用上限と、実験中に実際に起きたことを分けて記録してください。少数回の結果から上限やモデル全体の性能を断定しないでください。

## 3. `answer.md` にまとめる

[answer.md](../answer.md) には、次の内容を記録します。

- 比較したモデル・質問・試行回数・実行間隔などの条件
- モデル・質問ごとの応答時間とtoken数の傾向
- 成功・失敗の回数と、発生したエラー
- AI Studioで確認した制限と、実験で観測した事実との関係
- 試行回数や混雑など、結果を解釈するうえでの限界
- 根拠をたどれるよう、確認したレポートへの相対パス

観測した数値と、その数値からの考察を区別して書いてください。
