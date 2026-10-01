---
name: deck-review
description: Re-review a pptx from real rendered captures. lint (text/XML), render, a review-only subagent verdict, then review-N.md (PASS/FAIL). Final stage of /deck; can also review an externally made pptx on its own. Use for "review my PPT", "check this deck", "does this look AI-made", "PPT 검수", "슬라이드 리뷰", "AI 티 나는지 봐줘".
argument-hint: "[decks/<slug> folder | file.pptx]"
---

# deck-review

Input: $ARGUMENTS
Scripts: `python "${CLAUDE_PLUGIN_ROOT}/scripts/<name>.py"` (use `python3` if `python` is missing). Wrap every path in a command in double quotes.
If a script fails for a reason not described below (exit code 1, etc.), relay the error message and stop.

Talk to the user in the user's language (e.g. Korean if they write in Korean). The review file (review-N.md) follows the deck's language.

## 0. Pick the target
- **A folder W is given**
  - Target: `W/out.pptx`
  - Reference files: whichever of `W/brief.md`, `W/style.json`, `W/outline.md`, `W/assets/credits.json` exist
- **A pptx file is given (standalone mode)**
  - W: `<same folder as the file>/<file name>-review/`
  - Judge by general criteria, with no reference files.
- N: number of `review-*.md` files already in W + 1

## 1. lint
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/lint.py" "<target>" --out "W/lint.json" [--style "W/style.json"]
```
Exit code 1 means "there are problems" (blockers or majors exist), so do not stop; go on to the next step.
Exit code 2 means a lint error itself (corrupt file, etc.). In that case stop and relay the error message to the user.
`W/lint.json` holds `findings` and the per-slide speaker notes `notes`.

## 2. Render
```
python "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" "<target>" --out "W/renders" --sheet
```
Exit code 2 means no renderer is available. Stop and relay the printed install instructions to the user as they are. **Never review without a render.**
render.py renders a temporary copy, so it is safe even if the user has that file open in PowerPoint.

## 3. Call the reviewer
Call the Agent tool with `subagent_type: "ppt-craft:deck-reviewer"`.

Put in the prompt (all absolute paths):
- The slide PNG folder `W/renders` and the overview `W/renders/sheet.png`
- The automated check result `W/lint.json` (includes per-slide speaker notes `notes`)
- Only those that exist: brief.md, style.json, outline.md, assets/credits.json
- The rules `${CLAUDE_PLUGIN_ROOT}/rules/tells.md`
- The checklist `${CLAUDE_PLUGIN_ROOT}/skills/deck-review/checklist.md`
- The result file `W/review-N.md`

Do not put in the prompt: the contents of build.py, a description of the build process, your own opinions, or earlier review-*.md files. This keeps the reviewer from taking on the maker's point of view.

## 4. Verdict
- Check that the first line of `W/review-N.md` is `RESULT: PASS` or `RESULT: FAIL`. If the format is wrong, call the reviewer once more to fix only the format.
- If called from /deck, return the result (PASS/FAIL, counts, file path).
- In standalone mode, or if the user called it directly, do the following.
  1. Summarize the counts and the blocker/major list for the user.
  2. If the SendUserFile tool is available, send `W/renders/sheet.png`.
  3. Do not make fixes.
     - If you reviewed a folder (a deck), only ask "Want me to fix it?"
     - Do not fix an external pptx yourself. If they want, explain that /ppt-craft:deck can build a new one using this file as a reference.
