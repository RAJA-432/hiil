import { useState, useEffect, useCallback, Fragment } from 'react'
import { replaceEmojiShortcodes } from '../../utils/emoji'

const _ALLOWED_URI_SCHEMES = new Set(['http', 'https', 'mailto', 'file'])
function isSafeUrl(url) {
  try {
    const parsed = new URL(url)
    return _ALLOWED_URI_SCHEMES.has(parsed.protocol.replace(':', ''))
  } catch {
    return false
  }
}

function CodeBlock({ className, children }) {
  const match = /language-(\w+)/.exec(className || '')
  const lang = match ? match[1] : ''
  const code = String(children).replace(/\n$/, '')

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).catch(() => {})
  }, [code])

  return (
    <div className="code-block-wrapper">
      <div className="code-block-header">
        <span className="code-block-lang">{lang || 'code'}</span>
        <button className="code-block-copy" onClick={handleCopy} aria-label="Copy code">Copy</button>
      </div>
      <pre><code className={className}>{code}</code></pre>
    </div>
  )
}

function Link({ href, children, ...props }) {
  const handleClick = useCallback((e) => {
    if (href && (href.startsWith('file://') || href.startsWith('/'))) {
      e.preventDefault()
      const event = new CustomEvent('open-file', { detail: href })
      document.dispatchEvent(event)
    }
  }, [href])

  if (href && (href.startsWith('file://') || href.startsWith('/'))) {
    return <a href="#" data-file={href} onClick={handleClick} {...props}>{children}</a>
  }
  if (href && !isSafeUrl(href)) {
    return <span>{children}</span>
  }
  return <a href={href} target="_blank" rel="noopener" onClick={handleClick} {...props}>{children}</a>
}

function Image({ src, alt, ...props }) {
  if (src && !isSafeUrl(src)) {
    return null
  }
  return <img src={src} alt={alt || ''} loading="lazy" {...props} />
}

function Checkbox({ checked, ...props }) {
  return (
    <input type="checkbox" checked={checked} disabled {...props} />
  )
}

function Table({ children }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table>{children}</table>
    </div>
  )
}

export default function MarkdownRenderer({ content }) {
  const [MD, setMD] = useState(null)
  const [plugins, setPlugins] = useState(null)
  const processed = replaceEmojiShortcodes(content || '')

  useEffect(() => {
    Promise.all([
      import('react-markdown'),
      import('remark-gfm'),
      import('rehype-raw'),
    ]).then(([md, gfm, raw]) => {
      setMD(() => md.default)
      setPlugins({ remarkGfm: gfm.default, rehypeRaw: raw.default })
    })
  }, [])

  if (!MD || !plugins) {
    return <Fragment>{processed}</Fragment>
  }

  return (
    <MD
      remarkPlugins={[plugins.remarkGfm]}
      rehypePlugins={[plugins.rehypeRaw]}
      components={{
        code({ node, inline, className, children, ...props }) {
          if (!inline) {
            return <CodeBlock className={className}>{children}</CodeBlock>
          }
          return <code className={className} {...props}>{children}</code>
        },
        a: Link,
        img: Image,
        input: Checkbox,
        table: Table,
      }}
    >
      {processed}
    </MD>
  )
}
