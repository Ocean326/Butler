# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import sys

from agent import load_config
from memory_manager import EXTERNAL_HEARTBEAT_ENV_NAME, run_heartbeat_service_subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    cfg["__config_path"] = os.path.abspath(args.config)
    os.environ[EXTERNAL_HEARTBEAT_ENV_NAME] = "1"
    run_heartbeat_service_subprocess(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())