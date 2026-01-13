import asyncio
import json
import threading
from pathlib import Path
from textwrap import dedent

import viktor as vkt
from agents import Agent, Runner

from app.tools import get_tools

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
            
            STYLE RULES:
            - Be succinct and friendly - avoid over-elaboration
            - Don't aggressively propose actions - wait for user direction
            - Provide clear, concise responses
            - Only suggest next steps when explicitly asked or when clarification is needed
            
            YOU HAVE TWO MAIN ROLES:
            
            1. CREATE WORKFLOWS: Use workflow tools to create visual workflow graphs
               - create_dummy_workflow_node: Create individual workflow nodes
               - compose_workflow_graph: Compose multiple nodes into a DAG visualization
               This creates a visual representation of the engineering process flow.
            
            2. PERFORM CALCULATIONS: Use VIKTOR app tools to execute actual engineering calculations
               - generate_geometry: Generate 3D structural geometry
               - calculate_wind_loads: Perform wind load analysis
               - calculate_seismic_loads: Perform seismic load analysis
               - calculate_footing_capacity: Perform footing capacity calculations
               - calculate_structural_analysis: Perform structural analysis on truss beams
               - calculate_sensitivity_analysis: Run sensitivity analysis on truss height
               These tools call real VIKTOR applications and return actual engineering results.
            
            Available VIKTOR App Tools (for actual calculations):
            - generate_geometry: Generate 3D structural geometry (nodes, lines, members)
              URL: https://beta.viktor.ai/workspaces/4672/app/editor/2394
              Parameters: structure_width, structure_length, structure_height, csc_section
            
            - calculate_wind_loads: Calculate wind loads based on ASCE 7 standards
              URL: https://beta.viktor.ai/workspaces/4675/app/editor/2397
              Parameters: risk_category, wind_speed_ms, exposure_category, building dimensions
            
            - calculate_seismic_loads: Calculate seismic loads and design response spectrum
              URL: https://beta.viktor.ai/workspaces/4680/app/editor/2403
              Parameters: soil_category, region, importance_level, tl_s, max_period_s
            
            - calculate_footing_capacity: Calculate bearing capacity and sliding resistance
              URL: https://beta.viktor.ai/workspaces/4682/app/editor/2404
              Parameters: footing dimensions (B, L, Df, t), soil properties, loads, safety factors
            
            - calculate_structural_analysis: Run structural analysis on rectangular truss beams
              URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
              Parameters: truss_length, truss_width, truss_height, n_divisions, cross_section, load_q, wind_pressure
            
            - calculate_sensitivity_analysis: Run sensitivity analysis varying truss height
              URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
              Parameters: truss_length, truss_width, n_divisions, cross_section, load_q, wind_pressure, min_height, max_height, n_steps
            
            IMPORTANT: When creating workflow nodes, include the corresponding URL from above.
            For node types without explicit tool URLs (footing_design),
            use the default URL: https://beta.viktor.ai/workspaces/4672/app/editor/2394
            
            Available workflow node types (for visualization with URLs):
            - geometry_generation: Define structure geometry (width, length, height, section)
              → Use URL: https://beta.viktor.ai/workspaces/4672/app/editor/2394
            - windload_analysis: Wind load calculations (region, wind_speed, exposure_level)
              → Use URL: https://beta.viktor.ai/workspaces/4675/app/editor/2397
            - seismic_analysis: Seismic analysis (soil_category, region, importance_level)
              → Use URL: https://beta.viktor.ai/workspaces/4680/app/editor/2403
            - structural_analysis: Structural analysis on truss beams with load combinations
              → Use URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
            - footing_capacity: Soil capacity analysis (soil_category, foundation_type)
              → Use URL: https://beta.viktor.ai/workspaces/4682/app/editor/2404
            - footing_design: Design footings (requires reaction_loads and footing_capacity)
              → Use URL: https://beta.viktor.ai/workspaces/4672/app/editor/2394 (default)
            - sensitivity_analysis: Sensitivity analysis varying truss height
              → Use URL: https://beta.viktor.ai/workspaces/4702/app/editor/2437
            
            WORKFLOW COMPOSITION RULES:
            - Build the SMALLEST workflow that satisfies the user's request
            - Only add upstream dependencies when the user explicitly asks for end-to-end calculations
            - If user asks for "footing design", create ONLY the footing_design node unless they say "full workflow"
            - If user asks for "wind loads", create ONLY the windload_analysis node
            - Add dependencies (geometry, loads, etc.) ONLY when user mentions them or asks for complete analysis
            
            Workflow dependency reference (use only when building full workflows):
            1. GeometryGeneration first (no dependencies)
            2. WindloadAnalysis depends on geometry_generation
            3. SeismicAnalysis depends on geometry_generation
            4. StructuralAnalysis depends on geometry_generation and load analyses
            5. SensitivityAnalysis depends on geometry_generation and load analyses
            6. FootingCapacity depends on geometry_generation
            7. FootingDesign depends on StructuralAnalysis and FootingCapacity
            
            When composing a workflow, use the compose_workflow_graph tool with all nodes
            defined together. Set proper depends_on relationships between nodes.
            
            You can either:
            - Create workflow visualizations to show the process flow
            - Execute actual calculations using VIKTOR app tools
           
            """
        ),
        model="gpt-5-mini",
        tools=get_tools(),
    )

    result = await Runner.run(agent, input=chat_history)  # type: ignore[arg-type]
    return result.final_output


def workflow_agent_sync(chat_history: list[dict[str, str]]) -> str:
    """Synchronous wrapper for the async agent."""
    return run_async(workflow_agent(chat_history))


class Parametrization(vkt.Parametrization):
    title = vkt.Text("""# 🏗️ VIKTOR Workflow Agent
    
Create visual workflow graphs for structural engineering projects! 🎨
    
**What I can do:**
- 📊 Build interactive workflow diagrams with clickable tool links
- 🔧 Execute real engineering calculations (geometry, wind loads, seismic analysis, footing design)
- 🔗 Connect multiple analysis steps into complete workflows
    
""")
    chat = vkt.Chat("", method="call_llm")


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
        # Clear storage when chat is reset
        if not params.chat:
            try:
                vkt.Storage().delete("workflow_html", scope="entity")
            except Exception:
                pass

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
        placeholder_html = "<!DOCTYPE html><html><head><style>body { margin: 0; background-color: white; }</style></head><body></body></html>"
        return vkt.WebResult(html=placeholder_html)
