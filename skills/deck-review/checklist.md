# Review checklist (judged from captured images)

Rule IDs and descriptions are in tells.md.
There are three grades.
- blocker: must not ship as is
- major: a clear AI tell, or harms readability
- minor: nice to polish

Items with a grade written follow that grade. For items without one, use the tells.md severity table as a floor, and if it is not in the table, it is minor.
The per-slide speaker notes are in `notes` of `lint.json` (for H5, S9, and checking sources that appear only in the notes).

## 1. Render defects
- Text clipped, overflowing, or overlapping (L14): major
- Signs of font substitution. Fonts differ from slide to slide or look like Gulim/Batang (T10): major, (T12): blocker
- A Hangul word breaks in the middle of a line (T11): major
- Only one word left on the last line (T15): minor
- Broken or stretched images (aspect distortion): major

## 2. Style fidelity (when style.json exists)
- Are colors, fonts, and motifs the same as the style
- Is the accent color in one place per slide (C9)
- Is the title position the same on every slide (L15)
- Does the style hold up after the cover (L13)

## 3. Layout (look at the overall rhythm in sheet.png first)
- Is the same layout repeated (L2), do the key slides have a scale break (S4, T6)
- Card grid (L1): major
- Everything center-aligned (L4), web-page-like composition (L7), nested cards (L10)
- Alignment, grid, and margins (L3, L16): do element edges line up on the same line

## 4. Readability
- Is contrast WCAG AA or better
- Does the body look like 14pt or more
- Is the size difference between title and body 2:1 or more (T7)
- Density: a wall of text, or an empty slide with only decoration (L11)

## 5. Content
- A credits slide after the closing request/decision slide is an appendix: do not apply S1, S2, W4, W8 or the 14pt body check to it.
- Do the titles alone, read in sequence, form an argument (S2): major
- Is the title a claim (W4)
- Are there empty sentences that would stay true if pasted onto a competitor (W11)
- Is the source of figures visible on the slide (D3). If it is only in the notes, minor. `[source needed]` (`[출처 필요]` in Korean decks) is the D3 marker. Do not treat it as W14.
- Do charts have axes, units, and a source (D6)
- Are the speaker notes written as speech and not a copy of the slide text (H5, S9)
- Does it fit the brief's goal, audience, and length

## 6. Overall AI-tell impression
- Look at the visual items lint cannot catch: I1, I2, I4, I5, I6, C3, C4, C5, C7, L3, L10
- Ask yourself: "Is there a point where someone seeing it for the first time would feel AI made it?" If so, write where and why.

## 7. Images
- Crop: are faces, heads, and text not cut off, is the focus in the right place, is it not blurry
- Do photos not look AI-generated, and are they not cliché stock (I4, I5)
- Is attribution given for materials that need it (when credits.json exists): records for images that appear in the captures, with `attribution_required`, `share_alike`, or `ai_generated`, appear on the credits slide
- Are `low_res` images kept out of large slots
- If there is a logo, is it in the same position on every body slide
- Text over a photo (bleed-scrim, strip, any text on an image): does it read clearly in the capture, at about 4.5:1 for body and 3:1 for 24pt or larger. If not: major. Check the footer and page number on full-bleed slides too
- Full-bleed slides over `imagery.max_bleed` in style.json (default 3) (L24): major. The same placement pattern on 3 slides in a row (L2)
- One treatment across the deck: photos that differ in tone, saturation, or gray/duotone (I12): major
- Texture: above 0.1 opacity, on more than one slide, or over a textured theme (C13): major
- Every photo and figure has a caption or source line with provenance (I13). Scrims are solid, never gradients (C1)
- No fake device frames around screenshots (I11), no circle or polygon masks imitating a cutout (I10). An image slide with more than 4 elements or a title over 2 lines (L19)

## 8. Human touch (tells.md H1-H8)
- A slide without H1 (specificity): major. If the brief has `lack of factual material`, minor. A one-sentence slide satisfies H1 with the fact in its title.
- Anything else missing: minor. Also briefly note the ones that are present.
