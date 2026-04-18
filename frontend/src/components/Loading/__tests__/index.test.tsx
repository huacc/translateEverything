/**
 * Loading组件单元测试
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Loading from '@/components/Loading'

describe('Loading组件', () => {
  describe('渲染', () => {
    it('应该渲染加载组件', () => {
      render(<Loading />)
      const spinner = screen.getByRole('img', { hidden: true })
      expect(spinner).toBeInTheDocument()
    })

    it('应该显示默认提示文本', () => {
      render(<Loading />)
      expect(screen.getByText('加载中...')).toBeInTheDocument()
    })

    it('应该显示自定义提示文本', () => {
      render(<Loading tip="请稍候..." />)
      expect(screen.getByText('请稍候...')).toBeInTheDocument()
    })
  })

  describe('尺寸', () => {
    it('应该渲染small尺寸', () => {
      const { container } = render(<Loading size="small" />)
      const spinner = container.querySelector('.ant-spin-sm')
      expect(spinner).toBeInTheDocument()
    })

    it('应该渲染default尺寸', () => {
      const { container } = render(<Loading size="default" />)
      const spinner = container.querySelector('.ant-spin')
      expect(spinner).toBeInTheDocument()
    })

    it('应该渲染large尺寸', () => {
      const { container } = render(<Loading size="large" />)
      const spinner = container.querySelector('.ant-spin-lg')
      expect(spinner).toBeInTheDocument()
    })
  })

  describe('全屏模式', () => {
    it('应该渲染全屏加载', () => {
      const { container } = render(<Loading fullscreen />)
      const loadingContainer = container.querySelector('.loading-fullscreen')
      expect(loadingContainer).toBeInTheDocument()
    })

    it('应该不渲染全屏加载当fullscreen为false', () => {
      const { container } = render(<Loading fullscreen={false} />)
      const loadingContainer = container.querySelector('.loading-fullscreen')
      expect(loadingContainer).not.toBeInTheDocument()
    })
  })
})
