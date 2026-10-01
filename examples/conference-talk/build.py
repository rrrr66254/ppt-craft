"""Example deck: a conference talk, "Why we stopped deploying on Fridays" (keynote-type preset, English).

The team, the incidents and every number are fictional sample data.
Run from the repo root: python examples/conference-talk/build.py [out.pptx]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "lib"))
from deckkit import Deck  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out.pptx"
d = Deck(HERE / "style.json", lang="en")
META = "Why we stopped deploying on Fridays · Example talk, November 2026"
SRC = "Source: sample data, 1,412 production deploys, January 2025 – February 2026"
TOP, BOTTOM = d.content_top, d.content_bottom


def source(s, text=SRC):
    d.text(s, (d.m, BOTTOM - 0.3, d.col(0, 9)[1], 0.3), text, "caption", color="muted", fit=False)


def statement(text, y=d.H * 0.26, h=2.6):
    """One sentence in big type on the upper third line (scale break). The sentence is the slide title."""
    x, w = d.col(0, 10)
    return d.slide(text, box=(x, y, w, h), role="head")


# 1. Cover -------------------------------------------------------------------
x, w = d.col(0, 9)
s = d.slide("Why we stopped deploying\non Fridays", box=(x, d.H * 0.28, w, 2.2), role="head")
d.text(s, (x, d.H * 0.28 + 2.35, w, 0.8),
       "Fourteen months of incident data from a nine-person platform team", color="muted")
d.text(s, (x, d.H - d.m - 0.3, w, 0.3), "Example talk · November 2026 · fictional team, sample data",
       "caption", color="accent", fit=False)
d.notes(s, "This is a story about one rule we added, and the data that talked us into it.")

# 2. One sentence: the hook ---------------------------------------------------
s = statement("Our worst outage of 2025 started at 16:52 on a Friday.")
source(s, "Incident 2025-31, sample data")
d.notes(s, "A config change went out at 16:52. The person who shipped it logged off at 17:00. "
           "We found out on Saturday morning, from a customer.")
d.footer(s, META, 2)

# 3. Big number with its baseline (scale break) --------------------------------
s = d.slide("Half of our weekend pages started with a Friday deploy")
x, w = d.col(0, 7)
d.text(s, (x, TOP, w, 3.0), "30 of 63", "head", size=130, color="accent", anchor="bottom")
d.text(s, (x, TOP + 3.1, w, 0.4), "weekend pages traced to a deploy made that Friday", "caption", color="muted")
x, w = d.col(8, 4)
d.text(s, (x, TOP, w, 3.5), ["Friday carried 297 of 1,412 deploys, about 21%",
                             "Monday to Thursday carried the rest and caused only 33"],
       anchor="bottom", bullets=True)
source(s)
d.notes(s, "Friday was a fifth of the work and half of the weekend pain. " + SRC)
d.footer(s, META, 3)

# 4. Chart: the problem was detection, not quality -----------------------------
s = d.slide("Friday’s bad deploys sat unnoticed for nine hours")
x, w = d.col(0, 8)
d.chart(s, (x, TOP, w, BOTTOM - TOP - 0.45), "column", ["Mon", "Tue", "Wed", "Thu", "Fri"],
        {"Median time to detect a bad deploy (hours)": [0.4, 0.3, 0.4, 1.1, 9.2]},
        highlight=4, number_format="0.0", labels=True, source="sample data, 58 bad deploys, January 2025 – February 2026")
x, w = d.col(9, 3)
d.text(s, (x, TOP, w, BOTTOM - TOP - 0.45),
       "The failure rate was flat: 3.8 to 4.4% of deploys on every weekday.", anchor="bottom")
d.notes(s, "We expected Friday changes to be sloppier. They weren’t. Same failure rate as Tuesday. "
           "The difference is who was watching when they failed. Source: sample data, 58 bad deploys.")
d.footer(s, META, 4)

# 5. Code with one callout ------------------------------------------------------
s = d.slide("The fix was one line in our deploy policy")
code = ["deploy:", "  windows:", '    mon-thu: "10:00-16:00"', '    fri:     "10:00-12:00"',
        "  canary:", "    steps: [5, 50, 100]", "    hold: 30m", "  override: incident-commander"]
size = d.style["scale"]["mono"] + 4
line_h = size * 1.2 * d.style["rhythm"]["line_height"] / 72      # PowerPoint's proportional line height
x, w = d.col(0, 6)
y = TOP + 0.3
d.text(s, (x, y, w, line_h * len(code) + 0.2), "\v".join(code), "mono", size=size, fit=False)  # one paragraph
target = (x - 0.12, y + 3 * line_h - 0.04, 4.6, line_h + 0.08)                               # the fri: line
lx, lw = d.col(7, 5)
d.callout(s, target, "Added in March 2026. Nothing else changed.", (lx, target[1] + target[3] / 2 - 0.3, lw, 0.6))
d.text(s, (lx, y + 4.4 * line_h, lw, 1.4), "An incident commander can still override it.", color="muted")
d.notes(s, "This is the whole change. Friday deploys close at noon instead of four.")
d.footer(s, META, 5)

# 6. Diagram: why noon -----------------------------------------------------------
s = d.slide("A deploy needs 90 minutes of daylight after merge")
x0, x1 = d.col(2, 10)[0], d.W - d.m
hours = list(range(12, 19))
per_h = (x1 - x0) / (hours[-1] - hours[0])


def at(h):
    return x0 + (h - hours[0]) * per_h


axis_y = TOP + 0.35
for h in hours:
    d.text(s, (at(h) - 0.4, TOP, 0.8, 0.3), f"{h}:00", "caption", color="muted", align="center", fit=False)
d.rule(s, x0, axis_y, x1 - x0, color="muted", weight=0.5)
lab_x, lab_w = d.col(0, 2)
for r, (name, start) in enumerate([("Started 16:00", 16), ("Started 12:00", 12)]):
    ry = axis_y + 0.5 + r * 1.35
    d.text(s, (lab_x, ry, lab_w, 0.6), name, anchor="middle")
    d.rect(s, (at(start), ry, 0.5 * per_h, 0.6), "muted")
    d.rect(s, (at(start + 0.5), ry, per_h, 0.6), "ink")
    d.text(s, (at(start) + 0.1, ry, 0.5 * per_h, 0.6), "5%", "caption", color="bg", anchor="middle", fit=False)
    d.text(s, (at(start + 0.5) + 0.12, ry, per_h, 0.6), "50%", "caption", color="bg", anchor="middle",
           fit=False)
    d.text(s, (at(start + 1.5) + 0.1, ry, 1.2, 0.6), "100%", "caption", color="muted", anchor="middle", fit=False)
handoff_x = at(17)
d.rect(s, (handoff_x - 0.02, axis_y, 0.04, 2.5), "accent")
d.text(s, (handoff_x + 0.12, axis_y + 2.2, 2.6, 0.6), "17:00: weekend on-call\vtakes over", "caption", color="accent",
       fit=False)
x, w = d.col(2, 10)
d.text(s, (x, BOTTOM - 1.0, w, 0.5),
       "Start at four and the last step lands with someone who never saw the change.")
source(s, "Source: rollout steps from our deploy policy, sample data")
d.notes(s, "Canary for half an hour, half the fleet for an hour, then everyone. "
           "Start at noon and you have the whole afternoon to notice.")
d.footer(s, META, 6)

# 7. Before / after ------------------------------------------------------------------
s = d.slide("Seven months later we page less and ship just as often")
cols = {"label": d.col(0, 4), "before": d.col(5, 3), "after": d.col(9, 3)}
d.text(s, (cols["before"][0], TOP, cols["before"][1], 0.3), "Jan 2025 – Feb 2026", "caption", color="muted")
d.text(s, (cols["after"][0], TOP, cols["after"][1], 0.3), "Mar – Sep 2026", "caption", color="muted")
rows = [("Weekend pages per month", "4.5", "1.6"), ("Deploys per week", "23.2", "23.6"),
        ("Share of deploys on Friday", "21%", "9%")]
for i, (label, before, after) in enumerate(rows):
    ry = TOP + 0.45 + i * 1.15
    d.text(s, (cols["label"][0], ry, cols["label"][1], 1.0), label, anchor="middle")
    d.text(s, (cols["before"][0], ry, cols["before"][1], 1.0), before, "head", size=48, color="muted", bold=False, anchor="middle")
    d.text(s, (cols["after"][0], ry, cols["after"][1], 1.0), after, "head", size=48, bold=False,
           color="accent" if i == 0 else "ink", anchor="middle")
source(s, "Source: sample data, 2,129 production deploys and 74 weekend pages, January 2025 – September 2026")
d.notes(s, "Weekend pages fell by about two thirds. Deploys per week did not move. "
           "The Friday work moved to Friday morning and to Monday.")
d.footer(s, META, 7)

# 8. The ask ----------------------------------------------------------------------------
s = statement("Close Friday afternoons\nfor one quarter and count\nyour weekend pages.", h=3.3)
x, w = d.col(0, 8)
d.text(s, (x, d.H * 0.26 + 3.65, w, 0.8),
       "Measure three things before and after: weekend pages per month, deploys per week, time to detect.",
       color="muted")
d.notes(s, "If your numbers don’t move, reopen Friday. Ours moved in the first month.")
d.footer(s, META, 8)

d.save(OUT)
