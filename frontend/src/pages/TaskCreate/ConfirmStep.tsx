import { Alert, Descriptions, Tag } from 'antd'
import type { Config, CreateTaskData } from '@/types/task'
import { formatFileSize, formatLanguagePair } from '@/utils/format'

interface ConfirmStepProps {
  formData: Partial<CreateTaskData>
  config: Config
}

const ConfirmStep = ({ formData, config }: ConfirmStepProps) => {
  const getLanguageName = (code: string) => {
    const lang = config.languages.find(item => item.code === code)
    return lang ? `${lang.name} (${lang.native_name})` : code
  }

  const getGlossaryName = (id: number | null | undefined) => {
    if (!id) return '未选择'
    const glossary = config.glossaries.find(item => item.id === id)
    return glossary ? glossary.name : '未知'
  }

  const getStyleName = (id: string | undefined) => {
    if (!id) return '专业技术'
    const style = config.translation_styles.find(item => item.id === id)
    return style ? style.name : id
  }

  return (
    <div className="confirm-step">
      <Alert
        title="请确认任务信息"
        description="确认无误后点击“开始翻译”创建任务。"
        type="success"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Descriptions bordered column={1} size="middle">
        <Descriptions.Item label="文档名称">
          {formData.file?.name || '-'}
        </Descriptions.Item>

        <Descriptions.Item label="文件大小">
          {formData.file ? formatFileSize(formData.file.size) : '-'}
        </Descriptions.Item>

        <Descriptions.Item label="文件格式">
          <Tag color="blue">PDF</Tag>
        </Descriptions.Item>

        <Descriptions.Item label="源语言">
          {formData.source_lang ? getLanguageName(formData.source_lang) : '-'}
        </Descriptions.Item>

        <Descriptions.Item label="目标语言">
          {formData.target_lang ? getLanguageName(formData.target_lang) : '-'}
        </Descriptions.Item>

        <Descriptions.Item label="语言对">
          {formData.source_lang && formData.target_lang ? (
            <Tag color="geekblue">
              {formatLanguagePair(formData.source_lang, formData.target_lang)}
            </Tag>
          ) : (
            '-'
          )}
        </Descriptions.Item>

        <Descriptions.Item label="术语库">
          {getGlossaryName(formData.glossary_id)}
        </Descriptions.Item>

        <Descriptions.Item label="翻译风格">
          {getStyleName(formData.translation_style)}
        </Descriptions.Item>

        <Descriptions.Item label="质量检查">
          {formData.enable_quality_check ? (
            <Tag color="green">已启用</Tag>
          ) : (
            <Tag>未启用</Tag>
          )}
        </Descriptions.Item>
      </Descriptions>

      <Alert
        title="预计翻译时间"
        description="根据文档大小和复杂度，预计需要 10 到 30 分钟完成翻译。"
        type="info"
        showIcon
        style={{ marginTop: 24 }}
      />
    </div>
  )
}

export default ConfirmStep
