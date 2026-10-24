"""법령 상호참조 그래프 데이터 생성.

사용: python build_graph.py "보험업법" data/insurance.json

노드: 법 조문(L), 시행령 조문(D), 시행규칙 조문(R), 판례(P), 외부 법령(X)
엣지: delegates(위임), cites(조문 인용), external(타법 인용), precedent(판례→조문)
"""
import json
import pathlib
import re
import sys

import lawapi as L

HEAD = {"L": "법", "D": "영", "R": "규칙"}
SUFFIX = {"L": "", "D": " 시행령", "R": " 시행규칙"}

ART = re.compile(r"제\s?(\d+)\s?조(?:\s?의\s?(\d+))?")
SUB = re.compile(r"제\s?\d+\s?(?:항|호)(?:\s?의\s?\d+)?|[가-하]목")
CONNECTIVE = re.compile(r"^[\s,ㆍ·~\-]*(?:(?:및|또는|부터|까지|와|과|내지|이나|나)[\s,ㆍ·]*)*$")


def art_id(prefix, no, sub):
    return f"{prefix}:{int(no)}" + (f"-{int(sub)}" if sub and int(sub) else "")


def art_label(prefix, no, sub):
    return f"{HEAD[prefix]} 제{int(no)}조" + (f"의{int(sub)}" if sub and int(sub) else "")


