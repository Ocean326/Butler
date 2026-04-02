# -*- coding: utf-8 -*-
"""
端到端测试：模拟从 run_agent 返回到 _send_output_files 的完整流程

用法:
  cd scripts/feishu-bots && python tests/run_decide_e2e_test.py
  # 带实际上传（需先发一条消息到飞书机器人，复制 message_id 到环境变量）:
  $env:FEISHU_TEST_MESSAGE_ID="om_xxx"; python tests/run_decide_e2e_test.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bots"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "bots"))

# 加载配置
import json
cfg_path = os.path.join(os.path.dirname(__file__), "..", "configs", "butler_bot.json")
with open(cfg_path, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

import agent
agent.CONFIG.clear()
agent.CONFIG.update(CONFIG)

workspace = CONFIG.get("workspace_root", "")

# 模拟 run_agent 的返回值（与管家bot 中处理后的格式一致）
MOCK_AGENT_RETURN = """正在读取工作区内与 GPT 5.4 相关的 Markdown 文件。

以下是 4 个文件的摘要，已整理好发给你：

1. **gpt54_news_20250307.md** - 最新资讯
2. **GPT54_研究空白.md** - 研究空白
3. **GPT54_文献卡.md** - 文献卡
4. **GPT54_学术检索与文献整理.md** - 学术检索

【decide】
[{"send": "工作区/literature/GPT54_研究空白.md"}, {"send": "工作区/literature/GPT54_文献卡.md"}, {"send": "工作区/literature/GPT54_学术检索与文献整理.md"}, {"send": "工作区/literature/gpt54_news_20250307.md"}]"""


def main():
    print("=== 模拟 handle_message_async 中的流程 ===\n")

    # 1. 解析
    print("[1] 解析 decide...")
    clean_reply, decide_list = agent._parse_decide_from_reply(MOCK_AGENT_RETURN)
    print(f"    clean_reply 长度: {len(clean_reply)}")
    print(f"    decide_list 长度: {len(decide_list)}")
    if not decide_list:
        print("    [FAIL] 未解析到 decide!")
        return 1
    print(f"    [OK] 解析到: {[d.get('send') for d in decide_list]}\n")

    # 2. 路径检查
    print("[2] 路径检查...")
    for d in decide_list:
        p = (d.get("send") or "").strip()
        full = os.path.join(workspace, p) if not os.path.isabs(p) else p
        exists = os.path.isfile(full)
        size = os.path.getsize(full) if exists else 0
        ok = exists and size <= agent.OUTPUT_FILE_MAX_BYTES
        print(f"    {p} -> exists={exists} size={size} ok={ok}")
    print()

    # 3. 测试 upload_file（不依赖 message_id）
    print("[3] 测试 upload_file API...")
    test_path = os.path.join(workspace, "工作区/literature/gpt54_news_20250307.md")
    fkey = agent.upload_file(test_path)
    if fkey:
        print(f"    [OK] 上传成功 file_key={fkey[:50]}...")
    else:
        print("    [FAIL] 上传失败，请检查 app_id/app_secret 或飞书权限")
    print()

    # 4. 实际上传并回复（需 message_id）
    msg_id = os.environ.get("FEISHU_TEST_MESSAGE_ID", "")
    if msg_id:
        print(f"[4] 实际上传并回复 message_id={msg_id[:40]}...")
        agent._send_output_files(msg_id, workspace, decide_list)
        print("    [OK] 发送完成")
    else:
        print("[4] 跳过回复（设置 FEISHU_TEST_MESSAGE_ID 可测试完整发送）")

    print("\n=== 自测完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
