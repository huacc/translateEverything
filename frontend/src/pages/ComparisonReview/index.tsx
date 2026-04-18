import {
  ArrowLeftOutlined,
  DownloadOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import { Button, Empty, Segmented, Slider, Space, Tag, message } from 'antd'
import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Loading from '@/components/Loading'
import PDFViewer from '@/components/PDFViewer'
import PageNavigation from '@/components/PageNavigation'
import { usePDFViewer } from '@/hooks/usePDFViewer'
import { useSyncScroll } from '@/hooks/useSyncScroll'
import { taskService } from '@/services/taskService'
import { useTaskStore } from '@/stores/taskStore'
import './styles.css'

type PreviewMode = 'server' | 'pdfjs'

const ComparisonReview = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentTask, fetchTaskDetail } = useTaskStore()
  const { leftRef, rightRef, scale, zoomIn, zoomOut, resetZoom, setZoom } =
    useSyncScroll()

  const [currentPage, setCurrentPage] = useState(1)
  const [pageCount, setPageCount] = useState(0)
  const [previewMode, setPreviewMode] = useState<PreviewMode>('server')

  useEffect(() => {
    if (id) {
      void fetchTaskDetail(Number(id))
    }
  }, [id, fetchTaskDetail])

  const sourcePdfUrl = currentTask?.source_file_path ?? ''
  const translatedPdfUrl = currentTask?.target_file_path ?? ''
  const previewDpi = scale > 1 ? 216 : 144

  const sourceViewer = usePDFViewer({
    url: sourcePdfUrl,
    onLoadSuccess: pages => {
      setPageCount(prev => Math.max(prev, pages))
    },
  })

  const translatedViewer = usePDFViewer({
    url: translatedPdfUrl,
    onLoadSuccess: pages => {
      setPageCount(prev => Math.max(prev, pages))
    },
  })

  useEffect(() => {
    if (sourcePdfUrl && previewMode === 'pdfjs') {
      void sourceViewer.loadDocument()
    }
  }, [previewMode, sourcePdfUrl, sourceViewer.loadDocument])

  useEffect(() => {
    if (translatedPdfUrl && previewMode === 'pdfjs') {
      void translatedViewer.loadDocument()
    }
  }, [previewMode, translatedPdfUrl, translatedViewer.loadDocument])

  const totalPages = useMemo(() => {
    return (
      pageCount ||
      sourceViewer.numPages ||
      translatedViewer.numPages ||
      currentTask?.page_count ||
      1
    )
  }, [
    currentTask?.page_count,
    pageCount,
    sourceViewer.numPages,
    translatedViewer.numPages,
  ])

  const sourcePreviewUrl = useMemo(() => {
    if (!id) {
      return ''
    }

    return taskService.getPreviewImageUrl(
      Number(id),
      'source',
      currentPage,
      previewDpi
    )
  }, [currentPage, id, previewDpi])

  const translatedPreviewUrl = useMemo(() => {
    if (!id || !currentTask?.artifact_available) {
      return ''
    }

    return taskService.getPreviewImageUrl(
      Number(id),
      'target',
      currentPage,
      previewDpi
    )
  }, [currentPage, currentTask?.artifact_available, id, previewDpi])

  const downloadFile = async (url: string, filename: string) => {
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error('文件下载失败')
    }

    const blob = await response.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = blobUrl
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
    window.URL.revokeObjectURL(blobUrl)
  }

  const handleDownloadOriginal = async () => {
    if (!currentTask?.source_file_path) {
      message.error('原文文件不可用')
      return
    }

    try {
      await downloadFile(
        currentTask.source_file_path,
        currentTask.source_file_name
      )
      message.success('原文下载成功')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '下载失败')
    }
  }

  const handleDownloadTranslated = async () => {
    if (!id) return

    try {
      const blob = await taskService.downloadArtifact(Number(id))
      const blobUrl = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = blobUrl
      anchor.download = `${currentTask?.source_file_name.replace(/\.[^/.]+$/, '')}_translated.pdf`
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      window.URL.revokeObjectURL(blobUrl)
      message.success('译文下载成功')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '下载失败')
    }
  }

  if (!currentTask) {
    return <Loading tip="正在加载审校页面..." fullscreen />
  }

  const sourceLoading =
    Boolean(sourcePdfUrl) && sourceViewer.loading && !sourceViewer.pdfDocument
  const translatedLoading =
    Boolean(translatedPdfUrl) &&
    translatedViewer.loading &&
    !translatedViewer.pdfDocument

  return (
    <div className="comparison-review-page">
      <div className="toolbar">
        <div className="toolbar-left">
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/tasks')}
          >
            返回任务列表
          </Button>
          <div className="file-summary">
            <span className="file-name">{currentTask.source_file_name}</span>
            <div className="file-meta">
              <Tag color="green">
                {currentTask.status === 'completed'
                  ? '已完成'
                  : currentTask.status}
              </Tag>
              <span>
                第 {currentPage} 页 / 共 {totalPages} 页
              </span>
            </div>
          </div>
        </div>

        <div className="toolbar-right">
          <Space wrap>
            <Button icon={<ZoomOutOutlined />} onClick={zoomOut}>
              缩小
            </Button>
            <Slider
              min={50}
              max={200}
              value={scale * 100}
              onChange={value => setZoom(Number(value) / 100)}
              style={{ width: 120 }}
              tooltip={{ formatter: value => `${value}%` }}
            />
            <Button icon={<ZoomInOutlined />} onClick={zoomIn}>
              放大
            </Button>
            <Button icon={<ReloadOutlined />} onClick={resetZoom}>
              重置
            </Button>
            <Segmented<PreviewMode>
              value={previewMode}
              onChange={value => setPreviewMode(value as PreviewMode)}
              options={[
                { label: '后端高保真', value: 'server' },
                { label: 'PDF.js', value: 'pdfjs' },
              ]}
            />
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownloadOriginal}
            >
              下载原文
            </Button>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleDownloadTranslated}
              disabled={!currentTask.artifact_available}
            >
              下载译文
            </Button>
            <Button onClick={() => navigate('/tasks/new')}>重新翻译</Button>
          </Space>
        </div>
      </div>

      <div className="comparison-container">
        <div className="pdf-panel">
          <div className="panel-header">原文 PDF</div>
          <div className="pdf-content" ref={leftRef}>
            {previewMode === 'server' && sourcePreviewUrl ? (
              <PDFViewer
                pdfDocument={null}
                imageUrl={sourcePreviewUrl}
                imageRenderDpi={previewDpi}
                pageNumber={currentPage}
                scale={scale}
              />
            ) : sourceLoading ? (
              <Loading tip="正在加载原文 PDF..." />
            ) : sourceViewer.pdfDocument ? (
              <PDFViewer
                pdfDocument={sourceViewer.pdfDocument}
                pageNumber={currentPage}
                scale={scale}
              />
            ) : (
              <Empty description="原文 PDF 不可用" />
            )}
          </div>
        </div>

        <div className="pdf-panel">
          <div className="panel-header">译文 PDF</div>
          <div className="pdf-content" ref={rightRef}>
            {previewMode === 'server' && translatedPreviewUrl ? (
              <PDFViewer
                pdfDocument={null}
                imageUrl={translatedPreviewUrl}
                imageRenderDpi={previewDpi}
                pageNumber={currentPage}
                scale={scale}
              />
            ) : translatedLoading ? (
              <Loading tip="正在加载译文 PDF..." />
            ) : translatedViewer.pdfDocument ? (
              <PDFViewer
                pdfDocument={translatedViewer.pdfDocument}
                pageNumber={currentPage}
                scale={scale}
              />
            ) : (
              <Empty description="译文 PDF 尚未生成" />
            )}
          </div>
        </div>
      </div>

      <PageNavigation
        currentPage={currentPage}
        totalPages={totalPages}
        onPageChange={setCurrentPage}
      />
    </div>
  )
}

export default ComparisonReview
