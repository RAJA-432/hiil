let convCounter = 4
let msgCounter = 20

function ago(minutes) {
  const d = new Date(Date.now() - minutes * 60 * 1000)
  return d.toISOString()
}

const conversations = [
  { id: 'conv_1', title: 'How do I implement a binary search tree?', created: ago(30), updated: ago(25), message_count: 5 },
  { id: 'conv_2', title: 'Refactor the auth module', created: ago(120), updated: ago(90), message_count: 12 },
  { id: 'conv_3', title: 'Debug database connection pool', created: ago(240), updated: ago(210), message_count: 8 },
  { id: 'conv_4', title: 'Explain the MCP protocol architecture', created: ago(480), updated: ago(460), message_count: 3 },
]

const messages = {
  conv_1: [
    { id: 'm1', role: 'user', content: 'Can you show me how to implement a binary search tree in Python?', timestamp: ago(30), tool_calls: [], artifacts: [] },
    { id: 'm2', role: 'assistant', content: `Here's a clean implementation of a BST in Python:

\`\`\`python
class Node:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, key):
        if not self.root:
            self.root = Node(key)
            return
        curr = self.root
        while True:
            if key < curr.key:
                if curr.left is None:
                    curr.left = Node(key)
                    return
                curr = curr.left
            else:
                if curr.right is None:
                    curr.right = Node(key)
                    return
                curr = curr.right

    def search(self, key):
        curr = self.root
        while curr:
            if key == curr.key:
                return True
            curr = curr.left if key < curr.key else curr.right
        return False

    def inorder(self, node=None, out=None):
        if out is None: out = []
        if node is None: node = self.root
        if node:
            self.inorder(node.left, out)
            out.append(node.key)
            self.inorder(node.right, out)
        return out
\`\`\`

The key operations:

- **Insert**: O(log n) average, walks the tree left/right until finding an empty spot
- **Search**: O(log n) average, follows the same comparison path
- **Inorder traversal**: returns keys in sorted order

Would you like me to add \`delete\` and \`balance\` methods as well?`, timestamp: ago(29), tool_calls: [{ tool: 'read_document', args: { path: 'src/datastructures/tree.py' }, status: 'done', result: 'Found existing file with basic tree structure' }], artifacts: [{ type: 'code', title: 'bst.py', content: 'class Node...' }] },
    { id: 'm3', role: 'user', content: 'Yes, add delete and balance methods', timestamp: ago(28) },
    { id: 'm4', role: 'assistant', content: `Here's the extended implementation with deletion and balancing:

\`\`\`python
def delete(self, key):
    self.root = self._delete(self.root, key)

def _delete(self, node, key):
    if node is None:
        return None
    if key < node.key:
        node.left = self._delete(node.left, key)
    elif key > node.key:
        node.right = self._delete(node.right, key)
    else:
        if node.left is None:
            return node.right
        if node.right is None:
            return node.left
        min_larger = self._min(node.right)
        node.key = min_larger.key
        node.right = self._delete(node.right, min_larger.key)
    return node

def _min(self, node):
    while node.left:
        node = node.left
    return node
\`\`\`

For balancing, you can run a **sorted array → balanced BST** algorithm on the inorder traversal. This re-constructs the tree in O(n).`, timestamp: ago(27), tool_calls: [{ tool: 'edit_document', args: { path: 'src/datastructures/tree.py' }, status: 'done', result: 'Added delete and balance methods' }], artifacts: [{ type: 'code', title: 'bst_extended.py', content: 'def delete...' }] },
  ],
  conv_2: [
    { id: 'm5', role: 'user', content: 'I need to refactor the auth module. Currently it uses basic auth and I want JWT.', timestamp: ago(120), tool_calls: [], artifacts: [] },
    { id: 'm6', role: 'assistant', content: 'Let me look at the current auth module first.\n\n```\nReading src/auth/authenticator.py...\nFound 245 lines\n```', timestamp: ago(119), tool_calls: [{ tool: 'read_document', args: { path: 'src/auth/authenticator.py' }, status: 'done' }], artifacts: [] },
  ],
  conv_3: [
    { id: 'm7', role: 'user', content: 'The database connection pool keeps exhausting under load.', timestamp: ago(240), tool_calls: [], artifacts: [] },
    { id: 'm8', role: 'assistant', content: 'Let me investigate the connection pool configuration.\n\n\`\`\`\nChecking config/database.py...\nPool size: 5, max overflow: 2\nTimeout: 30s\n\`\`\`\n\nThe issue is likely the pool size being too small for concurrent requests. With 5 workers × 5 connections, you can handle 25 concurrent queries before overflow kicks in.', timestamp: ago(239), tool_calls: [{ tool: 'read_document', args: { path: 'config/database.py' }, status: 'done' }], artifacts: [] },
  ],
  conv_4: [
    { id: 'm9', role: 'user', content: 'Can you explain the MCP protocol architecture?', timestamp: ago(480), tool_calls: [], artifacts: [] },
    { id: 'm10', role: 'assistant', content: `The **Model Context Protocol (MCP)** follows a client-server architecture:

\`\`\`
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│   Host      │────▶│   Client     │────▶│   Server     │
│ (Claude,    │     │  (SDK)       │     │  (Tools,     │
│  IDE, etc)  │     │              │     │   Resources) │
└─────────────┘     └──────────────┘     └──────────────┘
\`\`\`

**Key concepts:**

1. **Resources** — Read-only data (files, database records, APIs)
2. **Tools** — Functions the server exposes (search, compute, transform)
3. **Prompts** — Reusable prompt templates

The transport layer uses either **stdio** (for local subprocess) or **SSE** (for remote servers).`, timestamp: ago(479), tool_calls: [], artifacts: [{ type: 'markdown', title: 'MCP Architecture', content: '# MCP...' }] },
  ],
}

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

