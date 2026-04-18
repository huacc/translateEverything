/**
 * EmptyState组件单元测试
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from '@/components/EmptyState'

describe('EmptyState组件', () => {
  describe('渲染', () => {
    it('应该渲染空状态组件', () => {
      render(<EmptyState />)
      expect(screen.getByText('暂无数据')).toBeInTheDocument()
    })

    it('应该显示默认标题', () => {
      render(<EmptyState />)
      expect(screen.getByText('暂无数据')).toBeInTheDocument()
    })

    it('应该显示自定义标题', () => {
      render(<EmptyState title="没有找到任何内容" />)
      expect(screen.getByText('没有找到任何内容')).toBeInTheDocument()
    })

    it('应该显示描述文本', () => {
      render(<EmptyState title="暂无任务" description="请尝试其他搜索条件" />)
      expect(screen.getByText('暂无任务')).toBeInTheDocument()
      expect(screen.getByText('请尝试其他搜索条件')).toBeInTheDocument()
    })
  })

  describe('操作按钮', () => {
    it('应该渲染操作按钮', () => {
      render(
        <EmptyState
          title="暂无数据"
          action={<button>创建新任务</button>}
        />
      )
      expect(screen.getByText('创建新任务')).toBeInTheDocument()
    })
  })

  describe('自定义图标', () => {
    it('应该渲染自定义图标', () => {
      render(
        <EmptyState
          icon={<div data-testid="custom-icon">自定义图标</div>}
          title="暂无数据"
        />
      )
      expect(screen.getByTestId('custom-icon')).toBeInTheDocument()
    })
  })
})
