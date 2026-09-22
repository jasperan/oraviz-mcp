# Historical research snapshot

`paper.pdf`, its LaTeX sources, and generated figures describe the original OraViz
token-efficiency experiment before security hardening. The copy published under
`docs/paper/`, the benchmark results, and the slides refer to the same historical
work. Their numbers and PDFs are preserved unchanged, not recomputed or validated
against the current tool schemas.

Implementation claims in the paper can therefore be outdated, particularly
authentication, SQL admission, LOB handling, output limits, auditing, and timeout
semantics. `ORACLE_CALL_TIMEOUT` bounds a database round trip, not an entire
statement or tool call. The lexical SQL guard is not a security proof.

Use [SECURITY.md](../SECURITY.md) for current guarantees, limitations, and deployment
responsibilities, the [README](../README.md) for current setup, and
[benchmarks/README.md](../benchmarks/README.md) for the historical methodology.
A new evaluation should identify its exact revision, configuration, and database
permissions and be published separately from these preserved results.
