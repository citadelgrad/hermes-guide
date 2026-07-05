import sys
from pathlib import Path

# ponytail: makes `import backend.main` work without PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))
