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

`make eval` runs the full evaluation and writes [`results/eval.md`](results/eval.md). It covers:
- 10 in-document questions on Apple's fiscal 2026 10-K, scored against XBRL
- 5 out-of-document questions (today's stock price, the next CEO, …) where the only correct answer is "Not found in document"
- the judge-vs-ground-truth table
- the bias probe on both companies

The run takes about 100 API calls, well under $1.

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
make test                 # 23 tests, no API key needed (a scripted fake model stands in)
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
tests/           23 tests using real excerpts and figures from Apple's fiscal 2026 10-K
```

## Limits
- One filing per company and a small question set. This is a working method, not a benchmark.
- The numeric checker covers figures. It can't verify qualitative claims ("risks include…"), which still rely on the judge.
- The bias probe uses one pair of companies. A real study would use many pairs matched by industry.
