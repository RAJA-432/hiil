import { useState, useEffect, useCallback } from 'react'
import { useModels } from './useModels'
import { useSkills } from './useSkills'
import { useWorkspace } from './useWorkspace'
import { useToast } from './useToast'

export function useAppState(initialModel) {
  const { models, activeModel, switchModel, loading: modelsLoading } = useModels(initialModel)
  const { skills, activeSkill, switchSkill, loading: skillsLoading } = useSkills()
  const { fileTree, selectedFile, fileContent, fileLanguage, loading: fileLoading, loadFileTree, openFile, closeFile } = useWorkspace()
  const { toasts, remove: removeToast, success: toastSuccess, error: toastError } = useToast()
  const [fileTreeError, setFileTreeError] = useState(null)

  useEffect(() => {
    loadFileTree()
      .then(() => setFileTreeError(null))
      .catch(err => { console.error('Failed to load file tree:', err); toastError('Failed to load file tree'); setFileTreeError(err.message || 'Failed to load file tree') })
  }, [])

  const handleSwitchModel = useCallback(async (modelId) => {
    try {
      await switchModel(modelId)
    } catch {
      toastError('Failed to switch model')
    }
  }, [switchModel, toastError])

  const handleSelectSkill = useCallback(async (skillId) => {
    try {
      await switchSkill(skillId)
    } catch {
      toastError('Failed to activate skill')
    }
  }, [switchSkill, toastError])

  return {
    models, activeModel, modelsLoading,
    skills, activeSkill, skillsLoading,
    fileTree, selectedFile, fileContent, fileLanguage, fileLoading, fileTreeError,
    toasts, removeToast, toastSuccess, toastError,
    handleSwitchModel, handleSelectSkill,
    loadFileTree, openFile, closeFile,
  }
}
