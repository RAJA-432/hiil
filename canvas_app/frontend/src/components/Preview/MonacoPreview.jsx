import Editor from '@monaco-editor/react'

export default function MonacoPreview({ content, language, theme }) {
  return (
    <Editor
      height="100%"
      language={language}
      value={content}
      theme={theme === 'light' ? 'vs' : 'vs-dark'}
      options={{
        readOnly: true,
        minimap: { enabled: true },
        scrollBeyondLastLine: false,
        fontSize: 13,
        lineNumbers: 'on',
        renderLineHighlight: 'none',
        folding: true,
        automaticLayout: true,
        padding: { top: 8 },
      }}
    />
  )
}
