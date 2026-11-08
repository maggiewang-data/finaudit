# FinAudit: Checking Whether an LLM's Answer About a 10-K Is True

An LLM can answer a question about an annual report fluently, cite a page, and still give the wrong year's number. In a regulated setting, that answer is worse than no answer, because nothing about it looks wrong.

FinAudit answers questions about SEC 10-K filings and then **checks its own answers**. It does this in two independent ways, so the checking itself can be checked.

```
question
  → retrieve the 3 most relevant pages of the 10-K (BM25)
  → answer using ONLY those pages, citing them, or say "Not found in document"
  → judge: a second, different model decides GROUNDED / PARTIAL / HALLUCINATED / REFUSED
  → if rejected: show the model the judge's reason and let it try once more
  → audit log: one JSON line per question, recording everything above
```

Separately, `evaluate.py` scores every answer against **the company's own XBRL figures from the same filing**. That measures how often the model is right and how often the judge is right.

---

## Why each design choice

**Ground truth comes from the filing itself, not from me.** Every 10-K is filed with machine-readable XBRL data containing the same figures as the financial statements. Comparing the model's numbers with those figures gives an answer key that doesn't depend on another model's opinion. For facts XBRL doesn't carry, such as headcount, I extracted the value by hand and recorded the page it came from.

**The judge is evaluated, not trusted.** LLM-as-judge is the standard way to flag hallucinations, but the judge is also a model. FinAudit reports a confusion table of judge verdicts against ground truth. A judge that waves through a wrong number (a false "GROUNDED") is the failure that matters most here, so that cell gets the attention.

**The judge is a different model from the answerer.** Asking a model to grade its own family's output invites shared blind spots. The answer and judge models are set separately in `.env`.

**One reflection retry, not a loop.** When the judge rejects an answer, the model sees the judge's reason and gets one more attempt. Each extra round costs money and latency, and an answer that fails twice should be escalated, not polished. Both attempts are logged, so the retry's effect is measurable rather than assumed.

**BM25 retrieval by default.** Financial questions usually share exact terms with the filing ("research and development", "net sales"), so keyword ranking works well with no model download and no cost. Dense embeddings are available as an option and are cached once rather than recomputed per query.

**An append-only audit log.** Each line records the filing's accession number, the pages the model saw, both model names, a hash of the prompts, every attempt with its verdict, and the token cost. Months later, "why did the system say this?" has a recorded answer.

## The representation-bias probe

Models see far more text about Apple than about a small company like Universal Electronics, a consumer electronics maker worth thousands of times less than Apple. Does that change how the model behaves on identical questions?

The probe asks the same seven financial questions about both companies under two conditions:

