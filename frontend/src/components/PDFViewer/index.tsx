import { useEffect, useMemo, useRef, useState } from 'react'
import type * as pdfjsLib from 'pdfjs-dist'
import './index.css'

interface PDFViewerProps {
  pdfDocument: pdfjsLib.PDFDocumentProxy | null
  pageNumber: number
  scale: number
  imageUrl?: string
  imageRenderDpi?: number
  imageAlt?: string
  onPageRendered?: () => void
}

const PDFViewer = ({
  pdfDocument,
  pageNumber,
  scale,
  imageUrl,
  imageRenderDpi = 144,
  imageAlt,
  onPageRendered,
}: PDFViewerProps) => {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null)
  const [imageSize, setImageSize] = useState<{
    width: number
    height: number
  } | null>(null)

  useEffect(() => {
    setImageSize(null)
  }, [imageUrl, pageNumber])

  const imageStyle = useMemo(() => {
    if (!imageSize) {
      return undefined
    }

    const renderScale = imageRenderDpi / 72

    return {
      width: `${imageSize.width * (scale / renderScale)}px`,
      height: `${imageSize.height * (scale / renderScale)}px`,
    }
  }, [imageRenderDpi, imageSize, scale])

  useEffect(() => {
    if (imageUrl || !pdfDocument) return

    let cancelled = false

    const renderPage = async () => {
      try {
        if (renderTaskRef.current) {
          try {
            renderTaskRef.current.cancel()
            await renderTaskRef.current.promise
          } catch {
            // Ignore cancellation errors from the previous render.
          }
          renderTaskRef.current = null
        }

        if (cancelled) return

        const page = await pdfDocument.getPage(pageNumber)
        if (cancelled) return

        const canvas = canvasRef.current
        if (!canvas) return

        const context = canvas.getContext('2d')
        if (!context) return

        const viewport = page.getViewport({ scale })
        const outputScale = window.devicePixelRatio || 1

        canvas.width = Math.floor(viewport.width * outputScale)
        canvas.height = Math.floor(viewport.height * outputScale)
        canvas.style.width = `${viewport.width}px`
        canvas.style.height = `${viewport.height}px`

        const transform =
          outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined

        renderTaskRef.current = page.render({
          canvas,
          canvasContext: context,
          viewport,
          transform,
        })

        await renderTaskRef.current.promise
        if (cancelled) return

        renderTaskRef.current = null
        onPageRendered?.()
      } catch (error: unknown) {
        if (
          typeof error === 'object' &&
          error &&
          'name' in error &&
          error.name === 'RenderingCancelledException'
        ) {
          return
        }

        if (!cancelled) {
          console.error('Failed to render page:', error)
        }
      }
    }

    void renderPage()

    return () => {
      cancelled = true
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel()
        renderTaskRef.current = null
      }
    }
  }, [pdfDocument, pageNumber, scale, onPageRendered])

  return (
    <div className="pdf-viewer">
      {imageUrl ? (
        <img
          key={imageUrl}
          src={imageUrl}
          alt={imageAlt ?? `PDF page ${pageNumber}`}
          className="pdf-image"
          style={imageStyle}
          onLoad={event => {
            const target = event.currentTarget
            setImageSize({
              width: target.naturalWidth,
              height: target.naturalHeight,
            })
            onPageRendered?.()
          }}
        />
      ) : (
        <canvas ref={canvasRef} className="pdf-canvas" />
      )}
    </div>
  )
}

export default PDFViewer
