# Tokenizer accuracy benchmark

`python -m contextshift.benchmark --suite tokenizer`

10-sample corpus spanning short phrases, code, URLs, emoji/non-ASCII
text, and long repeated content, measured against `TiktokenTokenizer`
(`cl100k_base`) as the reference — see
[ADR 0014](../decisions/0014-accurate-tokenizers.md) for the full
reasoning and the corpus itself
(`tests/test_tokenizer_bench.py::test_heuristic_tokenizer_error_rate_against_tiktoken_is_measured_not_assumed`).

| Tokenizer | Mean Abs. Error | Mean % Error | Max % Error | Samples |
| --- | --- | --- | --- | --- |
| HeuristicTokenizer | 9.60 | 27.77% | 93.33% | 10 |
| TiktokenTokenizer | 0.00 | 0.00% | 0.00% | 10 |

`TiktokenTokenizer` scoring zero error against itself is the harness's
own sanity check, not a claim about its accuracy against a *different*
reference (e.g. Anthropic's tokenizer, which this corpus doesn't
compare against).
