const escMap = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
}

function escapeHtml(str) {
  return str.replace(/[&<>"]/g, (c) => escMap[c])
}

export function marked(text) {
  if (!text) return ''

  let html = escapeHtml(text)

  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    const langAttr = lang ? ` data-lang="${lang}"` : ''
    return `<pre${langAttr}><code>${code}</code></pre>`
  })

  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')

  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" loading="lazy" />')

  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, url) => {
    if (url.startsWith('file://') || url.startsWith('/')) {
      return `<a href="#" data-file="${url}">${text}</a>`
    }
    return `<a href="${url}" target="_blank" rel="noopener">${text}</a>`
  })

  html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>')

  html = html.replace(/^-{3,}$/gm, '<hr />')

  const lines = html.split('\n')
  const result = []
  let inList = false
  let listType = null

  for (const line of lines) {
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
      } else {
        if (line.startsWith('<')) {
          result.push(`${line}`)
        } else {
          result.push(`<p>${line}</p>`)
        }
      }
    }
  }

  if (inList) result.push(`</${listType}>`)

  return result.join('\n')
}
