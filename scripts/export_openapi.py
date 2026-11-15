"""Write apps/web/openapi.json from the FastAPI app (source of truth for the generated TypeScript client)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langgraph.checkpoint.memory import InMemorySaver

from apps.api.main import create_app

out = Path(__file__).resolve().parents[1] / "apps/web/openapi.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(create_app(checkpointer=InMemorySaver(), seed=False).openapi(), indent=1))
print("wrote", out)
