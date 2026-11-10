#!/usr/bin/env python3
import sys
import asyncio
from pathlib import Path

cur_dir = str(Path(__file__).resolve().parent)
if cur_dir not in sys.path:
    sys.path.insert(0, cur_dir)

# Ensure parent directory is also in python path if inside a package
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    from bot.main import main
except (ImportError, ModuleNotFoundError):
    import main as main_mod
    main = main_mod.main

if __name__ == "__main__":
    asyncio.run(main())
