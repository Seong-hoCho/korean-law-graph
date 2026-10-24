"""데이터와 생성 파일 점검. 문제가 있으면 목록을 출력하고 1로 끝난다.

사용: python check.py
  1) data/*.json: 끊긴 연결, 이상한 판례 날짜, 각주에 필요한 메타 정보, 축소 그림
  2) docs/*.html·docs/index.html·README.md를 다시 만들어, 커밋된 내용과 같은지(생성물이 최신인지)
     git 작업 트리가 깨끗한 상태에서 돌려야 2)가 의미 있다. 다시 만든 결과는 그대로 남는다.
"""
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
problems = []


def check_data(page, data):
    ids = {n["id"] for n in data["nodes"]}
    dangling = [e for e in data["edges"] if e["source"] not in ids or e["target"] not in ids]
    if dangling:
        problems.append(f"{page}: 양 끝 노드가 없는 연결 {len(dangling)}개 (예: {dangling[0]['source']} → {dangling[0]['target']})")
    bad = [n["label"] for n in data["nodes"] if n["kind"] == "P" and n.get("date") and not re.match(r"(19|20)\d\d\.\d\d\.\d\d$", n["date"])]
    if bad:
        problems.append(f"{page}: 형식이 이상한 판례 선고일 {len(bad)}건 (예: {bad[0]})")
    meta = data["meta"]
    need = ["laws", "precedentsChecked"] if "laws" in meta else ["main", "tiers", "precedentsListed", "precedentsTotal", "precedentsUnavailable", "precedentBasis"]
    miss = [k for k in need if k not in meta]
    if miss:
        problems.append(f"{page}: 메타 정보 없음 {miss} → build_graph.py로 다시 빌드")
    if not (HERE / "docs" / "thumbs" / f"{page}.svg").exists():
        problems.append(f"{page}: 축소 그림 없음 → node tools/thumbs.js {page}")


def main():
    maps = json.loads((HERE / "maps.json").read_text(encoding="utf-8"))
    for m in maps:
        path = HERE / "data" / f"{m['page']}.json"
        if not path.exists():
            problems.append(f"{m['page']}: {path.name} 없음")
            continue
        check_data(m["page"], json.loads(path.read_text(encoding="utf-8")))
    listed = {m["page"] for m in maps}
    for html in (HERE / "docs").glob("*.html"):
        if html.stem != "index" and html.stem not in listed:
            problems.append(f"docs/{html.name}: maps.json에 없어 첫 화면에 카드가 없음")

    for m in maps:
        if (HERE / "data" / f"{m['page']}.json").exists():
            subprocess.run([sys.executable, "make_page.py", f"data/{m['page']}.json", f"docs/{m['page']}.html"], cwd=HERE, check=True, capture_output=True)
    subprocess.run([sys.executable, "make_index.py"], cwd=HERE, check=True, capture_output=True)
    changed = subprocess.run(["git", "status", "--porcelain", "--", "docs", "README.md"], cwd=HERE, capture_output=True, text=True).stdout.strip()
    if changed:
        problems.append("다시 만든 파일이 커밋된 내용과 다름 (템플릿·데이터를 바꾼 뒤 make_page.py / make_index.py를 안 돌림):\n    "
                        + changed.replace("\n", "\n    "))

    if problems:
        print("점검 실패:")
        for p in problems:
            print(" -", p)
        sys.exit(1)
    print(f"점검 통과: 지도 {len(maps)}개")


if __name__ == "__main__":
    main()
