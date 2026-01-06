import asyncio
import json
import threading
from pathlib import Path
from textwrap import dedent

import viktor as vkt
from agents import Agent, Runner

from app.tools import get_dummy_tools

from dotenv import load_dotenv

load_dotenv()

# Event loop management for async agent in sync VIKTOR context
event_loop: asyncio.AbstractEventLoop | None = None
event_loop_thread: threading.Thread | None = None


def ensure_loop() -> asyncio.AbstractEventLoop:
    """Ensure a background event loop is running."""
    global event_loop, event_loop_thread
    if event_loop and event_loop.is_running():
        return event_loop
    event_loop = asyncio.new_event_loop()
    event_loop_thread = threading.Thread(
        target=event_loop.run_forever, name="agent-loop", daemon=True
    )
    event_loop_thread.start()
    return event_loop


def run_async(coro):
    """Run async coroutine in background loop and wait for result."""
    loop = ensure_loop()
    fut = asyncio.run_coroutine_threadsafe(coro, loop)
    return fut.result()


async def workflow_agent(chat_history: list[dict[str, str]]) -> str:
    """Async agent that helps users create workflow graphs."""
    agent = Agent(
        name="Workflow Assistant",
        instructions=dedent(
            """You are a helpful assistant that creates structural engineering workflows.
            Use tools to create workflow nodes and compose them into graphs.
            
            Available node types:
            - geometry_generation: Define structure geometry (width, length, height, section)
            - windload_analysis: Wind load calculations (region, wind_speed, exposure_level)
            - seismic_analysis: Seismic analysis (soil_category, region, importance_level)
            - structural_analysis: Requires geometry and load results
            - footing_capacity: Soil capacity analysis (soil_category, foundation_type)
            - footing_design: Design footings (requires reaction_loads and footing_capacity)
            
            Workflow order:
            1. GeometryGeneration first (no dependencies)
            2. WindloadAnalysis and SeismicAnalysis can run in parallel (no dependencies)
            3. StructuralAnalysis depends on geometry and load analyses
            4. FootingCapacity has no dependencies
            5. FootingDesign depends on StructuralAnalysis and FootingCapacity
            
            When composing a workflow, use the compose_workflow_graph tool with all nodes
            defined together. Set proper depends_on relationships between nodes.
            """
        ),
        model="gpt-4o",
        tools=get_dummy_tools(),
    )

    result = await Runner.run(agent, input=chat_history)  # type: ignore[arg-type]
    return result.final_output


def workflow_agent_sync(chat_history: list[dict[str, str]]) -> str:
    """Synchronous wrapper for the async agent."""
    return run_async(workflow_agent(chat_history))


class Parametrization(vkt.Parametrization):
    chat = vkt.Chat("Workflow Assistant", method="call_llm")


class Controller(vkt.Controller):
    parametrization = Parametrization

    def call_llm(self, params, **kwargs) -> vkt.ChatResult | None:
        """Handle chat interaction with the workflow agent."""
        if not params.chat:
            return None

        messages = params.chat.get_messages()
        chat_history = [{"role": m["role"], "content": m["content"]} for m in messages]

        response = workflow_agent_sync(chat_history)

        # Check for generated workflow HTML and store path
        self._update_workflow_storage()

        return vkt.ChatResult(params.chat, response)

    def _update_workflow_storage(self) -> None:
        """Scan for generated workflows and store the latest one."""
        workflows_dir = Path.cwd() / "workflow_graph" / "generated_workflows"
        if not workflows_dir.exists():
            return

        # Find the most recently modified workflow
        workflow_dirs = [d for d in workflows_dir.iterdir() if d.is_dir()]
        if not workflow_dirs:
            return

        latest_dir = max(workflow_dirs, key=lambda d: d.stat().st_mtime)
        html_path = latest_dir / "index.html"

        if html_path.exists():
            html_content = html_path.read_text(encoding="utf-8")
            data_json = json.dumps(
                {
                    "html": html_content,
                    "workflow_name": latest_dir.name,
                }
            )
            vkt.Storage().set(
                "workflow_html",
                data=vkt.File.from_data(data_json),
                scope="entity",
            )

    @vkt.WebView("Workflow Graph", width=100)
    def workflow_view(self, params, **kwargs) -> vkt.WebResult:
        """Display the generated workflow graph."""
        try:
            stored_file = vkt.Storage().get("workflow_html", scope="entity")
            if stored_file:
                data_json = stored_file.getvalue_binary().decode("utf-8")
                data = json.loads(data_json)
                html_content = data.get("html", "")
                if html_content:
                    return vkt.WebResult(html=html_content)
        except Exception:
            pass

        # Default placeholder when no workflow exists
        placeholder_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                }
                .container {
                    text-align: center;
                    padding: 2rem;
                }
                h1 { font-size: 2rem; margin-bottom: 1rem; }
                p { font-size: 1.1rem; opacity: 0.9; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🔧 Workflow Graph Viewer</h1>
                <p>Use the chat to create a workflow graph.</p>
                <p>Try: "Create a structural analysis workflow with wind and seismic loads"</p>
            </div>
        </body>
        </html>
        """
        return vkt.WebResult(html=placeholder_html)
