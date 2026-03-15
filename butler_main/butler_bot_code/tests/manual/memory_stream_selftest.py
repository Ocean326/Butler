import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bots"))

import agent
from memory_manager import MemoryManager

cfg = json.loads((ROOT / "configs" / "butler_bot.json").read_text(encoding="utf-8"))
agent.CONFIG.clear()
agent.CONFIG.update(cfg)

agent.reply_message = lambda *args, **kwargs: True

summary_json = json.dumps(
    {
        "topic": "stream fallback selftest",
        "summary": "validated short-term memory persistence from streamed segments when final result is empty",
        "next_actions": ["confirm recent_memory updated"],
        "long_term_candidate": {
            "should_write": False,
            "title": "",
            "summary": "",
            "keywords": [],
        },
    },
    ensure_ascii=False,
)

memory = MemoryManager(config_provider=lambda: cfg, run_model_fn=lambda *args: (summary_json, True))
marker = f"selftest-{int(time.time())}"


def fake_run_agent(prompt, stream_callback=None, image_paths=None):
    if stream_callback:
        stream_callback(f"segment for {marker}")
    return ""


agent.handle_message_async(
    message_id=f"memory-selftest-{marker}",
    prompt=f"please remember {marker}",
    image_keys=None,
    run_agent_fn=fake_run_agent,
    supports_images=False,
    supports_stream_segment=True,
    on_reply_sent=lambda user_prompt, assistant_reply: memory.on_reply_sent_async(user_prompt, assistant_reply),
)

time.sleep(3)
print(marker)
