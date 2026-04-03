from __future__ import annotations

from butler_main.products.butler_flow import main as butler_flow_main


def main(argv: list[str] | None = None) -> int:
    return butler_flow_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
