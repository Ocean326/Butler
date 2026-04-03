# Fulltext PDF Gap and Plan

## Current status
- Local `docs/0402/fulltext_cache/` is not materialized in this repository.
- The current 100-paper chain is recoverable only through bounded-repair notes summarized into the stable `docs/0402` package.
- The bounded repair recorded a prior remote verification that five evidence tables and one bibliography file each existed with 100 data rows (or 100 entries plus header) and that `stable_access_url` coverage was 100/100.
- A fresh SSH re-check on 2026-04-02 could not find `/home/jianghy/Transfer_Recovery/docs/0402`, so the evidence tables are presently missing from both the local repo and the remote target path.

## Provenance used in this bounded repair
- Main evidence recovery source: flow-local drafting notes used during the bounded repair and intentionally omitted from the portable repo snapshot.
- Verification log source: flow-local verification notes used during the bounded repair and intentionally omitted from the portable repo snapshot.
- Main draft source: `docs/0402/20260402_KDD_Section1_en.md`.

## 100-paper key list
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

## Gap summary
- Missing locally: evidence CSVs, bibliography mirror, and 100 local PDFs.
- Missing remotely at re-check time: `docs/0402/` tree under `/home/jianghy/Transfer_Recovery`.
- Still available locally: recovered narrative, representative paper ids, prior verification logs, and the 100-key index above.

## Recovery plan
1. Recreate or restore the evidence tables and bibliography mirror under `docs/0402/` from the authoritative research workspace.
2. Add `fulltext_cache/` plus a manifest that maps each paper id to `local_pdf_path` and retrieval status.
3. Replace the current trace-note workflow with true `\cite{...}` references once the bibliography file is restored.
4. Rebuild the final ACM/KDD PDF using `docs/0402/kdd_template_pdf_build.md`.
