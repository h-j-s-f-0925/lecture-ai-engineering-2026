"""
発展のテスト問題を確かめ、講座の検索結果を付けて JSON ファイルに書き出す処理。

テスト問題とは、LoRA の学習の効果を測るためにモデルに聞く質問の一覧のこと。
学習データ（glossary_sft.jsonl）とは別に用意し、学習前・学習後・検索ありの 3 つの方式で同じように聞く。
1 問は、質問の文・質問の種類・採点の基準（答えに含むべき語句）でできている。

全体の流れ:
    1. 22 問（同じ文 8 問・言い換え 8 問・知らない語 6 問）をこのファイルに書く（TEST_ITEMS）。
    2. 約束を守っているかを 5 つの確認で調べる（find_problems）。
    3. 問題が無いときだけ、講座の検索の結果を付けて glossary_test.json に書き出す（main）。
    4. glossary_test.json を Colab にアップロードし、3 つの方式で答えさせて採点する。

使い方（リポジトリのルートで、Git Bash から）:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. uv run python lectures/02/advanced/make_glossary_test.py

PYTHONPATH=. は、リポジトリのルートにある app/ を import するために付ける。
"""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from app.tools import load_glossary, search_glossary
from scripts.make_sft_dataset import TEMPLATES

# 書き出すファイル。このスクリプトと同じフォルダに置き、Colab にアップロードする
OUTPUT = Path(__file__).resolve().parent / "glossary_test.json"
# リポジトリのルート（lectures/02/advanced/ の 3 つ上）。書き出した場所を短く表示するために使う
REPO_ROOT = Path(__file__).resolve().parents[3]
# 「知らない」を表す語句。知らない語の質問は、答えがどれか 1 つを含めば正解
UNKNOWN_PHRASES = ("分かりません", "わかりません", "知りません", "記載がありません", "情報がありません", "確認が必要")
# search_glossary が見つからなかったときに返す文の先頭
NOT_FOUND_PREFIX = "用語集に"

# 質問の種類。same: 学習データと同じ文、paraphrase: 言い換え、unknown: 用語集に無い語
Kind = Literal["same", "paraphrase", "unknown"]


@dataclass(frozen=True)
class EvalItem:
    """
    テスト問題 1 問を表すクラス。

    frozen=True で、作ったあとに値を書き換えられないようにする。

    Attributes:
        kind: 質問の種類（same・paraphrase・unknown）。
        question: モデルに渡す質問の文。例: "「LoRA」とは何ですか？"
        term_id: 答えになる用語集の語の id。例: "lora"。unknown では None。
        must_include: すべて含めば正解にする語句。same と paraphrase で使う。例: ("行列", "固定")
        must_any: どれか 1 つを含めば正解にする語句。unknown で使う。
    """

    kind: Kind
    question: str
    term_id: str | None = None
    must_include: tuple[str, ...] = ()
    must_any: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """
        質問の種類と、埋めた項目の組み合わせを確かめるメソッド。

        Raises:
            ValueError: 種類に合わない項目が埋まっている、または必要な項目が空のとき。
        """
        # 種類が 3 つのどれでもない場合（Literal は実行時に確かめないので、ここで確かめる）
        if self.kind not in get_args(Kind):
            raise ValueError(f"質問の種類が正しくない: {self.kind}")
        # 空の語句がある場合（"" はどんな答えにも含まれるので、何を答えても正解になってしまう）
        if any(not word.strip() for word in self.must_include + self.must_any):
            raise ValueError(f"採点の語句に空の文字列がある: {self.question}")
        # 知らない語の場合: term_id なし、must_any だけを使う
        if self.kind == "unknown":
            is_valid = self.term_id is None and not self.must_include and bool(self.must_any)
        # 同じ文・言い換えの場合: term_id あり、must_include だけを使う
        else:
            is_valid = self.term_id is not None and bool(self.must_include) and not self.must_any
        # 組み合わせが合わない場合
        if not is_valid:
            raise ValueError(f"質問の種類（{self.kind}）と項目の組み合わせが合わない: {self.question}")

    def to_json_dict(self, search_result: str) -> dict[str, object]:
        """
        Colab で読む JSON の 1 問分の辞書を作るメソッド。

        Args:
            search_result: 質問の文で search_glossary を呼んだ結果の文字列。

        Returns:
            kind・term_id・question・採点の語句・search_result を持つ辞書。
        """
        data: dict[str, object] = {"kind": self.kind, "term_id": self.term_id, "question": self.question}
        # 知らない語の場合: must_any を入れる
        if self.kind == "unknown":
            data["must_any"] = list(self.must_any)
        # 同じ文・言い換えの場合: must_include を入れる
        else:
            data["must_include"] = list(self.must_include)
        data["search_result"] = search_result
        return data


