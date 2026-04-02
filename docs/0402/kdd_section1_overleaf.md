---
title: "Section 1. Background and Current Landscape"
subtitle: "Overleaf-ready Markdown handoff"
---

# 1 Background and Current Landscape

## Problem definition
Road-network-constrained trajectory recovery studies how to reconstruct a dense trajectory, a route-segment sequence, or a complete path from sparse and partially missing observations while preserving explicit topological feasibility on the road network. Unlike conventional map matching, the task is not limited to aligning observed points to candidate roads; it must also infer latent locations, connecting segments, and path legality over the missing intervals under a unified model. The problem is therefore a coupled estimation task over topology, spatiotemporal dependence, and uncertainty induced by low sampling rates, long missing spans, and irregular sampling intervals. As a result, the literature has converged on map-constrained sparse-GPS recovery as the core benchmark setting, while camera-based recovery, multimodal recovery, and generative completion extend the task boundary rather than replace its main formulation. (Trace to the evidence map for representative paper ids before replacing these notes with `\cite{...}` commands in the final ACM manuscript.)

## Method evolution
The methodological line first grew from constrained path inference and sequence restoration, where sparse observations were completed by searching road-feasible transitions and learning map-aware recovery under strong structural priors. It then moved toward graph-enhanced and transformer-style recovery, where richer spatial representations, longer-range road dependencies, and interval-aware temporal modeling improved performance beyond local transition heuristics. More recent work broadens the design space again by incorporating pretrained models, streaming inference, multimodal cues, and generative mechanisms to better handle longer missing spans, irregular intervals, and higher uncertainty. Across these shifts, however, sparse-GPS road-network reconstruction remains the dominant evaluation anchor, so newer paradigms are still judged by how well they preserve or extend this core recovery setting. (Insert final citations using the paper ids listed in `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`.)

## Limitations of prior work
Despite rapid progress, prior studies still optimize point-wise reconstruction more directly than route validity or segment-level fidelity, so gains on MAE- or RMSE-style metrics do not necessarily imply stronger path recovery quality. A second limitation is that road-network knowledge remains unevenly incorporated: weaker methods underuse structural priors, whereas stronger graph or semantic designs often introduce heavier assumptions, curated inputs, or higher transfer cost across cities and sensing regimes. Generalization evidence is also thinner than in-distribution accuracy evidence, especially under irregular intervals, observation shift, and cross-domain deployment. Finally, foundation-model and generative directions enlarge the modeling space, but they still leave unresolved how to maintain topology consistency, data efficiency, and operational stability under strict road constraints. (Replace this trace note with KDD-style citations once the bibliography mirror is restored.)

## This paper's entry point
This paper therefore does not position itself as merely another deeper recovery backbone. Instead, it treats sparse trajectory recovery as a unified point-level and segment-level problem under explicit road-network constraints, and argues that route legality, reconstruction fidelity, and transferability should be modeled and evaluated together rather than as loosely connected local improvements. Our entry point is to organize prior work around the missing synthesis between road priors, spatiotemporal dynamics, and robustness to irregular or shifted observations. This framing gives the next methodological step a clearer target: success should be judged by coherent recovery quality and cross-scenario robustness, not only by isolated benchmark gains on a single recovery submetric.

## Notes for Overleaf
- Replace trace notes with `\cite{...}` using the representative paper ids in `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`.
- Move this section into the ACM manuscript body and keep the section title aligned with the final paper outline.
- Keep `docs/0402/kdd_template_pdf_build.md` as the packaging checklist for the eventual ACM/KDD PDF build.
