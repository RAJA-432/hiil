from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# --- Requests ---

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class KaryaRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class AuthRequest(BaseModel):
    username: str
    password: str


class ActivateSkillRequest(BaseModel):
    skill_id: str


class ResumeDecisionModel(BaseModel):
    action: str
    args: dict[str, Any] = {}


class ResumeRequest(BaseModel):
    decisions: list[ResumeDecisionModel]


class AgentRouteRequest(BaseModel):
    virtual_prefix: str
    real_path: str


class AgentRunRequest(BaseModel):
    input: str


class SetModelRequest(BaseModel):
    model: str


class ToolCallRequest(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = 5
    min_score: float = 0.0


class SessionSwitchRequest(BaseModel):
    session_id: str


class SessionRenameRequest(BaseModel):
    session_id: str
    new_title: str


class SessionDeleteRequest(BaseModel):
    session_id: str


# --- Responses ---

class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class UsageResponse(BaseModel):
    session: TokenUsage
    total: TokenUsage


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_secs: float
    chat_initialized: bool


class WorkspaceResponse(BaseModel):
    name: str
    root: str


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str


class ModelsResponse(BaseModel):
    models: list[ModelInfo]
    active: str | None = None


class ModelSetRequest(BaseModel):
    model: str


class ModelSetResponse(BaseModel):
    model: str


class AuthResponse(BaseModel):
    token: str
    username: str
    first_login: bool = False


class AgentCreateResponse(BaseModel):
    agent_id: str
    name: str
    role: str
    capabilities: list[str]
    status: str


class AgentListResponse(BaseModel):
    agents: list[dict[str, Any]]


class AgentDetailResponse(BaseModel):
    agent_id: str
    config: dict[str, Any]
    state: dict[str, Any]
    virtual_files: dict[str, Any]


class AgentStopResponse(BaseModel):
    status: str


class AgentRouteResponse(BaseModel):
    status: str
    virtual_prefix: str
    real_path: str


class SkillInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    category: str
    systemPrompt: str
    promptTemplates: list[dict[str, str]]
    toolPresets: list[str]
    color: str


class SkillsListResponse(BaseModel):
    skills: list[SkillInfo]


class SkillActivateResponse(BaseModel):
    success: bool
    skill: SkillInfo


class SessionListResponse(BaseModel):
    sessions: list[str]
    active: str | None = None


class ConversationItem(BaseModel):
    id: str
    title: str
    created: str
    updated: str
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationItem]
    total: int


class HistoryResponse(BaseModel):
    messages: list[dict[str, Any]]


class SessionNewResponse(BaseModel):
    session_id: str


class SessionSwitchResponse(BaseModel):
    session_id: str
    messages: int


class SessionRenameResponse(BaseModel):
    session_id: str


class SessionDeleteResponse(BaseModel):
    deleted: str


class ToolListResponse(BaseModel):
    tools: list[str]


class ToolCallResponse(BaseModel):
    result: Any = None


class ChatResponse(BaseModel):
    reply: str


class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    rag: dict[str, Any] = {}


class DocumentListResponse(BaseModel):
    documents: list[dict[str, Any]]


class DocumentDetailResponse(BaseModel):
    doc_id: str
    content: str | None = None
    has_file: bool
    file_size: int


class RetrieveResponse(BaseModel):
    results: list[dict[str, Any]]
    count: int


class KnowledgeListResponse(BaseModel):
    documents: list[dict[str, Any]]
    count: int


class FileItem(BaseModel):
    name: str
    type: str
    path: str
    size: int = 0
    children: list[FileItem] | None = None


class FileTreeResponse(BaseModel):
    name: str
    type: str
    path: str
    children: list[FileItem]


class SearchResultItem(BaseModel):
    conversation_id: str
    conversation_title: str
    message_id: int
    content: str
    snippet: str
    timestamp: str


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
    total_count: int


class StatusResponse(BaseModel):
    session_id: str | None = None
    model: str | None = None
    message_count: int = 0
    tool_count: int = 0


# --- LangGraph API models ---

class ThreadCreateRequest(BaseModel):
    thread_id: str | None = None
    metadata: dict[str, Any] = {}


class ThreadCreateResponse(BaseModel):
    thread_id: str


class ThreadItem(BaseModel):
    thread_id: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = {}
    message_count: int = 0


class ThreadListResponse(BaseModel):
    threads: list[ThreadItem]


class ThreadSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    filter: dict[str, Any] = {}


class ThreadRunRequest(BaseModel):
    assistant_id: str = "default"
    input: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class ThreadRunResponse(BaseModel):
    run_id: str
    thread_id: str
    status: str
    output: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class ServerInfoResponse(BaseModel):
    name: str
    version: str
    description: str
    endpoints: list[str]
    langgraph_compat: bool = True


# --- LangGraph streaming / stateless / store ---

class StreamEvent(BaseModel):
    event: str
    data: dict[str, Any] = {}


class RunWaitRequest(BaseModel):
    assistant_id: str = "default"
    input: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class RunWaitResponse(BaseModel):
    run_id: str
    thread_id: str | None = None
    status: str
    output: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    events: list[dict[str, Any]] = []


class StatelessRunRequest(BaseModel):
    input: dict[str, Any] = {}
    assistant_id: str = "default"
    metadata: dict[str, Any] = {}


class StatelessRunResponse(BaseModel):
    run_id: str
    output: dict[str, Any] = {}
    metadata: dict[str, Any] = {}


class StoreItem(BaseModel):
    namespace: str = "default"
    key: str
    value: dict[str, Any] = {}
    created_at: str = ""
    updated_at: str = ""


class StoreUpsertRequest(BaseModel):
    namespace: str = "default"
    items: list[StoreItem] = []


class StoreGetRequest(BaseModel):
    namespace: str = "default"
    keys: list[str] = []


class StoreGetResponse(BaseModel):
    items: list[StoreItem]


class StoreDeleteRequest(BaseModel):
    namespace: str = "default"
    keys: list[str] = []


class StoreSearchRequest(BaseModel):
    namespace: str = "default"
    filter: dict[str, Any] = {}
    limit: int = 10


class StoreSearchResponse(BaseModel):
    items: list[StoreItem]
    count: int
