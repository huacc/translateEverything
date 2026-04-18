import {
  DeleteOutlined,
  DownloadOutlined,
  EyeOutlined,
  FileTextOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  StopOutlined,
} from '@ant-design/icons'
import { Button, Card, Modal, Progress, Space, Tag, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { taskService } from '@/services/taskService'
import { useTaskStore } from '@/stores/taskStore'
import type { TranslationJob } from '@/types/task'
import {
  calculateQualityScore,
  formatDate,
  formatLanguagePair,
  getStatusConfig,
} from '@/utils/format'

interface TaskCardProps {
  task: TranslationJob
}

const TaskCard = ({ task }: TaskCardProps) => {
  const navigate = useNavigate()
  const { deleteTask, pauseTask, resumeTask, cancelTask } = useTaskStore()
  const statusConfig = getStatusConfig(task.status)

  const handleView = () => {
    if (task.status === 'completed') {
      navigate(`/tasks/${task.id}/review`)
      return
    }

    navigate(`/tasks/${task.id}/translate`)
  }

  const handleDownload = async () => {
    try {
      const blob = await taskService.downloadArtifact(task.id)
      const url = window.URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = task.source_file_name.replace(/\.[^/.]+$/, '_translated.pdf')
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
      window.URL.revokeObjectURL(url)
      message.success('下载成功')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '下载失败')
    }
  }

  const handlePause = async () => {
    try {
      await pauseTask(task.id)
      message.success('任务已暂停')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '暂停失败')
    }
  }

  const handleResume = async () => {
    try {
      await resumeTask(task.id)
      message.success('任务已继续')
    } catch (error) {
      message.error(error instanceof Error ? error.message : '继续失败')
    }
  }

  const handleCancel = () => {
    Modal.confirm({
      title: '确认取消任务',
      content: '取消后任务将停止执行，确认继续吗？',
      okText: '确认',
      cancelText: '返回',
      onOk: async () => {
        try {
          await cancelTask(task.id)
          message.success('任务已取消')
        } catch (error) {
          message.error(error instanceof Error ? error.message : '取消失败')
        }
      },
    })
  }

  const handleDelete = () => {
    Modal.confirm({
      title: '确认删除任务',
      content: '删除后无法恢复，确认删除吗？',
      okText: '删除',
      cancelText: '返回',
      okType: 'danger',
      onOk: async () => {
        try {
          await deleteTask(task.id)
          message.success('任务已删除')
        } catch (error) {
          message.error(error instanceof Error ? error.message : '删除失败')
        }
      },
    })
  }

  return (
    <Card className="task-card" hoverable>
      <div className="task-header">
        <FileTextOutlined className="file-icon" />
        <span className="file-name" title={task.source_file_name}>
          {task.source_file_name}
        </span>
        <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
      </div>

      <div className="task-info">
        <div className="info-item">
          <span className="label">语言对：</span>
          <span className="value">
            {formatLanguagePair(task.source_lang, task.target_lang)}
          </span>
        </div>
        <div className="info-item">
          <span className="label">创建时间：</span>
          <span className="value">{formatDate(task.created_at)}</span>
        </div>
        {task.completed_at && (
          <div className="info-item">
            <span className="label">完成时间：</span>
            <span className="value">{formatDate(task.completed_at)}</span>
          </div>
        )}
      </div>

      {task.status === 'in_progress' && (
        <div className="task-progress">
          <Progress percent={Math.round(task.progress_percent)} status="active" />
          <div className="progress-text">
            {task.completed_segments}/{task.total_segments} 分段
          </div>
        </div>
      )}

      {task.status === 'completed' && (
        <div className="task-quality">
          <span className="label">质量评分：</span>
          <span className="score">{calculateQualityScore(task)} 分</span>
          {task.quality_issue_counts.critical > 0 && (
            <Tag color="red">{task.quality_issue_counts.critical} 个严重问题</Tag>
          )}
          {task.quality_issue_counts.warning > 0 && (
            <Tag color="orange">{task.quality_issue_counts.warning} 个警告</Tag>
          )}
        </div>
      )}

      {task.status === 'failed' && task.error_message && (
        <div className="task-error">
          <Tag color="red">错误：{task.error_message}</Tag>
        </div>
      )}

      <div className="task-actions">
        <Space wrap>
          <Button icon={<EyeOutlined />} onClick={handleView}>
            查看
          </Button>

          {task.status === 'in_progress' && (
            <Button icon={<PauseCircleOutlined />} onClick={handlePause}>
              暂停
            </Button>
          )}

          {task.status === 'paused' && (
            <Button icon={<PlayCircleOutlined />} onClick={handleResume}>
              继续
            </Button>
          )}

          {(task.status === 'in_progress' || task.status === 'paused') && (
            <Button icon={<StopOutlined />} onClick={handleCancel}>
              取消
            </Button>
          )}

          {task.artifact_available && (
            <Button
              icon={<DownloadOutlined />}
              onClick={handleDownload}
              disabled={task.export_blocked}
            >
              下载
            </Button>
          )}

          <Button
            danger
            icon={<DeleteOutlined />}
            onClick={handleDelete}
            disabled={task.status === 'in_progress'}
          >
            删除
          </Button>
        </Space>
      </div>
    </Card>
  )
}

export default TaskCard
