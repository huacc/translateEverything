/**
 * Mock服务
 * 提供Mock数据支持，用于前端开发和测试
 */

import type {
  TranslationJob,
  CreateTaskData,
  TasksResponse,
  TaskDetailResponse,
  CreateTaskResponse,
  DeleteTaskResponse,
  Config,
  JobStatus,
} from '@/types/task';

class MockService {
  private mockDelay = 500; // 模拟网络延迟（毫秒）

  /**
   * 模拟网络延迟
   */
  private delay(): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, this.mockDelay));
  }

  /**
   * 获取任务列表
   */
  async getTasks(): Promise<TasksResponse> {
    await this.delay();
    const response = await fetch('/mock-data/tasks.json');
    if (!response.ok) {
      throw new Error('Failed to fetch tasks');
    }
    return response.json();
  }

  /**
   * 获取任务详情
   */
  async getTaskDetail(id: number): Promise<TaskDetailResponse> {
    await this.delay();
    const { jobs } = await this.getTasks();
    const job = jobs.find((j) => j.id === id);
    if (!job) {
      throw new Error('Task not found');
    }
    return { job };
  }

  /**
   * 创建任务
   */
  async createTask(data: CreateTaskData): Promise<CreateTaskResponse> {
    await this.delay();

    // 模拟文件格式检查
    const fileName = data.file.name;
    const isPdf = fileName.toLowerCase().endsWith('.pdf');
    const isDocx = fileName.toLowerCase().endsWith('.docx');

    if (!isPdf && !isDocx) {
      throw new Error('只支持PDF和DOCX格式');
    }

    // 模拟文件大小检查
    const maxSize = 100 * 1024 * 1024; // 100MB
    if (data.file.size > maxSize) {
      throw new Error('文件大小不能超过100MB');
    }

    const newJob: TranslationJob = {
      id: Date.now(),
      source_file_name: data.file.name,
      source_file_path: `/uploads/${data.file.name}`,
      target_file_path: null,
      source_lang: data.source_lang,
      target_lang: data.target_lang,
      source_format: isPdf ? 'pdf' : 'docx',
      session_id: null,
      task_run_id: null,
      current_prompt_bundle_id: null,
      status: 'pending' as JobStatus,
      stage: 'queued',
      page_count: 0,
      total_segments: 0,
      completed_segments: 0,
      failed_segments: 0,
      progress_percent: 0,
      document_summary: null,
      translation_notes: [],
      task_prompt_text: null,
      options: {
        enable_quality_check: data.enable_quality_check ?? true,
        translation_style: data.translation_style ?? 'professional',
        glossary_id: data.glossary_id ?? null,
      },
      quality_issue_counts: { critical: 0, warning: 0, info: 0 },
      critical_issue_count: 0,
      warning_issue_count: 0,
      info_issue_count: 0,
      export_blocked: false,
      export_status: 'ready',
      artifact_available: false,
      error_message: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
    };

    return { job: newJob };
  }

  /**
   * 暂停任务
   */
  async pauseTask(id: number): Promise<TaskDetailResponse> {
    await this.delay();
    const { job } = await this.getTaskDetail(id);

    if (job.status !== 'in_progress') {
      throw new Error('只能暂停进行中的任务');
    }

    job.status = 'paused' as JobStatus;
    job.updated_at = new Date().toISOString();
    return { job };
  }

  /**
   * 继续任务
   */
  async resumeTask(id: number): Promise<TaskDetailResponse> {
    await this.delay();
    const { job } = await this.getTaskDetail(id);

    if (job.status !== 'paused') {
      throw new Error('只能继续已暂停的任务');
    }

    job.status = 'in_progress' as JobStatus;
    job.updated_at = new Date().toISOString();
    return { job };
  }

  /**
   * 取消任务
   */
  async cancelTask(id: number): Promise<TaskDetailResponse> {
    await this.delay();
    const { job } = await this.getTaskDetail(id);

    if (job.status === 'completed' || job.status === 'cancelled') {
      throw new Error('无法取消已完成或已取消的任务');
    }

    job.status = 'cancelled' as JobStatus;
    job.updated_at = new Date().toISOString();
    return { job };
  }

  /**
   * 删除任务
   */
  async deleteTask(id: number): Promise<DeleteTaskResponse> {
    await this.delay();
    const { job } = await this.getTaskDetail(id);

    if (job.status === 'in_progress') {
      throw new Error('无法删除进行中的任务，请先暂停或取消');
    }

    return { ok: true };
  }

  /**
   * 获取配置
   */
  async getConfig(): Promise<Config> {
    await this.delay();
    const response = await fetch('/mock-data/config.json');
    if (!response.ok) {
      throw new Error('Failed to fetch config');
    }
    return response.json();
  }

  /**
   * 下载译文
   */
  async downloadArtifact(id: number): Promise<Blob> {
    await this.delay();
    const { job } = await this.getTaskDetail(id);

    if (!job.artifact_available) {
      throw new Error('译文尚未生成');
    }

    if (job.export_blocked) {
      throw new Error('存在严重质量问题，导出被阻断');
    }

    // 模拟返回一个空的Blob
    return new Blob(['Mock translated content'], { type: 'application/pdf' });
  }
}

export const mockService = new MockService();
