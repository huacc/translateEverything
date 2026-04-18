// SSE事件类型
export type SSEEventType = 'progress' | 'translation_chunk' | 'execution_log' | 'task_completed' | 'error';

// 进度事件数据
export interface ProgressEventData {
  currentPage: number
  totalPages: number
  percentage: number
}

// 翻译内容块事件数据
export interface TranslationChunkEventData {
  pageNum: number
  blockId: string
  content: string
  isComplete: boolean
}

// 执行日志事件数据
export interface ExecutionLogEventData {
  stage: string
  step: string
  status: 'pending' | 'in_progress' | 'completed' | 'failed'
  message: string
  timestamp?: string
}

// 任务完成事件数据
export interface TaskCompletedEventData {
  taskId: string
  status: 'completed' | 'failed'
  message?: string
}

// SSE事件
export interface SSEEvent {
  type: SSEEventType
  data:
    | ProgressEventData
    | TranslationChunkEventData
    | ExecutionLogEventData
    | TaskCompletedEventData
}
