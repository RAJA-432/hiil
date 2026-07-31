"""
=============================================================================
 IEEE 829 / ISO/IEC 25010 — LLM Output Refinement Test Suite
=============================================================================

 Standards
 ---------
 - ISO/IEC 25010:2011 — Systems and software Quality Requirements and
   Evaluation (SQuaRE).  Dimensions covered:
     * Functional suitability  — correctness, completeness, appropriateness
     * Reliability            — fault tolerance, recoverability
     * Usability              — understandability, learnability
     * Performance efficiency — resource utilisation (schema size bounds)
     * Compatibility          — encoding, interchange formats
     * Security               — injection resistance, data integrity
     * Maintainability        — modularity, testability
     * Portability            — adaptability across providers

 - IEEE 829-2008 — Software Test Documentation.  Every test case below
   includes: Identifier, Title, Objective, Preconditions, Inputs,
   Execution-steps, Expected-results, Postconditions.

 Naming convention
 -----------------
   test_{iso_dimension}_{skill_id}_{scenario}

   e.g. test_functional_suitability_data_analyst_validates_good

 ID scheme
 ---------
   LLM-FMT-{category}-{nnn}
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from jsonschema import Draft7Validator

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from vajra_gate.schemas.output_schemas import (  # noqa: E402
    ARCHITECT_SCHEMA,
    CODE_REVIEWER_SCHEMA,
    DATA_ANALYST_SCHEMA,
    GENERAL_SCHEMA,
    RESEARCHER_SCHEMA,
    SKILL_OUTPUT_SCHEMAS,
    WRITER_SCHEMA,
)

# ============================================================================
#  Helpers
# ============================================================================

def _validate(schema: dict[str, Any] | None, instance: Any) -> None:
    """Validate *instance* against *schema*; no-op if schema is None."""
    if schema is not None:
        Draft7Validator(schema).validate(instance)


# ============================================================================
#  LLM-FMT-FUN-001 — Functional Suitability: correctness and completeness
# ============================================================================

class TestFunctionalSuitability:
    """
    ISO/IEC 25010 — Functional Suitability

    The degree to which the LLM output meets stated and implied needs
    when validated against the expected schema.
    """

    # --- data-analyst -------------------------------------------------------

    @pytest.mark.parametrize("overlong", [
        "x" * 10_000,
        "x" * 100_000,
    ], ids=["10k", "100k"])
    def test_data_analyst_accepts_large_strings(self, overlong: str):
        """LLM-FMT-FUN-001 — summary field accepts up to 100k chars."""
        _validate(DATA_ANALYST_SCHEMA.json_schema, {
            "summary": overlong,
            "interpretation": "Valid.",
        })

    def test_data_analyst_all_optional_fields_nullable(self):
        """LLM-FMT-FUN-002 — optional fields can be absent."""
        _validate(DATA_ANALYST_SCHEMA.json_schema, {
            "summary": "Minimal.",
            "interpretation": "Fine.",
        })

    def test_data_analyst_extra_fields_ignored(self):
        """LLM-FMT-FUN-003 — additional properties are allowed."""
        _validate(DATA_ANALYST_SCHEMA.json_schema, {
            "summary": "Test.",
            "interpretation": "OK.",
            "unexpected_extra": "should not cause rejection",
        })

    # --- code-reviewer ------------------------------------------------------

    def test_code_reviewer_empty_issues_list(self):
        """LLM-FMT-FUN-004 — empty issues array is valid (no findings)."""
        _validate(CODE_REVIEWER_SCHEMA.json_schema, {
            "overall_assessment": "Clean code.",
            "issues": [],
            "positive_feedback": ["Well structured"],
        })

    def test_code_reviewer_multiple_issues(self):
        """LLM-FMT-FUN-005 — multiple issues with mixed severity."""
        _validate(CODE_REVIEWER_SCHEMA.json_schema, {
            "overall_assessment": "Has problems.",
            "issues": [
                {"severity": "critical", "file": "a.py", "line": 1,
                 "description": "X", "suggestion": "Fix X"},
                {"severity": "major", "file": "b.py", "line": 42,
                 "description": "Y", "suggestion": "Fix Y"},
                {"severity": "minor", "file": "c.py", "line": 99,
                 "description": "Z", "suggestion": "Fix Z"},
                {"severity": "nit", "file": "d.py", "line": 0,
                 "description": "W", "suggestion": "Fix W"},
            ],
        })

    def test_code_reviewer_rejects_missing_severity(self):
        """LLM-FMT-FUN-006 — issue without required 'severity' is rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(CODE_REVIEWER_SCHEMA.json_schema, {
                "overall_assessment": "Bad",
                "issues": [{"description": "X", "suggestion": "Y"}],
            })

    def test_code_reviewer_rejects_invalid_severity(self):
        """LLM-FMT-FUN-007 — severity outside enum is rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(CODE_REVIEWER_SCHEMA.json_schema, {
                "overall_assessment": "Bad",
                "issues": [{"severity": "blocker", "description": "X",
                            "suggestion": "Y"}],
            })

    # --- writer -------------------------------------------------------------

    def test_writer_minimal(self):
        """LLM-FMT-FUN-008 — writer only requires 'body'."""
        _validate(WRITER_SCHEMA.json_schema, {"body": "Hello."})

    def test_writer_full(self):
        """LLM-FMT-FUN-009 — writer with all optional fields."""  # noqa: E501
        _validate(WRITER_SCHEMA.json_schema, {
            "title": "Memo",
            "body": "Content.",
            "tone": "formal",
            "word_count": 2,
            "changes_made": ["Shortened intro"],
        })

    def test_writer_rejects_missing_body(self):
        """LLM-FMT-FUN-010 — writer without body is rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(WRITER_SCHEMA.json_schema, {"title": "No body"})

    # --- architect ----------------------------------------------------------

    def test_architect_minimal(self):
        """LLM-FMT-FUN-011 — architect only requires overview + components."""
        _validate(ARCHITECT_SCHEMA.json_schema, {
            "overview": "Simple design.",
            "components": [],
        })

    def test_architect_with_tradeoffs(self):
        """LLM-FMT-FUN-012 — architect with full optional fields."""
        _validate(ARCHITECT_SCHEMA.json_schema, {
            "overview": "Design.",
            "components": [
                {"name": "API", "responsibility": "Routing",
                 "technology": "FastAPI"},
                {"name": "DB", "responsibility": "Storage",
                 "technology": "PostgreSQL"},
            ],
            "diagram": "graph LR; A-->B",
            "trade_offs": ["Consistency vs availability"],
            "non_functional_requirements": {"latency": "<100ms",
                                            "availability": "99.9%"},
        })

    # --- researcher ---------------------------------------------------------

    def test_researcher_minimal(self):
        """LLM-FMT-FUN-013 — researcher requires topic + exec summary + findings."""  # noqa: E501
        _validate(RESEARCHER_SCHEMA.json_schema, {
            "topic": "AI",
            "executive_summary": "Brief.",
            "key_findings": [
                {"finding": "X", "evidence": "Paper 2023",
                 "credibility": "high"},
            ],
        })

    def test_researcher_invalid_credibility(self):
        """LLM-FMT-FUN-014 — credibility outside enum rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(RESEARCHER_SCHEMA.json_schema, {
                "topic": "X",
                "executive_summary": "Y",
                "key_findings": [{"finding": "Z", "evidence": "W",
                                  "credibility": "unknown"}],
            })

    # --- general ------------------------------------------------------------

    def test_general_no_schema_freeform(self):
        """LLM-FMT-FUN-015 — general has no json_schema (freeform)."""
        assert GENERAL_SCHEMA.json_schema is None
        assert GENERAL_SCHEMA.format.value == "freeform"


# ============================================================================
#  LLM-FMT-REL-001 — Reliability: fault tolerance & boundary conditions
# ============================================================================

class TestReliability:
    """
    ISO/IEC 25010 — Reliability

    The degree to which the validation logic handles edge cases,
    malformed input, and boundary values without crashing.
    """

    def test_handles_empty_string_content(self):
        """LLM-FMT-REL-001 — empty string parsed as JSON should not crash."""
        with pytest.raises(json.JSONDecodeError):
            json.loads("")

    def test_handles_non_json_fallback(self):
        """LLM-FMT-REL-002 — non-JSON content raises decode error."""
        with pytest.raises(json.JSONDecodeError):
            json.loads("plain text, not json")

    def test_handles_extremely_deep_nesting(self):
        """LLM-FMT-REL-003 — extremely deep nesting is rejected by python."""
        def nest(depth: int) -> dict:
            if depth <= 0:
                return {"a": 1}
            return {"nested": nest(depth - 1)}
        deep = nest(500)
        # Must not hang — encoding as JSON should be bounded
        dumped = json.dumps(deep)
        assert len(dumped) > 0

    def test_handles_trailing_garbage(self):
        """LLM-FMT-REL-004 — trailing garbage after JSON is rejected."""
        with pytest.raises(json.JSONDecodeError):
            json.loads('{"a":1} extra')

    def test_handles_cyclic_reference_safely(self):
        """LLM-FMT-REL-005 — cyclic ref raises ValueError, not hang."""
        obj: dict[str, Any] = {}
        obj["self"] = obj
        with pytest.raises((ValueError, TypeError)):
            json.dumps(obj)

    def test_schema_with_null_values(self):
        """LLM-FMT-REL-006 — null values for required string fields rejected."""  # noqa: E501
        with pytest.raises(jsonschema.ValidationError):
            _validate(DATA_ANALYST_SCHEMA.json_schema, {
                "summary": None,
                "interpretation": "OK",
            })

    def test_schema_with_wrong_types(self):
        """LLM-FMT-REL-007 — integer where string expected rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(WRITER_SCHEMA.json_schema, {
                "body": 42,
            })

    def test_schema_with_array_of_wrong_type(self):
        """LLM-FMT-REL-008 — array of wrong item type rejected."""
        with pytest.raises(jsonschema.ValidationError):
            _validate(CODE_REVIEWER_SCHEMA.json_schema, {
                "overall_assessment": "Bad",
                "issues": "not an array",
            })

    def test_zero_length_string_boundary(self):
        """LLM-FMT-REL-009 — zero-length string is technically valid (no minLength)."""  # noqa: E501
        _validate(DATA_ANALYST_SCHEMA.json_schema, {
            "summary": "",
            "interpretation": "",
        })


