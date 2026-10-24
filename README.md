# 한국 법령 참조 지도

법률 하나를 중심으로 **시행령·시행규칙 위임, 조문 사이 인용, 다른 법령 인용, 판례 연결**을 한 그래프에 모은 인터랙티브 지도입니다.

- 지도 보기: https://seong-hocho.github.io/korean-law-graph/
  - [개인정보 보호법](https://seong-hocho.github.io/korean-law-graph/privacy.html): 법 128조 · 시행령 142조 · 판례 130건
  - [보험업법](https://seong-hocho.github.io/korean-law-graph/insurance.html): 법 253조 · 시행령 146조 · 시행규칙 61조 · 판례 145건

법 조문은 장 순서대로 안쪽 원에 놓입니다. 시행령·시행규칙·판례는 연결된 법 조문 쪽 바깥 고리에 놓이므로, 판례가 몰린 방향이 곧 분쟁이 많은 조문입니다. 조문이나 판례를 누르면 연결된 것만 남고, 옆 패널에 원문과 연결 목록이 나옵니다.

## 연결을 만드는 방법

| 연결 | 출처 |
|---|---|
| 위임 | 법제처 위임조문 3단비교(`thdCmp`) |
| 조문 인용 | 조문 본문의 `「법령명」 제N조`, `같은 법`, `법 제N조`, `영 제N조` 같은 표현을 규칙으로 추출 |
| 다른 법령 | 위와 같은 방식으로 `「다른 법령」`을 인용한 경우 |
| 판례 | 본문에 법령명이 나오는 판례를 찾은 뒤 참조조문 → 판시사항·판결요지 → 판결문 본문 순으로 조문 추출 |

## 다른 법령으로 만들기

Python 3.10 이상, 외부 패키지는 없습니다.

```bash
python build_graph.py "상법" data/commercial.json
python make_page.py data/commercial.json docs/commercial.html
```

시행령·시행규칙이 있으면 자동으로 함께 들어갑니다. 법제처 응답은 `data/raw/`에 캐시됩니다.

법제처 Open API 인증값(OC)은 `LAW_OC` 환경변수로 넣습니다. 넣지 않으면 공개 테스트값(`test`)을 쓰는데, 많이 호출할 때는 [공동활용 신청](https://open.law.go.kr)으로 받은 값을 쓰는 편이 안전합니다.

| 파일 | 역할 |
|---|---|
| `lawapi.py` | 법제처 Open API 호출과 캐시 |
| `build_graph.py` | 조문·위임·인용·판례를 모아 그래프 JSON 생성 |
| `make_page.py` | 그래프 JSON을 `graph_template.html`에 넣어 단일 HTML 생성 |
| `data/*.json` | 생성된 그래프 데이터 |
| `docs/` | GitHub Pages로 공개되는 페이지 |

## 주의

- 판례는 판결 당시 법의 조문 번호로 인용합니다. 개정으로 번호가 바뀌거나 삭제된 조문은 현행 조문과 내용이 다를 수 있습니다.
- 자동 추출이라 빠지거나 잘못 잡힌 연결이 있을 수 있습니다. 실무에는 [국가법령정보센터](https://www.law.go.kr) 원문을 확인해 주세요.
