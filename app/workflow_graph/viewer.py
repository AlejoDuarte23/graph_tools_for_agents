import json
import webbrowser
from pathlib import Path
from typing import Any
from collections.abc import Callable


class WorkflowViewer:
    def __init__(
        self,
        workflow_factory: Callable[[], Any],
        *,
        root_dir: Path | None = None,
    ) -> None:
        self._workflow_factory = workflow_factory
        self._root_dir = root_dir or Path().cwd()

    @property
    def root_dir(self) -> Path:
        return self._root_dir

    def _model_dump(self, obj: Any) -> dict[str, Any]:
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        raise TypeError("Expected a Pydantic model.")

    def render_html(self) -> str:
        css = (self.root_dir / "styles.css").read_text(encoding="utf-8")
        js = (self.root_dir / "workflow.js").read_text(encoding="utf-8")
        js = js.replace("export class WorkflowGraph", "class WorkflowGraph")

        workflow = self._workflow_factory()
        workflow_json = json.dumps(self._model_dump(workflow), ensure_ascii=False)

        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Workflow</title>
    <style>{css}</style>
  </head>
  <body>
    <div class="app">
      <main id="stage">
        <svg id="edges"></svg>
        <div id="nodes"></div>
      </main>
    </div>

    <script id="workflow-data" type="application/json">{workflow_json}</script>
    <script>{js}</script>
    <script>
      const dataEl = document.getElementById("workflow-data");
      const workflow = JSON.parse(dataEl.textContent || "{{}}");

      const graph = new WorkflowGraph({{
        stage: document.getElementById("stage"),
        edgesSvg: document.getElementById("edges"),
        nodesHost: document.getElementById("nodes"),
        logEl: null,
      }});

      graph.setData(workflow);
      graph.relayout({{ resetDragged: true }});
      graph.render();

      window.addEventListener("resize", () => {{
        graph.relayout({{ resetDragged: false }});
        graph.render();
      }});
    </script>
  </body>
</html>
"""

    def write(self, out_path: Path | str | None = None) -> Path:
        path = (
            Path(out_path) if out_path is not None else (self.root_dir / "index.html")
        )
        path.write_text(self.render_html(), encoding="utf-8")
        return path

    def show(self, out_path: Path | str | None = None) -> Path:
        path = self.write(out_path)
        webbrowser.open_new_tab(path.resolve().as_uri())
        return path
