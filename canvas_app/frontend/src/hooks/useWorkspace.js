import { useState, useCallback } from 'react'
import { getFileTree, readFile } from '../api/files'

export function useWorkspace() {
  const [fileTree, setFileTree] = useState(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [fileContent, setFileContent] = useState(null)
  const [fileLanguage, setFileLanguage] = useState('plaintext')
  const [loading, setLoading] = useState(false)

  const loadFileTree = useCallback(async () => {
    const tree = await getFileTree()
    setFileTree(tree)
  }, [])

  const openFile = useCallback(async (path) => {
    setLoading(true)
    setSelectedFile(path)
    try {
      const result = await readFile(path)
      setFileContent(result.content)
      setFileLanguage(result.language || 'plaintext')
    } catch {
      setFileContent(`// Error: could not load ${path}`)
      setFileLanguage('plaintext')
    }
    setLoading(false)
  }, [])

  const closeFile = useCallback(() => {
    setSelectedFile(null)
    setFileContent(null)
    setFileLanguage('plaintext')
  }, [])

  return { fileTree, selectedFile, fileContent, fileLanguage, loading, loadFileTree, openFile, closeFile }
}
