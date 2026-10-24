"""그래프 JSON을 템플릿에 넣어 단일 HTML 페이지를 만든다.

사용: python make_page.py data/insurance.json docs/insurance.html
      python make_page.py data/multi-commercial.json docs/multi-commercial.html   (build_multi.py 결과)
      python make_page.py data/insurance.json insurance-act-graph.html --fragment   (Claude 아티팩트용)
"""
import html as H
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
HEAD = ('<!doctype html>\n<html lang="ko">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n')

args = [a for a in sys.argv[1:] if not a.startswith("--")]
fragment = "--fragment" in sys.argv
src, dst = (HERE / args[0]), (HERE / args[1])
data = json.loads(src.read_text(encoding="utf-8"))
# </script> 가 데이터 안에 있어도 깨지지 않도록
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
base = (HERE / "graph_template.html").read_text(encoding="utf-8")
if "laws" in data["meta"]:  # 여러 법령 지도(build_multi.py): 개별 지도의 CSS를 그대로 가져다 쓴다
    css = base.split("<style>", 1)[1].split("</style>", 1)[0]
    title = "·".join(l["name"] for l in data["meta"]["laws"])
    page = (HERE / "multi_template.html").read_text(encoding="utf-8")
    page = page.replace("/*__BASE_CSS__*/", css).replace("__TITLE__", H.escape(data["meta"]["laws"][0]["name"] + " 중심 관련 법령 지도"))
    page = page.replace("/*__DATA__*/null", payload)
else:
    page = base.replace("/*__DATA__*/null", payload).replace("__MAIN__", H.escape(data["meta"]["main"]))
if not fragment:
    # 아티팩트 뷰어가 붙여 주던 문서 머리를 직접 붙인다: <title>·<style>까지 head, 나머지는 body
    split = page.index("</style>") + len("</style>")
    page = HEAD + page[:split] + "\n</head>\n<body>\n" + page[split:] + "\n</body>\n</html>\n"
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(page, encoding="utf-8")
print(dst, f"{dst.stat().st_size / 1024:.0f} KB")
