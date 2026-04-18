import { useEffect, useRef, useCallback } from 'react'
import { sseService } from '../services/sseService'
import type { SSEEventHandler, SSEErrorHandler } from '../services/sseService'

interface UseSSEOptions {
  onEvent: SSEEventHandler
  onError?: SSEErrorHandler
  autoConnect?: boolean
}

export const useSSE = (taskId: string, options: UseSSEOptions) => {
  const { onEvent, onError, autoConnect = true } = options
  const isConnectedRef = useRef(false)
  const onEventRef = useRef(onEvent)
  const onErrorRef = useRef(onError)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  useEffect(() => {
    onErrorRef.current = onError
  }, [onError])

  // 连接SSE
  const connect = useCallback(() => {
    if (taskId && !isConnectedRef.current) {
      sseService.connect(
        taskId,
        event => onEventRef.current(event),
        error => onErrorRef.current?.(error)
      )
      isConnectedRef.current = true
    }
  }, [taskId])

  // 断开SSE
  const disconnect = useCallback(() => {
    if (isConnectedRef.current) {
      sseService.disconnect()
      isConnectedRef.current = false
    }
  }, [])

  // 自动连接
  useEffect(() => {
    if (autoConnect) {
      connect()
    } else {
      disconnect()
    }

    // 组件卸载时断开连接
    return () => {
      disconnect()
    }
  }, [autoConnect, connect, disconnect])

  return {
    connect,
    disconnect,
    isConnected: sseService.isConnected(),
  }
}
