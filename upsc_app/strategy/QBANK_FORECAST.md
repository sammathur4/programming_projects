# What the questions themselves tell us about the next paper

Only the question text is used here. No news, no books, no opinions.
Run: `.venv/bin/python upsc_app/tools/qbank_analysis.py`

---

## The one number that decides everything

I pulled every named thing out of every question — "Lok Sabha", "China", "Hilton-Young
Commission", "Money Bill" — and counted how many different years each one appears in.

| | Prelims | Mains |
|---|---|---|
| Different things named | 2,327 | 856 |
| Appeared in **only 1** of 14 years | **90%** | **88%** |
| Appeared in 3 or more years | 3% | 4% |

**UPSC almost never asks the same thing twice.** That is the whole answer to "can we predict
the paper". You cannot predict *which* question. Anyone selling you a "prediction list" is
selling you something with a 3% hit rate.

But 3% is not zero, and that 3% is not random. It is the same kind of thing every time.

---

## What does come back — the recurring core

Prelims things seen in 4 or more separate years:

| Thing | Years out of 14 |
|---|---|
| Lok Sabha | 12 |
| Rajya Sabha | 8 |
| Earth | 7 |
| Article (of the Constitution) | 6 |
| China | 6 |
| Governor | 6 |
| Prime Minister | 6 |
| Amendment | 5 |
| European Union | 5 |
| Speaker | 5 |
| Supreme Court of India | 5 |
| United Nations | 5 |
| Schedule | 5 |
| Money Bill | 4 |
| Minimum Support Price | 4 |
| Arunachal Pradesh | 4 |
| Kerala | 4 |
| NITI Aayog | 4 |

Mains things seen in 4 or more years:

| Thing | Years out of 14 |
|---|---|
| Constitution | 8 |
| Dalit | 7 |
| Article | 6 |
| Mahatma Gandhi / Gandhian | 5 |
| Parliament | 5 |
| British | 5 |

Look at what is on those lists. It is not trivia. It is **the machinery of the Indian state
plus India's immediate neighbourhood plus your own states**. UPSC's repeat budget is spent on
institutions and geography, never on one-off facts.

That gives a real rule: anything that is a *body, a post, a constitutional article, a
neighbouring country, or a state of India* should be known to the last detail, because those
are the only things with a repeat life.

---

## The format of 2027 is knowable even if the content is not

Percent of each year's prelims paper:

| Year | "Which statements are correct" | "How many of the above" | "Codes given below" |
|---|---|---|---|
| 2015 | 28 | 0 | 26 |
| 2020 | 34 | 0 | 31 |
| **2023** | 33 | **40** | **0** |
| 2024 | 29 | 13 | 16 |
| 2025 | 40 | 17 | 8 |
| 2026 | 47 | 2 | — |

Expect **2027 to be about half statement-checking questions**. Statement questions give you
partial credit for knowing some statements and punish guessing, so they reward exactness
("does Article 356 say *may* or *shall*"), not general reading of a chapter.

The old codes format is dead. Any mock built before 2023 trains the wrong thing.

---

## The paper has been moving away from current affairs

This uses the `nature` tag, which is only filled for 8 of the 14 years. Treat it as a lead,
not a fact — it needs a 50-question spot check before you act on it.

| Year | Purely static ("Fundamental") | Linked to news |
|---|---|---|
| 2015 | 28% | 48% |
| 2020 | 47% | 30% |
| 2024 | 51% | 24% |
| 2025 | 43% | 33% |

If that tagging is trustworthy, the direction is clear: **more book knowledge, less news**.
That is the opposite of what most coaching sells. Check it yourself on a random 50 questions
spread across those years before you rebalance your time.

---

## Mains: what they are actually asking you to do

The instruction word in each mains GS question (share of questions containing it):

| Instruction | 2014–17 | 2023–26 |
|---|---|---|
| Discuss | 31% | **18%** |
| Critically analyse | 9% | **4%** |
| Explain | 8% | 11% |
| Examine | 8% | 9% |
| Comment | 2% | **6%** |
| Elucidate | 1% | 2% |

"Discuss" has nearly halved and "Critically analyse" has halved, while "Explain" and
"Comment" have grown. That is a shift away from *write broadly about a topic* toward *say
what is happening mechanically, then add one line of judgement*. An essay-style answer scores
less than it used to.

Mains is also fixed in shape: 1,292 of 1,615 questions are **10 marks / 150 words**. That is
15 words per mark. 20 questions in 180 minutes is 9 minutes each. Any practice that does not
hit that pace is practising a different exam.

---

## What is "due" in 2027 (weak list, use with care)

Things asked 2+ times but not since 2022 (noise removed):

`Buddha / Buddhism (last 2020), Wildlife (2019), Indian National Congress (2019),
Himachal Pradesh (2022), Madhya Pradesh (2022), Legislative Assembly (2019),
Recognition of Forest Rights (2021), UN-Habitat (2021), Aadhaar (2020)`

How much is this worth? An item seen in 3 of 14 years has roughly a 3-in-14 chance
(~21%) of showing up in a given year, against a ~1% chance for a random topic — a real 20×
lift, but still four times more likely to *not* appear. Use it as a revision prompt, never as
a bet.

⚠️ The extraction has about 20% English-word noise ("Location", "Right", "Protection"). The
counts above are only the clean ones.

---

## How to actually use all of this

1. **Stop looking for predicted questions.** 90% of named items never repeat. The effort is
   better spent on the 3% that do.
2. **Over-learn the recurring core**: constitutional bodies, constitutional articles,
   Governor/Speaker/PM powers, Money Bill, and India's neighbours + your own states.
3. **Practise the 2023+ format**, not pre-2023 papers. Statement-checking is ~half the paper.
4. **Test the "less current affairs" claim** on 50 random questions. If it holds, move hours
   from news to static revision.
5. **Mains: train "Explain" and "Comment"**, not "Discuss". Mechanism plus one line of
   judgement, 150 words in 9 minutes.

---

## What this analysis cannot do

- **It cannot name the 2027 questions.** The data does not contain that information; the
  exam is built specifically to avoid it.
- **2026 is the least trustworthy year in the file.** All 99 of its rows have difficulty
  "Medium", which means that column was bulk-filled, not judged. Its section labels are also
  lumped differently from every other year.
- **Tagging is half-finished.** `sub_theme` is empty in all 1,615 mains rows. `nature` is
  empty in 6 of 14 prelims years. Any finer-grained prediction than the tables above is not
  possible until those are filled.
