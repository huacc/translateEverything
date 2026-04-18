import { Alert, Form, Select, Switch } from 'antd'
import type { Config, CreateTaskData } from '@/types/task'

const { Option } = Select

interface ConfigStepProps {
  formData: Partial<CreateTaskData>
  onChange: (data: Partial<CreateTaskData>) => void
  config: Config
  errors: Record<string, string>
}

const ConfigStep = ({ formData, onChange, config, errors }: ConfigStepProps) => {
  return (
    <div className="config-step">
      <Alert
        title="翻译参数配置"
        description="请选择源语言、目标语言和其他翻译选项。"
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
      />

      <Form layout="vertical" size="large">
        <Form.Item
          label="源语言"
          required
          validateStatus={errors.language ? 'error' : ''}
          help={errors.language}
        >
          <Select
            placeholder="请选择源语言"
            value={formData.source_lang || undefined}
            onChange={value => onChange({ source_lang: value })}
          >
            {config.languages.map(lang => (
              <Option key={lang.code} value={lang.code}>
                {lang.name} ({lang.native_name})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          label="目标语言"
          required
          validateStatus={errors.language ? 'error' : ''}
        >
          <Select
            placeholder="请选择目标语言"
            value={formData.target_lang || undefined}
            onChange={value => onChange({ target_lang: value })}
          >
            {config.languages.map(lang => (
              <Option
                key={lang.code}
                value={lang.code}
                disabled={lang.code === formData.source_lang}
              >
                {lang.name} ({lang.native_name})
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="术语库（可选）">
          <Select
            placeholder="请选择术语库"
            allowClear
            value={formData.glossary_id || undefined}
            onChange={value => onChange({ glossary_id: value ?? null })}
          >
            {config.glossaries.map(glossary => (
              <Option key={glossary.id} value={glossary.id}>
                {glossary.name} - {glossary.description} ({glossary.term_count} 个术语)
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="翻译风格">
          <Select
            placeholder="请选择翻译风格"
            value={formData.translation_style || 'professional'}
            onChange={value => onChange({ translation_style: value })}
          >
            {config.translation_styles.map(style => (
              <Option key={style.id} value={style.id}>
                {style.name} - {style.description}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item label="启用质量检查">
          <Switch
            checked={formData.enable_quality_check ?? true}
            onChange={checked => onChange({ enable_quality_check: checked })}
          />
          <span style={{ marginLeft: 8, color: '#8c8c8c' }}>
            开启后会自动检查翻译质量并生成摘要信息
          </span>
        </Form.Item>
      </Form>
    </div>
  )
}

export default ConfigStep
