import type { JobStatus, TranslationJob } from '@/types/task'

export const formatDate = (dateString: string): string => {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now.getTime() - date.getTime()

  if (diff < 60 * 1000) {
    return '刚刚'
  }

  if (diff < 60 * 60 * 1000) {
    const minutes = Math.floor(diff / (60 * 1000))
    return `${minutes}分钟前`
  }

  if (diff < 24 * 60 * 60 * 1000) {
    const hours = Math.floor(diff / (60 * 60 * 1000))
    return `${hours}小时前`
  }

  if (diff < 7 * 24 * 60 * 60 * 1000) {
    const days = Math.floor(diff / (24 * 60 * 60 * 1000))
    return `${days}天前`
  }

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes}`
}

export const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const index = Math.floor(Math.log(bytes) / Math.log(k))

  return `${(bytes / Math.pow(k, index)).toFixed(2)} ${sizes[index]}`
}

export const calculateQualityScore = (task: TranslationJob): number => {
  const { critical_issue_count, warning_issue_count, info_issue_count } = task

  let score = 100
  score -= critical_issue_count * 20
  score -= warning_issue_count * 5
  score -= info_issue_count

  return Math.max(0, score)
}

export const getStatusConfig = (status: JobStatus) => {
  const configs: Record<JobStatus, { color: string; text: string }> = {
    pending: { color: 'default', text: '等待中' },
    in_progress: { color: 'blue', text: '进行中' },
    completed: { color: 'green', text: '已完成' },
    failed: { color: 'red', text: '失败' },
    paused: { color: 'orange', text: '已暂停' },
    cancelled: { color: 'default', text: '已取消' },
  }

  return configs[status] || { color: 'default', text: '未知' }
}

export const formatLanguagePair = (sourceLang: string, targetLang: string): string => {
  const langMap: Record<string, string> = {
    zh: '中文',
    en: '英文',
    ja: '日文',
    ko: '韩文',
    fr: '法文',
    de: '德文',
    es: '西班牙文',
  }

  const source = langMap[sourceLang] || sourceLang
  const target = langMap[targetLang] || targetLang

  return `${source} → ${target}`
}
