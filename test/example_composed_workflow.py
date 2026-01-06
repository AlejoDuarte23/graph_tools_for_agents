import asyncio

from app.tools import (
    ComposeWorkflowGraphArgs,
    DummyWorkflowNode,
    compose_workflow_graph_func,
)


async def main() -> None:
    payload = ComposeWorkflowGraphArgs(
        workflow_name="example",
        nodes=[
            DummyWorkflowNode(
                node_id="geometry",
                node_type="geometry_generation",
                label="Geometry Generation App",
            ),
            DummyWorkflowNode(
                node_id="seismic",
                node_type="seismic_analysis",
                label="Seismic Analysis App",
                depends_on=["geometry"],
            ),
            DummyWorkflowNode(
                node_id="wind",
                node_type="windload_analysis",
                label="Wind Load Analysis App",
                depends_on=["geometry"],
            ),
            DummyWorkflowNode(
                node_id="structural",
                node_type="structural_analysis",
                label="Structural Analysis App",
                depends_on=["seismic", "wind"],
            ),
            DummyWorkflowNode(
                node_id="footing_cap",
                node_type="footing_capacity",
                label="Footing Capacities",
            ),
            DummyWorkflowNode(
                node_id="footing_design",
                node_type="footing_design",
                label="Footing Design",
                depends_on=["structural", "footing_cap"],
            ),
        ],
    )

    result = await compose_workflow_graph_func(ctx=None, args=payload.model_dump_json())
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
