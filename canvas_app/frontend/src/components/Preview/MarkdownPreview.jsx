import { marked } from '../Chat/markdown'

export default function MarkdownPreview({ content }) {
  return (
    <div
      style={{
        padding: 24,
        overflow: 'auto',
        height: '100%',
        lineHeight: 1.7,
        fontSize: 14,
      }}
      dangerouslySetInnerHTML={{ __html: marked(content) }}
    />
  )
}