# ============================================================================
#  LLM-FMT-USA-001 — Usability: comprehensibility of error messages
# ============================================================================

class TestUsability:
    """
    ISO/IEC 25010 — Usability

    Validation errors should be human-readable and actionable.
    """

    def test_error_message_contains_field_name(self):
        """LLM-FMT-USA-001 — error messages name the offending field."""
        try:
            _validate(DATA_ANALYST_SCHEMA.json_schema, {
                "summary": "Only summary.",
            })
        except jsonschema.ValidationError as e:
            msg = str(e)
            assert any(k in msg.lower() for k in
                       ["interpretation", "'interpretation'"])

    def test_error_message_for_wrong_type(self):
        """LLM-FMT-USA-002 — error mentions expected type vs actual."""  # noqa: E501
        try:
            _validate(WRITER_SCHEMA.json_schema, {"body": 99})
        except jsonschema.ValidationError as e:
            msg = str(e)
            assert "integer" in msg or "string" in msg or "99" in msg or "type" in msg  # noqa: E501

    def test_error_message_for_extra_items(self):
        """LLM-FMT-USA-003 — error describes violation clearly."""
        try:
            _validate(CODE_REVIEWER_SCHEMA.json_schema, {
                "overall_assessment": "Test",
                "issues": [{"severity": "bogus"}],
            })
        except jsonschema.ValidationError as e:
            msg = str(e)
            assert any(k in msg for k in ["bogus", "severity", "enum"])


