"""Example deck: a lab-meeting research talk on street-tree shade and pavement temperature (academic-figure preset, Korean).

The study, the sites and every number are fictional sample data.
Run from the repo root: python examples/research-talk/build.py [out.pptx]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from deckkit import Deck  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out.pptx"
d = Deck(HERE / "style.json")
META = "가로수 그늘과 보도 표면온도 · 도시환경연구실 랩미팅 2026.10.21"
SRC = "출처: 예시 데이터 (가상의 측정, 도심 보도 48개 구간 × 맑은 날 6일, n = 288)"
TOP, BOTTOM = d.content_top, d.content_bottom
CAP_H = 0.3


def figure(s, cols, no, caption, source, kind, categories, series, *, y_range=None, **kw):
    """Native chart + "그림 N." caption + source line, ending just above the footer. Returns the chart height.
    y_range=(min, max) zooms the value axis of a line chart (deckkit starts bar charts at 0 on its own)."""
    x, w = d.col(*cols)
    h = BOTTOM - TOP - 2 * CAP_H - 0.1
    frame = d.chart(s, (x, TOP, w, h), kind, categories, series, **kw)
    if y_range:
        frame.chart.value_axis.minimum_scale, frame.chart.value_axis.maximum_scale = y_range
    d.text(s, (x, TOP + h + 0.08, w, CAP_H), f"그림 {no}. {caption}", "caption")
    d.text(s, (x, TOP + h + 0.08 + CAP_H, w, CAP_H), source, "caption", color="muted", fit=False)
    return h


def table(s, x, y, w, rows, widths, *, row_h=0.55, numeric=(), accent_row=None, bold_cell=None):
    """Rules-only table (python-pptx: deckkit has no table). Header row in muted caption size, numeric columns
    right-aligned, one rule under the header and one at the bottom (D9)."""
    gf = s.shapes.add_table(len(rows), len(rows[0]), Inches(x), Inches(y), Inches(w), Inches(row_h * len(rows)))
    tbl = gf.table
    tbl.first_row = tbl.horz_banding = False   # no header fill, no banding
    for c, cw in enumerate(widths):
        tbl.columns[c].width = Inches(cw)
    for r, row in enumerate(rows):
        tbl.rows[r].height = Inches(row_h)
        for c, value in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.background()             # the default table style would tint every cell
            cell.margin_left = cell.margin_right = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text = value
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.RIGHT if c in numeric else PP_ALIGN.LEFT
            for run in p.runs:
                run.font.size = Pt(d.style["scale"]["caption" if r == 0 else "body"])
                run.font.color.rgb = d._rgb("muted" if r == 0 else "accent" if r == accent_row else "ink")
                run.font.bold = (r, c) == bold_cell
                run.font._rPr.set("lang", "ko-KR")
    d.rule(s, x, y + row_h, w, color="ink")
    d.rule(s, x, y + row_h * len(rows), w, color="muted", weight=0.5)
    return y + row_h * len(rows)


def oval(s, box, color, alpha=None):
    """Ellipse for the site schematic (deckkit has rectangles only). Solid fill, no outline, optional transparency."""
    sh = s.shapes.add_shape(MSO_SHAPE.OVAL, *(Inches(v) for v in box))
    sh.fill.solid()
    sh.fill.fore_color.rgb = d._rgb(color)
    sh.line.fill.background()
    if alpha is not None:
        srgb = sh.fill._xPr.find(f".//{qn('a:srgbClr')}")
        srgb.append(srgb.makeelement(qn("a:alpha"), {"val": str(round(alpha * 100000))}))
    return sh


# 1. Cover (band) --------------------------------------------------------------
x, w = d.col(0, 10)
band_h = d.H * 0.55
s = d.slide("가로수 그늘이 보행로 표면온도에\n미치는 영향", box=(x, 1.0, w, band_h - 1.4), role="head", color="bg")
d.send_to_back(s, d.rect(s, (0, 0, d.W, band_h), "accent"))
d.text(s, (x, band_h + 0.35, d.col(0, 8)[1], 0.8), "도심 보도 48개 구간 열화상 측정, 2026년 8월 (예시 연구)")
d.text(s, (x, d.H - d.m - 0.3, w, 0.3), "2026.10.21 도시환경연구실 랩미팅 · 가상의 연구와 예시 데이터입니다",
       "caption", color="muted", fit=False)
d.notes(s, "결과부터 말씀드리고, 방법과 한계, 그리고 10월 측정 전에 정할 것 하나를 여쭙겠습니다.")

# 2. Result first: shade vs exposed, by material -------------------------------
s = d.slide("그늘진 보도는 재질과 관계없이 오후 2시 표면온도가 8~11°C 낮았다")
h = figure(s, (0, 8), 1, "재질별 오후 2시 표면온도 중앙값 (°C)", SRC, "column", ["보도블록", "아스팔트", "투수블록"],
           {"수관 그늘": [38.2, 41.0, 37.5], "노출": [47.9, 52.3, 45.8]}, number_format="0.0", labels=True)
x, w = d.col(8, 4)
d.text(s, (x + 0.2, TOP + 0.4, w - 0.2, h - 0.4),
       ["차이는 아스팔트에서\v가장 컸음 (11.3°C)", "투수블록은 그늘이 없어도\v보도블록보다 2.1°C 낮음"], bullets=True)
d.notes(s, "세 재질 모두 그늘 쪽이 8도에서 11도 낮았습니다. 아스팔트가 가장 뜨겁고, 그늘 효과도 가장 큽니다. " + SRC)
d.footer(s, META, 2)

# 3. Method diagram: one 20 m site seen from above -----------------------------
s = d.slide("48개 구간을 수관 피복률로 나누고, 같은 시각에 열화상으로 쟀다")
x, w = d.col(0, 7)
walk_y, walk_h = TOP + 1.1, 1.6
d.text(s, (x, walk_y - 0.45, w, CAP_H), "차도 쪽", "caption", color="muted")
d.rule(s, x, walk_y, w, color="ink")
d.rule(s, x, walk_y + walk_h, w, color="ink")
d.text(s, (x, walk_y + walk_h + 0.1, w, CAP_H), "건물 쪽", "caption", color="muted")
for cx, r in [(0.17, 0.12), (0.49, 0.145), (0.8, 0.1)]:     # tree canopies (share of the site width), translucent
    oval(s, (x + (cx - r) * w, walk_y + 0.1 - r * w * 0.55, 2 * r * w, 1.8 * r * w), "accent", alpha=0.35)
for i in range(5):                                         # 10 measurement points, 2 rows x 5
    for j in range(2):
        oval(s, (x + (0.07 + i * 0.19) * w, walk_y + 0.45 + j * 0.7, 0.14, 0.14), "ink")
d.rule(s, x, walk_y + walk_h + 0.75, w, color="muted", weight=1.5)    # scale bar = the full 20 m site
d.text(s, (x, walk_y + walk_h + 0.85, w, CAP_H), "20 m", "caption", color="muted")
d.text(s, (x, BOTTOM - 2 * CAP_H, w, CAP_H), "그림 2. 측정 구간 모식도 (위에서 본 모습, 점은 측정 지점)", "caption")
d.text(s, (x, BOTTOM - CAP_H, w, CAP_H), "출처: 예시 연구 설계", "caption", color="muted", fit=False)
x, w = d.col(7, 5)
rows = [("구간", "도심 보도 48곳, 각 20m"), ("피복률", "드론 정사영상의 수관 면적 ÷ 보도 면적\v구간별 0~92%"),
        ("측정", "8월 맑은 날 6일, 14시 전후 30분\v열화상 카메라, 지면 위 1.5m"), ("분석", "구간을 무작위효과로 둔 혼합효과 회귀")]
for i, (label, value) in enumerate(rows):
    ry = TOP + 0.1 + i * 1.1
    d.text(s, (x + 0.3, ry, w - 0.3, CAP_H), label, "caption", color="muted")
    d.text(s, (x + 0.3, ry + 0.28, w - 0.3, 0.75), value)
d.notes(s, "구간마다 측정점 열 곳을 정해 두고, 맑은 날 오후 2시 전후에만 찍었습니다. "
           "피복률은 드론 사진에서 나무 그늘 면적을 보도 면적으로 나눈 값입니다.")
d.footer(s, META, 3)

# 4. Dose-response: cover vs temperature ---------------------------------------
s = d.slide("수관 피복률이 10%p 오를 때마다 표면온도는 약 1.2°C 내려갔다")
h = figure(s, (0, 8), 3, "수관 피복률 구간별 오후 2시 평균 표면온도 (°C), 세로축은 35°C부터",
           "출처: 예시 데이터, 구간별 n = 9, 11, 12, 9, 7", "line",
           ["0~10%", "10~30%", "30~50%", "50~70%", "70% 이상"], {"평균 표면온도 (°C)": [49.1, 46.8, 44.0, 41.7, 39.6]},
           number_format="0.0", labels=True, y_range=(35, 51))
x, w = d.col(8, 4)
d.text(s, (x + 0.2, TOP + 0.4, w - 0.2, 0.35), "기울기", "caption", color="muted")
d.text(s, (x + 0.2, TOP + 0.75, w - 0.2, 0.9), "−1.19°C / 10%p", "head", size=30, color="accent")
d.text(s, (x + 0.2, TOP + 1.8, w - 0.2, 1.6), "70% 이상 구간은 7곳뿐이라 마지막 점의 불확실성이 가장 크다.")
d.notes(s, "피복률이 높아질수록 거의 직선으로 내려갑니다. 마지막 구간은 일곱 곳뿐이라 조심해서 봐야 합니다. "
           "출처: 예시 데이터, 구간별 표본 수는 그림 아래에 적었습니다.")
d.footer(s, META, 4)

# 5. Time of day: two series, the gap peaks at 14:00 ----------------------------
s = d.slide("차이는 오후 2시에 10.3°C로 가장 컸고, 저녁 8시에는 0.8°C로 줄었다")
h = figure(s, (0, 9), 4, "시간대별 표면온도 (°C), 12개 구간 × 2일 반복 측정",
           "출처: 예시 데이터 (가상의 시간대별 측정, 2026년 8월 12일·19일)", "line",
           ["08시", "10시", "12시", "14시", "16시", "18시", "20시"],
           {"수관 그늘": [27.8, 31.4, 36.0, 38.6, 37.2, 33.1, 30.4], "노출": [29.5, 38.0, 46.2, 48.9, 45.1, 36.0, 31.2]},
           number_format="0", y_range=(20, 50))
x, w = d.col(9, 3)
d.text(s, (x + 0.2, TOP + 0.4, w - 0.2, h - 0.4), "그늘 효과는 해가 높은 시간에만 크다. 밤 보행 환경은 이 측정으로 알 수 없다.")
d.notes(s, "오전 8시에는 1.7도 차이였다가 오후 2시에 10도를 넘고, 해가 지면 거의 같아집니다. 출처: 예시 데이터.")
d.footer(s, META, 5)

# 6. Table: the mixed-effects model -----------------------------------------------
s = d.slide("재질과 기온을 통제해도 피복률 효과는 10%p당 −1.2°C로 유지됐다")
x, w = d.col(0, 8)
d.text(s, (x, TOP, w, CAP_H), "표 1. 오후 2시 표면온도에 대한 혼합효과 회귀 (구간 무작위절편, n = 288)", "caption")
end = table(s, x, TOP + 0.45, w, [["변수", "추정값 (°C)", "95% 신뢰구간", "p"],
                                   ["수관 피복률 (10%p당)", "−1.21", "−1.48 ~ −0.94", "< 0.001"],
                                   ["아스팔트 (보도블록 대비)", "+3.10", "2.31 ~ 3.89", "< 0.001"],
                                   ["투수블록 (보도블록 대비)", "−1.05", "−1.82 ~ −0.28", "0.008"],
                                   ["기온 (1°C당)", "+1.62", "1.30 ~ 1.94", "< 0.001"]],
            [3.0, 1.5, 1.9, w - 6.4], numeric=(1, 2, 3), accent_row=1, bold_cell=(1, 1))
d.text(s, (x, end + 0.15, w, CAP_H), SRC, "caption", color="muted", fit=False)
x, w = d.col(8, 4)
d.text(s, (x + 0.2, TOP + 1.0, w - 0.2, 2.4),
       "피복률 10%p는 기온을 0.75°C 낮춘 것과 비슷한 크기다. 재질을 바꾸지 않아도 얻을 수 있다.")
d.notes(s, "모형에 재질과 기온을 넣어도 피복률 계수는 그대로 마이너스 1.2입니다. "
           "기온 1도가 표면온도 1.6도이니, 피복률 10%p는 기온 0.75도만큼의 효과입니다. " + SRC)
d.footer(s, META, 6)

# 7. Limitations, what they mean, and what the next round changes ---------------------
s = d.slide("한여름 맑은 날의 표면온도만 쟀으므로, 보행자가 느끼는 더위까지는 말할 수 없다")
x, w = d.col(0, 12)
end = table(s, x, TOP + 0.1, w, [["한계", "이번 결론에 미치는 영향", "10월 측정에서"],
                                  ["8월 맑은 날 6일만 측정", "계절과 날씨로 일반화할 수 없음", "10~11월, 같은 48개 구간 반복"],
                                  ["표면온도만 측정", "보행자 체감 더위는 말할 수 없음", "흑구온도계로 평균복사온도 추가 (B안)"],
                                  ["접근하기 쉬운 구간 위주", "효과가 과대 추정됐을 수 있음", "무작위로 고른 12곳 추가"],
                                  ["건물 그늘이 섞인 구간 6곳", "피복률 효과 일부가 건물 그늘일 수 있음", "6곳을 빼고 재분석, −1.17°C로 거의 같음"]],
            [3.4, 4.3, w - 7.7], row_h=0.7, accent_row=2)
d.text(s, (x, end + 0.15, w, CAP_H), SRC, "caption", color="muted", fit=False)
d.notes(s, "가장 큰 한계는 두 번째 줄입니다. 바닥이 덜 뜨겁다는 것과 사람이 덜 덥다는 것은 다른 이야기입니다. "
           "그래서 다음 측정에서 장비를 하나 더하고 싶습니다.")
d.footer(s, META, 7)

# 8. Decision -------------------------------------------------------------------------
s = d.slide("10월 반복 측정에 흑구온도계 4대를 더할지 오늘 정해 주세요")
options = [("A안. 지금 장비로 반복", "추가 비용 없음", "8월 결과와 바로 비교할 수 있지만, 체감 더위는 여전히 알 수 없다.", "ink"),
           ("B안. 흑구온도계 4대 추가 (제안)", "약 120만 원, 측정 인원 1명 추가",
            "평균복사온도로 보행자 체감까지 추정할 수 있다. 구청에 낼 정책 제안에 필요한 숫자다.", "accent")]
for i, (name, cost, detail, color) in enumerate(options):
    x, w = d.col(0 if i == 0 else 6, 5 if i == 0 else 6)
    d.rule(s, x, TOP + 0.6, w, color=color, weight=1.5 if i else 0.75)
    d.text(s, (x, TOP + 0.85, w, 0.5), name, "governing", color=color)
    d.text(s, (x, TOP + 1.4, w, CAP_H), cost, "caption", color="muted")
    d.text(s, (x, TOP + 1.9, w, 1.4), detail)
x, w = d.col(0, 9)
d.text(s, (x, BOTTOM - 1.3, w, 0.8),
       "흑구온도계는 주문 뒤 2주가 걸린다. 10월 13일 첫 측정에 맞추려면 이번 주에 주문해야 한다.")
d.text(s, (d.m, BOTTOM - CAP_H, d.col(0, 8)[1], CAP_H), "출처: 예시 데이터 (장비 견적과 납기는 가상의 값)", "caption",
       color="muted", fit=False)
d.notes(s, "저는 B안을 제안합니다. 120만 원은 연구실 소모품 예산 안에서 가능하고, 이번 주에 주문해야 10월 측정에 맞출 수 있습니다.")
d.footer(s, META, 8)

d.save(OUT)
