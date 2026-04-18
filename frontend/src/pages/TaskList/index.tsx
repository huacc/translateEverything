import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Empty, Input, Select, Space, message } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Loading from '@/components/Loading'
import { useTaskStore } from '@/stores/taskStore'
import type { TranslationJob } from '@/types/task'
import TaskCard from './TaskCard'
import './styles.css'

const { Search } = Input
const { Option } = Select

const TaskList = () => {
  const navigate = useNavigate()
  const { tasks, loading, error, fetchTasks, clearError } = useTaskStore()

  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [langFilter, setLangFilter] = useState<string>('all')
  const [sortBy, setSortBy] = useState<string>('created_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [searchKeyword, setSearchKeyword] = useState<string>('')
  const [filteredTasks, setFilteredTasks] = useState<TranslationJob[]>([])

  useEffect(() => {
    void fetchTasks()
  }, [fetchTasks])

  useEffect(() => {
    if (error) {
      message.error(error)
      clearError()
    }
  }, [error, clearError])

  useEffect(() => {
    let result = [...tasks]

    if (statusFilter !== 'all') {
      result = result.filter(task => task.status === statusFilter)
    }

    if (langFilter !== 'all') {
      const [source, target] = langFilter.split('-')
      result = result.filter(
        task => task.source_lang === source && task.target_lang === target
      )
    }

    if (searchKeyword) {
      const keyword = searchKeyword.toLowerCase()
      result = result.filter(task =>
        task.source_file_name.toLowerCase().includes(keyword)
      )
    }

    result.sort((a, b) => {
      const aValue = a[sortBy as keyof TranslationJob]
      const bValue = b[sortBy as keyof TranslationJob]

      if (aValue === null || aValue === undefined) return 1
      if (bValue === null || bValue === undefined) return -1

      if (sortOrder === 'asc') {
        return aValue > bValue ? 1 : -1
      }

      return aValue < bValue ? 1 : -1
    })

    setFilteredTasks(result)
  }, [tasks, statusFilter, langFilter, sortBy, sortOrder, searchKeyword])

  const handleSearch = (value: string) => {
    setSearchKeyword(value)
  }

  return (
    <div className="task-list-page">
      <div className="page-header">
        <h1>翻译任务</h1>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => navigate('/tasks/new')}
        >
          创建新任务
        </Button>
      </div>

      <div className="toolbar">
        <Space size="middle" wrap>
          <Search
            placeholder="搜索文档名称"
            allowClear
            style={{ width: 300 }}
            prefix={<SearchOutlined />}
            onSearch={handleSearch}
            onChange={event => handleSearch(event.target.value)}
          />

          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 150 }}
          >
            <Option value="all">全部状态</Option>
            <Option value="pending">待开始</Option>
            <Option value="in_progress">进行中</Option>
            <Option value="completed">已完成</Option>
            <Option value="failed">失败</Option>
            <Option value="paused">已暂停</Option>
            <Option value="cancelled">已取消</Option>
          </Select>

          <Select
            value={langFilter}
            onChange={setLangFilter}
            style={{ width: 170 }}
          >
            <Option value="all">全部语言</Option>
            <Option value="zh-en">中文 → 英文</Option>
            <Option value="en-zh">英文 → 中文</Option>
          </Select>

          <Select
            value={`${sortBy}-${sortOrder}`}
            onChange={value => {
              const [field, order] = value.split('-')
              setSortBy(field)
              setSortOrder(order as 'asc' | 'desc')
            }}
            style={{ width: 180 }}
          >
            <Option value="created_at-desc">创建时间（最新）</Option>
            <Option value="created_at-asc">创建时间（最早）</Option>
            <Option value="updated_at-desc">更新时间（最新）</Option>
            <Option value="updated_at-asc">更新时间（最早）</Option>
            <Option value="source_file_name-asc">文档名称（A-Z）</Option>
            <Option value="source_file_name-desc">文档名称（Z-A）</Option>
          </Select>
        </Space>
      </div>

      <div className="task-list">
        {loading ? (
          <div className="loading-container">
            <Loading size="large" tip="正在加载任务..." />
          </div>
        ) : filteredTasks.length === 0 ? (
          <Empty
            description={
              searchKeyword
                ? `没有找到包含“${searchKeyword}”的任务`
                : '当前还没有翻译任务'
            }
          >
            {!searchKeyword && (
              <Button type="primary" onClick={() => navigate('/tasks/new')}>
                创建第一个任务
              </Button>
            )}
          </Empty>
        ) : (
          <div className="task-grid">
            {filteredTasks.map(task => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default TaskList