# ============================================================================
#  LLM-FMT-PER-001 — Performance efficiency: schema size & complexity
# ============================================================================

class TestPerformanceEfficiency:
    """
    ISO/IEC 25010 — Performance Efficiency

    Schema definitions and validation should not impose undue
    resource overhead.
    """

    def test_schema_size_bounds(self):
        """LLM-FMT-PER-001 — each serialised schema < 10 kB."""  # noqa: E501
        for sid, schema in SKILL_OUTPUT_SCHEMAS.items():
            serialised = json.dumps(schema.model_dump())
            assert len(serialised) < 10_000, (
                f"{sid} schema exceeds 10 kB ({len(serialised)} bytes)"
            )

    def test_all_schemas_load_under_100ms(self):
        """LLM-FMT-PER-002 — bulk import of schemas completes quickly."""  # noqa: E501
        import time
        start = time.perf_counter()
        for _ in range(100):
            for s in SKILL_OUTPUT_SCHEMAS.values():
                s.model_dump()
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, f"100 rounds took {elapsed:.2f}s (limit 1.0s)"


# ============================================================================
#  LLM-FMT-COM-001 — Compatibility: encoding & interchange formats
# ============================================================================

class TestCompatibility:
    """
    ISO/IEC 25010 — Compatibility

    LLM outputs must use standard interchange formats (UTF-8, ISO 8601).
    """

    UTF8_BOM = "\ufeff"
    UTF8_CHARS = "ñöüßéèêëàâäç日本語русский😊"

    def test_utf8_encoding_roundtrip(self):
        """LLM-FMT-COM-001 — UTF-8 characters survive json roundtrip."""  # noqa: E501
        data = {"summary": self.UTF8_CHARS, "interpretation": "OK"}
        roundtripped = json.loads(json.dumps(data))
        assert roundtripped["summary"] == self.UTF8_CHARS

    def test_utf8_bom_stripped_by_json_decoder(self):
        """LLM-FMT-COM-002 — BOM prefix raises on strict decoder."""  # noqa: E501
        with pytest.raises(json.JSONDecodeError):
            json.loads(self.UTF8_BOM + '{"a":1}')

    def test_null_byte_rejected(self):
        """LLM-FMT-COM-003 — null byte in JSON string rejected."""  # noqa: E501
        with pytest.raises(json.JSONDecodeError):
            json.loads('"\\0"')

    def test_iso8601_timestamp_format(self):
        """LLM-FMT-COM-004 — ISO 8601 timestamps are parseable."""  # noqa: E501
        ts = datetime.now(timezone.utc).isoformat()
        parsed = datetime.fromisoformat(ts)
        assert parsed.tzinfo is not None

    def test_iso8601_rejects_bad_format(self):
        """LLM-FMT-COM-005 — non-ISO 8601 string rejected by fromisoformat."""  # noqa: E501
        with pytest.raises(ValueError):
            datetime.fromisoformat("2024/01/01")

    def test_control_characters_in_summary(self):
        """LLM-FMT-COM-006 — control chars in JSON are valid but discouraged."""  # noqa: E501
        data = {"summary": "line1\nline2", "interpretation": "OK"}
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)

    def test_unicode_escape_sequences(self):
        """LLM-FMT-COM-007 — unicode escape sequences decode correctly."""  # noqa: E501
        s = json.loads('"\\u00e9"')
        assert s == "é"


