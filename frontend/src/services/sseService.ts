import { CONFIG } from '../constants/config'
import type { SSEEvent } from '../types/sse'

export type SSEEventHandler = (event: SSEEvent) => void
export type SSEErrorHandler = (error: Error) => void

export class SSEService {
  private eventSource: EventSource | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000

  // 连接SSE
  connect(
    taskId: string,
    onEvent: SSEEventHandler,
    onError?: SSEErrorHandler
  ): void {
    const url = `${CONFIG.API_BASE_URL}/v1/translations/${taskId}/stream`

    try {
      this.eventSource = new EventSource(url)

      // 监听消息事件
      this.eventSource.onmessage = event => {
        try {
          const data = JSON.parse(event.data) as SSEEvent
          onEvent(data)
        } catch (error) {
          console.error('Failed to parse SSE event:', error)
        }
      }

      // 监听错误事件
      this.eventSource.onerror = () => {
        console.error('SSE connection error')
        this.handleError(taskId, onEvent, onError)
      }

      // 重置重连次数
      this.reconnectAttempts = 0
    } catch (error) {
      console.error('Failed to create EventSource:', error)
      if (onError) {
        onError(error as Error)
      }
    }
  }

  // 处理错误和重连
  private handleError(
    taskId: string,
    onEvent: SSEEventHandler,
    onError?: SSEErrorHandler
  ): void {
    this.disconnect()

    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++
      console.log(
        `Reconnecting... Attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`
      )

      setTimeout(() => {
        this.connect(taskId, onEvent, onError)
      }, this.reconnectDelay)
    } else {
      console.error('Max reconnect attempts reached')
      if (onError) {
        onError(new Error('SSE connection failed after multiple attempts'))
      }
    }
  }

  // 断开连接
  disconnect(): void {
    if (this.eventSource) {
      this.eventSource.close()
      this.eventSource = null
    }
  }

  // 获取连接状态
  getReadyState(): number {
    return this.eventSource?.readyState ?? EventSource.CLOSED
  }

  // 是否已连接
  isConnected(): boolean {
    return this.getReadyState() === EventSource.OPEN
  }
}

// 导出单例
export const sseService = new SSEService()
