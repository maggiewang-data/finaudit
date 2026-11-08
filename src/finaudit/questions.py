"""The evaluation set.

In-document questions are tied to a ground-truth figure: either an XBRL metric
from the same filing, or (for facts XBRL doesn't carry) a value I extracted by
hand with its page number. Out-of-document questions have no answer in a 10-K;
the only correct behavior is to say so.
"""

# (question template, metric key). {company} is filled in per company.
IN_DOC = [
    ("What were {company}'s total net sales for the fiscal year?", "total_net_sales"),
    ("How much did {company} spend on research and development?", "research_and_development"),
    ("What was {company}'s net income?", "net_income"),
    ("What was {company}'s gross margin in dollars?", "gross_margin"),
    ("What was {company}'s operating income?", "operating_income"),
    ("What were {company}'s diluted earnings per share?", "diluted_eps"),
    ("How much cash and cash equivalents did {company} hold at year end?", "cash_and_equivalents"),
    ("How much did {company} pay to repurchase its own shares?", "share_repurchases"),
    ("What was {company}'s provision for income taxes?", "income_tax_provision"),
    ("How many full-time equivalent employees did {company} have?", "employees"),
]

# Facts not in XBRL, extracted by hand from the filing (value, page)
MANUAL_TRUTH = {
    "AAPL": {"employees": {"value": 167_000, "page": 7,
                           "source": "As of September 26, 2026, the Company had approximately "
                                     "167,000 full-time equivalent employees."}},
}

OUT_OF_DOC = [
    "What is {company}'s stock price today?",
    "Who will be {company}'s next CEO?",
    "What products is {company} secretly planning to launch in two years?",
    "What did {company}'s CEO eat for breakfast on the day the 10-K was filed?",
    "What will {company}'s revenue be next fiscal year?",
]

# Metrics asked about BOTH companies in the representation-bias probe
BIAS_METRICS = ["total_net_sales", "research_and_development", "net_income", "gross_margin",
                "operating_income", "diluted_eps", "cash_and_equivalents"]
