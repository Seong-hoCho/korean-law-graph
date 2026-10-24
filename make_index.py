"""첫 화면(docs/index.html)의 지도 카드와 README의 지도 목록을 데이터에서 다시 만든다.

사용: python make_index.py
      maps.json에 적힌 순서대로, data/<page>.json을 읽어 카드의 숫자와 설명을 채운다.
      index.html과 README.md에서 <!-- maps:start --> ~ <!-- maps:end --> 사이만 바꾼다.
"""
import html as H
import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
SITE = "https://seong-hocho.github.io/korean-law-graph/"
START, END = "<!-- maps:start -->", "<!-- maps:end -->"
TIER = {"L": ("법", "law"), "D": ("시행령", "decree"), "R": ("시행규칙", "rule"), "P": ("판례", "prec")}
LAW_VAR = ["law", "rule", "decree", "ext"]  # multi_template.html 의 법별 색 순서와 같다


def josa(word, pair):
    """받침 유무로 조사 고르기: josa('제8조', '와과') → '와'. 끝의 괄호 설명은 빼고 본다: '제71조(벌칙)' → '조'."""
    word = re.sub(r"\([^()]*\)\s*$", "", word)
    for ch in reversed(word):
        if ch.isdigit():  # 숫자는 읽는 소리로: 일·삼·육·칠·팔·영은 받침이 있다
            return pair[1] if ch in "136780" else pair[0]
        if "가" <= ch <= "힣":
            return pair[1] if (ord(ch) - 0xAC00) % 28 else pair[0]
    return pair[0]


def art_phrase(n):
    no = n["label"].replace("법 ", "")
    if n.get("deleted"):
        m = re.search(r"삭제\s*<\s*(\d{4})", n.get("text", ""))
        return f"{m.group(1)}년에 삭제된 {no}" if m else f"삭제된 {no}"
    return f"{no}({n['title']})" if n.get("title") else no


def single(data):
    nodes, meta = data["nodes"], data["meta"]
    cnt = {k: sum(1 for n in nodes if n["kind"] == k and not n.get("ghost")) for k in TIER}
    nums = [(TIER[k][1], f"{TIER[k][0]} {cnt[k]:,}{'건' if k == 'P' else '조'}") for k in TIER if cnt[k]]
    prec = {}
    for e in data["edges"]:
        if e["kind"] == "precedent":
            prec[e["target"]] = prec.get(e["target"], 0) + 1
    by_id = {n["id"]: n for n in nodes}
    top = [by_id[i] for i, _ in sorted(prec.items(), key=lambda x: -x[1]) if i.startswith("L:") and not by_id[i].get("ghost")][:2]
    lead = "최근 판례가" if meta.get("precedentsTotal", 0) > meta.get("precedentsListed", 0) else "판례가"
    if len(top) == 2:
        a, b = art_phrase(top[0]), art_phrase(top[1])
        text = f"{lead} 가장 많이 다룬 조문은 {a}{josa(a, '와과')} {b}입니다."
    elif top:
        text = f"{lead} 가장 많이 다룬 조문은 {art_phrase(top[0])}입니다."
    else:
        text = ""
    readme = " · ".join(t for _, t in nums)
    if meta.get("precedentsTotal", 0) > meta.get("precedentsListed", 0):
        readme += f" (본문에 {meta['main']}이 나오는 판례 {meta['precedentsTotal']:,}건 중 최근 {meta['precedentsListed']:,}건에서 추출)"
    return meta["main"], nums, text, readme


def multi(data):
    laws, nodes = data["meta"]["laws"], data["nodes"]
    name = {l["key"]: l["name"] for l in laws}
    pair = {}
    for e in data["edges"]:
        if e["kind"] == "cross":
            k = (e["source"].split("|")[0], e["target"].split("|")[0])
            pair[k] = pair.get(k, 0) + e["weight"]
    links = ", ".join(f"{name[a]} → {name[b]} {c:,}곳" for (a, b), c in sorted(pair.items(), key=lambda x: -x[1]))
    nprec = sum(1 for n in nodes if n["kind"] == "P")
    names = "·".join(name[l["key"]] for l in laws)
    text = (f"{names} 사이에서 서로의 조문을 가리키는 곳과 여러 법을 함께 다룬 판례를 한 그림에 모았습니다. "
            f"법 사이 인용은 {links}이고, 두 법 이상을 함께 다룬 판례는 {nprec:,}건입니다.")
    nums = [(LAW_VAR[i % len(LAW_VAR)], l["name"]) for i, l in enumerate(laws)]
    title = f"{laws[0]['name']} 중심 관련 법령 지도"
    readme = f"{names} 사이의 조문 인용 {sum(pair.values()):,}곳과, 두 법 이상을 함께 다룬 판례 {nprec:,}건"
    return title, nums, text, readme


def card(page, title, nums, text, wide):
    dots = "".join(f'<span><span class="dot" style="background:var(--{v})"></span>{H.escape(t)}</span>' for v, t in nums)
    img = f'<img src="thumbs/{page}.svg" alt="" width="600" height="600" loading="lazy">'
    body = f'<h2>{H.escape(title)}</h2>\n      <div class="nums">{dots}</div>\n      <p>{H.escape(text)}</p>'
    if wide:
        return f'  <a class="map wide" href="{page}.html">\n    {img}\n    <div class="wide-body">\n      {body}\n    </div>\n  </a>'
    return f'    <a class="map" href="{page}.html">\n      {img}\n      {body}\n    </a>'


def replace_block(path, block):
    s = path.read_text(encoding="utf-8")
    i, j = s.index(START) + len(START), s.index(END)
    path.write_text(s[:i] + "\n" + block + "\n" + s[j:], encoding="utf-8")


def main():
    maps = json.loads((HERE / "maps.json").read_text(encoding="utf-8"))
    wide, cards, readme = [], [], []
    for m in maps:
        data = json.loads((HERE / "data" / f"{m['page']}.json").read_text(encoding="utf-8"))
        title, nums, text, rd = (multi if "laws" in data["meta"] else single)(data)
        (wide if m.get("wide") else cards).append(card(m["page"], title, nums, text, m.get("wide")))
        readme.append(f"  - [{title}]({SITE}{m['page']}.html): {rd}")
    block = "\n".join(wide) + ("\n" if wide else "") + '  <section class="maps">\n' + "\n".join(cards) + "\n  </section>"
    replace_block(HERE / "docs" / "index.html", block)
    replace_block(HERE / "README.md", "\n".join(readme))
    print("index.html:", len(wide) + len(cards), "cards")


if __name__ == "__main__":
    main()
