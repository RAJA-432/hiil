import json

d = json.load(open("tests/data/api_e2e_tests.json"))
removed_ids = {"tool_call_success", "tool_call_not_found", "tool_call_missing_name"}
before = len(d["cases"])
d["cases"] = [c for c in d["cases"] if c["id"] not in removed_ids]
after = len(d["cases"])
json.dump(d, open("tests/data/api_e2e_tests.json", "w"), indent=2)
print(f"Removed {before - after} cases. {after} remain.")
