import json

d = json.load(open("tests/data/api_e2e_tests.json"))
for i,c in enumerate(d["cases"]):
    print(f"{i:2d} {c['id']:30s} {c['method']:4s} {c['path']}")
