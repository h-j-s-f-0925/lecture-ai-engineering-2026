# 追加質問の実行結果 20261120_111808

- commit: 7970788（未コミットの変更あり）
- AIE_RAG_DB: 未設定（既定の data/rag_data/index.sqlite3）
- 方式: full-context vector tree graph

## multi-page

質問: 第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか

### full-context

```text
exit status: 0
[model] gemini-3.5-flash-lite
[full-context] 入力227,985文字
[time] 回答完了まで 3.10 秒（検索・埋め込みを含む）
[usage] 入力 117,031 tokens / 出力 371 tokens / モデル応答 1 回
[cost] 生成APIの推定コスト: $0.005081 USD（埋め込み・索引構築分は含まない）
```

### vector

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_materials({'query': 'コンパクション セッション メモリ 長期メモリ 日々のメモ'})
[time] 回答完了まで 4.30 秒（検索・埋め込みを含む）
[usage] 入力 3,254 tokens / 出力 458 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.002121 USD（埋め込み・索引構築分は含まない）
```

### tree

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   browse_tree({})
[tool call]   browse_tree({'node_id': 'lec03-main'})
[tool call]   browse_tree({'node_id': 'lec03-main-s037'})
[tool call]   browse_tree({'node_id': 'lec03-main-p039'})
[tool call]   browse_tree({'node_id': 'lec03-main-p040'})
[tool call]   browse_tree({'node_id': 'lec03-main-p041'})
[time] 回答完了まで 25.20 秒（検索・埋め込みを含む）
[usage] 入力 11,066 tokens / 出力 586 tokens / モデル応答 7 回
[cost] 生成APIの推定コスト: $0.004785 USD（埋め込み・索引構築分は含まない）
```

### graph

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_graph({'query': 'コンパクション セッション 長期メモリ 第3回'})
[time] 回答完了まで 3.96 秒（検索・埋め込みを含む）
[usage] 入力 5,301 tokens / 出力 471 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.002768 USD（埋め込み・索引構築分は含まない）
```

## not-in-materials

質問: 今回作ったRAGの実測平均応答時間と正答率を教えてください

### full-context

```text
exit status: 0
[model] gemini-3.5-flash-lite
[full-context] 入力227,957文字
[time] 回答完了まで 4.21 秒（検索・埋め込みを含む）
[usage] 入力 117,016 tokens / 出力 140 tokens / モデル応答 1 回
[cost] 生成APIの推定コスト: $0.035455 USD（埋め込み・索引構築分は含まない）
```

### vector

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_materials({'query': 'RAG 平均応答時間 正答率 実測'})
[time] 回答完了まで 4.01 秒（検索・埋め込みを含む）
[usage] 入力 3,874 tokens / 出力 130 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.001487 USD（埋め込み・索引構築分は含まない）
```

### tree

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   browse_tree({})
[tool call]   browse_tree({'node_id': 'lec01-main'})
[tool call]   browse_tree({'node_id': 'lec02-main'})
[tool call]   browse_tree({'node_id': 'lec03-main'})
[time] 回答完了まで 21.81 秒（検索・埋め込みを含む）
[usage] 入力 3,075 tokens / 出力 204 tokens / モデル応答 3 回
[cost] 生成APIの推定コスト: $0.001432 USD（埋め込み・索引構築分は含まない）
```

### graph

```text
exit status: 0
[model] gemini-3.5-flash-lite
[tool call]   search_graph({'query': '実測平均応答時間 正答率'})
[time] 回答完了まで 13.37 秒（検索・埋め込みを含む）
[usage] 入力 5,421 tokens / 出力 220 tokens / モデル応答 2 回
[cost] 生成APIの推定コスト: $0.002176 USD（埋め込み・索引構築分は含まない）
```

