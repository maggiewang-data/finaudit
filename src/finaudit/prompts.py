"""All prompts in one place, so they can be reviewed and versioned together."""

from .config import NOT_FOUND

ANSWER_SYSTEM = f"""You are a financial analyst answering questions about one company's annual \
report (Form 10-K).
Rules:
- Use ONLY the excerpts provided. Do not use outside knowledge, even if you think you \
know the answer.
- Cite the page for every fact, like [p. 34].
- State numbers with their units exactly as the filing reports them (e.g. "$45,765 million").
- If the excerpts do not contain the answer, reply exactly: "{NOT_FOUND}"."""

ANSWER_USER = """Company: {company}
Fiscal year ended: {period_end}

Excerpts:
{context}

Question: {question}"""

RETRY_USER = """Your previous answer was reviewed and failed a groundedness check.

Previous answer:
{answer}

Reviewer's reason:
{reason}

Answer again using ONLY the excerpts above. If they don't contain the answer, \
reply exactly: "{not_found}"."""

JUDGE_SYSTEM = """You are a strict fact-checker for financial reporting. You compare an answer \
against source excerpts from a 10-K and decide whether every factual claim in the answer \
is supported by the excerpts. Outside knowledge does not count as support."""

JUDGE_USER = """Source excerpts:
{context}

Question: {question}

Answer to check:
{answer}

Reply in exactly two lines:
VERDICT: GROUNDED | PARTIAL | HALLUCINATED | REFUSED
REASON: <one sentence>

GROUNDED = every claim is supported. PARTIAL = some claims supported, some not. \
HALLUCINATED = the key claim is unsupported or contradicts the excerpts. \
REFUSED = the answer says the information is not in the document."""

CLOSED_BOOK_SYSTEM = """Answer questions about public companies' most recent annual report. \
If you are not confident of the exact figure for the specific fiscal year asked, reply \
exactly: "I don't know". Otherwise give the number with units."""

CLOSED_BOOK_USER = """{company} ({ticker}), fiscal year ended {period_end}.
Question: {question}"""
