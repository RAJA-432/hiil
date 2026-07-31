export function getMockModels() {
  return [
    { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai' },
    { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai' },
    { id: 'claude-sonnet-4', name: 'Claude Sonnet 4', provider: 'anthropic' },
    { id: 'gemma4:31b-cloud', name: 'Gemma 4 31B', provider: 'ollama' },
  ]
}
