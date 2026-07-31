from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class OutputFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    code = "code"
    structured = "structured"
    freeform = "freeform"


class OutputSchema(BaseModel):
    skill_id: str
    name: str
    description: str
    format: OutputFormat
    json_schema: dict[str, Any] | None = None
    instructions: str
    example: str


DATA_ANALYST_SCHEMA = OutputSchema(
    skill_id="data-analyst",
    name="Data Analyst Output",
    description="Structured data analysis with code, results, and interpretation",
    format=OutputFormat.structured,
    json_schema={
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "summary": {"type": "string", "description": "Plain-language summary of findings"},
            "code": {"type": "string", "description": "Python/pandas code used"},
            "results": {"type": "string", "description": "Numerical or tabular results"},
            "visualization": {"type": "string", "description": "Suggested chart type and rationale"},
            "interpretation": {"type": "string", "description": "Statistical interpretation"},
        },
        "required": ["summary", "interpretation"],
    },
    instructions="""Structure your response as:
1. **Summary** — 2-3 sentence plain-language overview
2. **Code** — Python/pandas code block
3. **Results** — Output with axis labels and color palettes
4. **Interpretation** — Statistical meaning (R-squared, p-values, coefficients)
5. **Visualization** — Suggested chart type""",
    example="""**Summary**: The dataset shows a strong positive correlation (r=0.87) between advertising spend and revenue.

**Code**:
```python
import pandas as pd
df = pd.read_csv('data.csv')
corr = df['ad_spend'].corr(df['revenue'])
```

**Results**: Pearson r = 0.87, p < 0.001

**Interpretation**: Advertising spend explains approximately 76% of revenue variance (R² = 0.76).""",
)

CODE_REVIEWER_SCHEMA = OutputSchema(
    skill_id="code-reviewer",
    name="Code Review Output",
    description="Line-level code review with severity, file location, and suggestions",
    format=OutputFormat.structured,
    json_schema={
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "overall_assessment": {"type": "string"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "enum": ["critical", "major", "minor", "nit"]},
                        "file": {"type": "string"},
                        "line": {"type": "integer"},
                        "description": {"type": "string"},
                        "suggestion": {"type": "string"},
                    },
                    "required": ["severity", "description", "suggestion"],
                },
            },
            "positive_feedback": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["overall_assessment", "issues"],
    },
    instructions="""For each issue found, include:
- **Severity**: critical | major | minor | nit
- **File** and **line number**
- **Description** of the problem
- **Suggestion** with code example

Group by severity. End with positive observations.""",
    example="""## Overall Assessment
Code is functionally correct but has performance and security concerns.

### Critical
- **File**: auth.py, line 42 — SQL injection risk. Use parameterized queries.

### Major
- **File**: api.py, line 88 — N+1 query. Add `select_related()`.

### Positive
- Clean separation of concerns in the service layer.""",
)

WRITER_SCHEMA = OutputSchema(
    skill_id="writer",
    name="Writer & Editor Output",
    description="Polished text with tone adaptation and structural metadata",
    format=OutputFormat.markdown,
    json_schema={
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "body": {"type": "string"},
            "tone": {"type": "string"},
            "word_count": {"type": "integer"},
            "changes_made": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["body"],
    },
    instructions="""Adapt tone to the audience. Vary sentence structure.
Avoid passive voice. Proofread for clarity and concision.
If editing, summarize key changes made.""",
    example="""**Title**: Q3 Revenue Report

**Body**: Revenue grew 23% year-over-year, driven primarily by the APAC region...

**Tone**: Professional, concise

**Changes Made**:
- Reduced from 450 to 310 words
- Converted passive to active voice (6 instances)
- Added section headers for scannability""",
)

ARCHITECT_SCHEMA = OutputSchema(
    skill_id="architect",
    name="System Architect Output",
    description="Architecture documentation with diagrams, trade-offs, and decisions",
    format=OutputFormat.structured,
    json_schema={
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "overview": {"type": "string"},
            "diagram": {"type": "string", "description": "Mermaid or ASCII architecture diagram"},
            "components": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "responsibility": {"type": "string"},
                        "technology": {"type": "string"},
                    },
                },
            },
            "trade_offs": {"type": "array", "items": {"type": "string"}},
            "non_functional_requirements": {"type": "object"},
        },
        "required": ["overview", "components"],
    },
    instructions="""Use Mermaid diagrams to illustrate architecture.
Always discuss trade-offs clearly — document what was decided against and why.
Explicitly address non-functional requirements: scalability, availability, latency, cost.
Include an ADR-style decision log for key choices.""",
    example="""## Architecture Overview
Event-driven microservices with Kafka-backed CQRS...

## Diagram
```mermaid
graph LR
    A[API Gateway] --> B[Auth Service]
    A --> C[Order Service]
    C --> D[(PostgreSQL)]
```

## Trade-offs
- Chose Kafka over RabbitMQ for better replay and partitioning
- Accepted eventual consistency for higher write throughput""",
)

RESEARCHER_SCHEMA = OutputSchema(
    skill_id="researcher",
    name="Research Assistant Output",
    description="Structured research brief with citations and source evaluation",
    format=OutputFormat.structured,
    json_schema={
        "$schema": "https://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "executive_summary": {"type": "string"},
            "key_findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "finding": {"type": "string"},
                        "evidence": {"type": "string"},
                        "credibility": {"type": "string", "enum": ["high", "medium", "low"]},
                    },
                },
            },
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "sources": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["topic", "executive_summary", "key_findings"],
    },
    instructions="""Distinguish clearly between fact, inference, and speculation.
Evaluate source credibility (high/medium/low).
Cite every source. Identify consensus and disagreements in the literature.
End with open questions and suggested next steps.""",
    example="""## Topic: Transformer Inference Optimization

## Executive Summary
Recent advances in speculative decoding and quantization reduce LLM inference cost by 2-4x...

## Key Findings
- **Speculative decoding** — 2-3x speedup (credibility: high, multiple reproductions)
- **INT4 quantization** — <1% accuracy loss at 50% memory reduction (credibility: medium, vendor benchmarks)

## Sources
1. Leviathan et al. (2023) — Fast Inference from Transformers via Speculative Decoding
2. Dettmers et al. (2022) — LLM.int8(): 8-bit Matrix Multiplication for Transformers""",
)

GENERAL_SCHEMA = OutputSchema(
    skill_id="general",
    name="General Assistant Output",
    description="Freeform response with no strict structure",
    format=OutputFormat.freeform,
    json_schema=None,
    instructions="Respond helpfully. Use markdown for readability. Be concise and accurate.",
    example="",
)

SKILL_OUTPUT_SCHEMAS: dict[str, OutputSchema] = {
    "data-analyst": DATA_ANALYST_SCHEMA,
    "code-reviewer": CODE_REVIEWER_SCHEMA,
    "writer": WRITER_SCHEMA,
    "architect": ARCHITECT_SCHEMA,
    "researcher": RESEARCHER_SCHEMA,
    "general": GENERAL_SCHEMA,
}
