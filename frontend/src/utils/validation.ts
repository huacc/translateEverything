import type { CreateTaskData } from '@/types/task'

export const validateFile = (file: File | null): string | null => {
  if (!file) {
    return '请上传文件'
  }

  if (file.type !== 'application/pdf') {
    return '当前 MVP 仅支持 PDF 格式文件'
  }

  const maxSize = 100 * 1024 * 1024
  if (file.size > maxSize) {
    return '文件大小不能超过 100MB'
  }

  return null
}

export const validateLanguage = (
  sourceLang: string,
  targetLang: string
): string | null => {
  if (!sourceLang) {
    return '请选择源语言'
  }

  if (!targetLang) {
    return '请选择目标语言'
  }

  if (sourceLang === targetLang) {
    return '目标语言不能与源语言相同'
  }

  return null
}

export const validateTaskForm = (
  formData: Partial<CreateTaskData>
): Record<string, string> => {
  const errors: Record<string, string> = {}

  const fileError = validateFile(formData.file || null)
  if (fileError) {
    errors.file = fileError
  }

  const langError = validateLanguage(
    formData.source_lang || '',
    formData.target_lang || ''
  )
  if (langError) {
    errors.language = langError
  }

  return errors
}
