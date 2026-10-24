"""여러 법령을 엮은 그래프 데이터 생성. 각 법령의 data/*.json(build_graph.py 결과)을 먼저 만들어 둔다.

사용: python build_multi.py data/multi-commercial.json 상법=data/commercial.json \\
          보험업법=data/insurance.json "근로자퇴직급여 보장법=data/retirement.json:퇴직급여법"
      첫 법령이 가운데에 놓인다. ':' 뒤는 판결문 약칭(쉼표로 여러 개).

노드: 각 법의 법 조문 전체, 다른 법과 이어진 시행령·시행규칙 조문, 두 법 이상을 다룬 판례
엣지: cross(법 사이 조문 인용), precedent(판례→조문)
"""
import json
import pathlib
import re
import sys

import build_graph as B
import lawapi as L


def cross_refs(text, names, own):
    """조문 본문에서 다른 법령(names: 법령명 → (법 키, 단계))의 조문 인용을 뽑는다."""
    text = B.clean(text)
    out, prev, cur, last = [], 0, None, None
    for m in B.ART.finditer(text):
        gap = text[prev:m.start()]
        prev = m.end()
        ext = re.search(r"「([^」]+)」\s*$", gap)
        if ext:
            cur = names.get(ext.group(1).strip())
            last = cur
        elif cur and B.CONNECTIVE.match(B.SUB.sub("", gap)):
            pass
        elif re.search(r"같은 법\s*$", gap) and last:
            cur = last
        else:
            cur = None
        if cur and cur[0] != own:
            out.append((cur[0], B.art_id(cur[1], m.group(1), m.group(2))))
    return out


def main(out_path, specs):
    laws = []
    for i, spec in enumerate(specs):
        name, _, rest = spec.partition("=")
        path, _, alias = rest.partition(":")
        data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
        key = "k%d" % i
        laws.append({"key": key, "name": name, "aliases": [a.strip() for a in alias.split(",") if a.strip()],
                     "page": pathlib.Path(path).stem + ".html", "data": data})
    names = {}
    for lw in laws:
        for p, suf in B.SUFFIX.items():
            names[lw["name"] + suf] = (lw["key"], p)
    # 판례가 옛 조문 번호로 가리킨 자리(ghost)는 현행 조문이 아니므로 뺀다
    art = {lw["key"]: {n["id"]: n for n in lw["data"]["nodes"] if n["kind"] in "LDR" and not n.get("ghost")} for lw in laws}
    # 하위 법령 조문은 위임 근거 법 조문 쪽에 놓기 위해 근거를 기억해 둔다
    parent = {lw["key"]: {} for lw in laws}
    for lw in laws:
        for e in lw["data"]["edges"]:
            if e["kind"] == "delegates":
                parent[lw["key"]].setdefault(e["target"], e["source"])

    edges = {}

    def add(s, t, kind):
        k = (s, t, kind)
        if k in edges:
            edges[k]["weight"] += 1
        else:
            edges[k] = {"source": s, "target": t, "kind": kind, "weight": 1}

    used = set()
    for lw in laws:
        for n in art[lw["key"]].values():
            for k2, tid in cross_refs(n.get("text", ""), names, lw["key"]):
                if tid in art[k2]:
                    s, t = lw["key"] + "|" + n["id"], k2 + "|" + tid
                    add(s, t, "cross")
                    used.update((s, t))

    # 판례: 각 법의 판례 목록을 모두 모아, 판결문에서 모든 법의 조문을 다시 뽑는다
    max_no = {lw["key"]: {} for lw in laws}
    for lw in laws:
        for i in art[lw["key"]]:
            p, rest = i.split(":")
            max_no[lw["key"]][p] = max(max_no[lw["key"]].get(p, 0), int(rest.split("-")[0]))
    seen, precs = set(), []
    for lw in laws:
        for it in B.precedents(lw["name"])[0]:
            if it["판례일련번호"] not in seen:
                seen.add(it["판례일련번호"])
                precs.append(it)
    nodes_p = []
    for it in precs:
        try:
            p = L.service("prec", ID=it["판례일련번호"])["PrecService"]
        except Exception:  # noqa: BLE001  본문 없는 판례
            continue
        got = {}
        for lw in laws:
            for field in ("참조조문", None, "판례내용"):
                txt = p.get(field, "") if field else (p.get("판시사항", "") + " " + p.get("판결요지", ""))
                refs = {r for r in B.prec_refs(txt or "", lw["name"], lw["aliases"])
                        if r in art[lw["key"]] and int(r[2:].split("-")[0]) <= max_no[lw["key"]].get(r[0], 0)}
                if refs:
                    got[lw["key"]] = refs
                    break
        if len(got) < 2:
            continue
        pid = "P|" + it["판례일련번호"]
        nodes_p.append({
            "id": pid, "law": "P", "kind": "P", "label": B.prec_field(it, p, "사건번호"), "title": it.get("사건명", ""),
            "court": B.prec_field(it, p, "법원명"), "date": B.prec_date(it, p),
            "text": B.clean(p.get("판시사항") or "").strip()[:700],
            "url": f"https://www.law.go.kr/precInfoP.do?precSeq={it['판례일련번호']}",
        })
        for k, refs in got.items():
            for r in refs:
                add(pid, k + "|" + r, "precedent")
                used.add(k + "|" + r)

    nodes = []
    for lw in laws:
        for i, n in art[lw["key"]].items():
            nid = lw["key"] + "|" + i
            if n["kind"] != "L" and nid not in used:
                continue
            nodes.append({"id": nid, "law": lw["key"], "kind": n["kind"], "label": n["label"], "title": n.get("title", ""),
                          "chapter": n.get("chapter", ""), "deleted": bool(n.get("deleted")), "text": n.get("text", ""),
                          **({"anchor": lw["key"] + "|" + parent[lw["key"]][i]} if i in parent[lw["key"]] else {})})
    nodes += nodes_p
    meta = {
        "laws": [{"key": lw["key"], "name": lw["name"], "page": lw["page"], "tiers": lw["data"]["meta"]["tiers"]} for lw in laws],
        "precedentsChecked": len(precs),
        "source": "법제처 국가법령정보 공동활용 Open API (DRF)",
    }
    out = pathlib.Path(out_path)
    out.write_text(json.dumps({"meta": meta, "nodes": nodes, "edges": list(edges.values())}, ensure_ascii=False), encoding="utf-8")
    pairs = {}
    for e in edges.values():
        a = e["source"].split("|")[0]
        b = e["target"].split("|")[0]
        pairs[(e["kind"], a, b)] = pairs.get((e["kind"], a, b), 0) + e["weight"]
    print(out, "nodes", len(nodes), "precedents", len(nodes_p), "edges", pairs)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
