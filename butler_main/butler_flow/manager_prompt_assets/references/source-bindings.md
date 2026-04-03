Source bindings

- `source_bindings` should only include sources that materially help this template or flow.
- Prefer a short, high-signal set of source paths or docs over exhaustive context dumps.
- If a source only matters for the current run, keep it at the flow layer instead of polluting the template.
- If the request can be fulfilled from current asset context alone, leave `source_bindings` empty.
