---
name: deck
description: Build a PowerPoint (.pptx) deck that doesn't look AI-generated, end to end. Interview, compare and pick rendered style candidates, fine-tune details such as fonts, build, then run a capture-based review loop. Use for requests like "make a PPT", "build a deck", "presentation", "PPT 만들어줘", "발표자료", "슬라이드 만들어", "슬라이드 수정해줘".
argument-hint: "[topic | source path | existing decks/<slug> folder]"
---

# /deck: orchestrator

Input: $ARGUMENTS

## 0. Setup
- Run commands with `python`; if it is missing, use `python3`. Wrap every path in a command in double quotes.
- Talk to the user in the user's language (e.g. Korean if they write in Korean). File contents you write for the user (brief.md, outline.md, review-N.md) follow the deck's language.
- On `ModuleNotFoundError`, get the user's consent and run `pip install -r "${CLAUDE_PLUGIN_ROOT}/requirements.txt"`.
- For a new deck, check the renderer before the interview.
  ```
  python "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" --check
  ```
  Exit code 2 means no renderer is available. Stop and relay the printed install instructions to the user (review needs captures).
- If a stage skill or script stops with an error, relay the error message and stop. Exception: exit 1 from `assets.py` is handled inside deck-build, which carries on without the image.
- **Network consent:** before the first network use in a session, ask the user once, naming what goes where: photo searches (Openverse, Wikimedia Commons; Pexels/Pixabay if their keys are set), image generation (Cloudflare, Pollinations or Hugging Face if keys are set, otherwise the volunteer-run AI Horde), icons (Iconify), fonts (Google Fonts, GitHub). Say that search words and generation prompts are sent to these services. Remember the answer for the session. If they decline, use only their own images and installed fonts, and no icons.
- Run `assets.py` and `fonts.py` commands one at a time, never in parallel (they share JSON files such as `candidates.json` and `credits.json`).
- Search queries and generation prompts must not contain confidential text from the brief.

## Working folder and resuming
- **New deck:** create `decks/<slug>/` under the current working folder. The slug is the topic as short English kebab-case. If the input is a topic or a source path, pass that information to deck-brief.
- **Existing deck:** if the input is an existing `decks/<slug>`, or a folder for the same topic already exists, look at the files in the folder and **resume** from there.

| What is in the folder | Next stage |
|---|---|
| Nothing | 1 brief |
| brief.md | 2 style |
| + style.json | 3 build |
| + out.pptx | 4 review |
| + the last review-N.md starts with `RESULT: FAIL` and has no `## Applied` | 3 build (fix mode) |
| + the last review-N.md has `## Applied` | 4 review |
| + the last review-N.md starts with `RESULT: PASS` | 5 wrap-up |

Follow the first matching row from the top. The `## Applied` row comes before the PASS row, so a deck fixed after a PASS gets reviewed again.

- All state between stages lives in files in the working folder. Do not rely on conversation memory.
- Intermediate states inside a stage (only one candidate left in `candidates/`, `outline.md` present) are resumed by that stage's skill itself.
- If the user asks for fixes after a PASS, relay their instructions while calling 3 build, then go to 4 review. The review count starts over.

## 1-4. Run the stages
Invoke each stage's skill with the Skill tool. Pass only the working folder path (`decks/<slug>`, relative) as the argument.
1. `ppt-craft:deck-brief` → brief.md
2. `ppt-craft:deck-style` → style.json (includes candidate comparison, selection, fonts and other details)
3. `ppt-craft:deck-build` → outline.md, build.py, out.pptx
4. `ppt-craft:deck-review` → review-N.md

Review loop rules:
- If the result of 4 is FAIL, call `ppt-craft:deck-build` with the same argument to fix it (the skill decides fix mode by looking at the review file). Then go to 4 again.
- Review runs **at most 3 times**. Count the review files since the last PASS. If all 3 are FAIL, go straight to the options.
- If the 3rd review is also FAIL, show the remaining blocker and major list and have the user pick one of the following.
  - Accept as is
  - Drop the affected slide
  - Give direct instructions

## 5. Wrap-up (after PASS)
1. If the SendUserFile tool is available, send `out.pptx` and `renders/sheet.png` (if present). If you arrived at wrap-up directly by resuming and renders is missing, regenerate it.
   ```
   python "${CLAUDE_PLUGIN_ROOT}/scripts/render.py" "decks/<slug>/out.pptx" --out "decks/<slug>/renders" --sheet
   ```
2. Clean up.
   - Delete: `renders/`, `candidates/` (if still there), `assets/_cand/` (if present), `lint.json`
   - Keep: brief.md, style.json, outline.md, build.py, out.pptx, assets/, review-*.md
3. Report briefly.
   - Path of out.pptx and the slide count
   - The chosen style
   - Summary of remaining minor issues
   - Where `[source needed]` (`[출처 필요]`) remains (slide numbers), and that you will fill them in if the user supplies sources
   - A note that fonts may be substituted if the recipient's PC lacks them. If needed, tell them to turn on File > Options > Save > "Embed fonts in the file" in PowerPoint and save.
   - That they can continue later with `/ppt-craft:deck decks/<slug>`

## Principles
- Never show the user the raw style.json. Always show styles as rendered images.
- If the user stops or changes direction, fix the file at that point and resume from the corresponding stage.
