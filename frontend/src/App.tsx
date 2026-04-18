import { RouterProvider } from 'react-router-dom'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { router } from './router'
import { antdTheme } from './styles/antd-theme'
import ErrorBoundary from './components/ErrorBoundary'
import './styles/global.css'

function App() {
  return (
    <ErrorBoundary>
      <ConfigProvider locale={zhCN} theme={antdTheme}>
        <RouterProvider router={router} />
      </ConfigProvider>
    </ErrorBoundary>
  )
}

export default App