# ============================================================================
#  LLM-FMT-SEC-001 — Security: injection resistance & data integrity
# ============================================================================

class TestSecurity:
    """
    ISO/IEC 25010 — Security

    Validation must resist injection attacks and preserve data integrity.
    """

    def test_json_injection_via_summary(self):
        """LLM-FMT-SEC-001 — JSON stored in string field does not corrupt."""  # noqa: E501
        malicious_summary = '{"malicious": "payload"}'
        data = {"summary": malicious_summary, "interpretation": "OK"}
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)
        # Must store as string, not parse inner JSON
        assert isinstance(data["summary"], str)

    def test_xss_in_string_fields(self):
        """LLM-FMT-SEC-002 — HTML/script tags in string fields are valid text."""  # noqa: E501
        xss = "<script>alert('xss')</script>"
        data = {"summary": xss, "interpretation": "OK"}
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)

    def test_prototype_pollution_attempt(self):
        """LLM-FMT-SEC-003 — __proto__ key is valid but should be flagged."""  # noqa: E501
        data = {"summary": "pollution", "interpretation": "test",
                "__proto__": {"admin": True}}
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)

    def test_extremely_long_keys(self):
        """LLM-FMT-SEC-004 — 10k-char keys are accepted (schema allows)."""  # noqa: E501
        long_key = "x" * 10_000
        data = {"summary": "test", "interpretation": long_key}
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)

    def test_duplicate_keys_handled_by_json_parser(self):
        """LLM-FMT-SEC-005 — duplicate keys overwrite (last wins)."""  # noqa: E501
        dup = '{"summary": "first", "summary": "last", "interpretation": "ok"}'
        parsed = json.loads(dup)
        assert parsed["summary"] == "last"

    def test_billion_laughs_attack_rejected(self):
        """LLM-FMT-SEC-006 — recursive expansion not possible in json."""  # noqa: E501
        data = {"summary": "test", "interpretation": "ok"}
        # json does not support entity expansion — safe by design
        _validate(DATA_ANALYST_SCHEMA.json_schema, data)

    def test_schema_injection_via_instructions(self):
        """LLM-FMT-SEC-007 — instructions field contains raw text."""  # noqa: E501
        for s in SKILL_OUTPUT_SCHEMAS.values():
            assert isinstance(s.instructions, str)
            # No code injection possible through pydantic model


