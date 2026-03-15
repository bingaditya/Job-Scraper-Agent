from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from job_hunter.agent import JobHunterAgent
from job_hunter.config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Job Hunter Agent")
    parser.add_argument(
        "--profile",
        default="config/profile.json",
        help="Path to the candidate profile JSON file.",
    )
    parser.add_argument(
        "--database-dir",
        default="database",
        help="Directory where run artifacts are stored.",
    )
    parser.add_argument(
        "--dashboard-dir",
        default="dashboard",
        help="Directory where dashboard assets are published.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(Path(args.profile))
    agent = JobHunterAgent(
        config=config,
        database_dir=Path(args.database_dir),
        dashboard_dir=Path(args.dashboard_dir),
    )
    result = agent.run()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"agent failed: {exc}", file=sys.stderr)
        raise

