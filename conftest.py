import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.pop("OPENAI_API_KEY", None)
from warehouse import build_warehouse
build_warehouse()
