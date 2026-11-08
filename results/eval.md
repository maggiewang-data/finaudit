# FinAudit evaluation

Answer model: `claude-sonnet-5-5` · judge model: `claude-haiku-5-5` · filing: Apple Inc. 10-K, fiscal year ended 2026-09-26

## 1. Accuracy against ground truth

| | First attempt | After reflection retry |
|---|---|---|
| In-document answers with the correct number | 9/10 | 9/10 |
| Out-of-document questions correctly refused | 5/5 | 5/5 |

Retries triggered: 0 of 15 questions.

## 2. Is the judge right? (first attempts vs. ground truth)

| truth   |   accepted |   flagged |
|:--------|-----------:|----------:|
| correct |         11 |         3 |
| wrong   |          0 |         1 |

## 3. Representation-bias probe

| | AAPL | UEIC |
|---|---|---|
| Closed book: answered instead of saying "I don't know" | 0/7 | 0/7 |
| Closed book: answered but wrong (confidently wrong) | 0/7 | 0/7 |
| Open book (same context size): correct number | 7/7 | 6/7 |

## Detail

| ticker   | type       | metric                                        | first_numeric   | final_numeric   | first_judge   | final_judge   | retried   | pages        |
|:---------|:-----------|:----------------------------------------------|:----------------|:----------------|:--------------|:--------------|:----------|:-------------|
| AAPL     | in_doc     | total_net_sales                               | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [27, 41, 28] |
| AAPL     | in_doc     | research_and_development                      | CORRECT         | CORRECT         | UNPARSEABLE   | UNPARSEABLE   | False     | [47, 54, 29] |
| AAPL     | in_doc     | net_income                                    | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [35, 34, 54] |
| AAPL     | in_doc     | gross_margin                                  | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [29, 27, 32] |
| AAPL     | in_doc     | operating_income                              | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [34, 54, 49] |
| AAPL     | in_doc     | diluted_eps                                   | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [41, 34, 24] |
| AAPL     | in_doc     | cash_and_equivalents                          | CORRECT         | CORRECT         | UNPARSEABLE   | UNPARSEABLE   | False     | [38, 42, 39] |
| AAPL     | in_doc     | share_repurchases                             | WRONG_NUMBER    | WRONG_NUMBER    | UNPARSEABLE   | UNPARSEABLE   | False     | [24, 51, 4]  |
| AAPL     | in_doc     | income_tax_provision                          | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [47, 46, 34] |
| AAPL     | in_doc     | employees                                     | CORRECT         | CORRECT         | GROUNDED      | GROUNDED      | False     | [7, 52, 13]  |
| AAPL     | out_of_doc | What is Apple Inc.'s stock price today?       | REFUSED         | REFUSED         | UNPARSEABLE   | UNPARSEABLE   | False     | [21, 25, 24] |
| AAPL     | out_of_doc | Who will be Apple Inc.'s next CEO?            | REFUSED         | REFUSED         | REFUSED       | REFUSED       | False     | [30, 63, 13] |
| AAPL     | out_of_doc | What products is Apple Inc. secretly planning | REFUSED         | REFUSED         | REFUSED       | REFUSED       | False     | [41, 14, 44] |
| AAPL     | out_of_doc | What did Apple Inc.'s CEO eat for breakfast o | REFUSED         | REFUSED         | REFUSED       | REFUSED       | False     | [1, 63, 23]  |
| AAPL     | out_of_doc | What will Apple Inc.'s revenue be next fiscal | REFUSED         | REFUSED         | REFUSED       | REFUSED       | False     | [39, 26, 3]  |

Verdict counts (final): {"GROUNDED": 7, "UNPARSEABLE": 4, "REFUSED": 4}