# テスト問題の一覧。引数の順は（種類, 質問の文, 用語集の id）
TEST_ITEMS = (
    # 同じ文: 学習データの 1 つ目のひな形と同じ文
    EvalItem("same", "「宿題の3レベル」とは何ですか？", "homework-levels", must_include=("基礎", "実装", "発展")),
    EvalItem("same", "「answer.md」とは何ですか？", "answer-md", must_include=("lectures", "PR")),
    EvalItem("same", "「lecNN-start タグ」とは何ですか？", "lec-start-tag", must_include=("タグ", "ブランチ")),
    EvalItem("same", "「既定モデル」とは何ですか？", "default-model", must_include=("gemini-3.5-flash-lite",)),
    EvalItem("same", "「Pi」とは何ですか？", "pi", must_include=("ターミナル", "コーディングエージェント")),
    EvalItem("same", "「mcpServers設定」とは何ですか？", "mcp-config", must_include=("mcp_servers.json",)),
    EvalItem("same", "「LoRA」とは何ですか？", "lora", must_include=("行列", "固定")),
    EvalItem("same", "「temperature」とは何ですか？", "temperature", must_include=("多様",)),
    # 言い換え: 別名で聞く
    EvalItem("paraphrase", "AIE2026 の宿題レベルには何がありますか？", "homework-levels", must_include=("基礎", "実装", "発展")),
    EvalItem("paraphrase", "この講座のデフォルトモデルは何ですか？", "default-model", must_include=("gemini-3.5-flash-lite",)),
    EvalItem("paraphrase", "Low-Rank Adaptation の仕組みを教えてください。", "lora", must_include=("行列", "固定")),
    EvalItem("paraphrase", "温度パラメータを上げると、出力はどう変わりますか？", "temperature", must_include=("多様",)),
    # 言い換え: 用語名も別名も出さずに聞く
    EvalItem("paraphrase", "AIE2026 で、各回の結果を書いて出すファイルは何ですか？", "answer-md", must_include=("lectures", "PR")),
    EvalItem("paraphrase", "前の回が終わっていなくても、次の回を始められる仕組みは何ですか？", "lec-start-tag", must_include=("タグ", "ブランチ")),
    EvalItem("paraphrase", "2026 年 10 月に 1.0 が公開された、最小構成のエージェントは何ですか？", "pi", must_include=("ターミナル", "コーディングエージェント")),
    EvalItem("paraphrase", "本講座で、使う MCP サーバーを書いておくファイルはどれですか？", "mcp-config", must_include=("mcp_servers.json",)),
    # 知らない語: 用語集の語に近い語
    EvalItem("unknown", "「lecNN-end タグ」とは何ですか？", must_any=UNKNOWN_PHRASES),
    EvalItem("unknown", "「question.md」とは何ですか？", must_any=UNKNOWN_PHRASES),
    EvalItem("unknown", "「宿題の応用レベル」とは何ですか？", must_any=UNKNOWN_PHRASES),
    # 知らない語: 遠い語（一般的な意味で答えられないよう「AIE2026の」を付ける）
    EvalItem("unknown", "「AIE2026の修了課題」とは何ですか？", must_any=UNKNOWN_PHRASES),
    EvalItem("unknown", "「AIE2026の講座バッジ」とは何ですか？", must_any=UNKNOWN_PHRASES),
    EvalItem("unknown", "「AIE2026の週次チェックイン」とは何ですか？", must_any=UNKNOWN_PHRASES),
)


