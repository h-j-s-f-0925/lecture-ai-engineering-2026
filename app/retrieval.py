"""第5回: ページ単位のベクトル検索。"""

import argparse
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from collections import defaultdict, deque
from pathlib import Path

from google import genai
from google.genai import types
from pydantic_ai.exceptions import ModelHTTPError
import sqlite_vec

from app.config import (
    EMBEDDING_DIMENSIONS, EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL,
    RAG_DB, RAG_DOCUMENT_IDS, RAG_SOURCE, RAG_TOP_K, RAG_TREE, get_api_key,
    RAG_GRAPH, GRAPH_START_K, GRAPH_HOPS, GRAPH_MAX_RESULTS,
)


def get_all_materials() -> str:
    """全資料を、講義・章・ページの情報付きで1つの文字列にまとめる。"""
    documents = json.loads(RAG_SOURCE.read_text(encoding="utf-8"))
    return "\n\n".join(
        f"資料: {document['id']} / {document['title']}\n"
        f"章: {section['section']}\n"
        f"ページ: PDF p.{page['page']} / {page['title']}\n{page['content']}"
        for document in documents
        for section in document["content"]
        for page in section["content"]
    )

def load_pages(source: Path = RAG_SOURCE) -> list[dict]:
    """資料→章→ページのJSONを、対象資料のページ一覧に変換する。"""
    documents = json.loads(source.read_text(encoding="utf-8"))
    pages = []
    for document in documents:
        if document["id"] not in RAG_DOCUMENT_IDS:
            continue
        for section in document["content"]:
            for page in section["content"]:
                pages.append({"page_id": page["id"], "document_id": document["id"],
                              "lecture": int(document["id"][3:5]), "document_title": document["title"],
                              "section": section["section"], "title": page["title"],
                              "page": page["page"], "content": page["content"]})
    return pages


def browse_tree(node_id: str | None = None) -> dict:
    """直下のページは先頭文、指定したページ自身は全文を返す。"""
    tree = json.loads(RAG_TREE.read_text(encoding="utf-8"))
    tree["children"] = [node for node in tree["children"] if node["id"] in RAG_DOCUMENT_IDS]
    node_id = node_id or tree["id"]
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}

    def describe(node, full=False):
        info = {key: node[key] for key in ("id", "kind", "title")}
        if node["kind"] == "page":
            info.update({key: value for key, value in pages[node["id"]].items() if key != "page_id"})
            if not full:
                info["content"] = re.split(r"(?<=[。！？])|\n", info["content"].strip(), maxsplit=1)[0]
        return info

    remaining = [tree]
    while remaining:
        node = remaining.pop()
        if node["id"] == node_id:
            return {
                "node": describe(node, full=True),
                "children": [describe(child) for child in node.get("children", [])],
            }
        remaining.extend(node.get("children", []))
    raise ValueError("対象の目次ノードが見つかりません。")


def read_page(page_id: str) -> dict:
    """第1〜3回の本講義から、指定した1ページの本文と引用情報を返す。"""
    for page in load_pages(RAG_SOURCE):
        if page["page_id"] == page_id:
            return page
    raise ValueError("対象のページが見つかりません。")


def normalized_vector(values: list[float]) -> list[float]:
    """ベクトルの長さを1に揃える。"""
    norm = math.hypot(*values)
    if norm == 0:
        raise ValueError("埋め込みがゼロベクトルです。")
    return [value / norm for value in values]


def embed_text(text: str, task_type: str) -> list[float]:
    """Geminiで文章を埋め込む。入力上限を超えた場合は切り捨てず停止する。"""
    with genai.Client(api_key=get_api_key()) as client:
        count = client.models.count_tokens(model=EMBEDDING_MODEL, contents=text).total_tokens
        if count is None or count > EMBEDDING_MAX_TOKENS:
            raise ValueError(f"埋め込み入力が上限を超えるか計測不能です: {count} tokens。")
        response = client.models.embed_content(
            model=EMBEDDING_MODEL, contents=text,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
        )
    embedding = response.embeddings[0]
    if embedding.statistics and embedding.statistics.truncated:
        raise ValueError("埋め込みAPIが本文を切り捨てました。")
    return normalized_vector(embedding.values)


@contextmanager
def open_index(path: Path):
    """既存の検索DBを読み取り専用で開き、終了時に閉じる。"""
    if not path.is_file():
        raise FileNotFoundError("検索DBがありません。")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        yield db
    finally:
        db.close()


def search(query: str) -> list[dict]:
    """質問を埋め込み、近いページを最大RAG_TOP_K件返す。"""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("検索語が空です。")
    with open_index(RAG_DB) as db:
        vector = embed_text(query.strip(), "RETRIEVAL_QUERY")
        rows = db.execute("""
            SELECT page_id, document_id, lecture, document_title, section, title, page, content,
                   vec_distance_cosine(embedding, ?) AS distance
            FROM chunks ORDER BY distance, page_id LIMIT ?
        """, (sqlite_vec.serialize_float32(vector), RAG_TOP_K))
        return [dict(row) for row in rows]


