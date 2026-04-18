import { Layout } from 'antd'
import { Outlet } from 'react-router-dom'
import Header from '../Header'
import Footer from '../Footer'
import './index.css'

const MainLayout = () => {
  return (
    <Layout className="main-layout">
      <Header />
      <Layout.Content className="main-content">
        <Outlet />
      </Layout.Content>
      <Footer />
    </Layout>
  )
}

export default MainLayout
