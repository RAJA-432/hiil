const escMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
}

function escapeHtml(str) {
  return str.replace(/[&<>"]/g, (c) => escMap[c])
}

const _ALLOWED_URI_SCHEMES = new Set(['http', 'https', 'mailto', 'file'])
function _is_safe_url(url) {
  try {
    const parsed = new URL(url)
    return _ALLOWED_URI_SCHEMES.has(parsed.protocol.replace(':', ''))
  } catch {
    return false
  }
}

function replaceEmojiShortcodes(text) {
  const emojiMap = {
    ':smile:': '😊', ':laughing:': '😂', ':wink:': '😉', ':heart:': '❤️',
    ':thumbsup:': '👍', ':thumbsdown:': '👎', ':clap:': '👏', ':fire:': '🔥',
    ':rocket:': '🚀', ':star:': '⭐', ':check:': '✅', ':x:': '❌',
    ':warning:': '⚠️', ':bulb:': '💡', ':question:': '❓', ':info:': 'ℹ️',
    ':gear:': '⚙️', ':lock:': '🔒', ':key:': '🔑', ':bug:': '🐛',
    ':chart:': '📊', ':code:': '💻', ':file:': '📄', ':folder:': '📁',
    ':search:': '🔍', ':link:': '🔗', ':mail:': '📧', ':pen:': '✍️',
    ':sparkles:': '✨', ':tada:': '🎉', ':package:': '📦', ':book:': '📖',
  }
  return text.replace(/:[\w+-]+:/g, (match) => emojiMap[match] || match)
}

export function marked(text) {
  if (!text) return ''

  let html = escapeHtml(text)

  html = replaceEmojiShortcodes(html)

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const langLabel = lang || 'code'
    const encoded = encodeURIComponent(code)
    return `<div class="code-block-wrapper"><div class="code-block-header"><span class="code-block-lang">${langLabel}</span><button class="code-block-copy" data-copy="${encoded}">Copy</button></div><pre><code>${code}</code></pre></div>`
  })

  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')

  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
    if (!_is_safe_url(src)) src = '#'
    return `<img src="${src}" alt="${alt}" loading="lazy" />`
  })

  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
    if (url.startsWith('file://') || url.startsWith('/')) {
      return `<a href="#" data-file="${url}">${text}</a>`
    }
    if (!_is_safe_url(url)) url = '#'
    return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`
  })

  html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  html = html.replace(/^-{3,}$/gm, '<hr />')

  html = html.replace(/(?<![">])(https?:\/\/[^\s<]+)/g, (_, url) => {
    return `<a href="${url}" target="_blank" rel="noopener">${url}</a>`
  })

  const lines = html.split('\n')
  const result = []
  let inList = false
  let listType = null

  for (const line of lines) {
    const taskMatch = line.match(/^(\s*[-*]\s+)\[(.)\]\s+(.*)/)
    if (taskMatch) {
      const checked = taskMatch[2] === 'x' || taskMatch[2] === 'X'
      const content = taskMatch[3]
      if (!inList || listType !== 'ul') {
        if (inList) result.push(`</${listType}>`)
        result.push('<ul class="task-list">')
        inList = true
        listType = 'ul'
      }
      const attr = checked ? ' checked=""' : ''
      result.push(`<li class="task-list-item"><input type="checkbox" disabled${attr} />${content}</li>`)
      continue
    }

    if (line.startsWith('- ') || line.startsWith('* ')) {
      const content = line.slice(2)
      if (!inList || listType !== 'ul') {
        if (inList) result.push(`</${listType}>`)
        result.push('<ul>')
        inList = true
        listType = 'ul'
      }
      result.push(`<li>${content}</li>`)
    } else if (/^\d+\.\s/.test(line)) {
      const content = line.replace(/^\d+\.\s/, '')
      if (!inList || listType !== 'ol') {
        if (inList) result.push(`</${listType}>`)
        result.push('<ol>')
        inList = true
        listType = 'ol'
      }
      result.push(`<li>${content}</li>`)
    } else {
      if (inList) {
        result.push(`</${listType}>`)
        inList = false
        listType = null
      }
      if (line.trim() === '') {
        result.push('<br />')
      } else if (/^#{1,4}\s/.test(line)) {
        const level = line.match(/^#+/)[0].length
        const content = line.replace(/^#+\s/, '')
        result.push(`<h${level}>${content}</h${level}>`)
      } else if (/^>\s/.test(line)) {
        result.push(`<blockquote>${line.replace(/^>\s/, '')}</blockquote>`)
      } else if (/^\|.+\|/.test(line)) {
        result.push(`<p>${line}</p>`)
      } else {
        result.push(`<p>${line}</p>`)
      }
    }
  }

  if (inList) result.push(`</${listType}>`)

  return result.join('\n')
}