def search_graph(query: str) -> dict:
    """
    ベクトル検索で見つけたページから、前後ページと共通用語をたどって候補を広げる関数

    ベクトル検索の上位 GRAPH_START_K 件を、グラフをたどり始めるページ（出発点、seed）にし、幅優先探索で
    GRAPH_HOPS 歩以内のページを集める。ベクトル検索だけでは拾えない隣のページや、
    同じ用語を扱う別の回のページを補うために使う。
    たどる関係は next_page（前後のページ）と mentions（ページが言及する用語）の2種類だけ。

    Args:
        query: 出発点を選ぶベクトル検索の検索語

    Returns:
        次のキーを持つ辞書。seeds と expanded は合わせて最大 GRAPH_MAX_RESULTS 件
        - seeds: 出発点のページ。質問との距離 distance を持つ
        - expanded: たどって見つけたページ。歩数 hops と出発点からの道のり path を持つ
        - max_hops: たどった最大の歩数

    Raises:
        ValueError: 検索語が空の場合（search() から送出される）
        FileNotFoundError: 検索DBがない場合（search() から送出される）
    """
    # pages（対象ページ表）: ページIDを指定すると、そのページの本文・タイトルなどが取れる辞書。
    # 例: pages["lec02-main-p052"] で第2回 p.52 の情報が取れる。対象は第1〜3回の本講義214ページ
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}
    # graph（講義資料グラフ）: 点（ノード）の一覧 nodes と、ノードどうしを結ぶ線の一覧 edges を持つ
    graph = json.loads(RAG_GRAPH.read_text(encoding="utf-8"))
    # nodes（使うノードの表）: ノードID（ページIDか、"term:lora" のような用語ID）を指定すると、そのノードの情報が取れる辞書。
    # 用語と対象ページだけを残し、演習資料などの対象外へ探索が広がらないようにする
    nodes = {node["id"]: node for node in graph["nodes"]
             if node["kind"] == "term" or node["id"] in pages}
    # adjacent（つながり表）: ノードIDを指定すると、線でつながっているノードIDの集合が取れる辞書。
    # 例: adjacent["lec02-main-p052"] は、前後の p.51・p.53 と、用語の term:lora・term:qlora・term:peft
    # defaultdict(set): 未登録のキーを読むと空の集合を作る辞書。登録済みか確かめずに .add() できる
    adjacent = defaultdict(set)
    # グラフの線を1本ずつ処理する
    for edge in graph["edges"]:
        # a, b（線の両端）: 線の始点と終点のノードID
        a, b = edge["source"], edge["target"]
        # 「次のページ」か「用語に触れている」の線で、両端とも対象ノードの場合
        if edge["relation"] in ("next_page", "mentions") and a in nodes and b in nodes:
            # 両方向に登録する。次のページから前のページへ戻れるようにし、
            # ページから用語を経由して、同じ用語に触れた別のページへ渡れるようにするため
            adjacent[a].add(b)
            adjacent[b].add(a)

    # seeds（出発点の一覧）: グラフをたどり始めるページ。ベクトル検索の上位のうち、対象ページだけを使う
    seeds = [hit for hit in search(query) if hit["page_id"] in pages][:min(GRAPH_START_K, GRAPH_MAX_RESULTS)]
    # seed_ids（出発点IDの集合）: 出発点を、たどって見つけた候補として二重に返さないために使う
    seed_ids = {seed["page_id"] for seed in seeds}
    # results（返す出発点の一覧）: 戻り値の seeds になる
    # candidates（候補表）: ページIDを指定すると、そのページの (優先度, 候補) の組が取れる辞書
    results, candidates = [], {}
    # 出発点を、rank（出発点の検索順位。0 が最上位）とともに1件ずつ処理する
    for rank, seed in enumerate(seeds):
        # root（今の出発点）: 今たどっている出発点のページID
        root = seed["page_id"]
        # 出発点は0歩目のページとして、距離付きで結果に入れる
        results.append({**pages[root], "distance": seed["distance"], "hops": 0,
                        "path": [{"id": root, "title": pages[root]["title"]}]})
        # 幅優先探索（BFS）: 出発点から1歩のノードをすべて調べてから2歩のノードへ進む、近い順のたどり方。
        # 近い順に調べるので最初に着いた道が最短になり、返す hops（歩数）と path（道のり）が正しくなる
        # queue（探索待ちの行列）: これから調べる (ノードID, 道のり) の組を、調べる順に並べたもの
        # deque: 両端の出し入れが速いキュー。popleft() で先に入れたものから取り出すと近い順になる。
        # list.pop() で後から入れたものを先に出すと深さ優先探索になり、道や歩数が変わる
        queue = deque([(root, [root])])
        # visited（訪問済みの集合）: この出発点からの探索で、すでにキューに入れたノードID。
        # 同じノードを二度調べないようにし、p.51 と p.52 の間を行ったり来たりし続けるのを防ぐ。
        # 出発点ごとに作り直すので、同じページに別の出発点から届くことがある（優先度で良い方を残す）
        visited = {root}
        # 調べるノードがキューに残っている間、繰り返す
        while queue:
            # current（調査中のノード）: 今調べているノードID
            # path（現在地までの道のり）: 出発点から current までのノードIDのリスト。len(path) - 1 が歩数
            current, path = queue.popleft()
            # 出発点から GRAPH_HOPS 歩に達している場合
            if len(path) - 1 >= GRAPH_HOPS:
                continue
            # neighbors（隣のノードの一覧）: current と線でつながっているノードIDを、つながりの数が少ない順に並べたもの。
            # 多くのページに出る一般的な用語ほど、関係の薄いページへ広がりやすいため後回しにする
            neighbors = sorted(adjacent[current], key=lambda n: (len(adjacent[n]), n))
            # neighbor（調査中の隣のノード）を1件ずつ処理する
            for neighbor in neighbors:
                # すでにキューに入れたノードの場合
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                # route（隣までの道のり）: path の後ろに neighbor を足したもの
                route = path + [neighbor]
                # 用語も、別のページへ渡る中継点としてキューに入れる
                queue.append((neighbor, route))
                # neighbor（調査中の隣のノード）がページではない（用語の）場合、または出発点のページの場合
                if neighbor not in pages or neighbor in seed_ids:
                    # 候補としては返さない
                    continue
                # frequency（経由した用語の一般さ）: route で経由した用語のうち、最も多くのノードとつながっている用語の、
                # つながりの数。一般的な用語を経由したつながりほど弱いとみなし、優先度を下げるために使う。
                # 用語を経由しない道（前後のページだけでつながる道）は 0
                frequency = max((len(adjacent[n]) for n in route if nodes[n]["kind"] == "term"), default=0)
                # priority（候補の優先度）: 小さいほど優先するタプル。左の要素から順に比べる。
                # 歩数、frequency、rank、ページID の順で、最後のページIDは、ほかがすべて同じときの決め手
                priority = (len(route) - 1, frequency, rank, neighbor)
                # candidate（候補ページ）: ページの情報に、歩数 hops と道のり path を足したもの
                candidate = {**pages[neighbor], "hops": len(route) - 1,
                             "path": [{"id": n, "title": nodes[n]["title"]} for n in route]}
                # neighbor（調査中の隣のノード）が candidates（候補表）にまだ無い、または
                # 今回の priority（候補の優先度）が、登録済みの優先度 candidates[neighbor][0] より小さい（＝優先度が高い）場合
                # （candidates[neighbor] は (優先度, 候補) の組なので、[0] で優先度を取り出す）
                if neighbor not in candidates or priority < candidates[neighbor][0]:
                    # 今回の (優先度, 候補) で登録する。登録済みなら上書きする
                    candidates[neighbor] = (priority, candidate)

    # expanded（追加ページの一覧）: candidates の候補を、優先度の順に並べたもの。戻り値の expanded になる。
    # 優先度の最後がページIDで一意なので、並べ替えで辞書どうしの比較は起きない
    expanded = [candidate for _, candidate in sorted(candidates.values())]
    # 出発点と合わせて上限件数に収める。max(0, ...) は、負の数で切って「後ろから除く」動きになるのを防ぐ
    return {"seeds": results, "expanded": expanded[:max(0, GRAPH_MAX_RESULTS - len(results))],
            "max_hops": GRAPH_HOPS}



def run_full_context(agent, question: str, model, instructions: str, prompt_template: str):
    """全資料を一括投入し、検索ツールを使わずに回答する。"""
    prompt = prompt_template.format(materials=get_all_materials(), question=question)
    print(f"[full-context] 入力{len(prompt):,}文字")
    try:
        with agent.override(tools=[], instructions=instructions):
            return agent.run_sync(prompt, model=model)
    except ModelHTTPError as e:
        print(f"[full-context] APIエラー HTTP {e.status_code}: {e.body}")
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="エージェントを使わず、講義資料の検索だけを実行する")
    parser.add_argument("query", help="調べたい内容")
    args = parser.parse_args()
    for i, result in enumerate(search(args.query), 1):
        print(f"\n{'=' * 60}\n検索結果 {i}\n{'=' * 60}")
        print(f"講義: {result['document_title']}")
        print(f"章: {result['section']}")
        print(f"タイトル: {result['title']}")
        print(f"ページ: {result['page']}")
        print(f"\n{result['content']}")
