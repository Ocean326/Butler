# Section 1. Background and Current Landscape

## Problem definition
Road-network-constrained trajectory recovery asks how to reconstruct a dense trajectory, an ordered route-segment sequence, or a complete path from sparse and partially missing observations while preserving explicit topological feasibility on the road network. Unlike conventional map matching, the task is not only to align observed points to candidate roads, but also to infer the latent positions, connecting segments, and path-level legality of the missing intervals under the same model. The problem is therefore a coupled estimation task over topology, spatiotemporal dependence, and uncertainty induced by low sampling rates, missing spans, and irregular intervals. Existing high-impact work has consequently converged on map-constrained sparse-GPS recovery as the core benchmark setting, while camera-based recovery, multimodal recovery, and generative completion define the expanding boundary of the problem rather than replacing its main formulation.
(Evidence anchors: `docs/0402/fulltext_reference_summaries_20260402.csv`, `docs/0402/classification_matrix_v1_20260402.csv`, `docs/0402/papers_master_20260402.csv`, `docs/0402/bib/transfer_recovery_20260402.bib`; representative keys: `Ren2021MTrajRec`, `Chen2023RNTrajRec`, `Wei2024MMSTGED`, `Sun2025TedTrajRec`.)

## Method evolution
The methodological line first developed from constrained path inference and sequence restoration, where sparse observations were completed by searching road-feasible transitions and learning map-aware point recovery under strong structural priors. It then evolved toward graph-enhanced and transformer-based recovery, in which richer spatial representations, longer-range road dependencies, and interval-aware temporal modeling improved performance beyond local transition heuristics. Recent work broadens the design space again by incorporating pretrained models, streaming inference, multimodal cues, and generative mechanisms, aiming to handle longer missing spans, irregular sampling, and higher uncertainty. Across these shifts, however, the field still treats sparse-GPS road-network reconstruction as the dominant evaluation anchor, so newer paradigms are judged largely by how well they preserve or extend this core recovery setting.
(Evidence anchors: `docs/0402/fulltext_reference_summaries_20260402.csv`, `docs/0402/reading_summaries_v2_20260402.csv`, `docs/0402/classification_matrix_v1_20260402.csv`, `docs/0402/bib/transfer_recovery_20260402.bib`; representative keys: `Ren2021MTrajRec`, `Zhao2024GRFTrajRec`, `Wei2024PLMTrajRec`, `han2025stream`, `Long2025DiffMove`.)

## Limitations of prior work
Despite rapid progress, prior studies still optimize point-wise reconstruction more directly than route validity or segment-level fidelity, so better MAE- or RMSE-style outcomes do not always imply stronger path recovery quality. A second limitation is that road-network knowledge remains unevenly incorporated: some methods rely on relatively weak or implicit structural encoding, whereas stronger graph or semantic designs often demand heavier assumptions, more curated inputs, or higher transfer cost across cities and sensing regimes. Generalization evidence is also thinner than in-distribution accuracy evidence, especially for irregular intervals, observation shift, and cross-domain deployment. Finally, foundation-model and generative directions enlarge the modeling space, but they still leave unresolved how to maintain topology consistency, data efficiency, and operational stability under strict road constraints.
(Evidence anchors: `docs/0402/classification_matrix_v1_20260402.csv`, `docs/0402/fulltext_reference_summaries_20260402.csv`, `docs/0402/reading_summaries_v2_20260402.csv`, `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`; representative keys: `Chen2024TERI`, `Wei2024MMSTGED`, `Wei2024PLMTrajRec`, `Yu2022CameraRecovery`, `shi2023road_const`.)

## This paper's entry point
This paper therefore does not position itself as merely another deeper recovery backbone. Instead, it treats sparse trajectory recovery as a unified point-level and segment-level problem under explicit road-network constraints, and argues that route legality, reconstruction fidelity, and transferability should be modeled and evaluated together rather than as loosely connected local improvements. Our entry point is to organize prior work around the missing synthesis between road priors, spatiotemporal dynamics, and robustness to irregular or shifted observations. This framing gives the next methodological step a clearer target: success should be judged by coherent recovery quality and cross-scenario robustness, not only by isolated benchmark gains on one recovery submetric.
(Evidence anchors: `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`, `docs/0402/classification_matrix_v1_20260402.csv`, `docs/0402/fulltext_reference_summaries_20260402.csv`, `docs/0402/bib/transfer_recovery_20260402.bib`; representative keys: `Ren2021MTrajRec`, `Chen2023RNTrajRec`, `Wei2024MMSTGED`, `Chen2024TERI`, `Long2025DiffMove`.)

## Overleaf and PDF placeholders
The current Overleaf-oriented Markdown handoff already exists at `docs/0402/20260402_KDD_Section1_overleaf_ready.md`. The current review PDF already exists at `docs/0402/20260402_KDD_Section1_en_review.pdf`. A full ACM/KDD-template PDF should be generated after the complete paper is merged into the final LaTeX project; recommended placeholder target: `docs/0402/pdf/transfer_recovery_kdd_draft_v1.pdf`.