def find_problems(items: tuple[EvalItem, ...], terms: list[dict]) -> list[str]:
    """
    テスト問題が約束を守っているかを、5 つの確認で調べる関数。

    確認 1: 知らない語は、講座の検索で用語集を探しても見つからない。
    確認 2: 同じ文の質問は、その語の学習データの質問（1 つ目のひな形）と一字一句同じ。
    確認 3: 言い換えの質問は、学習データのどの質問とも違う。
    確認 4: 必須語句が、その語の定義にすべてある。
    確認 5: 必須語句がすべてそろう定義が、ほかの語に無い。

    Args:
        items: テスト問題の一覧（TEST_ITEMS）。
        terms: load_glossary() が返す、用語集の語の辞書のリスト（65 語）。

    Returns:
        見つかった問題を説明する文のリスト。問題が無ければ空のリスト。
    """
    # by_id（id から語を引く辞書）: 例えば by_id["pi"]["definition"] で Pi の定義が取れる
    by_id = {term["id"]: term for term in terms}
    # train_questions（学習データの質問）: 65 語 × ひな形 2 つで作り直した 130 個の集合
    train_questions = {template.format(term=term["term"]) for term in terms for template in TEMPLATES}
    problems: list[str] = []

    for item in items:
        # 確認 1: 知らない語の場合（確認 2〜5 はしない）
        if item.kind == "unknown":
            # match（「」の中を探した結果）: group(1) で「」の中の語が取れる。「」が無ければ None
            match = re.search(r"「(.+?)」", item.question)
            # 「」が無い場合
            if match is None:
                problems.append(f"知らない語の質問に「」が無い: {item.question}")
            # 「」の中の語が、用語集で見つかった場合
            elif not search_glossary(match.group(1)).startswith(NOT_FOUND_PREFIX):
                problems.append(f"知らない語が用語集で見つかった: {match.group(1)}")
            continue

        # term_id が用語集に無い場合（定義を引けないので、確認 2〜5 はしない）
        if item.term_id not in by_id:
            problems.append(f"用語集に無い id: {item.term_id}")
            continue

        # 確認 2: 同じ文の質問が、その語の学習データの質問と違う場合
        expected_question = TEMPLATES[0].format(term=by_id[item.term_id]["term"])
        if item.kind == "same" and item.question != expected_question:
            problems.append(f"同じ文の質問が {item.term_id} の学習データの質問と違う: {item.question}")

        # 確認 3: 言い換えの質問が、学習データの質問と同じ場合
        if item.kind == "paraphrase" and item.question in train_questions:
            problems.append(f"言い換えの質問なのに学習データにある: {item.question}")

        # 確認 4: 必須語句が 1 つでも自分の定義に無い場合
        own_definition = by_id[item.term_id]["definition"]
        if not all(word in own_definition for word in item.must_include):
            problems.append(f"必須語句が自分の定義に無い: {item.term_id} {list(item.must_include)}")

        # 確認 5: ほかの語の定義に、必須語句がすべてそろう場合
        for term in terms:
            if term["id"] != item.term_id and all(word in term["definition"] for word in item.must_include):
                problems.append(f"{item.term_id} の必須語句が {term['id']} の定義にもそろう")

    return problems


def main() -> int:
    """
    テスト問題を確かめ、問題が無ければ検索結果を付けてファイルに書き出す関数。

    Returns:
        終了コード。書き出せたら 0、問題が見つかったら 1。
    """
    # 用語集を読み、22 問を 5 つの確認で調べて、見つかった問題の文のリストを受け取る
    problems = find_problems(TEST_ITEMS, load_glossary())
    # 問題がある場合: 表示して、ファイルは書き出さずに終える
    if problems:
        # 問題の文を 1 行ずつ、標準エラー（エラー用の出力先）に表示する
        print("\n".join(problems), file=sys.stderr)
        # 終了コード 1（失敗）を返す
        return 1

    # 1 問ずつ、質問の文をそのまま講座の検索に渡し、結果を付ける
    records = [item.to_json_dict(search_glossary(item.question)) for item in TEST_ITEMS]
    # ensure_ascii=False で、日本語をそのまま書き出す
    OUTPUT.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # 書き出した問題の数と、リポジトリのルートから見たファイルの場所を表示する
    print(f"問題なし。{len(records)} 問を {OUTPUT.relative_to(REPO_ROOT).as_posix()} に書き出した")
    # 終了コード 0（成功）を返す
    return 0


# 直接実行した場合: main() の戻り値（0 か 1）を終了コードにして終える
if __name__ == "__main__":
    sys.exit(main())
