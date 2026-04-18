/**
 * format工具函数单元测试
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  formatDate,
  formatFileSize,
  calculateQualityScore,
  getStatusConfig,
  formatLanguagePair,
} from '@/utils/format'
import type { TranslationJob } from '@/types/task'

describe('format工具函数', () => {
  describe('formatDate', () => {
    beforeEach(() => {
      // 固定当前时间为 2024-01-01 12:00:00
      vi.setSystemTime(new Date('2024-01-01T12:00:00Z'))
    })

    it('应该返回"刚刚"当时间差小于1分钟', () => {
      const date = new Date('2024-01-01T11:59:30Z').toISOString()
      expect(formatDate(date)).toBe('刚刚')
    })

    it('应该返回"X分钟前"当时间差小于1小时', () => {
      const date = new Date('2024-01-01T11:30:00Z').toISOString()
      expect(formatDate(date)).toBe('30分钟前')
    })

    it('应该返回"X小时前"当时间差小于1天', () => {
      const date = new Date('2024-01-01T08:00:00Z').toISOString()
      expect(formatDate(date)).toBe('4小时前')
    })

    it('应该返回"X天前"当时间差小于7天', () => {
      const date = new Date('2023-12-29T12:00:00Z').toISOString()
      expect(formatDate(date)).toBe('3天前')
    })

    it('应该返回格式化日期当时间差大于7天', () => {
      const date = new Date('2023-12-20T15:30:00Z').toISOString()
      expect(formatDate(date)).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/)
    })
  })

  describe('formatFileSize', () => {
    it('应该返回"0 B"当大小为0', () => {
      expect(formatFileSize(0)).toBe('0 B')
    })

    it('应该格式化字节大小', () => {
      expect(formatFileSize(500)).toBe('500.00 B')
    })

    it('应该格式化KB大小', () => {
      expect(formatFileSize(1024)).toBe('1.00 KB')
      expect(formatFileSize(2048)).toBe('2.00 KB')
    })

    it('应该格式化MB大小', () => {
      expect(formatFileSize(1024 * 1024)).toBe('1.00 MB')
      expect(formatFileSize(5 * 1024 * 1024)).toBe('5.00 MB')
    })

    it('应该格式化GB大小', () => {
      expect(formatFileSize(1024 * 1024 * 1024)).toBe('1.00 GB')
      expect(formatFileSize(2.5 * 1024 * 1024 * 1024)).toBe('2.50 GB')
    })
  })

  describe('calculateQualityScore', () => {
    it('应该返回100分当没有问题', () => {
      const task = {
        critical_issue_count: 0,
        warning_issue_count: 0,
        info_issue_count: 0,
      } as TranslationJob

      expect(calculateQualityScore(task)).toBe(100)
    })

    it('应该扣20分每个严重问题', () => {
      const task = {
        critical_issue_count: 2,
        warning_issue_count: 0,
        info_issue_count: 0,
      } as TranslationJob

      expect(calculateQualityScore(task)).toBe(60)
    })

    it('应该扣5分每个警告问题', () => {
      const task = {
        critical_issue_count: 0,
        warning_issue_count: 4,
        info_issue_count: 0,
      } as TranslationJob

      expect(calculateQualityScore(task)).toBe(80)
    })

    it('应该扣1分每个提示问题', () => {
      const task = {
        critical_issue_count: 0,
        warning_issue_count: 0,
        info_issue_count: 10,
      } as TranslationJob

      expect(calculateQualityScore(task)).toBe(90)
    })

    it('应该综合计算多种问题', () => {
      const task = {
        critical_issue_count: 1,
        warning_issue_count: 2,
        info_issue_count: 5,
      } as TranslationJob

      // 100 - 20 - 10 - 5 = 65
      expect(calculateQualityScore(task)).toBe(65)
    })

    it('应该返回0分当分数为负数', () => {
      const task = {
        critical_issue_count: 10,
        warning_issue_count: 0,
        info_issue_count: 0,
      } as TranslationJob

      expect(calculateQualityScore(task)).toBe(0)
    })
  })

  describe('getStatusConfig', () => {
    it('应该返回正确的pending状态配置', () => {
      const config = getStatusConfig('pending')
      expect(config).toEqual({ color: 'default', text: '等待中' })
    })

    it('应该返回正确的in_progress状态配置', () => {
      const config = getStatusConfig('in_progress')
      expect(config).toEqual({ color: 'blue', text: '进行中' })
    })

    it('应该返回正确的completed状态配置', () => {
      const config = getStatusConfig('completed')
      expect(config).toEqual({ color: 'green', text: '已完成' })
    })

    it('应该返回正确的failed状态配置', () => {
      const config = getStatusConfig('failed')
      expect(config).toEqual({ color: 'red', text: '失败' })
    })

    it('应该返回正确的paused状态配置', () => {
      const config = getStatusConfig('paused')
      expect(config).toEqual({ color: 'orange', text: '已暂停' })
    })

    it('应该返回正确的cancelled状态配置', () => {
      const config = getStatusConfig('cancelled')
      expect(config).toEqual({ color: 'default', text: '已取消' })
    })

    it('应该返回默认配置当状态未知', () => {
      const config = getStatusConfig('unknown' as any)
      expect(config).toEqual({ color: 'default', text: '未知' })
    })
  })

  describe('formatLanguagePair', () => {
    it('应该格式化中英语言对', () => {
      expect(formatLanguagePair('zh', 'en')).toBe('中文 → 英文')
    })

    it('应该格式化英中语言对', () => {
      expect(formatLanguagePair('en', 'zh')).toBe('英文 → 中文')
    })

    it('应该格式化日文语言对', () => {
      expect(formatLanguagePair('zh', 'ja')).toBe('中文 → 日文')
    })

    it('应该格式化韩文语言对', () => {
      expect(formatLanguagePair('zh', 'ko')).toBe('中文 → 韩文')
    })

    it('应该格式化法文语言对', () => {
      expect(formatLanguagePair('zh', 'fr')).toBe('中文 → 法文')
    })

    it('应该格式化德文语言对', () => {
      expect(formatLanguagePair('zh', 'de')).toBe('中文 → 德文')
    })

    it('应该格式化西班牙文语言对', () => {
      expect(formatLanguagePair('zh', 'es')).toBe('中文 → 西班牙文')
    })

    it('应该保留未知语言代码', () => {
      expect(formatLanguagePair('unknown', 'test')).toBe('unknown → test')
    })
  })
})
