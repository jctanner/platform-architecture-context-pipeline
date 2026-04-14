#!/usr/bin/env python3
"""Repository processing and analysis tool."""

import sys
import asyncio
from pathlib import Path

from dotenv import load_dotenv

from lib.cli import parse_args
from lib.phases import main

# Load environment variables: .env file takes precedence over existing env vars.
# If no .env file exists, existing environment variables are used as-is.
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
