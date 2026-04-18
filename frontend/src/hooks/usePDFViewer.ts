import { useCallback, useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).toString()

interface UsePDFViewerOptions {
  url: string
  pageCountHint?: number
  onLoadSuccess?: (numPages: number) => void
  onLoadError?: (error: Error) => void
}

export const usePDFViewer = (options: UsePDFViewerOptions) => {
  const { url, pageCountHint, onLoadSuccess, onLoadError } = options
  const [pdfDocument, setPdfDocument] =
    useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(1)
  const [loading, setLoading] = useState(false)
  const onLoadSuccessRef = useRef(onLoadSuccess)
  const onLoadErrorRef = useRef(onLoadError)

  useEffect(() => {
    onLoadSuccessRef.current = onLoadSuccess
  }, [onLoadSuccess])

  useEffect(() => {
    onLoadErrorRef.current = onLoadError
  }, [onLoadError])

  useEffect(() => {
    setPdfDocument(null)
    setNumPages(0)
    setCurrentPage(1)
  }, [url])

  const resolvedPageCount = numPages || pageCountHint || 0

  const loadDocument = useCallback(async () => {
    if (!url) {
      setPdfDocument(null)
      setNumPages(0)
      setLoading(false)
      return
    }

    setLoading(true)
    try {
      const assetBaseUrl = new URL(
        `${import.meta.env.BASE_URL}pdfjs/`,
        window.location.origin
      ).toString()
      const loadingTask = pdfjsLib.getDocument({
        url,
        cMapUrl: new URL('cmaps/', assetBaseUrl).toString(),
        cMapPacked: true,
        standardFontDataUrl: new URL(
          'standard_fonts/',
          assetBaseUrl
        ).toString(),
        useSystemFonts: true,
      })
      const pdf = await loadingTask.promise
      setPdfDocument(pdf)
      setNumPages(pdf.numPages)
      onLoadSuccessRef.current?.(pdf.numPages)
    } catch (error) {
      console.error('Failed to load PDF:', error)
      onLoadErrorRef.current?.(error as Error)
    } finally {
      setLoading(false)
    }
  }, [url])

  const goToPage = useCallback(
    (pageNum: number) => {
      if (pageNum >= 1 && pageNum <= resolvedPageCount) {
        setCurrentPage(pageNum)
      }
    },
    [resolvedPageCount]
  )

  const previousPage = useCallback(() => {
    goToPage(currentPage - 1)
  }, [currentPage, goToPage])

  const nextPage = useCallback(() => {
    goToPage(currentPage + 1)
  }, [currentPage, goToPage])

  const zoomIn = useCallback(() => {
    setScale(prev => Math.min(prev + 0.1, 2))
  }, [])

  const zoomOut = useCallback(() => {
    setScale(prev => Math.max(prev - 0.1, 0.5))
  }, [])

  const resetZoom = useCallback(() => {
    setScale(1)
  }, [])

  return {
    pdfDocument,
    numPages: resolvedPageCount,
    currentPage,
    scale,
    loading,
    loadDocument,
    goToPage,
    previousPage,
    nextPage,
    zoomIn,
    zoomOut,
    resetZoom,
  }
}
