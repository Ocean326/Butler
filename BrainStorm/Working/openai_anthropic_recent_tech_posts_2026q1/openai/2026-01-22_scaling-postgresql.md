# Scaling PostgreSQL to power 800 million ChatGPT users

- 机构：OpenAI
- 日期：2026-01-22
- 分类：Engineering
- 原文链接：https://openai.com/index/scaling-postgresql/
- 关键词：database, postgresql, replica, pgbouncer, caching, rate limiting

## 中文速览
- 讲的是 OpenAI 如何把单主 PostgreSQL 架构继续推到更高读吞吐，而不是立刻全面分片。
- 核心手段包括：读流量尽量下沉到近 50 个只读副本、通过 PgBouncer 做连接池化、缓存防击穿、分层限流，以及把可分片的高写入 workload 迁移到 Cosmos DB 一类分片系统。
- 文中强调当前 PostgreSQL 仍保持单主写入，原因是对既有业务做分片改造成本极高；在读多写少前提下，先榨干现有架构的上限更划算。
- 这篇很适合看“高增长产品下，工程上如何延后复杂分片”的思路。

## 备注
官方站原文链接；本地文件为中文整理摘要，不是网页镜像。
