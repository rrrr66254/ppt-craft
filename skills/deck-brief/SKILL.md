---
name: deck-brief
description: Run a light interview before building a PPT and write brief.md (audience, goal, length, content sources, references, tone, presentation context). First stage of /deck.
argument-hint: "[decks/<slug> folder]"
---

# deck-brief

Working folder W: $ARGUMENTS
If the folder does not exist, create `decks/<slug>/` under the current working folder. The slug is the topic as short English kebab-case.

Talk to the user in the user's language (e.g. Korean if they write in Korean). Write the values in brief.md in the deck's language, but keep the template's field labels (`Language:`, `Images:`, `Avoid/Caution:`, …) and the marker `lack of factual material` in English exactly as written: later stages look for those strings.

## 1. Questions
**Do not ask for information that already came up in the conversation.** If the AskUserQuestion tool is available, ask with choices; otherwise ask everything at once as a numbered list.

Required (ask only what is missing):
1. Audience and goal
   - Who is the talk for
   - What should the audience do when it ends (persuade, report, teach, share)
2. Length: number of slides or talk time. If they answer with time, convert at 1 minute ≈ 1 slide and confirm.
3. Content source: topic only / materials available (path) / outline available
   - **If "topic only"**, ask in one go for the facts to use on each slide (figures, dates, proper nouns, real examples).
   - If they say they have none, write `lack of factual material` under `Avoid/Caution` in the brief.
4. References and images
   - References: pptx, images, URLs, template-site pages
   - Images to put on slides. If there is a logo, append `(logo)` after its path.

Optional (bundle into one question and allow "skip"):
5. Presentation context and voice
   - Presentation date, event name, presenter name (used on the cover and footer)
   - Voice (formal/polite or conversational, first person or not)
   - A sample of their own writing

Decide the deck language (ko | en) from the language used in the conversation, and ask if unsure.

## 2. Read the materials
If materials exist, read them and organize the following.
- Core claims
- Usable **figures and their sources** (file, page, URL). Write figures exactly as in the original.
- Proper nouns and real examples

Mark figures whose source you cannot find with `[source needed]` (`[출처 필요]` in Korean decks). Never invent figures.

## 3. Output: W/brief.md
```markdown
# Brief: <working title>

- Language: ko | en
- Audience:
- Goal / what the audience does afterward:
- Length: N slides (M minutes)
- Tone: (formal/conversational, first person or not, writing sample path)
- Structure suggestion: assertion | governing   (governing for business, report, proposal decks)
- Presentation context: date / event / presenter
- References: (list of paths/URLs, or "none")
- Images: (list of paths, or "none". Logos as `path (logo)`)
- Avoid/Caution: (what the user said. If there is no factual material, `lack of factual material`)

## One-line thesis
<the one sentence the whole deck supports>

## Content source summary
### Claims
### Figures (source)
### Examples and proper nouns
```
When done, just state the file path and move on to the next stage.
