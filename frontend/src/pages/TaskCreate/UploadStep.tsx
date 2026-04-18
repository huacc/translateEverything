import { InboxOutlined } from '@ant-design/icons'
import { Alert, Upload } from 'antd'
import type { UploadProps } from 'antd'
import type { CreateTaskData } from '@/types/task'
import { formatFileSize } from '@/utils/format'
import { validateFile } from '@/utils/validation'

const { Dragger } = Upload

interface UploadStepProps {
  formData: Partial<CreateTaskData>
  onChange: (data: Partial<CreateTaskData>) => void
  errors: Record<string, string>
}

const UploadStep = ({ formData, onChange, errors }: UploadStepProps) => {
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    maxCount: 1,
    accept: '.pdf',
    beforeUpload: file => {
      const error = validateFile(file)
      if (error) {
        return Upload.LIST_IGNORE
      }

      onChange({ file })
      return false
    },
    onRemove: () => {
      onChange({ file: undefined })
    },
    fileList: formData.file ? [formData.file as never] : [],
  }

  return (
    <div className="upload-step">
      <Alert
        title="支持的文件格式"
        description="当前 MVP 仅支持 PDF 格式，单个文件不超过 100MB。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到这里上传</p>
        <p className="ant-upload-hint">
          仅支持 PDF 格式，单个文件不超过 100MB
        </p>
      </Dragger>

      {errors.file && (
        <Alert
          title={errors.file}
          type="error"
          showIcon
          style={{ marginTop: 16 }}
        />
      )}

      {formData.file && (
        <div className="file-info" style={{ marginTop: 24 }}>
          <h3>文件信息</h3>
          <div className="info-item">
            <span className="label">文件名：</span>
            <span className="value">{formData.file.name}</span>
          </div>
          <div className="info-item">
            <span className="label">文件大小：</span>
            <span className="value">{formatFileSize(formData.file.size)}</span>
          </div>
          <div className="info-item">
            <span className="label">文件类型：</span>
            <span className="value">PDF</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default UploadStep
