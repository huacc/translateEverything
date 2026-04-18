import { LoadingOutlined } from '@ant-design/icons'
import { Spin } from 'antd'
import './index.css'

interface LoadingProps {
  tip?: string
  size?: 'small' | 'default' | 'middle' | 'large'
  fullscreen?: boolean
}

const Loading = ({
  tip = '加载中...',
  size = 'default',
  fullscreen = false,
}: LoadingProps) => {
  const resolvedSize = size === 'default' ? 'middle' : size
  const antIcon = (
    <LoadingOutlined
      style={{
        fontSize: resolvedSize === 'large' ? 48 : resolvedSize === 'small' ? 16 : 24,
      }}
      spin
    />
  )

  if (fullscreen) {
    return (
      <div className="loading-fullscreen">
        <Spin indicator={antIcon} description={tip} size={resolvedSize} />
      </div>
    )
  }

  return <Spin indicator={antIcon} description={tip} size={resolvedSize} />
}

export default Loading
