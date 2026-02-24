import sys
from pathlib import Path

# Make plan.py importable as `import plan` directly from the plugin script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugins" / "plan-mode" / "skills" / "plan" / "scripts"))
