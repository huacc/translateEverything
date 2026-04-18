/**
 * Mock API服务
 * 提供完整的Mock数据支持，包括静态数据和SSE流式响应
 */

import type {
  TranslationJob,
  CreateTaskData,
  TasksResponse,
  TaskDetailResponse,
  CreateTaskResponse,
  DeleteTaskResponse,
  Config,
  TranslationSegment,
  QualityIssue
} from '../types/task';

// 模拟网络延迟
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * 加载JSON文件
 */
async function loadJSON<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.statusText}`);
  }
  return response.json();
}

/**
 * Mock API类
 */
export class MockApi {
  private baseUrl = '/mock-data';

  /**
   * 获取任务列表
   */
  async getTasks(): Promise<TasksResponse> {
    await delay(300);
    const data = await loadJSON<{ jobs: TranslationJob[] }>(`${this.baseUrl}/tasks.json`);
    return { jobs: data.jobs };
  }

  /**
   * 获取任务详情
   */
  async getTaskDetail(taskId: number): Promise<TaskDetailResponse> {
    await delay(200);
    return loadJSON<TaskDetailResponse>(`${this.baseUrl}/task-details/task-${taskId}.json`);
  }

  /**
   * 获取翻译段落列表
   */
  async getSegments(taskId: number, page: number = 1, pageSize: number = 20): Promise<{
    task_id: number;
    total_segments: number;
    page_size: number;
    current_page: number;
    total_pages: number;
    segments: TranslationSegment[];
  }> {
    await delay(250);
    const data = await loadJSON<{
      task_id: number;
      total_segments: number;
      page_size: number;
      current_page: number;
      total_pages: number;
      segments: TranslationSegment[];
    }>(`${this.baseUrl}/segments/task-${taskId}-segments.json`);

    // 模拟分页
    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const paginatedSegments = data.segments.slice(start, end);

    return {
      ...data,
      current_page: page,
      page_size: pageSize,
      segments: paginatedSegments
    };
  }

  /**
   * 获取质量问题列表
   */
  async getQualityIssues(taskId: number): Promise<{
    task_id: number;
    total_issues: number;
    issues: QualityIssue[];
  }> {
    await delay(200);
    return loadJSON<{
      task_id: number;
      total_issues: number;
      issues: QualityIssue[];
    }>(`${this.baseUrl}/quality-issues/task-${taskId}-issues.json`);
  }

  /**
   * 获取配置数据
   */
  async getConfig(): Promise<Config> {
    await delay(150);
    return loadJSON<Config>(`${this.baseUrl}/config.json`);
  }

  /**
   * 创建翻译任务
   */
  async createTask(data: CreateTaskData): Promise<CreateTaskResponse> {
    await delay(500);

    // 模拟创建任务
    const newTask: TranslationJob = {
      id: Date.now(),
      source_file_name: data.file.name,
      source_file_path: `/uploads/${data.file.name}`,
      target_file_path: null,
      source_lang: data.source_lang,
      target_lang: data.target_lang,
      source_format: 'pdf',
      session_id: null,
      task_run_id: null,
      current_prompt_bundle_id: null,
      status: 'pending',
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
        enable_quality_check: data.enable_quality_check,
        translation_style: data.translation_style,
        glossary_id: data.glossary_id,
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

    return { job: newTask };
  }

  /**
   * 更新任务
   */
  async updateTask(taskId: number, updates: Partial<TranslationJob>): Promise<TranslationJob> {
    await delay(300);

    // 模拟更新任务
    const response = await this.getTaskDetail(taskId);
    return {
      ...response.job,
      ...updates,
      updated_at: new Date().toISOString()
    };
  }

  /**
   * 删除任务
   */
  async deleteTask(taskId: number): Promise<DeleteTaskResponse> {
    await delay(200);
    console.log(`Mock: Deleted task ${taskId}`);
    return { ok: true };
  }

  /**
   * 暂停翻译任务
   */
  async pauseTask(taskId: number): Promise<TaskDetailResponse> {
    await delay(200);
    console.log(`Mock: Paused translation task ${taskId}`);
    const task = await this.getTaskDetail(taskId);
    return task;
  }

  /**
   * 恢复翻译任务
   */
  async resumeTask(taskId: number): Promise<TaskDetailResponse> {
    await delay(200);
    console.log(`Mock: Resumed translation task ${taskId}`);
    const task = await this.getTaskDetail(taskId);
    return task;
  }

  /**
   * 取消翻译任务
   */
  async cancelTask(taskId: number): Promise<TaskDetailResponse> {
    await delay(200);
    console.log(`Mock: Cancelled translation task ${taskId}`);
    const task = await this.getTaskDetail(taskId);
    return task;
  }

  /**
   * 下载译文
   */
  async downloadArtifact(taskId: number): Promise<Blob> {
    await delay(500);
    const content = `这是任务 ${taskId} 的翻译结果\n生成时间: ${new Date().toLocaleString()}`;
    return new Blob([content], { type: 'text/plain' });
  }

  /**
   * 获取源文件PDF URL
   */
  getSourcePdfUrl(_taskId: number): string {
    return `${this.baseUrl}/source.pdf`;
  }

  /**
   * 获取译文PDF URL
   */
  getTranslatedPdfUrl(_taskId: number): string {
    return `${this.baseUrl}/translated.pdf`;
  }
}

// 导出单例
export const mockApi = new MockApi();
