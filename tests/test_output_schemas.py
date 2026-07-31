from __future__ import annotations

import sys
from pathlib import Path

import jsonschema
import pytest
from jsonschema import Draft7Validator

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from vajra_gate.schemas.output_schemas import (  # noqa: E402
    CODE_REVIEWER_SCHEMA,
    DATA_ANALYST_SCHEMA,
    GENERAL_SCHEMA,
    SKILL_OUTPUT_SCHEMAS,
)


def test_schema_definitions_exist():
    assert isinstance(SKILL_OUTPUT_SCHEMAS, dict)
    assert len(SKILL_OUTPUT_SCHEMAS) == 6
    assert set(SKILL_OUTPUT_SCHEMAS.keys()) == {
        "data-analyst",
        "code-reviewer",
        "writer",
        "architect",
        "researcher",
        "general",
    }


def test_data_analyst_schema_validates_good():
    valid = {
        "summary": "Sales increased 15% QoQ driven by APAC expansion.",
        "code": "df.groupby('region').sum()",
        "results": "APAC: +15%, EMEA: +5%",
        "visualization": "Bar chart with region on x-axis",
        "interpretation": "R² = 0.92, p < 0.01 — strong model fit.",
    }
    Draft7Validator(DATA_ANALYST_SCHEMA.json_schema).validate(valid)


def test_data_analyst_schema_rejects_bad():
    invalid = {"summary": "Only summary present, missing interpretation."}
    with pytest.raises(jsonschema.ValidationError):
        Draft7Validator(DATA_ANALYST_SCHEMA.json_schema).validate(invalid)


def test_code_reviewer_schema_valid():
    valid = {
        "overall_assessment": "Solid code with minor issues.",
        "issues": [
            {
                "severity": "major",
                "file": "auth.py",
                "line": 42,
                "description": "SQL injection risk",
                "suggestion": "Use parameterized queries",
            },
        ],
        "positive_feedback": ["Good separation of concerns"],
    }
    Draft7Validator(CODE_REVIEWER_SCHEMA.json_schema).validate(valid)


def test_code_reviewer_schema_rejects_bad_invalid_severity():
    invalid = {
        "overall_assessment": "Needs work.",
        "issues": [
            {
                "severity": "blocker",
                "description": "Bad thing",
                "suggestion": "Fix it",
            },
        ],
    }
    with pytest.raises(jsonschema.ValidationError):
        Draft7Validator(CODE_REVIEWER_SCHEMA.json_schema).validate(invalid)


def test_output_schema_model_dump():
    for skill_id, schema in SKILL_OUTPUT_SCHEMAS.items():
        dumped = schema.model_dump()
        assert dumped["skill_id"] == skill_id
        assert dumped["name"]
        assert dumped["description"]
        assert dumped["format"]
        assert dumped["instructions"]
        assert "example" in dumped


def test_general_schema_has_no_json_schema():
    assert GENERAL_SCHEMA.json_schema is None
    assert GENERAL_SCHEMA.skill_id == "general"
    assert GENERAL_SCHEMA.format.value == "freeform"
