import sys
from pathlib import Path

# Ensure project root (/app) is on sys.path for module imports like "main" and "person_service"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
