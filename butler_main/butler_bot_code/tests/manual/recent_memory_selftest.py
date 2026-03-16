import importlib.util
import json
import sys
import time
from pathlib import Path

root = Path(__file__).resolve().parents[4]
bots_dir = root / "butler_bot_code" / "butler_bot"
config_path = root / "butler_bot_code" / "configs" / "butler_bot.json"
recent_path = root / "butler_bot_agent" / "agents" / "recent_memory" / "recent_memory.json"

sys.path.insert(0, str(bots_dir))
import agent as ag

spec = importlib.util.spec_from_file_location("butler_bot_mod", bots_dir / "butler_bot.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

cfg = json.loads(config_path.read_text(encoding="utf-8"))
ag.CONFIG.clear()
ag.CONFIG.update(cfg)
ag.reply_message = lambda *args, **kwargs: True
mod.MEMORY._run_model_fn = lambda *args, **kwargs: ("", False)


def load_entries():
    if not recent_path.exists():
        return []
    return json.loads(recent_path.read_text(encoding="utf-8"))


def run_once(tag: str):
    before = load_entries()
    before_count = len(before)

    def fake_run(prompt, stream_callback=None, image_paths=None):
        if stream_callback:
            stream_callback(f"{tag} segment one")
            stream_callback(f"{tag} segment two")
        return ""

    ag.handle_message_async(
        f"memory-selftest-{tag}",
        f"short memory selftest {tag}",
        None,
        fake_run,
        supports_images=False,
        supports_stream_segment=True,
        on_reply_sent=mod._after_reply_persist_memory_async,
    )

    deadline = time.time() + 20
    last = before
    while time.time() < deadline:
        time.sleep(0.5)
        last = load_entries()
        if len(last) > before_count:
            return {
                "before_count": before_count,
                "after_count": len(last),
                "last_entry": last[-1],
            }
    return {
        "before_count": before_count,
        "after_count": len(last),
        "last_entry": last[-1] if last else None,
    }


results = []
for idx in range(1, 3):
    tag = f"round{idx}-{int(time.time())}"
    results.append(run_once(tag))
    time.sleep(0.5)

print(json.dumps(results, ensure_ascii=False, indent=2))
