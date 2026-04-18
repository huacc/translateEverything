import { Layout } from 'antd'
import './index.css'

const Footer = () => {
  return (
    <Layout.Footer className="footer">
      <div className="footer-content">
        <div className="footer-info">
          <span>AI翻译系统 v1.0.0</span>
          <span className="footer-divider">|</span>
          <a href="#" className="footer-link">
            帮助文档
          </a>
          <span className="footer-divider">|</span>
          <a href="#" className="footer-link">
            反馈建议
          </a>
        </div>
        <div className="footer-copyright">
          © 2026 AI翻译系统. All rights reserved.
        </div>
      </div>
    </Layout.Footer>
  )
}

export default Footer