export function getMockConversations() {
  return [...conversations].sort((a, b) => new Date(b.updated) - new Date(a.updated))
}

export function getMockMessages(convId) {
  return messages[convId] || []
}

export function getMockFileTree() {
  return workspaceFiles
}

export function getMockFileContent(path) {
  return fileContents[path] || `// ${path}\n\n// File not found in mock data\n`
}

export function getMockModels() {
  return [
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai' },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai' },
    { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', provider: 'anthropic' },
    { id: 'gemma4:31b-cloud', name: 'Gemma 4 31B', provider: 'ollama' },
  ]
}

export function addMockMessage(convId, role, content, toolCalls, artifacts) {
  if (!messages[convId]) messages[convId] = []
  const msg = {
    id: `m${msgCounter++}`,
    role,
    content,
    timestamp: new Date().toISOString(),
    tool_calls: toolCalls || [],
    artifacts: artifacts || [],
  }
  messages[convId].push(msg)
  const conv = conversations.find(c => c.id === convId)
  if (conv) {
    conv.updated = msg.timestamp
    conv.message_count++
    if (role === 'user' && conv.title === `Conversation ${conv.id.split('_')[1]}`) {
      conv.title = content.slice(0, 60)
    }
  }
  return msg
}

export function addMockConversation(title) {
  const id = `conv_${convCounter++}`
  const now = new Date().toISOString()
  const conv = { id, title: title || `Conversation ${convCounter - 1}`, created: now, updated: now, message_count: 0 }
  conversations.push(conv)
  messages[id] = []
  return conv
}

export function deleteMockConversation(id) {
  const idx = conversations.findIndex(c => c.id === id)
  if (idx >= 0) conversations.splice(idx, 1)
  delete messages[id]
}

export function simulateStreamResponse(convId, text, onToken, onTool, onDone) {
  let i = 0
  let buffer = ''
  const toolCalls = []
  let timer = null

  function emit() {
    if (i >= text.length) {
      if (onDone) onDone(text, toolCalls, [])
      return
    }

    const chunkSize = Math.min(3 + Math.floor(Math.random() * 8), text.length - i)
    const chunk = text.slice(i, i + chunkSize)
    i += chunkSize
    buffer += chunk
    if (onToken) onToken(buffer)

    if (Math.random() < 0.02 && toolCalls.length === 0) {
      const tool = { tool: 'read_document', args: { path: 'src/main.py' }, status: 'running' }
      if (onTool) onTool(tool)
      setTimeout(() => {
        tool.status = 'done'
        tool.result = 'File contents loaded'
        if (onTool) onTool(tool)
        toolCalls.push(tool)
      }, 300 + Math.random() * 400)
    }

    const delay = 15 + Math.random() * 30
    timer = setTimeout(emit, delay)
  }

  emit()
  return () => { if (timer) clearTimeout(timer) }
}
