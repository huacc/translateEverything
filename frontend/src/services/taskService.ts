import { CONFIG } from '@/constants/config'
import { FALLBACK_CONFIG } from '@/constants/fallbackConfig'
import { mockApi } from './mockApi'
import type {
  Config,
  CreateTaskData,
  CreateTaskResponse,
  DeleteTaskResponse,
  TaskDetailResponse,
  TasksResponse,
} from '@/types/task'

class TaskService {
  private useMock = import.meta.env.VITE_USE_MOCK === 'true'
  private apiBaseUrl = `${CONFIG.API_BASE_URL}/v1`

  private buildUrl(path: string) {
    return `${this.apiBaseUrl}${path}`
  }

  getPreviewImageUrl(
    id: number,
    kind: 'source' | 'target',
    page: number,
    dpi = 144
  ) {
    const query = new URLSearchParams({
      kind,
      page: String(page),
      dpi: String(dpi),
    })

    return `${this.buildUrl(`/translations/${id}/preview`)}?${query.toString()}`
  }

  async getTasks(): Promise<TasksResponse> {
    if (this.useMock) {
      return mockApi.getTasks()
    }

    const response = await fetch(this.buildUrl('/translations'), {
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('获取任务列表失败')
    }

    return response.json()
  }

  async getTaskDetail(id: number): Promise<TaskDetailResponse> {
    if (this.useMock) {
      return mockApi.getTaskDetail(id)
    }

    const response = await fetch(this.buildUrl(`/translations/${id}`), {
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('获取任务详情失败')
    }

    return response.json()
  }

  async createTask(data: CreateTaskData): Promise<CreateTaskResponse> {
    if (this.useMock) {
      return mockApi.createTask(data)
    }

    const formData = new FormData()
    formData.append('file', data.file)
    formData.append('source_lang', data.source_lang)
    formData.append('target_lang', data.target_lang)

    if (data.glossary_id) {
      formData.append('glossary_id', data.glossary_id.toString())
    }

    if (data.translation_style) {
      formData.append('translation_style', data.translation_style)
    }

    if (data.enable_quality_check !== undefined) {
      formData.append(
        'enable_quality_check',
        data.enable_quality_check.toString()
      )
    }

    const response = await fetch(this.buildUrl('/translations/upload'), {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || '创建任务失败')
    }

    return response.json()
  }

  async pauseTask(id: number): Promise<TaskDetailResponse> {
    if (this.useMock) {
      return mockApi.pauseTask(id)
    }

    const response = await fetch(this.buildUrl(`/translations/${id}/pause`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('暂停任务失败')
    }

    return response.json()
  }

  async resumeTask(id: number): Promise<TaskDetailResponse> {
    if (this.useMock) {
      return mockApi.resumeTask(id)
    }

    const response = await fetch(this.buildUrl(`/translations/${id}/resume`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('继续任务失败')
    }

    return response.json()
  }

  async cancelTask(id: number): Promise<TaskDetailResponse> {
    if (this.useMock) {
      return mockApi.cancelTask(id)
    }

    const response = await fetch(this.buildUrl(`/translations/${id}/cancel`), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('取消任务失败')
    }

    return response.json()
  }

  async deleteTask(id: number): Promise<DeleteTaskResponse> {
    if (this.useMock) {
      return mockApi.deleteTask(id)
    }

    const response = await fetch(this.buildUrl(`/translations/${id}`), {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error('删除任务失败')
    }

    return response.json()
  }

  async getConfig(): Promise<Config> {
    if (this.useMock) {
      return mockApi.getConfig()
    }

    try {
      const response = await fetch(this.buildUrl('/config'), {
        headers: {
          'Content-Type': 'application/json',
        },
      })

      if (!response.ok) {
        throw new Error('获取配置失败')
      }

      return response.json()
    } catch (error) {
      console.warn(
        'Failed to load config from backend, using fallback config.',
        error
      )
      return FALLBACK_CONFIG
    }
  }

  async downloadArtifact(id: number): Promise<Blob> {
    if (this.useMock) {
      return mockApi.downloadArtifact(id)
    }

    const response = await fetch(
      this.buildUrl(`/translations/${id}/artifact`),
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    )

    if (!response.ok) {
      throw new Error('下载译文失败')
    }

    return response.blob()
  }
}

export const taskService = new TaskService()
