from __future__ import annotations

import re


def _resolve_path(data: dict | list, path: str):
    """Resolve a dotted path like ``sessions`` or ``messages.0.role``."""
    parts = path.split(".")
    current: object = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)) and part.lstrip("-").isdigit():
            idx = int(part)
            current = current[idx] if -len(current) <= idx < len(current) else None
        else:
            return None
    return current


def _check_schema(data: dict, schema: dict, path: str = "") -> list[str]:
    """Recursively validate *data* against *schema* (a dict of field→type/constraint dicts).

    Schema format::

        {
          "type": "object",                                    # required
          "properties": {
            "status": {"type": "string", "const": "ok"},
            "models": {"type": "array", "min_items": 1},
            "active": {"type": "string"},
            "reply": {"type": "string", "min_length": 1},
          },
          "required": ["status"],
          "additional_properties": False,                      # optional, default True
        }
    """
    errors: list[str] = []

    required = set(schema.get("required", []))
    allow_extra = schema.get("additional_properties", True)
    props = schema.get("properties", {})

    for key in required:
        if key not in data:
            errors.append(f"{path}{key}: missing required field")

    for key, value in data.items():
        fp = f"{path}{key}"
        if key not in props:
            if not allow_extra:
                errors.append(f"{fp}: unexpected field")
            continue

        spec = props[key]
        _check_value(value, spec, fp, errors)

    return errors


def _check_value(value, spec: dict, path: str, errors: list[str]):
    expected_type = spec.get("type")
    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": (list, tuple),
        "object": dict,
        "null": type(None),
    }
    if expected_type and expected_type != "null":
        py_type = type_map.get(expected_type)
        if py_type and not isinstance(value, py_type):
            errors.append(f"{path}: expected type {expected_type}, got {type(value).__name__}")
            return

    if "enum" in spec and value not in spec["enum"]:
        errors.append(f"{path}: expected one of {spec['enum']}, got {value!r}")

    if "const" in spec and value != spec["const"]:
        errors.append(f"{path}: expected const {spec['const']!r}, got {value!r}")

    if "pattern" in spec and isinstance(value, str):
        if not re.search(spec["pattern"], value):
            errors.append(f"{path}: did not match pattern {spec['pattern']!r}")

    if "min_length" in spec and isinstance(value, (str, list, tuple)):
        if len(value) < spec["min_length"]:
            errors.append(f"{path}: length {len(value)} < min {spec['min_length']}")

    if "max_length" in spec and isinstance(value, (str, list, tuple)):
        if len(value) > spec["max_length"]:
            errors.append(f"{path}: length {len(value)} > max {spec['max_length']}")

    if "min_items" in spec and isinstance(value, (list, tuple)):
        if len(value) < spec["min_items"]:
            errors.append(f"{path}: item count {len(value)} < min {spec['min_items']}")

    if "max_items" in spec and isinstance(value, (list, tuple)):
        if len(value) > spec["max_items"]:
            errors.append(f"{path}: item count {len(value)} > max {spec['max_items']}")

    if "contains" in spec and isinstance(value, (list, tuple)):
        if spec["contains"] not in value:
            errors.append(f"{path}: does not contain {spec['contains']!r}")

    if "properties" in spec and isinstance(value, dict):
        errors.extend(_check_schema(value, spec, f"{path}."))

    if "items" in spec and isinstance(value, (list, tuple)):
        items_spec = spec["items"]
        for i, item in enumerate(value):
            if isinstance(items_spec, dict):
                _check_value(item, items_spec, f"{path}[{i}]", errors)


