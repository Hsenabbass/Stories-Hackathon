"""Command-line entry points; run from the repository root for default paths."""

import argparse
import json
import sys
from pathlib import Path

from threadpoolctl import threadpool_limits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stories-promo", description="Stories promotion model and offer calculator")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["train", "evaluate", "reproduce"]:
        item = sub.add_parser(command)
        item.add_argument("--data", default="data/raw/stories_transactions.csv")
        item.add_argument("--artifact", default="artifacts/model.json")
        item.add_argument("--reports", default="reports")
        if command != "evaluate":
            item.add_argument("--config", default="configs/default.json")
    for command in ["recommend", "options", "serve"]:
        item = sub.add_parser(command)
        item.add_argument("--artifact", default="artifacts/model.json")
        if command == "recommend":
            item.add_argument("--request", required=True, help="JSON file, or - to read stdin")
        if command == "serve":
            item.add_argument("--host", default="127.0.0.1")
            item.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        with threadpool_limits(limits=1):
            if args.command in ("train", "reproduce"):
                from .training import train
                train(args.data, args.config, args.artifact, args.reports)
            if args.command in ("evaluate", "reproduce"):
                from .backtest import backtest
                backtest(args.data, args.artifact, args.reports)
            if args.command in ("recommend", "options"):
                from .service import PromotionService
                service = PromotionService(args.artifact)
                result = service.options() if args.command == "options" else service.recommend(
                    json.loads(sys.stdin.read() if args.request == "-" else Path(args.request).read_text()))
                print(json.dumps(result, indent=2, allow_nan=False))
            if args.command == "serve":
                import uvicorn
                from .api import create_app
                uvicorn.run(create_app(args.artifact), host=args.host, port=args.port)
    except (ValueError, FileNotFoundError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
