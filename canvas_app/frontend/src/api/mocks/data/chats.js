let convCounter = 4
let msgCounter = 20

function ago(minutes) {
  const d = new Date(Date.now() - minutes * 60 * 1000)
  return d.toISOString()
}

export const conversations = [
  { id: 'conv_1', title: 'How do I implement a binary search tree?', created: ago(30), updated: ago(25), message_count: 5 },
  { id: 'conv_2', title: 'Refactor the auth module', created: ago(120), updated: ago(90), message_count: 12 },
  { id: 'conv_3', title: 'Debug database connection pool', created: ago(240), updated: ago(210), message_count: 8 },
  { id: 'conv_4', title: 'Explain the MCP protocol architecture', created: ago(480), updated: ago(460), message_count: 3 },
]

export const messages = {
  conv_1: [
    { id: 'm1', role: 'user', content: 'Can you show me how to implement a binary search tree in Python?', timestamp: ago(30), tool_calls: [], artifacts: [], rag_chunks: [] },
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

Would you like me to add \`delete\` and \`balance\` methods as well?`, timestamp: ago(29), tool_calls: [{ tool: 'read_document', args: { path: 'src/datastructures/tree.py' }, status: 'done', result: 'Found existing file with basic tree structure' }], artifacts: [{ type: 'code', title: 'bst.py', content: 'class Node...' }], rag_chunks: [{ text: 'Binary search trees support O(log n) insertion, deletion, and search operations on average.', score: 0.92, metadata: { filename: 'dsa_notes.md' } }, { text: 'Python implementation of BST with insert, search, inorder traversal methods.', score: 0.87, metadata: { filename: 'examples/bst.py' } }] },
    { id: 'm3', role: 'user', content: 'Yes, add delete and balance methods', timestamp: ago(28), tool_calls: [], artifacts: [], rag_chunks: [] },
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

For balancing, you can run a **sorted array → balanced BST** algorithm on the inorder traversal. This re-constructs the tree in O(n).`, timestamp: ago(27), tool_calls: [{ tool: 'edit_document', args: { path: 'src/datastructures/tree.py' }, status: 'done', result: 'Added delete and balance methods' }], artifacts: [{ type: 'code', title: 'bst_extended.py', content: 'def delete...' }], rag_chunks: [] },
  ],
  conv_2: [
    { id: 'm5', role: 'user', content: 'I need to refactor the auth module. Currently it uses basic auth and I want JWT.', timestamp: ago(120), tool_calls: [], artifacts: [], rag_chunks: [] },
    { id: 'm6', role: 'assistant', content: 'Let me look at the current auth module first.\n\n```\nReading src/auth/authenticator.py...\nFound 245 lines\n```', timestamp: ago(119), tool_calls: [{ tool: 'read_document', args: { path: 'src/auth/authenticator.py' }, status: 'done' }], artifacts: [], rag_chunks: [] },
  ],
  conv_3: [
    { id: 'm7', role: 'user', content: 'The database connection pool keeps exhausting under load.', timestamp: ago(240), tool_calls: [], artifacts: [], rag_chunks: [] },
    { id: 'm8', role: 'assistant', content: 'Let me investigate the connection pool configuration.\n\n```\nChecking config/database.py...\nPool size: 5, max overflow: 2\nTimeout: 30s\n```\n\nThe issue is likely the pool size being too small for concurrent requests. With 5 workers × 5 connections, you can handle 25 concurrent queries before overflow kicks in.', timestamp: ago(239), tool_calls: [{ tool: 'read_document', args: { path: 'config/database.py' }, status: 'done' }], artifacts: [], rag_chunks: [] },
  ],
  conv_4: [
    { id: 'm9', role: 'user', content: 'Can you explain the MCP protocol architecture?', timestamp: ago(480), tool_calls: [], artifacts: [], rag_chunks: [] },
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

The transport layer uses either **stdio** (for local subprocess) or **SSE** (for remote servers).`, timestamp: ago(479), tool_calls: [], artifacts: [{ type: 'markdown', title: 'MCP Architecture', content: '# MCP...' }], rag_chunks: [] },
  ],
}

export function getMockConversations() {
  return [...conversations].sort((a, b) => new Date(b.updated) - new Date(a.updated))
}

export function getMockMessages(convId) {
  return messages[convId] || []
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
    rag_chunks: [],
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

export function getMockUsage() {
  return {
    session: { input_tokens: 1247, output_tokens: 892, total_tokens: 2139, cost: 0.042 },
    total: { input_tokens: 28470, output_tokens: 15630, total_tokens: 44100, cost: 1.24 },
  }
}