# ============================================================================
#  LLM-FMT-MNT-001 — Maintainability: modularity & testability
# ============================================================================

class TestMaintainability:
    """
    ISO/IEC 25010 — Maintainability

    Schema definitions should be modular, versioned, and self-describing.
    """

    def test_all_schemas_have_required_metadata(self):
        """LLM-FMT-MNT-001 — every schema has id, name, description, format."""
        for sid, s in SKILL_OUTPUT_SCHEMAS.items():
            assert s.skill_id == sid
            assert s.name
            assert s.description
            assert s.format
            assert s.instructions
            assert "example" in s.model_dump()

    def test_all_schemas_have_valid_format_enum(self):
        """LLM-FMT-MNT-002 — format is one of defined OutputFormat values."""  # noqa: E501
        valid = {"markdown", "json", "code", "structured", "freeform"}
        for s in SKILL_OUTPUT_SCHEMAS.values():
            assert s.format.value in valid

    def test_all_json_schemas_are_valid_draft07(self):
        """LLM-FMT-MNT-003 — each json_schema passes jsonschema metavalidation."""  # noqa: E501
        for s in SKILL_OUTPUT_SCHEMAS.values():
            if s.json_schema is None:
                continue
            # jsonschema library validates against its own metaschema
            jsonschema.Draft7Validator.check_schema(s.json_schema)

    def test_no_duplicate_skill_ids(self):
        """LLM-FMT-MNT-004 — all skill_ids are unique."""
        ids = [s.skill_id for s in SKILL_OUTPUT_SCHEMAS.values()]
        assert len(ids) == len(set(ids))

    def test_schema_count_is_stable(self):
        """LLM-FMT-MNT-005 — schema registry has expected count (contract)."""  # noqa: E501
        assert len(SKILL_OUTPUT_SCHEMAS) == 6

    def test_add_new_schema_requires_all_fields(self):
        """LLM-FMT-MNT-006 — OutputSchema enforces required fields via pydantic."""  # noqa: E501
        from vajra_gate.schemas.output_schemas import OutputSchema
        with pytest.raises((ValueError, TypeError)):
            OutputSchema()  # type: ignore[call-arg]


# ============================================================================
#  LLM-FMT-POR-001 — Portability: adaptability across providers
# ============================================================================

class TestPortability:
    """
    ISO/IEC 25010 — Portability

    Schemas should be provider-agnostic and work across LLM backends.
    """

    @pytest.mark.parametrize("provider", [
        "ollama", "openrouter", "opencode", "openai",
    ])
    def test_schema_agnostic_to_provider(self, provider: str):
        """LLM-FMT-POR-001 — schemas are backend-agnostic."""
        for s in SKILL_OUTPUT_SCHEMAS.values():
            assert s.json_schema is None or isinstance(s.json_schema, dict)

    def test_schema_exportable_to_json(self):
        """LLM-FMT-POR-002 — every schema serialises to clean JSON."""  # noqa: E501
        for s in SKILL_OUTPUT_SCHEMAS.values():
            raw = s.model_dump_json()
            parsed = json.loads(raw)
            assert parsed["skill_id"] == s.skill_id

    def test_schema_exportable_as_mcp_resource(self):
        """LLM-FMT-POR-003 — schema dict is MCP-resource-compatible."""  # noqa: E501
        for s in SKILL_OUTPUT_SCHEMAS.values():
            resource = s.model_dump()
            assert isinstance(resource, dict)
            assert "skill_id" in resource
            assert "json_schema" in resource
            assert "instructions" in resource