## 100-paper bibliography anchors
The current 100-paper evidence base is materialized in `docs/0402/papers_master_20260402.csv`, `docs/0402/classification_matrix_v1_20260402.csv`, `docs/0402/fulltext_reference_summaries_20260402.csv`, and `docs/0402/reading_summaries_v2_20260402.csv`. The 100 bib keys in `docs/0402/bib/transfer_recovery_20260402.bib` are:

1. `Ren2021MTrajRec`
2. `Sun2021PeriodicMove`
3. `Yu2022CameraRecovery`
4. `Chen2023RNTrajRec`
5. `Wei2024MMSTGED`
6. `Zhao2024GRFTrajRec`
7. `Chen2024TERI`
8. `Wei2024PLMTrajRec`
9. `Sun2025TedTrajRec`
10. `Long2025DiffMove`
11. `tian2025efficient`
12. `li2021a`
13. `chen2025vehicle`
14. `liu2025vehicle`
15. `lin2021vehicle`
16. `han2025stream`
17. `shi2025vehicle`
18. `shi2023road_const`
19. `li2025study`
20. `ma2025vehicle`
21. `ye2024a`
22. `shi2024road`
23. `barua2023ptin`
24. `zhao2022trajgat`
25. `wei2021a`
26. `bian2020a`
27. `xu2025deep_learn`
28. `ye2025map_inform`
29. `jin2025markov`
30. `xu2025physics`
31. `wang2025towards`
32. `bai2025trajectory`
33. `zheng2025vehicle`
34. `long2024learning`
35. `zhao2024vehicle`
36. `zhang2023enhancing`
37. `deng2023fusing`
38. `chondrogiann2022history`
39. `cao2022map`
40. `chen2022vehicle`
41. `qi2021vehicle`
42. `chen2026lidar`
43. `qiu2025a`
44. `xu2025a`
45. `ma2025an`
46. `ma2025arterial`
47. `kaya2025currus`
48. `ariyarathna2025deepsneak`
49. `truong2025efficient`
50. `li2025heterogene`
51. `barua2025human`
52. `qiu2025multi_node`
53. `jun2025s_traverse`
54. `wang2025trajdiff`
55. `choi2025vehicle`
56. `zhang2025vehicle`
57. `zhao2024a`
58. `shiau2024an`
59. `wang2024an`
60. `barua2024htim`
61. `zhang2024long_term`
62. `safarzadeh2024map`
63. `zhou2024trajectory`
64. `wang2024vehicle`
65. `hu2023a`
66. `zhang2023segmentati`
67. `chen2023unsupervis`
68. `long2023vehicle`
69. `deng2023vehicle`
70. `wang2022a`
71. `wang2022a`
72. `sun2022a`
73. `zhou2022platoon`
74. `tortora2022pytrack`
75. `li2022research`
76. `dong2021an`
77. `tong2021large_scal`
78. `he2021study`
79. `kashiwabara2021vehicle`
80. `yu2021vehicle`
81. `tan2020a`
82. `nawaz2020gps`
83. `aubin_franko2020kernel`
84. `liu2020map`
85. `hu2020vehicle`
86. `tang2025elevation_`
87. `wang2024cmmtse`
88. `yang2024detecting`
89. `liu2024graphmm`
90. `yang2023aircraft`
91. `zhang2023hybrid`
92. `jiang2023l2mm`
93. `dogramadzi2022accelerate`
94. `huang2022an`
95. `yu2022high_frequ`
96. `patnala2022hybridizat`
97. `yu2022low_freque`
98. `xiao2021path`
99. `nadeeshan2020a`
100. `luo2020incrementa`

## Suggested local PDF tree
No local PDF mirrors are created in this bounded step. If the operator later requires local mirroring, the recommended non-breaking directory layout is:

`docs/0402/fulltext_cache/`
`docs/0402/fulltext_cache/01_core_sparse_gps/`
`docs/0402/fulltext_cache/02_graph_and_transformer/`
`docs/0402/fulltext_cache/03_generalization_and_irregular_interval/`
`docs/0402/fulltext_cache/04_multimodal_and_camera/`
`docs/0402/fulltext_cache/05_generative_and_foundation/`
`docs/0402/fulltext_cache/README.md`

## Readiness note
Corrected in this bounded repair: the target output is normalized into one English KDD-style Section 1 file with the four required headings, direct evidence anchors, Overleaf/PDF placeholders, and the full 100-key bibliography index. Remaining issues: local PDF mirrors are still absent, ACM/KDD final pagination is not yet verified, and the flow still needs operator confirmation on whether `stable_access_url + systematic summaries` is sufficient for the 100-paper delivery requirement. Review next: `docs/0402/20260402_KDD风格_研究背景与现状_v2_证据映射.md`, `docs/0402/20260402_delivery_status.md`, `docs/0402/20260402_quality_review_report.md`, `docs/0402/readiness.md`.
