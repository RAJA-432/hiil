import { useCallback } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeRaw from 'rehype-raw'

const emojiMap = {
  ':smile:': '\u{1F60A}', ':laughing:': '\u{1F602}', ':wink:': '\u{1F609}', ':heart:': '\u2764\uFE0F',
  ':thumbsup:': '\u{1F44D}', ':thumbsdown:': '\u{1F44E}', ':clap:': '\u{1F44F}', ':fire:': '\u{1F525}',
  ':rocket:': '\u{1F680}', ':star:': '\u2B50', ':check:': '\u2705', ':x:': '\u274C',
  ':warning:': '\u26A0\uFE0F', ':bulb:': '\u{1F4A1}', ':question:': '\u2753', ':info:': '\u2139\uFE0F',
  ':gear:': '\u2699\uFE0F', ':lock:': '\u{1F512}', ':key:': '\u{1F511}', ':bug:': '\u{1F41B}',
  ':chart:': '\u{1F4CA}', ':code:': '\u{1F4BB}', ':file:': '\u{1F4C4}', ':folder:': '\u{1F4C1}',
  ':search:': '\u{1F50D}', ':link:': '\u{1F517}', ':mail:': '\u{1F4E7}', ':pen:': '\u270D\uFE0F',
  ':sparkles:': '\u2728', ':tada:': '\u{1F389}', ':package:': '\u{1F4E6}', ':book:': '\u{1F4D6}',
}

function replaceEmojiShortcodes(text) {
  return text.replace(/:[\w+-]+:/g, (match) => emojiMap[match] || match)
}

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
  const processed = replaceEmojiShortcodes(content || '')

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeRaw]}
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
    </ReactMarkdown>
  )
}
