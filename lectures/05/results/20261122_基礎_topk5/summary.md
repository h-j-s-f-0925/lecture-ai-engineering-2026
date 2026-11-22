# 基礎_topk5 の実行結果（2026-11-22 10:44:15）

- 質問ファイル: lectures/05/questions.tsv（3 問）
- commit: 5a08a47（未コミットの変更あり）
- AIE_MODEL: 未設定（app/config.py の既定）
- AIE_RAG_DB: 未設定（既定の data/rag_data/index.sqlite3）
- 方式: vector
- ログ: lectures/05/.log/20261122_基礎_topk5_4/

## lora

質問: 第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？

期待するふるまい: LoRA は元の重みを固定し、小さな行列 A・B（低ランクの差分）だけを学習する。QLoRA は元の重みを 4bit に圧縮する。根拠は第2回 p.52（p.51 も可）

### vector

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_materials({'query': 'LoRA 固定 学習 QLoRA 追加'})
[time] 回答完了まで 2.50 秒（検索・埋め込みを含む）
[usage] 入力 3,785 tokens / 出力 196 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.001626 USD（埋め込み・索引構築分は含まない）
```

## multi-page

質問: 第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか

期待するふるまい: コンパクションは同じセッションの中で古い履歴を要約に置き換える。メモリは外の保存先にあり、セッションをまたいで引き継ぐ。日々のメモは全部は入らず、見直し（dreaming）で基準を超えたものだけが長期メモリに移る。根拠は第3回 p.39・p.40（p.13 も可）

### vector

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_materials({'query': 'コンパクション セッション メモリ 長期メモリ 日々のメモ'})
[time] 回答完了まで 3.46 秒（検索・埋め込みを含む）
[usage] 入力 3,254 tokens / 出力 465 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.002139 USD（埋め込み・索引構築分は含まない）
```

## not-in-materials

質問: 今回作ったRAGの実測平均応答時間と正答率を教えてください

期待するふるまい: 講義資料には今回のシステムの実測値がないと答え、数値を作らない

### vector

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_materials({'query': 'RAG 実測 平均応答時間 正答率'})
[time] 回答完了まで 2.39 秒（検索・埋め込みを含む）
[usage] 入力 3,960 tokens / 出力 136 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.001528 USD（埋め込み・索引構築分は含まない）
```

