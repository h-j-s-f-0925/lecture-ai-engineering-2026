# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：
  - 素のLLM（`app.ask`）は「3レベル」の意味を特定できず、一般的な分類を推測して説明した。
  - エージェントは用語集を検索し、宿題の「基礎・実装・発展」の3段階と説明した。どれか1つに取り組めば完了という点も回答した。
- `--trace` で見えたツール呼び出し（ツール名と引数）：
  - `search_glossary({'query': 'LoRA'})`
  - `search_glossary({'query': 'QLoRA'})`
- 1つの質問での LLM 呼び出し回数（`requests`）：
  - `2` 回（`tool_calls` も `2`）
- 追加したツールと、docstring に書いた説明：
  - `make_quiz(lecture: int) -> str` を追加し、エージェントに登録した。
  - 指定した回の用語から1つをランダムに選び、「用語の意味は？」という問題と定義をJSON文字列で返す。
  - docstringには、「第2回の確認問題を出して」のように講座の用語を出題するときに使うことと、`lecture` に対象回を整数で指定することを書いた。
  - 実行時は `make_quiz({'lecture': 2})` が呼ばれ、「過学習」の問題と定義が返った。

## 宿題

- 取り組んだレベル：基礎
- やったこと：
    - 1. INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を消すと、検索せずに答えるようになるか
    - 2. search_glossary の docstring の「query には調べたい用語を1つだけ入れる」を「まとめて入れる」に変えると、検索の回数や引数がどう変わるか
    - 3. INSTRUCTIONS の「回答の最後に、関係する回（第N回）を示す」を別の指示（例：「最後に確認問題を1問出す」）に変えると、回答がどう変わるか
    - 4. INSTRUCTIONS を消して、最初に日付を出力してと書いた。(変更が本当に効いているか確認するため)
    - 5. モデルを`gemini-3.5-flash-lite`から`gemini-3.6-flash`に変更した。
      ```bash
      AIE_MODEL=gemini-3.6-flash uv run python -m app.agent --trace "第3回の内容から確認問題を1問出して"
      ```
- 結果：
    - `gemini-3.5-flash-lite`
        - 変更前後とも確認問題が出力された。`make_quiz({'lecture': 2})` が1回呼ばれ、`tool_calls=1`、`requests=2`。`search_glossary` は呼ばれなかった。
        - 変更前の出題語は「過学習」。変更後の6回は「事前学習」「ランク」「エポック」「LoRA」「QLoRA」「SFT」だった。
        - 日付を最初に出す指示を追加した後、回答の冒頭に日付が表示されたので変更は聞いていることを確認した。
    - `gemini-3.6-flash`
        - モデルを変えると、同じ質問で `make_quiz({'lecture': 2})` の後に `search_glossary({'query': 'ファインチューニング'})` も呼ばれた。`tool_calls=2`、`requests=3`。
- 気づき・疑問：
    - `gemini-3.5-flash-lite` は確認問題を求める質問と `make_quiz` のdocstringに沿って出題したと考えられる。質問とdocstringがツール選択に影響するため、1〜3の変更だけによる検索行動の変化は確認できなかった。
    - INSTRUCTIONS の変更が効いているのか確認するための指示変更が出力に反映されることを確認できた。
    - `gemini-3.6-flash` では同じ質問で `search_glossary` も呼ばれた。モデルによってツールの選び方が異なることが分かった。

---

- 取り組んだレベル：基礎 / 実装 / 発展
- やったこと：
- 結果：
- 気づき・疑問：
