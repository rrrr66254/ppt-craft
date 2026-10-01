# AI tells and human-touch signals (by ID)

The single source shared by build, lint, and review.

Severity (lint baseline):
- blocker: W14, I3, T12
- major: L2, L6, L24, C1, C6, C12, D3, D5, S1, T11
- Everything else is minor. Review uses this table as a floor; items whose grade is written in checklist.md follow that grade.

## 0. Core principles (research conclusions)

1. **The root cause is "uniformity".** Treating every slide the same way regardless of content is the root of almost every AI tell.
2. **Moving on to the next default after banning the old defaults is also an AI tell.** Ban purple and AI converges on these three:
   - Cream (around #F4F1EA) background + serif display + terracotta accent
   - Near-black background + one acid-green or vermilion accent
   - A newspaper look: hairline rules, sharp corners, dense columns
3. **Patterns that earlier AI-PPT guides recommended are now AI tells too.** For example: icons in circles, putting a visual on every slide, a row of stat tiles.
4. **The most-cited problems in Korean decks**
   - Style changes from slide to slide
   - Text and shapes overlap
   - Translationese sentences
   - Hangul font substitution and garbling
5. **Imagery is evidence, used with restraint.** An image goes in only when it proves the slide's point (H2, H7, I8); a type-only slide is always allowed. Every photo in a deck gets the same treatment (I12). Scrims are solid and translucent, never gradients (C1). Full-bleed slides stay within `imagery.max_bleed` (L24), and the same placement pattern is used at most 2 slides in a row (L2).
6. **Prior art**: [jkkms/ppt-deck](https://github.com/jkkms/ppt-deck) is a Korean PPT skill with the linter rules [CLICHE] [PARALLEL] [UNIFORM] [SENTENCE], worth a look.

---

## L. Layout and composition

| ID | Tell (in a checkable form) | Replace with |
|---|---|---|
| L1 | Three equal-size rounded cards in a row, each made of "icon + bold title + 1-2 lines of description" | The actual number of items, with widths that vary by importance. A table, a 2×2, or one main item plus supporting items also works |
| L2 | The same layout skeleton on 3 or more slides in a row (e.g. Copilot's "image left + text right") | Choose the slide type by content: big number, full-bleed image, chart, comparison, quote, process |
| L3 | Padding, corner radius, and card height are identical on every element | Big for key elements, small for supporting ones. Vary spacing by how elements group |
| L4 | Title, blocks, and body all center-aligned | Grid-aligned left alignment and deliberate asymmetry. Never center body text |
| L5 | A vertical stripe on the left or a color band on top of every card | No border; separate with a light fill over the whole card or with whitespace |
| L6 | An accent rule under the title, or a bar running across the whole header/footer | Separate with whitespace or a background change |
| L7 | Slides that look like a web page or app screen (hero section, badges, navigation-style cards, browser mockups) | Slide grammar: a claim headline + one piece of evidence |
| L8 | A small badge or pill above the title ("NEW", "2026 OUTLOOK") | Remove. If progress needs showing, put it in the same place on every slide |
| L9 | A "1 → 2 → 3" step row with numbers in circles | Only when there is a real order. Then show the real structure, such as branches or time spans |
| L10 | Nested containers, a card inside a card (the Gamma style) | Containers one level deep at most |
| L11 | Full of decoration but thin on content, or the opposite, a report-like wall of text | Match density to the slide's role (a key moment or reference material) |
| L12 | Most slides split into "half photo + half bullets" | Use an image only when it is evidence |
| L13 | Only the cover looks good and the style falls apart from slide 2. The color combination changes per slide | Enforce a single style.json on every slide |
| L14 | Text, photos, and shapes overlap each other | Place by grid coordinates and confirm with render review |
| L15 | Chapter name, title, and subtitle sit in different places per slide, and the lower part of the body is empty | Pin the title area to the same place on every slide. Fill the body area in balance |
| L16 | Tacky shadows and misaligned boxes (the typical python-pptx output) | No shadows. Snap every box to the grid |
| L17 | A grid or bento with empty cells, or with every cell the same size | Cell count = item count, and cell sizes follow the real weight of each item |
| L18 | Meaningless decoration (numbers, ornaments, badges) | Remove it, or tie it to a real fact (chapter, date, edition) |
| L19 | An image slide with more than 4 elements, or a title over 2 lines. Not counted: the image itself, scrims and panels, footer and page number, caption and source lines | Cut it down |
| L20 | The same spacing everywhere, instead of tight within a group and loose between groups | Group by spacing. More space above a title than below it |
| L21 | 01/02/03 numbering on items that have no order | Remove |
| L22 | A category label or a text wordmark on a logo slide | Logos only |
| L23 | A plain list of 6 or more bullets | Group them, split them into columns, or split the slide |
| L24 | More full-bleed background slides than `imagery.max_bleed` (default 3) | Cut down. Use split or inset instead |

## C. Color and effects

| ID | Tell | Replace with |
|---|---|---|
| C1 | Indigo-to-purple or blue-to-purple gradients | Flat color. Use a gradient only when it encodes meaning |
| C2 | Lavender or purple accent | Derive the palette from the brand or topic. Ratio: main color 60-70%, 1-2 secondary colors, 1 accent |
| C3 | Cream/beige background (around F5F5DC, FAF0E6, F4F1EA) + muted red/terracotta accent | White as the default neutral unless there is a brand reason |
| C4 | Dark mode as the default: navy/near-black background + neon cyan/violet, glowing card borders | Dark mode only when the projection setting or brand calls for it. Gray body text at WCAG AA or better |
| C5 | Glassmorphism (translucent cards, blurred spheres behind) | Opaque solid fills |
| C6 | Colored glow, the same soft shadow on every element | No shadows |
| C7 | Decorative 3D blobs, waves, gradient spheres | Remove |
| C8 | Title text filled with a gradient | Solid-color text |
| C9 | The accent color used on any word, bar, or icon | Accent only in the one place the audience should look |
| C10 | 4 or more colors on one slide | Background 60 : body 30 : accent 10. 3 colors or fewer per slide |
| C11 | A palette so perfect it fits no brand | Derive it from a reference or the brand |
| C12 | Pure #000 text | A deep ink that leans toward the palette |
| C13 | A texture above 0.1 opacity, a texture on several slides, or a texture over a textured theme | One cover or section slide, opacity 0.1 or less |
| C14 | A decorative background where the accent covers more than 5% of the area, or uses several accents | A flat solid area |
| C15 | Gray text on a colored area | Text tinted toward the area's color |

## T. Typography

| ID | Tell | Replace with |
|---|---|---|
| T1 | Inter/Roboto/Arial/system fonts everywhere | The font the user picked (record why it was chosen) |
| T2 | The "refined AI" combos: Space Grotesk, Instrument Serif, Geist, Poppins, Montserrat | Excluded from the default candidates. Only when the user explicitly wants them |
| T3 | One italic serif word mixed into a sans-serif title | One family per text level. No emphasis-word tricks |
| T4 | An all-caps eyebrow label above every title ("KEY INSIGHT") | Use only when it is a real section tracker |
| T5 | Every title in Title Case | Sentence case |
| T6 | Title size and position identical even on the key slides | Keep the title position fixed, but break the scale on 2-3 key slides (a giant number, a one-line declaration) |
| T7 | Almost no contrast in weight and size | Title:body size ratio of 2:1 or more, distinct weights |
| T8 | Office defaults (Aptos, Calibri, Malgun Gothic) left as they are | Set the theme fonts explicitly |
| T9 | Bold sprinkled in many places in the body | One bold phrase or less per slide |
| T10 | Fonts substituted on export or on another PC, shifting line breaks | Embed, or use common fonts. Confirm with the real render result |
| T11 | **A Hangul word breaks in the middle** (caused by PowerPoint's default "allow Hangul word breaks") | Set `lang="ko-KR"` on Hangul runs (confirmed by a render experiment on 2026-09-30; `eaLnBrk` has no effect) |
| T12 | **No East Asian font (`a:ea`) set**, so Hangul falls back to Malgun Gothic or Gulim | Specify both latin and ea fonts on every run and in the theme |
| T13 | Default Hangul tracking looks wide and "loose" | Titles -2 to -4%, body -1 to -2% |
| T14 | Line spacing of 1.0 looks cramped | Body 1.3-1.5x |
| T15 | A short particle or a single word left alone on the last line | Adjust box width or line breaks (confirm with render review) |
| T16 | A monospace font used to "look technical" | Mono only for code and data |

## I. Icons and images

| ID | Tell | Replace with |
|---|---|---|
| I1 | Thin line icons attached to every bullet or card | Only when they help tell things apart faster than text; otherwise none |
| I2 | Icons placed inside a colored circle or rounded square | Same standard |
| I3 | Emoji in bullets or titles (🚀 ✅ 💡 📈) | Banned outright |
| I4 | Stock images such as handshakes, diverse teams smiling at a laptop, light bulbs, chess pieces | Real product screenshots, real photos |
| I5 | An AI-generated **look**: glossy waxy skin, garbled text, odd hands, over-sharpening, over-saturated "cinematic" style | Judged by appearance, not by origin. Generated images are allowed if they show none of these; reject any image that does, whatever its source. Check at the selection stage |
| I6 | Tech clichés (glowing blue brain, circuit head, holographic globe, particle network) | A real system diagram |
| I7 | The same illustration style applied to every concept (Gamma) | The image should come from the topic |
| I8 | An image unrelated to the slide's claim | If you cannot answer "What does this image prove?", remove it |
| I9 | Unicode arrows and symbols in body text (a chain of → ≈ ✓) | Write words, or use native connector shapes |
| I10 | A circle, polygon, or gradient mask that imitates the outline of a person or object | A real cutout, or none at all |
| I11 | A hand-drawn fake browser, phone, or IDE frame | The real screenshot with a hairline border |
| I12 | Each photo has its own tone and saturation | One treatment for the whole deck (`imagery.treatment`) |
| I13 | A figure or photo with no caption or source | A caption with source, date, and place |

## W. Writing (English)

| ID | Tell | Replace with |
|---|---|---|
| W1 | Unlock/Unleash/Empower/Elevate/Harness/Revolutionize/Transform/Streamline/Leverage | A concrete verb and object |
| W2 | delve, tapestry, testament, pivotal, underscore, landscape, seamless, cutting-edge, game-changer, robust | Checked with a banned-word regex |
| W3 | Colon titles "X: The Y of Z" | A one-clause claim sentence |
| W4 | Topic-label titles ("Market Overview") | An action title |
| W5 | The rule of three (3 bullets, 3 adjectives, 3 pillars as the default) | The actual count (2, 4, 5 are fine) |
| W6 | "Not just X, but Y" / "It's not X, it's Y" | Say Y directly |
| W7 | Emphasis with an em dash (—) | Split the sentence or the line |
| W8 | A "**Lead-in:** explanation" format on every bullet | Plain prose, or a table with real column headings |
| W9 | Every bullet has the same length and grammatical structure | Uneven lengths are natural |
| W10 | "In today's fast-paced world", "crucial to note" | Delete |
| W11 | Empty sentences that stay true if pasted onto a competitor ("Drive engagement", "Build faster. Ship smarter.") | At least one of name, number, date, or example on every slide |
| W12 | Vague sources such as "Studies show", "Experts agree" | State the source in small type |
| W13 | Inflated significance such as "serves as a pivotal…", "marks a shift" | "is" |
| W14 | Leftover instructions and placeholders ("[Insert data]", "Add your logo here") | Fail immediately when found (hard fail) |
| W15 | Straight quotes, `--`, or three periods in an English deck | Curly quotes, an en dash for ranges, the ellipsis character |
| W16 | Fake names such as John Doe or Acme, or startup-style product names | Real names |

## K. Writing (Korean)

The Korean phrases in quotes are detection data: they are what the lint and the reviewer look for in Korean decks.

| ID | Tell | Replace with |
|---|---|---|
| K1 | Translationese "~를 통해" (through ~), "~에 있어서" (in terms of ~), "~에 대해" (regarding ~), "~함에 따라" (as ~ happens) | Write the subject and verb directly ("캐시를 도입해 지연이 줄었다", "latency fell after we added a cache") |
| K2 | Repeated obligations such as "~하는 것이 중요합니다" (it is important to ~), "~할 필요가 있습니다" (there is a need to ~) | Say directly what to do |
| K3 | "결론적으로 / 요약하자면 / 종합하면" (in conclusion / to sum up / all in all) | Delete |
| K4 | 혁신적 (innovative), 획기적 (groundbreaking), 차별화된 (differentiated), 독보적 (unrivaled), 패러다임 (paradigm), 심오한 (profound) | Concrete nouns and numbers |
| K5 | Empty modifiers: 다양한 (diverse), 핵심적인 (key), 효과적으로 (effectively), 효율성 제고 (improving efficiency), 전략적 접근 (strategic approach) | Delete or make concrete |
| K6 | 시너지 (synergy), 극대화 (maximize), 최적화 (optimize), 인사이트 (insight) | Make concrete (no Korean source, but kept as a warning) |
| K7 | "단순한 ~이 아니라 ~이다" (it is not merely ~ but ~) | Write only the second half |
| K8 | A mechanical "첫째/둘째/셋째" (first/second/third) list, symmetric parallels like "X의 이해/활용/전망" (understanding/use/outlook of X) | Follow the real structure |
| K9 | Bullets and sentences of uniform length | Vary the length |
| K10 | Overused connectives "또한, 이처럼, 이를 통해, 이러한" (also, like this, through this, such), too many commas | Delete |
| K11 | "✅ **키워드**: 설명" (emoji + bold + colon: "**keyword**: explanation"), chains of "→" | Plain prose |
| K12 | Overused "용어(Term)" parenthetical glosses, translatable English left as is | Only the one word your audience uses |
| K13 | Overused -적/-성/-화 suffixes (-tic/-ness/-ization) | Unfold them into verbs |
| K14 | Passives such as "~이 요구된다" (~ is required) that make the subject disappear | Name the subject |
| K15 | Slide bullets that are all "~습니다" declarative sentences (full formal-polite endings) | Bullets as noun phrases or terse report style (개조식); only the governing message is a full sentence |

The terse "~함/~임" report style (개조식) is itself a Korean report convention and not an AI tell ([mindlenews](https://www.mindlenews.com/news/articleView.html?idxno=6658)). The problem is monotony and uniform length.

## S. Structure and narrative

| ID | Tell | Replace with |
|---|---|---|
| S1 | Template flow: cover → agenda → intro → 3 pillars → Key Takeaways → conclusion → "Thank you / Q&A" (in Korean decks: "목차" (agenda), "감사합니다" (thank you)) | Problem → evidence → proposal. End on a request or a decision |
| S2 | Reading the titles in sequence does not form an argument | Write the title storyboard first |
| S3 | Scattered points with no governing message | Fix a one-line thesis for the whole deck and make every slide support it |
| S4 | Every slide has the same weight, so nothing signals what matters | Break the layout on the 2-3 slides that carry the argument |
| S5 | Too many thin slides that each say only a little | Merge them. The slide count follows the number of claims |
| S6 | Every slide follows a "bullets → image → one-line conclusion" pattern | Vary the types |
| S7 | Generic intro and conclusion slides | Start with the result you found |
| S8 | A section divider slide every 2 slides | Only in decks over 20 slides |
| S9 | Speaker notes missing, or just repeating the slide | The claim on the slide, what to say in the notes |
| S10 | No Korean report convention (title / governing message / body) | For a business or report tone, a 3-tier structure with the governing message written first |

## D. Data

| ID | Tell | Replace with |
|---|---|---|
| D1 | A row of 3-4 KPI tiles with no context ("10x", "99.9%", "24/7", "500+") | One number with its baseline, period, and source |
| D2 | Three boxes with invented percentages | A real chart built from the data provided |
| D3 | Fabricated or unsourced statistics (a test found 41% of Copilot's statistics were fabricated) | Every number must be traceable to the input materials. If it is not traceable, `[source needed]` (`[출처 필요]` in Korean decks) |
| D4 | Suspiciously round numbers, percentages that sum to exactly 100 | Keep the real precision |
| D5 | A chart drawn out of shapes | A native chart object |
| D6 | A decorative chart with no axis labels, units, or source, titled something like "Growth Trends" | A headline that states the conclusion, axis labels, a source, and only the key series emphasized |
| D7 | A smoothly rising curve or hockey stick with no data points | Plot the real points |
| D8 | A single percentage shown as a donut or ring infographic | Write it as text, or give it something to compare against |
| D9 | A table with a rule under every row | Separate rows with spacing and emphasize only the key rows |


## H. Human-touch signals (apply these)

| ID | Signal | How to apply |
|---|---|---|
| H1 | Specificity | At least one of proper noun, real figure, date, or real example on every slide (the opposite side of W11) |
| H2 | Real materials first | User screenshots, photos, code, data > free real photos or generated images without the I5 look > icons > nothing |
| H3 | Annotated screenshots | Boxes, arrows, and short notes as native shapes over the real screen (deckkit callout) |
| H4 | Traces of context | Presentation date, event name, and presenter on the cover and footer, page numbers, a small source line |
| H5 | The presenter's voice | Reflect the brief's tone (formal, conversational, first person) and writing sample in titles and notes; write notes as speech |
| H6 | Variation in rhythm | Mix one-sentence slides, big-number slides, and dense reference slides |
| H7 | Restraint | Slides without decoration are allowed; do not put an image or icon on every slide |
| H8 | A consistent personality | Keep one style motif to the end of the deck |

A "personal feel" does not mean sloppiness is fine. Alignment, grid, and typo standards stay strict.

## Lint-only IDs

| ID | Tell | Replace with |
|---|---|---|
| BULLET | A bullet character (•●▪■◦) typed directly into the text, so the bullet shows twice | Use the paragraph bullet property (deckkit `bullets=True`) |
