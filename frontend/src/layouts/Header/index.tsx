import { Layout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import { FileTextOutlined, PlusOutlined } from '@ant-design/icons'
import { ROUTES } from '../../constants/routes'
import { CONFIG } from '../../constants/config'
import './index.css'

const Header = () => {
  const navigate = useNavigate()
  const location = useLocation()

  const menuItems = [
    {
      key: ROUTES.TASK_LIST,
      icon: <FileTextOutlined />,
      label: '任务列表',
    },
    {
      key: ROUTES.TASK_CREATE,
      icon: <PlusOutlined />,
      label: '创建任务',
    },
  ]

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  return (
    <Layout.Header className="header">
      <div className="header-content">
        <div className="logo">{CONFIG.APP_TITLE}</div>
        <Menu
          mode="horizontal"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          className="header-menu"
        />
      </div>
    </Layout.Header>
  )
}

export default Header
