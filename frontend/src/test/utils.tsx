/**
 * 测试工具函数
 * 提供常用的测试辅助函数和Mock数据
 */

import { render } from '@testing-library/react'
import type { RenderOptions } from '@testing-library/react'
import type { ReactElement } from 'react'
import { BrowserRouter } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'

/**
 * 自定义render函数，包装常用的Provider
 */
export function renderWithProviders(
  ui: ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <BrowserRouter>
        <ConfigProvider locale={zhCN}>{children}</ConfigProvider>
      </BrowserRouter>
    )
  }

  return render(ui, { wrapper: Wrapper, ...options })
}

/**
 * 等待指定时间
 */
export const wait = (ms: number) =>
  new Promise((resolve) => setTimeout(resolve, ms))

/**
 * Mock任务数据
 */
export const mockTask = {
  id: '1',
  name: '测试任务',
  sourceFile: 'test.pdf',
  targetLanguage: 'zh-CN',
  status: 'pending' as const,
  progress: 0,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-01T00:00:00Z',
}

/**
 * Mock翻译块数据
 */
export const mockTranslationBlock = {
  id: 'block-1',
  pageNumber: 1,
  blockIndex: 0,
  sourceText: 'Hello World',
  translatedText: '你好世界',
  status: 'completed' as const,
  bbox: { x: 0, y: 0, width: 100, height: 50 },
}

/**
 * Mock SSE事件数据
 */
export const mockSSEEvent = {
  progress: {
    type: 'progress' as const,
    data: {
      taskId: '1',
      progress: 50,
      currentPage: 1,
      totalPages: 10,
    },
  },
  segmentCompleted: {
    type: 'segment_completed' as const,
    data: {
      taskId: '1',
      blockId: 'block-1',
      translatedText: '你好世界',
    },
  },
  completed: {
    type: 'translation_complete' as const,
    data: {
      taskId: '1',
      message: '翻译完成',
    },
  },
  error: {
    type: 'error' as const,
    data: {
      taskId: '1',
      error: '翻译失败',
    },
  },
}

/**
 * 创建Mock EventSource
 */
export function createMockEventSource() {
  const listeners: Record<string, ((event: MessageEvent) => void)[]> = {}

  return {
    addEventListener: (type: string, listener: (event: MessageEvent) => void) => {
      if (!listeners[type]) {
        listeners[type] = []
      }
      listeners[type].push(listener)
    },
    removeEventListener: (type: string, listener: (event: MessageEvent) => void) => {
      if (listeners[type]) {
        listeners[type] = listeners[type].filter((l) => l !== listener)
      }
    },
    close: () => {
      Object.keys(listeners).forEach((type) => {
        listeners[type] = []
      })
    },
    trigger: (type: string, data: unknown) => {
      if (listeners[type]) {
        const event = new MessageEvent('message', {
          data: JSON.stringify(data),
        })
        listeners[type].forEach((listener) => listener(event))
      }
    },
    readyState: 1,
    url: 'http://localhost:8000/api/sse',
    withCredentials: false,
    CONNECTING: 0,
    OPEN: 1,
    CLOSED: 2,
    onerror: null,
    onmessage: null,
    onopen: null,
  }
}
