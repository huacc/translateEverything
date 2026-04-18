import {
  ArrowLeftOutlined,
  CaretRightOutlined,
  CheckCircleOutlined,
  CloseOutlined,
  LeftOutlined,
  PauseOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Empty,
  Progress,
  Segmented,
  Space,
  Tag,
  message,
} from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import PDFViewer from '@/components/PDFViewer'
import TranslationOverlay from '@/components/TranslationOverlay'
import Loading from '@/components/Loading'
import { usePDFViewer } from '@/hooks/usePDFViewer'
import { useSSE } from '@/hooks/useSSE'
import { taskService } from '@/services/taskService'
import type { TranslationJob } from '@/types/task'
import type {
  ExecutionLogEventData,
  ProgressEventData,
  TranslationChunkEventData,
} from '@/types/sse'
import './index.css'

const stageLabelMap: Record<string, string> = {
  queued: '等待执行',
  analyzing: '文档分析',
  translating: '翻译执行',
  rendering: '生成译后文件',
  completed: '已完成',
  failed: '失败',
}

type PreviewMode = 'server' | 'pdfjs'

const TranslationExecution = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [task, setTask] = useState<TranslationJob | null>(null)
  const [taskLoading, setTaskLoading] = useState(true)
  const [progress, setProgress] = useState(0)
  const [currentTranslatingPage, setCurrentTranslatingPage] = useState(1)
  const [previewMode, setPreviewMode] = useState<PreviewMode>('server')
  const [translationBlocks, setTranslationBlocks] = useState<
    Array<{
      id: string
      pageNum: number
      content?: string
      status: 'pending' | 'translating' | 'completed'
    }>
  >([])
  const [executionLogs, setExecutionLogs] = useState<ExecutionLogEventData[]>(
    []
  )

  const taskId = id ? Number(id) : null

  const loadTask = useCallback(async () => {
    if (!taskId) {
      setTaskLoading(false)
      return
    }

    setTaskLoading(true)
    try {
      const { job } = await taskService.getTaskDetail(taskId)
      setTask(job)
      setProgress(job.progress_percent)
      setCurrentTranslatingPage(
        Math.max(1, Math.ceil(job.completed_segments / 6) || 1)
      )
    } catch (error) {
      message.error(error instanceof Error ? error.message : '加载任务失败')
    } finally {
      setTaskLoading(false)
    }
  }, [taskId])

  useEffect(() => {
    void loadTask()
  }, [loadTask])

  const pdfUrl = task?.source_file_path ?? ''
  const shouldConnectSSE = Boolean(
    taskId &&
    task &&
    task.status !== 'completed' &&
    task.status !== 'cancelled' &&
    task.status !== 'failed' &&
    task.status !== 'paused'
  )

  const {
    pdfDocument,
    numPages,
    currentPage,
    scale,
    loading: pdfLoading,
    loadDocument,
    previousPage,
    nextPage,
    zoomIn,
    zoomOut,
  } = usePDFViewer({
    url: pdfUrl,
    pageCountHint: task?.page_count,
    onLoadError: error => {
      message.error(`PDF 加载失败：${error.message}`)
    },
  })

  useEffect(() => {
    if (pdfUrl && previewMode === 'pdfjs') {
      void loadDocument()
    }
  }, [loadDocument, pdfUrl, previewMode])

  const previewDpi = scale > 1 ? 216 : 144
  const previewImageUrl = useMemo(() => {
    if (!taskId) {
      return ''
    }

    return taskService.getPreviewImageUrl(
      taskId,
      'source',
      currentPage,
      previewDpi
    )
  }, [currentPage, previewDpi, taskId])

  const { disconnect } = useSSE(taskId ? String(taskId) : '', {
    autoConnect: shouldConnectSSE,
    onEvent: async event => {
      switch (event.type) {
        case 'progress': {
          const data = event.data as ProgressEventData
          setProgress(data.percentage)
          setCurrentTranslatingPage(data.currentPage)
          break
        }
        case 'translation_chunk': {
          const data = event.data as TranslationChunkEventData
          setTranslationBlocks(prev => {
            const existing = prev.find(block => block.id === data.blockId)

            if (!existing) {
              return [
                ...prev,
                {
                  id: data.blockId,
                  pageNum: data.pageNum,
                  content: data.content,
                  status: data.isComplete ? 'completed' : 'translating',
                },
              ]
            }

            return prev.map(block =>
              block.id === data.blockId
                ? {
                    ...block,
                    content: data.content,
                    status: data.isComplete ? 'completed' : 'translating',
                  }
                : block
            )
          })
          break
        }
        case 'execution_log': {
          const data = event.data as ExecutionLogEventData
          setExecutionLogs(prev => [...prev, data].slice(-12))
          break
        }
        case 'task_completed': {
          disconnect()
          message.success('翻译完成，可以进入对比审校')
          await loadTask()
          break
        }
        case 'error': {
          message.error('翻译流程中断')
          await loadTask()
          break
        }
        default:
          break
      }
    },
    onError: error => {
      console.error('SSE error:', error)
    },
  })

  const handlePauseResume = async () => {
    if (!task) return

    try {
      if (task.status === 'paused') {
        const { job } = await taskService.resumeTask(task.id)
        setTask(job)
        message.success('任务已继续')
      } else {
        const { job } = await taskService.pauseTask(task.id)
        setTask(job)
        disconnect()
        message.success('任务已暂停')
      }
    } catch (error) {
      message.error(error instanceof Error ? error.message : '操作失败')
    }
  }

  const handleCancel = async () => {
    if (!task) return

    try {
      const { job } = await taskService.cancelTask(task.id)
      setTask(job)
      disconnect()
      message.success('任务已取消')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '终止失败')
    }
  }

  if (
    taskLoading ||
    (previewMode === 'pdfjs' && pdfUrl && pdfLoading && !pdfDocument)
  ) {
    return <Loading tip="正在加载任务与 PDF..." fullscreen />
  }

  if (!task) {
    return (
      <div className="translation-execution translation-empty-state">
        <Empty description="没有找到任务信息" />
      </div>
    )
  }

  const currentStageLabel = stageLabelMap[task.stage] ?? task.stage
  const canReview = task.status === 'completed' && task.artifact_available
  const isPaused = task.status === 'paused'
  const canShowPreview =
    previewMode === 'server' ? Boolean(previewImageUrl) : Boolean(pdfDocument)

  return (
    <div className="translation-execution">
      <div className="translation-header">
        <div className="translation-header-main">
          <Button
            type="text"
            icon={<ArrowLeftOutlined />}
            onClick={() => navigate('/tasks')}
          >
            返回任务列表
          </Button>
          <div className="translation-info">
            <h2>{task.source_file_name}</h2>
            <div className="translation-status-row">
              <Tag color={canReview ? 'green' : 'blue'}>
                {currentStageLabel}
              </Tag>
              <span className="translation-page-info">
                {canReview
                  ? `当前查看第 ${currentPage} 页 / 共 ${numPages || task.page_count || 1} 页`
                  : `正在处理第 ${currentTranslatingPage} 页 / 共 ${numPages || task.page_count || 1} 页`}
              </span>
            </div>
          </div>
        </div>

        <Progress
          percent={Math.round(progress)}
          status={task.status === 'failed' ? 'exception' : 'active'}
          strokeColor={{
            '0%': '#0f766e',
            '100%': '#16a34a',
          }}
          className="translation-progress"
        />

        <Space>
          <Segmented<PreviewMode>
            value={previewMode}
            onChange={value => setPreviewMode(value as PreviewMode)}
            options={[
              { label: '后端高保真', value: 'server' },
              { label: 'PDF.js', value: 'pdfjs' },
            ]}
          />
          {canReview && (
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              onClick={() => navigate(`/tasks/${task.id}/review`)}
            >
              进入审校
            </Button>
          )}

          {task.status !== 'completed' && task.status !== 'cancelled' && (
            <Button
              icon={isPaused ? <CaretRightOutlined /> : <PauseOutlined />}
              onClick={handlePauseResume}
            >
              {isPaused ? '继续' : '暂停'}
            </Button>
          )}

          {task.status !== 'completed' && task.status !== 'cancelled' && (
            <Button icon={<CloseOutlined />} danger onClick={handleCancel}>
              终止
            </Button>
          )}
        </Space>
      </div>

      <div className="translation-content">
        <div className="pdf-container">
          {!pdfUrl || !canShowPreview ? (
            <div className="translation-empty-state">
              <Empty description="当前任务没有可预览的 PDF 文件" />
            </div>
          ) : (
            <>
              <div className="pdf-viewer-wrapper">
                <PDFViewer
                  pdfDocument={previewMode === 'pdfjs' ? pdfDocument : null}
                  imageUrl={
                    previewMode === 'server' ? previewImageUrl : undefined
                  }
                  imageRenderDpi={previewDpi}
                  pageNumber={currentPage}
                  scale={scale}
                />
                <TranslationOverlay
                  blocks={translationBlocks}
                  currentPage={currentPage}
                />
              </div>

              <div className="pdf-controls">
                <Space>
                  <Button
                    icon={<LeftOutlined />}
                    onClick={previousPage}
                    disabled={currentPage <= 1}
                  >
                    上一页
                  </Button>
                  <span className="page-indicator">
                    {currentPage} / {numPages}
                  </span>
                  <Button
                    icon={<RightOutlined />}
                    onClick={nextPage}
                    disabled={currentPage >= numPages}
                  >
                    下一页
                  </Button>
                </Space>
                <Space>
                  <Button icon={<ZoomOutOutlined />} onClick={zoomOut}>
                    缩小
                  </Button>
                  <span className="zoom-indicator">
                    {Math.round(scale * 100)}%
                  </span>
                  <Button icon={<ZoomInOutlined />} onClick={zoomIn}>
                    放大
                  </Button>
                </Space>
              </div>
            </>
          )}
        </div>

        <aside className="execution-sidebar">
          <div className="execution-sidebar-card">
            <h3>AI 执行过程</h3>
            <Alert
              type={canReview ? 'success' : 'info'}
              showIcon
              title={
                canReview
                  ? '翻译已完成，可以进入对比审校'
                  : '系统正在按阶段执行任务'
              }
              description={
                canReview
                  ? '当前任务已经生成译后文件，建议到审校页确认原文与译文是否对应。'
                  : '当前展示的是任务调度、文档分析、翻译和产物生成的实时状态。'
              }
            />
          </div>

          <div className="execution-sidebar-card execution-log-card">
            <div className="execution-log-header">
              <h3>执行日志</h3>
              <Tag>{executionLogs.length} 条</Tag>
            </div>
            {executionLogs.length === 0 ? (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="等待执行日志"
              />
            ) : (
              <div className="execution-log-list">
                {executionLogs
                  .slice()
                  .reverse()
                  .map((log, index) => (
                    <div
                      className="execution-log-item"
                      key={`${log.step}-${index}`}
                    >
                      <div className="execution-log-title">
                        <span>{stageLabelMap[log.stage] ?? log.stage}</span>
                        <Tag
                          color={
                            log.status === 'completed'
                              ? 'green'
                              : log.status === 'failed'
                                ? 'red'
                                : 'blue'
                          }
                        >
                          {log.status}
                        </Tag>
                      </div>
                      <div className="execution-log-message">{log.message}</div>
                      <div className="execution-log-time">
                        {new Date(log.timestamp ?? Date.now()).toLocaleString()}
                      </div>
                    </div>
                  ))}
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

export default TranslationExecution
