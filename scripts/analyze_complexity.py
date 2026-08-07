import ast
import os

root = r"C:\Users\rajas\my-folder\hiil"
files = []
for base in ["mcp_cli", "vajra_gate", "veda_engine", "setu_bridge"]:
    d = os.path.join(root, base)
    for dirpath, dirs, fns in os.walk(d):
        dirs[:] = [x for x in dirs if x not in ("__pycache__",)]
        for fn in fns:
            if fn.endswith(".py"):
                files.append(os.path.join(dirpath, fn))

def _nesting(func):
    branches = [ast.If, ast.For, ast.While, ast.With, ast.Try, ast.comprehension]
    maxd = 0

    def walk(node, depth):
        nonlocal maxd
        cur = depth + 1 if isinstance(node, tuple(branches)) else depth
        maxd = max(maxd, cur)
        for child in ast.iter_child_nodes(node):
            walk(child, cur)

    walk(func, 0)
    return maxd


rows = []
for path in files:
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception:
        continue
    lines = len(src.splitlines())
    nfunc = sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))
    nclass = sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree))
    maxcc = 0
    maxname = ""
    maxdepth = 0
    deepname = ""
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cc = 1
            for m in ast.walk(n):
                if isinstance(
                    m,
                    (
                        ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With,
                        ast.AsyncFor, ast.AsyncWith, ast.Try, ast.BoolOp,
                        ast.comprehension,
                    ),
                ):
                    cc += 1
            if cc > maxcc:
                maxcc = cc
                maxname = n.name
            depth = _nesting(n)
            if depth > maxdepth:
                maxdepth = depth
                deepname = n.name
    rows.append((path, lines, nfunc, nclass, maxcc, maxname, maxdepth, deepname))

rows.sort(key=lambda r: -r[1])
rel = lambda p: os.path.relpath(p, root)  # noqa: E731
print(f"{'module':<55}{'LOC':>6}{'fn':>5}{'cls':>5}{'maxCC':>6}{'maxd':>5}  fn@maxCC")
for p, l, f, c, m, mn, md, dn in rows[:45]:
    print(f"{rel(p):<55}{l:>6}{f:>5}{c:>5}{m:>6}{md:>5}  {mn}")
