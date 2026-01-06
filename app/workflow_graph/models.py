from pydantic import BaseModel, Field


class Connection(BaseModel):
    node_id: str
    kind: str = "default"


class Node(BaseModel):
    id: str
    title: str
    type: str = "default"
    depends_on: list[Connection] = Field(default_factory=list)


class Workflow(BaseModel):
    nodes: list[Node]
