"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
import re
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LEARNING_LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を複数まとめて入れる。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回の用語から確認問題を1問作る。

    「第2回の確認問題を出して」のように、講座の用語について出題するときに使う。
    lecture には対象の回を整数で指定する。
    """
    # 用語集から指定した回の用語だけを集める
    terms = [term for term in load_glossary() if term["lecture"] == lecture]

    # 指定した回の用語が見つからない場合
    if not terms:
        return f"第{lecture}回の用語が見つかりません。"

    # 用語が見つかった場合
    term = random.choice(terms)
    quiz = {
        "question": f"「{term['term']}」の意味は？",
        "answer": term["definition"],
    }
    return json.dumps(quiz, ensure_ascii=False)


def _learning_log_slug(title: str) -> str:
    """内容を表すタイトルをファイル名に使える形式へ整える。"""
    # タイトルがMarkdown見出しでも、ファイル名には見出し記号を含めない
    title = re.sub(r"^#{1,6}\s*", "", title.strip())
    # 日本語などの文字・数字・ハイフン以外の連続を、区切りのハイフンに置き換える
    slug = re.sub(r"[^\w-]+", "-", title, flags=re.UNICODE)
    # ハイフンの連続と両端の記号を整え、ファイル名が長くなりすぎないよう40文字に制限する
    slug = re.sub(r"-+", "-", slug).strip("-_")[:40].rstrip("-_")
    # タイトルが空、または記号だけだった場合に使う既定名
    return slug or "学習記録"


def save_learning_log(content: str, title: str) -> str:
    """学習の振り返りを learning_log/ にMarkdownファイルとして保存する。

    title には本文全体の内容を表す短い名前を指定する。日時とtitleからファイル名を
    作り、contentを保存する。同名ファイルがある場合は上書きせずエラーにする。
    保存前の確認はアプリ側で行う設定で使う。
    """
    LEARNING_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{timestamp}_{_learning_log_slug(title)}.md"
    path = LEARNING_LOG_DIR / filename

    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(content)
            # 本文が改行で終わっていない場合
            if not content.endswith("\n"):
                file.write("\n")
    except FileExistsError as error:
        raise FileExistsError(f"学習記録を上書きしないため保存を中止しました: {path}") from error

    return f"学習記録を {path.as_posix()} に保存しました。"
