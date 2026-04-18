import { Empty } from 'antd'
import type { ReactNode } from 'react'
import './index.css'

interface EmptyStateProps {
  icon?: ReactNode
  title?: string
  description?: string
  action?: ReactNode
}

const EmptyState = ({
  icon,
  title = '暂无数据',
  description,
  action,
}: EmptyStateProps) => {
  return (
    <div className="empty-state">
      <Empty
        image={icon || Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          <div className="empty-state-content">
            <div className="empty-state-title">{title}</div>
            {description && (
              <div className="empty-state-description">{description}</div>
            )}
          </div>
        }
      >
        {action}
      </Empty>
    </div>
  )
}

export default EmptyState