- **Closed book (no filing shown).** The prompt allows "I don't know." The fiscal year asked about (Apple's year ended September 2026) is newer than the model's training data, so any confident number has to come from memory of earlier years. The prediction: more "confidently wrong" answers for the famous company, and more honest "I don't know"s for the obscure one.
- **Open book (filing excerpts shown).** Both companies get the same number of pages and the same character budget, so neither gets more context. With the source in front of it, accuracy shouldn't depend on fame. A remaining gap would point to bias in how the model reads, not just in what it memorized.

The first version of this test used a made-up "SmallCo Inc." with a few invented sentences. I replaced it, because a fictional company can't trigger bias that comes from pretraining, and giving the two companies unequal context would have confounded any difference.

## Results

Answer model Claude Sonnet 5.5, judge model Claude Haiku 5.5, on Apple's 10-K for the fiscal year ended September 26, 2026. Full output: [`results/eval.md`](results/eval.md). Every call is in [`results/audit_log.jsonl`](results/audit_log.jsonl).

| | Result |
|---|---|
| In-document questions answered with the correct number | **9 / 10** |
| Out-of-document questions correctly refused | **5 / 5** |
| Reflection retries needed | 0 |
| Judge verdicts that matched ground truth | 14 / 15 |

### What the numbers mean

**The model didn't invent anything.** Asked for today's stock price or the next CEO, it said "Not found in document" every time. When the excerpts showed nearby numbers, like average buyback prices or a shareholder-return index, it said explicitly that these were *not* the current stock price.

**The one "wrong" answer was grounded, and that's the most useful finding.** Asked how much Apple paid to repurchase shares, the model answered $85.8 billion and cited the equity note. The XBRL ground truth is $86.4 billion: the *cash paid*, from the cash flow statement. Both numbers are in the filing. Repurchases are recorded when shares are retired, but cash moves on its own schedule (the filing mentions up-front payments on accelerated repurchase agreements). The judge correctly marked the answer GROUNDED, because it *was* supported by the page. **Only the independent ground-truth check caught that it wasn't the figure the question needed.** A groundedness judge answers "is this in the document?", not "is this the right number?", and a financial question can have several defensible answers. That's the case for keeping a check that doesn't rely on another model.

**The judge never raised a false alarm, but this test can't show how good it is at catching errors.** It accepted all 14 correct answers. The model made almost no mistakes, so the judge was barely tested on wrong answers. Measuring its catch rate needs a set of deliberately wrong answers (wrong year, wrong unit, wrong line item), and that's the next step.

### Representation-bias probe

| | Apple | Universal Electronics |
|---|---|---|
| Closed book: gave a number instead of "I don't know" | 0 / 7 | 0 / 7 |
| Open book, same context size: correct number | 7 / 7 | 6 / 7 |

**No size bias showed up.** I expected the model to answer Apple questions from memory, since it has seen far more about Apple. Instead it declined every closed-book question for both companies, because the fiscal year was newer than anything it could know.

**The one open-book miss wasn't about size.** Universal Electronics *lost money*, so its filing reports an "operating **loss**." The keyword search looked for "operating income", never retrieved the income statement, and the model correctly said the answer wasn't in the excerpts. The failure came from how unprofitable companies label a line, not from how famous the company is. I left it unfixed on purpose: changing retrieval after seeing the test question would inflate the score. The fix (treating "income" and "loss" as related terms) is listed below.

### What broke on the first live run, and what I changed

| Symptom | Cause | Fix |
|---|---|---|
| Judge verdicts read as UNPARSEABLE | The judge wrapped its verdict in markdown, and the parser expected an exact line prefix | Pattern-based parsing; raw judge replies saved in the audit log |
| Judge replies cut off ("VERDICT: GRO") and some answers truncated | Token limits set too low (150 for the judge, 600 for answers) | Higher limits; every cut-off reply is now flagged and counted |
| Unreadable judge replies triggered a retry | Retry logic treated a judge failure as an answer failure | Retry only on HALLUCINATED or PARTIAL |

The second run had 0 unreadable judge replies and 0 truncations.

## Connection to published work

This project is a small, concrete take on problems in Domyn's recent research:

| FinAudit layer | Related work |
|---|---|
| Groundedness judge on 10-K question answering | FinReflectKG / HalluBench: hallucination detection in financial QA over SEC 10-K filings |
| Large-cap vs. small-cap probe | Domyn's work on representation bias in LLM investment decisions, which found models favor large, highly visible firms |
| Audit log, and evaluating the judge itself | Domyn's whitepaper "When Algorithms Make Decisions, Who Verifies Them?" on continuous verification |

## Run it

```bash
make install
cp .env.example .env      # add your Anthropic API key and an SEC user-agent (name + email)
make fetch                # latest 10-Ks + XBRL ground truth for AAPL and UEIC
make ask Q="How much did Apple spend on research and development?"
make eval                 # full evaluation -> results/eval.md
make test                 # 24 tests, no API key needed (a scripted fake model stands in)
```

## Project structure
```
src/finaudit/
  sec.py         download the latest 10-K and the matching XBRL ground truth from EDGAR
  document.py    split the filing into its printed pages (EDGAR page-break markers)
  retrieval.py   BM25 retriever; optional cached embedding retriever
  prompts.py     every prompt in one place
  llm.py         raw Anthropic API client + a scripted fake for tests
  pipeline.py    retrieve -> answer -> judge -> retry -> audit log
  verify.py      judge parsing, refusal detection, numeric check against ground truth
  bias.py        large-cap vs. small-cap probe
  evaluate.py    full evaluation and report
tests/           24 tests using real excerpts and figures from Apple's fiscal 2026 10-K
```

## Limits and next steps
- One filing per company and a small question set. This is a working method, not a benchmark.
- **Measure the judge's catch rate** with deliberately wrong answers (wrong year, wrong unit, wrong line item).
- **Make metric questions precise** ("cash paid for repurchases, per the cash flow statement"), or accept every defensible figure in the filing.
- **Retrieval for loss-making companies:** treat "income" and "loss" as related terms, or combine keyword and embedding search.
- The numeric checker covers figures. It can't verify qualitative claims ("risks include…"), which still rely on the judge.
- The bias probe uses one pair of companies. A real study would use many pairs matched by industry.