def flatten(node):
    """조문단위 dict 안의 모든 '...내용' 문자열을 순서대로 모은다."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k.endswith("내용"):
                if isinstance(v, str):
                    out.append(v)
                elif isinstance(v, list):
                    out.extend(flatten(v))
            elif isinstance(v, (dict, list)):
                out.extend(flatten(v))
    elif isinstance(node, list):
        for x in node:
            out.extend(flatten(x) if not isinstance(x, str) else [x])
    return out


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)            # <개정 ...>, <br/>
    for _ in range(3):
        text = re.sub(r"\([^()]*\)", "", text)       # 괄호 안 단서·개정 연혁
    return re.sub(r"[ \t]+", " ", text)


def find_mst(name):
    d = L.search("law", name, display=50)["LawSearch"]
    for x in L.as_list(d.get("law")):
        if x["법령명한글"] == name and x["현행연혁코드"] == "현행":
            return x["법령일련번호"]
    return None


def load_articles(mst, prefix):
    law = L.service("law", MST=mst)["법령"]
    arts, chapter = [], ""
    for u in L.as_list(law["조문"]["조문단위"]):
        if u["조문여부"] != "조문":
            m = re.search(r"제\d+장\s*(.+)", u.get("조문내용", ""))
            if m:
                chapter = re.sub(r"\s*<.*", "", m.group(0)).strip()
            continue
        no, sub = u["조문번호"], u.get("조문가지번호") or "0"
        parts = flatten(u)
        body = "\n".join(p.strip() for p in parts if p.strip())
        title = u.get("조문제목", "")
        arts.append({
            "id": art_id(prefix, no, sub),
            "label": art_label(prefix, no, sub),
            "title": title,
            "chapter": chapter,
            "deleted": "삭제" in parts[0][:40] and not title,
            "text": body,
        })
    return law["기본정보"], arts


def law_refs(text, prefix, self_id, main):
    """법령 본문에서 조문 참조 추출. 반환: [(대상, kind)] — 대상은 노드 id 또는 'X:법령명'."""
    own_names = {main + SUFFIX[p]: p for p in HEAD}
    text = clean(text)
    refs, prev_end, cur, last_ext = [], 0, None, None
    first = True
    for m in ART.finditer(text):
        gap = text[prev_end:m.start()]
        prev_end = m.end()
        if first and m.start() < 3:          # 조문 머리의 자기 번호
            first = False
            continue
        first = False
        g = SUB.sub("", gap)
        if cur is not None and CONNECTIVE.match(g):
            target = cur
        else:
            ext = re.search(r"「([^」]+)」\s*$", gap)
            if ext:
                name = ext.group(1).strip()
                target = own_names.get(name, "X:" + name)
                if target.startswith("X:"):
                    last_ext = target
            elif re.search(r"같은 법\s*$", gap) and last_ext:
                target = last_ext
            elif prefix != "L" and re.search(r"(?<![가-힣])법\s*$", gap):
                target = "L"
            elif prefix == "R" and re.search(r"(?<![가-힣])영\s*$", gap):
                target = "D"
            else:
                target = prefix
        cur = target
        if target.startswith("X:"):
            refs.append((target, "external"))
        else:
            tid = art_id(target, m.group(1), m.group(2))
            if tid != self_id:
                refs.append((tid, "cites"))
    return refs


def prec_refs(text, main):
    """판례 텍스트에서 이 법령 계열 조문만 추출(엄격: 법령명 직후 또는 연결어로 이어진 것만)."""
    name = r"\s*".join(map(re.escape, main.replace(" ", "")))
    own_end = re.compile(rf"(?<![가-힣])({name}(?:\s*시행령|\s*시행규칙)?)\s*(?:은|는|이|가|의|에|에서|상|및|,)?\s*$")
    text = clean(text)
    refs, prev_end, cur = set(), 0, None
    for m in ART.finditer(text):
        gap = text[prev_end:m.start()]
        prev_end = m.end()
        g = SUB.sub("", re.sub(r"\[\d+\]|/", " ", gap))
        own = own_end.search(gap)
        if own:
            cur = "R" if "시행규칙" in own.group(1) else "D" if "시행령" in own.group(1) else "L"
        elif cur is not None and (CONNECTIVE.match(g) or re.search(r"(같은 법|동법)\s*$", gap)):
            pass
        else:
            cur = None
        if cur:
            refs.add(art_id(cur, m.group(1), m.group(2)))
    return refs


def three_tier(law_mst):
    d = L.service("thdCmp", MST=law_mst, knd="2")
    body = d["LspttnThdCmpLawXService"]["위임조문삼단비교"]["법률조문"]
    edges = set()
    for row in L.as_list(body):
        if not row.get("조제목"):
            continue
        src = art_id("L", row["조번호"], row.get("조가지번호"))
        for key, p in (("시행령조문", "D"), ("시행규칙조문", "R")):
            for sub in L.as_list(row.get(key)):
                if sub and sub.get("조번호"):
                    edges.add((src, art_id(p, sub["조번호"], sub.get("조가지번호"))))
    return edges


def precedents(main):
    seen, out = set(), []
    for page in range(1, 11):
        d = L.search("prec", main, search="2", display=100, page=page)["PrecSearch"]
        items = L.as_list(d.get("prec"))
        if not items:
            break
        for it in items:
            if it["판례일련번호"] in seen:
                continue
            seen.add(it["판례일련번호"])
            out.append(it)
    return out


def main(main_name, out_path):
    tiers = {}
    for p in HEAD:
        mst = find_mst(main_name + SUFFIX[p])
        if mst:
            tiers[p] = (mst, *load_articles(mst, p))
    if "L" not in tiers:
        sys.exit(f"법령을 찾지 못함: {main_name}")
    all_arts = [a for _, _, arts in tiers.values() for a in arts]
    nodes = {a["id"]: {**a, "kind": a["id"][0]} for a in all_arts}
    edges = {}

    def add_edge(s, t, kind, **extra):
        key = (s, t, kind)
        if key in edges:
            edges[key]["weight"] += 1
        else:
            edges[key] = {"source": s, "target": t, "kind": kind, "weight": 1, **extra}

    def ghost(nid):
        if nid not in nodes:
            p, rest = nid.split(":")
            no, _, sub = rest.partition("-")
            nodes[nid] = {"id": nid, "kind": p, "label": art_label(p, no, sub or "0"),
                          "title": "현행 조문에 없음(구법 조문 번호)", "chapter": "",
                          "deleted": True, "ghost": True, "text": ""}

    for s, t in three_tier(tiers["L"][0]):
        if s in nodes and t in nodes:
            add_edge(s, t, "delegates")

    for a in all_arts:
        for tgt, kind in law_refs(a["text"], a["id"][0], a["id"], main_name):
            if kind == "external":
                if tgt not in nodes:
                    nodes[tgt] = {"id": tgt, "kind": "X", "label": tgt[2:], "title": "", "chapter": "", "text": ""}
                add_edge(a["id"], tgt, "external")
            elif tgt in nodes:
                add_edge(a["id"], tgt, "cites")

    max_no = {p: max(int(a["id"][2:].split("-")[0]) for a in arts) for p, (_, _, arts) in tiers.items()}
    precs = precedents(main_name)
    print(f"precedents listed: {len(precs)}", file=sys.stderr)
    basis_count = {"참조조문": 0, "판결요지": 0, "판례내용": 0, "없음": 0}
    for i, it in enumerate(precs):
        try:
            p = L.service("prec", ID=it["판례일련번호"])["PrecService"]
        except Exception as e:  # noqa: BLE001
            print("skip", it["사건번호"], e, file=sys.stderr)
            continue
        refs, basis = set(), "없음"
        for field, label in (("참조조문", "참조조문"), (None, "판결요지"), ("판례내용", "판례내용")):
            txt = p.get(field, "") if field else (p.get("판시사항", "") + " " + p.get("판결요지", ""))
            # 현행 최대 조번호를 넘는 번호는 다른 법 조문을 잘못 잡은 것으로 보고 버림
            refs = {r for r in prec_refs(txt or "", main_name)
                    if r[0] in max_no and int(r[2:].split("-")[0]) <= max_no[r[0]]}
            if refs:
                basis = label
                break
        basis_count[basis] += 1
        if not refs:
            continue
        pid = "P:" + it["판례일련번호"]
        summary = clean(p.get("판시사항") or "").strip()
        nodes[pid] = {
            "id": pid, "kind": "P",
            "label": it["사건번호"],
            "title": it.get("사건명", ""),
            "court": it.get("법원명", ""),
            "date": it.get("선고일자", ""),
            "caseType": it.get("사건종류명", ""),
            "basis": basis,
            "text": summary[:700],
            "url": f"https://www.law.go.kr/precInfoP.do?precSeq={it['판례일련번호']}",
        }
        for r in refs:
            ghost(r)
            add_edge(pid, r, "precedent", basis=basis)
        if i % 50 == 0:
            print(f"  {i}/{len(precs)}", file=sys.stderr)

    def info(p):
        i = tiers[p][1]
        return {"name": i["법령명_한글"], "efYd": i["시행일자"], "promul": i["공포일자"]}

    meta = {
        "main": main_name,
        "tiers": {p: info(p) for p in tiers},
        "precedentsListed": len(precs),
        "precedentBasis": basis_count,
        "source": "법제처 국가법령정보 공동활용 Open API (DRF)",
    }
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"meta": meta, "nodes": list(nodes.values()), "edges": list(edges.values())},
                              ensure_ascii=False), encoding="utf-8")
    count = lambda xs, k: {v: sum(1 for x in xs if x[k] == v) for v in sorted({x[k] for x in xs})}
    print("nodes", count(list(nodes.values()), "kind"), "edges", count(list(edges.values()), "kind"), "basis", basis_count)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
