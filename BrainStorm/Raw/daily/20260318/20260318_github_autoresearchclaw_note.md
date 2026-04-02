# AutoResearchClaw —— 全自主科研论文生成管线

> 来源：GitHub `aiming-lab/AutoResearchClaw`  
> 抓取时间：2026-03-18  
> 项目地址：https://github.com/aiming-lab/AutoResearchClaw  
> 许可证：MIT | ⭐ 4,390+ | 最新版本：v0.3.0 (2026-03-17)

---

## 一句话定位

"Chat an Idea. Get a Paper." —— 输入一句自然语言研究想法，全自动产出会议级学术论文（含 LaTeX、BibTeX、实验代码、图表、Peer Review）。

---

## 23-Stage, 8-Phase Pipeline

```
Phase A: Research Scoping          Phase E: Experiment Execution
  1. TOPIC_INIT                      12. EXPERIMENT_RUN
  2. PROBLEM_DECOMPOSE               13. ITERATIVE_REFINE  ← self-healing

Phase B: Literature Discovery      Phase F: Analysis & Decision
  3. SEARCH_STRATEGY                 14. RESULT_ANALYSIS    ← multi-agent
  4. LITERATURE_COLLECT  ← real API  15. RESEARCH_DECISION  ← PIVOT/REFINE
  5. LITERATURE_SCREEN   [gate]
  6. KNOWLEDGE_EXTRACT               Phase G: Paper Writing
                                     16. PAPER_OUTLINE
Phase C: Knowledge Synthesis         17. PAPER_DRAFT
  7. SYNTHESIS                       18. PEER_REVIEW        ← evidence check
  8. HYPOTHESIS_GEN    ← debate      19. PAPER_REVISION

Phase D: Experiment Design         Phase H: Finalization
  9. EXPERIMENT_DESIGN   [gate]      20. QUALITY_GATE      [gate]
 10. CODE_GENERATION                 21. KNOWLEDGE_ARCHIVE
 11. RESOURCE_PLANNING               22. EXPORT_PUBLISH     ← LaTeX
                                     23. CITATION_VERIFY    ← relevance check
```

Gate stages (5, 9, 20) 支持 human-in-the-loop 审批或 `--auto-approve` 跳过。

---

## 核心机制

### Multi-Agent Subsystems (v0.2.0+)
- **CodeAgent**: 4-phase 架构，迭代修复循环（最多 3 轮），硬验证门控（禁止相同消融、硬编码指标、跨文件导入错误），AST-based CodeMem
- **BenchmarkAgent**: 领域感知基准测试，导入验证，预训练模型支持
- **FigureAgent**: 学术级可视化，色盲安全配色，300 DPI 输出

### PIVOT / REFINE Loop
Stage 15 自主决策：PROCEED / REFINE（微调参数→Stage 13）/ PIVOT（新方向→Stage 8），产物自动版本化。

### Sentinel Watchdog
后台质量监控：NaN/Inf 检测、论文-证据一致性、引用相关性评分、反编造守卫。

### 4-Layer Citation Verification
arXiv ID check → CrossRef/DataCite DOI → Semantic Scholar title match → LLM relevance scoring。幻觉引用自动移除。

### Self-Learning (MetaClaw, v0.3.0)
跨轮次知识迁移：失败 → 结构化 lessons → 可复用 skills → 注入全部 23 个 stage。
实验结果：stage 重试率 -24.8%，refine 周期 -40%，鲁棒性 +18.3%。

### Hardware-Aware Execution
自动检测 GPU (NVIDIA CUDA / Apple MPS / CPU-only)，适配代码生成、imports 和实验规模。

---

## 产出物

| 产出 | 说明 |
|------|------|
| `paper_draft.md` | 完整学术论文（Introduction → Conclusion） |
| `paper.tex` | 会议级 LaTeX（NeurIPS/ICLR/ICML 模板） |
| `references.bib` | 真实 BibTeX，自动剪枝匹配行内引用 |
| `verification_report.json` | 4 层引用完整性+相关性验证 |
| `experiment runs/` | 代码+沙箱结果+结构化 JSON 指标 |
| `charts/` | 带误差棒和置信区间的对比图 |
| `reviews.md` | 多 Agent Peer Review（方法-证据一致性检查） |
| `evolution/` | 每轮自学习 lessons |

---

## 集成方式

- **OpenClaw 集成**（推荐）：读 `RESEARCHCLAW_AGENTS.md` 自动引导
- **ACP 协议**：支持任意 ACP 兼容 Agent（Claude Code / Codex CLI / Gemini CLI 等）作为 LLM 后端
- **OpenClaw Bridge**：6 个可选适配器（cron / message / memory / sessions_spawn / web_fetch / browser）
- **独立 CLI / Python API / AI 编码助手**

---

## 受启发项目

- AI Scientist (Sakana AI)
- AutoResearch (Karpathy)
- FARS (Analemma)