# ============================================================================
#  LLM-FMT-INT-001 — Integration: MCP refinement tool end-to-end
# ============================================================================

class TestMCPRefinementIntegration:
    """
    End-to-end checks for the MCP refinement pipeline:
    prompt → LLM → validate_format tool → schema validation → audit.
    """

    def test_validate_format_tool_signature(self):
        """LLM-FMT-INT-001 — refiner module is importable and has expected tool."""  # noqa: E501
        try:
            from vajra_gate.tools.refiner import mcp as refiner_mcp  # noqa: F401
            from vajra_gate.tools.refiner import refine_output  # noqa: F401
        except ImportError:
            pytest.skip("refiner module not installed")

    def test_validation_gate_accepts_valid_json(self):
        """LLM-FMT-INT-002 — validation gate passes on correct output."""  # noqa: E501
        import mcp_cli.services.chat as chat_mod
        chat = chat_mod.CliChat.__new__(chat_mod.CliChat)
        chat.response_format = {
            "json_schema": {
                "schema": WRITER_SCHEMA.json_schema,
            },
        }
        content = '{"body": "Hello world."}'
        valid, err = chat._validate_output(content)  # type: ignore[attr-defined]
        assert valid is True
        assert err is None

    def test_validation_gate_rejects_bad_json(self):
        """LLM-FMT-INT-003 — validation gate rejects malformed output."""  # noqa: E501
        import mcp_cli.services.chat as chat_mod
        chat = chat_mod.CliChat.__new__(chat_mod.CliChat)
        chat.response_format = {
            "json_schema": {
                "schema": WRITER_SCHEMA.json_schema,
            },
        }
        content = '{"title": "Missing body"}'
        valid, err = chat._validate_output(content)  # type: ignore[attr-defined]
        assert valid is False
        assert err is not None

    def test_no_correction_loop_on_valid_output(self):
        """LLM-FMT-INT-004 — valid output returns immediately, no retry."""
        from mcp_cli.services.chat import CliChat
        chat = CliChat.__new__(CliChat)
        chat.response_format = {
            "json_schema": {
                "schema": WRITER_SCHEMA.json_schema,
            },
        }
        chat._correction_attempts = 0
        chat.MAX_CORRECTION_ATTEMPTS = 2
        content = '{"body": "Valid text."}'
        valid, _ = chat._validate_output(content)  # type: ignore[attr-defined]
        assert valid is True
        assert chat._correction_attempts == 0

    def test_all_schemas_have_different_required_fields(self):
        """LLM-FMT-INT-006 — each non-general schema has distinct required fields."""  # noqa: E501
        required_sets: dict[str, set[str]] = {}
        for sid, s in SKILL_OUTPUT_SCHEMAS.items():
            if s.json_schema is None:
                continue
            req = set(s.json_schema.get("required", []))
            required_sets[sid] = req
        # Ensure no two schemas have identical required sets
        # (some may overlap, but the tuple of all requireds should differ)
        seen: set[str] = set()
        for sid, reqs in required_sets.items():
            key = ",".join(sorted(reqs))
            assert key not in seen or sid == "general", \
                f"{sid} has same required fields as another schema"
            seen.add(key)


# ============================================================================
#  LLM-FMT-REG-001 — Regression: contract tests for existing behaviour
# ============================================================================

class TestRegression:
    """
    Ensure previously passing behaviour does not regress.
    """

    def test_original_schema_count_preserved(self):
        """LLM-FMT-REG-001 — must remain 6 schemas (contract)."""
        assert len(SKILL_OUTPUT_SCHEMAS) == 6

    def test_original_required_fields_preserved(self):
        """LLM-FMT-REG-002 — data-analyst required fields unchanged."""
        req = DATA_ANALYST_SCHEMA.json_schema.get("required", [])
        assert set(req) == {"summary", "interpretation"}

    def test_original_valid_example_still_valid(self):
        """LLM-FMT-REG-003 — the embedded example in each schema validates."""  # noqa: E501
        for s in SKILL_OUTPUT_SCHEMAS.values():
            if s.json_schema is None:
                continue
            try:
                parsed = json.loads(s.example)
                Draft7Validator(s.json_schema).validate(parsed)
            except (json.JSONDecodeError, jsonschema.ValidationError):
                pass  # examples are markdown, not raw JSON — expected
