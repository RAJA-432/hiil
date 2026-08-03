export default function ArchitectureCard() {
  return (
    <div className="arch-card">
      <div className="arch-header">
        <svg className="arch-logo" width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
        </svg>
        <div>
          <h1>H.I.I.L.</h1>
          <div className="arch-sub">Hyper-Integrated Inference Engine</div>
        </div>
        <div className="arch-tagline">The MCP-native runtime for agents, RAG, and multimodal workflows</div>
      </div>

      <div className="arch-node arch-node-gateway">
        <strong>USER INTERFACE</strong>
        <span>React SPA / CLI</span>
      </div>
      <div className="arch-connector" aria-hidden="true">↓</div>
      <div className="arch-node arch-node-fastapi">
        <strong>FASTAPI GATEWAY</strong>
        <span>(Vajra Gate)</span>
      </div>

      <div className="arch-grid">
        <div className="arch-tile">
          <h3>Multi-Agent Runtime</h3>
          <ul>
            <li>Agent Registry</li>
            <li>Thread Manager</li>
            <li>A2A Orchestration</li>
          </ul>
        </div>
        <div className="arch-tile arch-tile-highlight">
          <h3>Knowledge Base (RAG)</h3>
          <ul>
            <li>Document Ingestion (PDF/DOCX)</li>
            <li>SQLite Vector Store</li>
            <li>Chunked Context Retrieval</li>
          </ul>
        </div>
        <div className="arch-tile">
          <h3>Tooling (MCP Native)</h3>
          <ul>
            <li>Built-in <code>veda_engine</code></li>
            <li>stdio servers (files, memory)</li>
            <li>Custom Connectors</li>
          </ul>
        </div>
      </div>

      <div className="arch-connector" aria-hidden="true">↓</div>
      <div className="arch-node arch-node-llm">
        <strong>LLM CONNECTION</strong>
        <span>Ollama / OpenAI Compatible · Multimodal Vision &amp; OCR Fallback</span>
      </div>
    </div>
  )
}