def assert_api_response(case: dict, response) -> None:
    """Assert an HTTP *response* matches the expectations in *case*.

    Supported assertion keys (all optional)::

        expect_status               int               HTTP status code match
        expect_json                 dict              Shallow or dotted-path key/value equality
        expect_json_has_keys        list[str]         Keys that must be present
        expect_json_missing_keys    list[str]         Keys that must NOT be present
        expect_json_types           dict[str,str]     Type assertions per dotted path
        expect_json_array_length    dict[str,list]    {path: [min, max]} array length bounds
        expect_json_array_contains  dict[str,any]     {path: value} array must contain
        expect_json_schema          dict              Full structural schema (see _check_schema)
        expect_headers              dict[str,str]     Response header checks
        expect_text_includes        str               Raw text must appear in body
        expect_text_excludes        str               Raw text must NOT appear in body
        extra                       dict              Legacy compat
    """
    expect_status = case.get("expect_status")
    if expect_status is not None:
        assert response.status_code == expect_status, (
            f"{case['id']}: expected status {expect_status}, got {response.status_code}: {response.text[:200]}"
        )

    data = None
    if response.status_code < 500:
        ctype = response.headers.get("content-type", "")
        if "json" in ctype or "javascript" in ctype:
            try:
                data = response.json()
            except Exception:
                pass

    # --- JSON schema (most thorough) ---
    if "expect_json_schema" in case:
        assert data is not None, f"{case['id']}: expect_json_schema requires JSON body"
        errors = _check_schema(data, case["expect_json_schema"])
        assert not errors, (
            f"{case['id']}: schema violations:\n  " + "\n  ".join(errors)
        )

    # --- Shallow / dotted-path JSON equality ---
    if "expect_json" in case:
        assert data is not None, f"{case['id']}: expect_json requires JSON body"
        for key, value in case["expect_json"].items():
            resolved = _resolve_path(data, key)
            assert resolved == value, (
                f"{case['id']}: expected json.{key}={value!r}, got {resolved!r}"
            )

    # --- Key presence ---
    expect_keys = case.get("expect_json_has_keys", [])
    if expect_keys:
        assert data is not None, f"{case['id']}: expect_json_has_keys requires JSON body"
        for key in expect_keys:
            resolved = _resolve_path(data, key)
            assert resolved is not None, f"{case['id']}: missing expected key {key!r} in {data}"

    expect_missing = case.get("expect_json_missing_keys", [])
    if expect_missing:
        assert data is not None, f"{case['id']}: expect_json_missing_keys requires JSON body"
        for key in expect_missing:
            resolved = _resolve_path(data, key)
            assert resolved is None, f"{case['id']}: unexpected key {key!r} present with value {resolved!r}"

    # --- Type assertions ---
    if "expect_json_types" in case:
        assert data is not None, f"{case['id']}: expect_json_types requires JSON body"
        type_map_rev = {str: "str", int: "int", float: "float", bool: "bool", list: "list", tuple: "list", dict: "dict", type(None): "null"}
        for key, expected_type in case["expect_json_types"].items():
            resolved = _resolve_path(data, key)
            py_type_name = type_map_rev.get(type(resolved), type(resolved).__name__)
            assert py_type_name == expected_type, (
                f"{case['id']}: expected json.{key} to be {expected_type}, got {py_type_name} ({resolved!r})"
            )

    # --- Array length bounds ---
    if "expect_json_array_length" in case:
        assert data is not None, f"{case['id']}: expect_json_array_length requires JSON body"
        for key, (lo, hi) in case["expect_json_array_length"].items():
            arr = _resolve_path(data, key)
            assert isinstance(arr, (list, tuple)), f"{case['id']}: {key} is not a list"
            assert lo <= len(arr) <= hi, (
                f"{case['id']}: expected {key}.length in [{lo},{hi}], got {len(arr)}"
            )

    # --- Array contains ---
    if "expect_json_array_contains" in case:
        assert data is not None, f"{case['id']}: expect_json_array_contains requires JSON body"
        for key, value in case["expect_json_array_contains"].items():
            arr = _resolve_path(data, key)
            assert isinstance(arr, (list, tuple)), f"{case['id']}: {key} is not a list"
            assert value in arr, f"{case['id']}: {value!r} not in {key}"

    # --- Response headers ---
    if "expect_headers" in case:
        for header, expected in case["expect_headers"].items():
            actual = response.headers.get(header)
            assert actual == expected, (
                f"{case['id']}: expected header {header}={expected!r}, got {actual!r}"
            )

    # --- Text includes / excludes ---
    if "expect_text_includes" in case:
        assert case["expect_text_includes"] in response.text, (
            f"{case['id']}: expected text {case['expect_text_includes']!r} not found in response body"
        )
    if "expect_text_excludes" in case:
        assert case["expect_text_excludes"] not in response.text, (
            f"{case['id']}: unexpected text {case['expect_text_excludes']!r} found in response body"
        )

    # --- Legacy extra assertions ---
    extra = case.get("extra", {})
    if "sessions_contains" in extra and data is not None:
        assert extra["sessions_contains"] in data.get("sessions", {}), (
            f"{case['id']}: expected session {extra['sessions_contains']} in {data.get('sessions', {})}"
        )
    if "tools_contains" in extra and data is not None:
        assert extra["tools_contains"] in data.get("tools", {}), (
            f"{case['id']}: expected tool {extra['tools_contains']} in {data.get('tools', {})}"
        )
    if "models_min_count" in extra and data is not None:
        assert len(data.get("models", [])) >= extra["models_min_count"], (
            f"{case['id']}: expected >= {extra['models_min_count']} models, got {len(data.get('models', []))}"
        )
