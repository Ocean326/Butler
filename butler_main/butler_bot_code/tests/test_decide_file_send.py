# -*- coding: utf-8 -*-
"""
自测：decide 解析与文件发送流程

运行:
  cd scripts/feishu-bots/bots && python -m pytest ../tests/test_decide_file_send.py -v -s
  或
  cd scripts/feishu-bots/bots && python ../tests/test_decide_file_send.py
"""

from __future__ import annotations

import json
import os
import sys

# 确保能导入 butler_bot 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "butler_bot"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "butler_bot"))

# 加载配置
import json as _json
_config_path = os.path.join(os.path.dirname(__file__), "..", "configs", "butler_bot.json")
if os.path.isfile(_config_path):
    with open(_config_path, "r", encoding="utf-8") as f:
        _CONFIG = _json.load(f)
    workspace = _CONFIG.get("workspace_root", os.getcwd())
else:
    workspace = os.path.join(os.path.dirname(__file__), "..", "..", "..")
    _CONFIG = {"workspace_root": workspace}

# 注入 CONFIG 供 agent 使用
import agent as _agent
_agent.CONFIG.clear()
_agent.CONFIG.update(_CONFIG)


def test_parse_decide():
    """测试 decide 解析"""
    sample = '''这是一段正文。

【decide】
[{"send": "./工作区/literature/GPT54_研究空白.md"}, {"send": "./工作区/literature/GPT54_文献卡.md"}, {"send": "./工作区/literature/GPT54_学术检索与文献整理.md"}, {"send": "./工作区/literature/gpt54_news_20250307.md"}, {"send": "./butler_bot_agent/agents/local_memory/GPT-5.4发布与文献整理记录.md"}]'''
    body, decide_list = _agent._parse_decide_from_reply(sample)
    assert "【decide】" not in body, "正文应不含 decide 块"
    assert len(decide_list) == 5, f"应解析到 5 条，实际 {len(decide_list)}"
    paths = [d.get("send") for d in decide_list]
    assert "./工作区/literature/GPT54_研究空白.md" in paths
    assert "./butler_bot_agent/agents/local_memory/GPT-5.4发布与文献整理记录.md" in paths
    print(f"[OK] 解析成功: {len(decide_list)} 条")
    return decide_list


def test_path_resolution():
    """测试路径解析与文件存在性"""
    decide_list = [
        {"send": "./工作区/literature/GPT54_研究空白.md"},
        {"send": "./工作区/literature/GPT54_文献卡.md"},
        {"send": "./工作区/literature/GPT54_学术检索与文献整理.md"},
        {"send": "./工作区/literature/gpt54_news_20250307.md"},
        {"send": "./butler_bot_agent/agents/local_memory/GPT-5.4发布与文献整理记录.md"},
    ]
    found = []
    for d in decide_list:
        p = (d.get("send") or "").strip()
        if not p:
            continue
        full = os.path.join(workspace, p) if not os.path.isabs(p) else p
        exists = os.path.isfile(full)
        size = os.path.getsize(full) if exists else 0
        ok = exists and size <= _agent.OUTPUT_FILE_MAX_BYTES
        print(f"  {p} -> exists={exists} size={size} ok={ok}")
        if ok:
            found.append(full)
    print(f"[OK] 可发送 {len(found)} 个文件")
    return found


def test_full_send_dry_run():
    """模拟完整发送流程（不实际调用 API）"""
    sample = '''正文

【decide】
[{"send": "./工作区/literature/gpt54_news_20250307.md"}]'''
    body, decide_list = _agent._parse_decide_from_reply(sample)
    assert len(decide_list) >= 1
    # 不调用 _send_output_files，只验证流程
    print(f"[OK] 完整流程（解析）通过")


def test_actual_upload_and_send():
    """实际调用上传与发送（需有效 message_id）"""
    # 使用环境变量传递 message_id，无则跳过
    msg_id = os.environ.get("FEISHU_TEST_MESSAGE_ID", "")
    if not msg_id:
        print("[SKIP] 未设置 FEISHU_TEST_MESSAGE_ID，跳过实际上传测试")
        return
    decide_list = [
        {"send": "./工作区/literature/gpt54_news_20250307.md"},
    ]
    print(f"[RUN] 实际上传并回复 message_id={msg_id[:30]}...")
    _agent._send_output_files(msg_id, workspace, decide_list)
    print("[OK] 发送完成")


if __name__ == "__main__":
    print("=== 1. 测试 decide 解析 ===")
    test_parse_decide()
    print("\n=== 2. 测试路径解析 ===")
    test_path_resolution()
    print("\n=== 3. 测试完整流程（dry run）===")
    test_full_send_dry_run()
    print("\n=== 4. 实际上传（可选）===")
    test_actual_upload_and_send()
    print("\n=== 自测完成 ===")
