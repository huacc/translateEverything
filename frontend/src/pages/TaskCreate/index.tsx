import { useEffect, useState } from 'react'
import { Alert, Button, Card, Result, Spin, Steps, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import type { Config, CreateTaskData } from '@/types/task'
import { taskService } from '@/services/taskService'
import { useTaskStore } from '@/stores/taskStore'
import { validateTaskForm } from '@/utils/validation'
import ConfigStep from './ConfigStep'
import ConfirmStep from './ConfirmStep'
import UploadStep from './UploadStep'
import './styles.css'

const TaskCreate = () => {
  const navigate = useNavigate()
  const { createTask } = useTaskStore()

  const [current, setCurrent] = useState(0)
  const [loading, setLoading] = useState(false)
  const [configLoading, setConfigLoading] = useState(true)
  const [configError, setConfigError] = useState<string | null>(null)
  const [config, setConfig] = useState<Config | null>(null)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [formData, setFormData] = useState<Partial<CreateTaskData>>({
    file: undefined,
    source_lang: '',
    target_lang: '',
    glossary_id: null,
    translation_style: 'professional',
    enable_quality_check: true,
  })

  const loadConfig = async () => {
    setConfigLoading(true)
    setConfigError(null)

    try {
      const nextConfig = await taskService.getConfig()
      setConfig(nextConfig)
    } catch (error) {
      const nextError =
        error instanceof Error ? error.message : '加载参数配置失败，请稍后重试'
      setConfig(null)
      setConfigError(nextError)
      message.error(nextError)
    } finally {
      setConfigLoading(false)
    }
  }

  useEffect(() => {
    void loadConfig()
  }, [])

  const steps = [
    {
      title: '上传文档',
      description: '选择需要翻译的 PDF 文件',
    },
    {
      title: '配置参数',
      description: '设置语言方向和翻译选项',
    },
    {
      title: '确认信息',
      description: '确认后创建翻译任务',
    },
  ]

  const handleNext = () => {
    if (current === 0) {
      if (!formData.file) {
        message.error('请先上传文件')
        return
      }
    }

    if (current === 1) {
      if (configLoading) {
        message.info('参数配置仍在加载，请稍后')
        return
      }

      if (!config) {
        message.error(configError || '参数配置加载失败，请重试')
        return
      }

      const validationErrors = validateTaskForm(formData)
      if (Object.keys(validationErrors).length > 0) {
        setErrors(validationErrors)
        message.error('请检查表单填写')
        return
      }
    }

    setErrors({})
    setCurrent(prev => prev + 1)
  }

  const handlePrev = () => {
    setCurrent(prev => prev - 1)
  }

  const handleSubmit = async () => {
    setLoading(true)

    try {
      const job = await createTask(formData as CreateTaskData)
      message.success('任务创建成功')
      navigate(`/tasks/${job.id}/translate`)
    } catch (error) {
      message.error(error instanceof Error ? error.message : '任务创建失败')
    } finally {
      setLoading(false)
    }
  }

  const updateFormData = (data: Partial<CreateTaskData>) => {
    setFormData(prev => ({ ...prev, ...data }))
  }

  const renderConfigState = () => {
    if (configLoading) {
      return (
        <div className="config-state">
          <Spin size="large" />
          <p>正在加载参数配置...</p>
        </div>
      )
    }

    if (!config) {
      return (
        <Result
          status="warning"
          title="参数配置加载失败"
          subTitle={configError || '暂时无法读取参数配置，请检查 mock 后端后重试。'}
          extra={
            <Button type="primary" onClick={() => void loadConfig()}>
              重新加载
            </Button>
          }
        />
      )
    }

    return null
  }

  return (
    <div className="task-create-page">
      <Card className="create-card">
        <h1>创建翻译任务</h1>
        <Steps current={current} items={steps} className="steps" />

        <div className="step-content">
          {current === 0 && (
            <UploadStep
              formData={formData}
              onChange={updateFormData}
              errors={errors}
            />
          )}
          {current > 0 && (configLoading || !config) && renderConfigState()}
          {current === 1 && config && (
            <ConfigStep
              formData={formData}
              onChange={updateFormData}
              config={config}
              errors={errors}
            />
          )}
          {current === 2 && config && <ConfirmStep formData={formData} config={config} />}
        </div>

        {configError && current > 0 && (
          <Alert
            type="warning"
            showIcon
            title="配置来自本地回退或重试结果"
            description="如果后端 mock 没有启动，任务列表和 PDF 文件仍然无法正常读取。"
            style={{ marginBottom: 16 }}
          />
        )}

        <div className="step-actions">
          {current > 0 && (
            <Button onClick={handlePrev} disabled={loading}>
              上一步
            </Button>
          )}

          {current < steps.length - 1 && (
            <Button type="primary" onClick={handleNext}>
              下一步
            </Button>
          )}

          {current === steps.length - 1 && (
            <Button type="primary" onClick={handleSubmit} loading={loading}>
              开始翻译
            </Button>
          )}

          <Button onClick={() => navigate('/tasks')} disabled={loading}>
            取消
          </Button>
        </div>
      </Card>
    </div>
  )
}

export default TaskCreate
