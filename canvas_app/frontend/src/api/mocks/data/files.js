const workspaceFiles = {
  name: 'hiil',
  type: 'dir',
  path: 'hiil',
  children: [
    { name: 'src', type: 'dir', path: 'hiil/src', children: [
      { name: 'main.py', type: 'file', path: 'hiil/src/main.py', size: 1200 },
      { name: 'config.py', type: 'file', path: 'hiil/src/config.py', size: 800 },
      { name: 'auth', type: 'dir', path: 'hiil/src/auth', children: [
        { name: 'authenticator.py', type: 'file', path: 'hiil/src/auth/authenticator.py', size: 4500 },
        { name: 'middleware.py', type: 'file', path: 'hiil/src/auth/middleware.py', size: 2100 },
      ]},
      { name: 'datastructures', type: 'dir', path: 'hiil/src/datastructures', children: [
        { name: 'tree.py', type: 'file', path: 'hiil/src/datastructures/tree.py', size: 3200 },
      ]},
    ]},
    { name: 'tests', type: 'dir', path: 'hiil/tests', children: [
      { name: 'test_auth.py', type: 'file', path: 'hiil/tests/test_auth.py', size: 1500 },
      { name: 'test_tree.py', type: 'file', path: 'hiil/tests/test_tree.py', size: 2800 },
    ]},
    { name: 'docs', type: 'dir', path: 'hiil/docs', children: [] },
    { name: 'README.md', type: 'file', path: 'hiil/README.md', size: 3400 },
    { name: 'pyproject.toml', type: 'file', path: 'hiil/pyproject.toml', size: 1200 },
  ],
}

const fileContents = {
  'src/main.py': 'def main():\n    print("hello world")\n\nif __name__ == "__main__":\n    main()\n',
  'src/config.py': 'import os\n\nDEBUG = os.getenv("DEBUG", "false").lower() == "true"\nDATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///db.sqlite")\n',
  'src/auth/authenticator.py': 'import jwt\nimport bcrypt\nfrom datetime import datetime, timedelta\n\nSECRET_KEY = os.getenv("JWT_SECRET", "dev-secret")\nALGORITHM = "HS256"\n\ndef hash_password(password: str) -> str:\n    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()\n\ndef verify_password(password: str, hashed: str) -> bool:\n    return bcrypt.checkpw(password.encode(), hashed.encode())\n\ndef create_token(user_id: str) -> str:\n    payload = {\n        "sub": user_id,\n        "exp": datetime.utcnow() + timedelta(hours=24),\n    }\n    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)\n',
  'src/datastructures/tree.py': 'class Node:\n    def __init__(self, key):\n        self.key = key\n        self.left = None\n        self.right = None\n\nclass BST:\n    def __init__(self):\n        self.root = None\n\n    def insert(self, key):\n        if not self.root:\n            self.root = Node(key)\n            return\n        curr = self.root\n        while True:\n            if key < curr.key:\n                if curr.left is None:\n                    curr.left = Node(key)\n                    return\n                curr = curr.left\n            else:\n                if curr.right is None:\n                    curr.right = Node(key)\n                    return\n                curr = curr.right\n\n    def search(self, key):\n        curr = self.root\n        while curr:\n            if key == curr.key:\n                return True\n            curr = curr.left if key < curr.key else curr.right\n        return False\n',
  'README.md': '# hiil\n\nA CLI + Web chat backed by MCP tool servers.\n',
  'pyproject.toml': '[project]\nname = "hiil"\nversion = "0.2.0"\ndescription = "CLI + Web chat backed by MCP tool servers"\n',
  'tests/test_auth.py': 'def test_hash_password():\n    ...\n',
  'tests/test_tree.py': 'def test_bst_insert():\n    ...\ndef test_bst_search():\n    ...\n',
}

export function getMockFileTree() {
  return workspaceFiles
}

export function getMockFileContent(path) {
  return fileContents[path] || `// ${path}\n\n// File not found in mock data\n`
}
