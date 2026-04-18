/**
 * usePDFViewer Hook单元测试
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { usePDFViewer } from '@/hooks/usePDFViewer'
import * as pdfjsLib from 'pdfjs-dist'

// Mock pdfjs-dist
vi.mock('pdfjs-dist', async () => {
  const actual = await vi.importActual('pdfjs-dist')
  return {
    ...(actual as object),
    getDocument: vi.fn(),
    GlobalWorkerOptions: {
      workerSrc: '',
    },
  }
})

describe('usePDFViewer Hook', () => {
  const mockPDFDocument = {
    numPages: 10,
    getPage: vi.fn(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(pdfjsLib.getDocument).mockReturnValue({
      promise: Promise.resolve(mockPDFDocument as any),
    } as any)
  })

  describe('初始化', () => {
    it('应该返回初始状态', () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      expect(result.current.pdfDocument).toBeNull()
      expect(result.current.numPages).toBe(0)
      expect(result.current.currentPage).toBe(1)
      expect(result.current.scale).toBe(1.0)
      expect(result.current.loading).toBe(false)
    })
  })

  describe('loadDocument', () => {
    it('应该成功加载PDF文档', async () => {
      const onLoadSuccess = vi.fn()
      const { result } = renderHook(() =>
        usePDFViewer({ url: '/test.pdf', onLoadSuccess })
      )

      await act(async () => {
        await result.current.loadDocument()
      })

      expect(result.current.pdfDocument).toBe(mockPDFDocument)
      expect(result.current.numPages).toBe(10)
      expect(result.current.loading).toBe(false)
      expect(onLoadSuccess).toHaveBeenCalledWith(10)
    })

    it('应该处理加载错误', async () => {
      const error = new Error('加载失败')
      const onLoadError = vi.fn()
      vi.mocked(pdfjsLib.getDocument).mockReturnValue({
        promise: Promise.reject(error),
      } as any)

      const { result } = renderHook(() =>
        usePDFViewer({ url: '/test.pdf', onLoadError })
      )

      await act(async () => {
        await result.current.loadDocument()
      })

      expect(result.current.loading).toBe(false)
      expect(onLoadError).toHaveBeenCalledWith(error)
    })
  })

  describe('页面导航', () => {
    it('应该切换到下一页', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        result.current.nextPage()
      })

      expect(result.current.currentPage).toBe(2)
    })

    it('应该切换到上一页', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        result.current.nextPage()
        result.current.nextPage()
        result.current.previousPage()
      })

      expect(result.current.currentPage).toBe(2)
    })

    it('不应该超过最大页数', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      await waitFor(() => {
        expect(result.current.numPages).toBe(10)
      })

      // 多次调用nextPage直到达到最大页数
      for (let i = 0; i < 15; i++) {
        act(() => {
          result.current.nextPage()
        })
      }

      expect(result.current.currentPage).toBe(10)
    })

    it('不应该小于第1页', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        result.current.goToPage(0)
      })

      expect(result.current.currentPage).toBe(1)
    })
  })

  describe('缩放控制', () => {
    it('应该放大', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        result.current.zoomIn()
      })

      expect(result.current.scale).toBe(1.1)
    })

    it('应该缩小', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        result.current.zoomOut()
      })

      expect(result.current.scale).toBe(0.9)
    })

    it('不应该超过最大缩放比例2.0', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        for (let i = 0; i < 20; i++) {
          result.current.zoomIn()
        }
      })

      expect(result.current.scale).toBe(2.0)
    })

    it('不应该小于最小缩放比例0.5', async () => {
      const { result } = renderHook(() => usePDFViewer({ url: '/test.pdf' }))

      await act(async () => {
        await result.current.loadDocument()
      })

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.zoomOut()
        }
      })

      expect(result.current.scale).toBe(0.5)
    })
  })
})
