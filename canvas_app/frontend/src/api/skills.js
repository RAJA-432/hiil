const USE_MOCK = (import.meta.env.VITE_USE_MOCK || 'false') === 'true'

import { apiGet, apiPost } from './client'

const MOCK_SKILLS = [
  {
    id: 'data-analyst',
    name: 'Data Analyst',
    description: 'Analyze data, create visualizations, and interpret statistical results with Python and SQL.',
    icon: 'chart',
    category: 'analysis',
    systemPrompt: 'You are a senior data analyst. Write clean Python/pandas code, explain statistical concepts clearly, and suggest the best visualization for every dataset. Always include axis labels and color palettes in plotting code.',
    promptTemplates: [
      { id: 'gen-chart', label: 'Generate a chart', prompt: 'Generate a chart for this data with proper labels and color scheme:\n\n' },
      { id: 'explain-reg', label: 'Explain regression output', prompt: 'Explain this regression output in plain language, including R-squared, p-values, and what the coefficients mean:\n\n' },
      { id: 'clean-data', label: 'Suggest data cleaning', prompt: 'Suggest data cleaning steps for this dataset. Check for missing values, outliers, and type inconsistencies:\n\n' },
      { id: 'describe-csv', label: 'Describe a CSV', prompt: 'Load and describe this CSV file: column names, data types, summary statistics, and initial observations:\n\n' },
    ],
    toolPresets: ['python', 'read_document', 'write_file', 'list_directory', 'search'],
    color: '#34d399',
  },
  {
    id: 'code-reviewer',
    name: 'Code Reviewer',
    description: 'Review code for bugs, performance issues, security vulnerabilities, and style violations.',
    icon: 'code',
    category: 'development',
    systemPrompt: 'You are an expert code reviewer. Review code for correctness, performance, security, and style. Provide specific line-level feedback with code examples. Follow the principle of leaving the codebase cleaner than you found it.',
    promptTemplates: [
      { id: 'review-pr', label: 'Review pull request', prompt: 'Review this code for bugs, performance issues, and style improvements. Be specific:\n\n' },
      { id: 'find-bugs', label: 'Find bugs', prompt: 'Find potential bugs and edge cases in this code. Consider null safety, race conditions, and error handling:\n\n' },
      { id: 'optimize', label: 'Suggest optimizations', prompt: 'Suggest performance optimizations for this code. Profile hotspots and propose specific improvements:\n\n' },
      { id: 'security-audit', label: 'Security audit', prompt: 'Audit this code for security vulnerabilities including injection, XSS, auth bypass, and secret exposure:\n\n' },
    ],
    toolPresets: ['read_document', 'search', 'write_file'],
    color: '#60a5fa',
  },
  {
    id: 'writer',
    name: 'Writer & Editor',
    description: 'Draft, edit, and polish documents, emails, articles, and technical writing.',
    icon: 'pen',
    category: 'writing',
    systemPrompt: 'You are a professional writer and editor. Adapt your tone to the audience, vary sentence structure, avoid passive voice where possible, and always proofread for clarity and concision.',
    promptTemplates: [
      { id: 'draft-email', label: 'Draft an email', prompt: 'Draft a professional email about:\n\n' },
      { id: 'polish-text', label: 'Polish and tighten', prompt: 'Polish this text for clarity, concision, and impact. Remove redundancies:\n\n' },
      { id: 'summarize', label: 'Summarize', prompt: 'Summarize the key points of this in 3-5 bullet points:\n\n' },
      { id: 'change-tone', label: 'Change tone', prompt: 'Rewrite this in a more {tone} tone:\n\n' },
    ],
    toolPresets: ['read_document', 'write_file', 'search'],
    color: '#a78bfa',
  },
  {
    id: 'architect',
    name: 'System Architect',
    description: 'Design system architecture, plan migrations, create API designs, and document technical decisions.',
    icon: 'layers',
    category: 'development',
    systemPrompt: 'You are a senior software architect. Focus on system design, trade-offs, scalability, and clear documentation. Use diagrams (ASCII or Mermaid) to illustrate architecture. Always consider non-functional requirements.',
    promptTemplates: [
      { id: 'design-api', label: 'Design an API', prompt: 'Design a REST/GraphQL API for:\n\nInclude endpoints, request/response shapes, and auth.\n\n' },
      { id: 'architecture-review', label: 'Architecture review', prompt: 'Review this architecture for scalability, fault tolerance, and cost. Suggest improvements:\n\n' },
      { id: 'migration-plan', label: 'Migration plan', prompt: 'Create a step-by-step migration plan for:\n\nInclude rollback strategy and risk assessment.\n\n' },
      { id: 'doc-decision', label: 'Document ADR', prompt: 'Write an Architecture Decision Record for:\n\nInclude context, options considered, decision, and consequences.\n\n' },
    ],
    toolPresets: ['read_document', 'write_file', 'search', 'list_directory'],
    color: '#fbbf24',
  },
  {
    id: 'researcher',
    name: 'Research Assistant',
    description: 'Gather information, synthesize findings, cite sources, and produce structured research briefs.',
    icon: 'search-lg',
    category: 'analysis',
    systemPrompt: 'You are a thorough research assistant. Gather information from multiple sources, evaluate credibility, cite everything, and produce well-structured research summaries. Distinguish between fact, inference, and speculation.',
    promptTemplates: [
      { id: 'research-topic', label: 'Research a topic', prompt: 'Research this topic and produce a structured brief with key findings, supporting evidence, and open questions:\n\n' },
      { id: 'compare-sources', label: 'Compare sources', prompt: 'Compare and contrast the following sources on this topic. Note disagreements and consensus:\n\n' },
      { id: 'literature-review', label: 'Literature review', prompt: 'Conduct a mini literature review on:\n\nInclude key papers, methodologies, and gaps.\n\n' },
    ],
    toolPresets: ['search', 'read_document', 'write_file'],
    color: '#f87171',
  },
  {
    id: 'general',
    name: 'General Assistant',
    description: 'Default persona. General-purpose AI assistant with no specialization.',
    icon: 'sparkles',
    category: 'general',
    systemPrompt: '',
    promptTemplates: [],
    toolPresets: ['read_document', 'write_file', 'search', 'list_directory', 'python'],
    color: '#9ca3af',
  },
]

let _mockActiveId = 'general'

export async function listSkills() {
  if (USE_MOCK) return [...MOCK_SKILLS]
  return (await apiGet('/api/skills')).skills || []
}

export async function getSkill(skillId) {
  if (USE_MOCK) return MOCK_SKILLS.find(s => s.id === skillId) || null
  return apiGet(`/api/skills/${skillId}`)
}

export async function activateSkill(skillId) {
  if (USE_MOCK) {
    _mockActiveId = skillId
    return { success: true, skill: MOCK_SKILLS.find(s => s.id === skillId) }
  }
  return apiPost('/api/skills/activate', { skill_id: skillId })
}

export function getActiveSkill() {
  if (USE_MOCK) return MOCK_SKILLS.find(s => s.id === _mockActiveId) || MOCK_SKILLS.find(s => s.id === 'general')
  return null
}
