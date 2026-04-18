/**
 * 任务相关类型定义
 * 与后端接口文档严格对齐
 */

// 作业状态类型
export type JobStatus = 'pending' | 'in_progress' | 'completed' | 'failed' | 'paused' | 'cancelled';

// 作业阶段类型
export type JobStage = 'queued' | 'analyzing' | 'translating' | 'rendering' | 'completed' | 'failed';

// 文档摘要
export interface DocumentSummary {
  title?: string;
  author?: string;
  subject?: string;
  keywords?: string[];
  page_count?: number;
  word_count?: number;
}

// 作业选项
export interface JobOptions {
  enable_quality_check?: boolean;
  translation_style?: string;
  glossary_id?: number | null;
}

// 质量问题计数
export interface QualityIssueCounts {
  critical: number;
  warning: number;
  info: number;
}

// 翻译作业主对象
export interface TranslationJob {
  // 基础信息
  id: number;
  source_file_name: string;
  source_file_path: string;
  target_file_path: string | null;
  source_lang: string;
  target_lang: string;
  source_format: 'docx' | 'pdf';

  // 关联信息
  session_id: string | null;
  task_run_id: string | null;
  current_prompt_bundle_id: number | null;

  // 状态信息
  status: JobStatus;
  stage: JobStage;

  // 进度信息
  page_count: number;
  total_segments: number;
  completed_segments: number;
  failed_segments: number;
  progress_percent: number;

  // 文档分析
  document_summary: DocumentSummary | null;
  translation_notes: string[];
  task_prompt_text: string | null;

  // 配置选项
  options: JobOptions | null;

  // 质量信息
  quality_issue_counts: QualityIssueCounts;
  critical_issue_count: number;
  warning_issue_count: number;
  info_issue_count: number;
  export_blocked: boolean;
  export_status: 'ready' | 'blocked';

  // 产物信息
  artifact_available: boolean;

  // 错误信息
  error_message: string | null;

  // 时间信息
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

// 语言选项
export interface LanguageOption {
  code: string;
  name: string;
  native_name: string;
}

// 术语库选项
export interface GlossaryOption {
  id: number;
  name: string;
  description: string;
  term_count: number;
  source_lang: string;
  target_lang: string;
}

// 翻译风格选项
export interface TranslationStyleOption {
  id: string;
  name: string;
  description: string;
}

// 配置对象
export interface Config {
  languages: LanguageOption[];
  glossaries: GlossaryOption[];
  translation_styles: TranslationStyleOption[];
}

// 创建任务数据
export interface CreateTaskData {
  file: File;
  source_lang: string;
  target_lang: string;
  glossary_id?: number | null;
  translation_style?: string;
  enable_quality_check?: boolean;
}

// API响应类型
export interface TasksResponse {
  jobs: TranslationJob[];
}

export interface TaskDetailResponse {
  job: TranslationJob;
}

export interface CreateTaskResponse {
  job: TranslationJob;
}

export interface DeleteTaskResponse {
  ok: boolean;
}

// 翻译段落
export interface TranslationSegment {
  id: number;
  page_num: number;
  block_id: string;
  source_text: string;
  translated_text: string;
  status: 'pending' | 'translating' | 'completed' | 'failed';
  quality_score?: number;
}

// 质量问题
export interface QualityIssue {
  id: number;
  segment_id: number;
  page_num: number;
  block_id: string;
  severity: 'critical' | 'warning' | 'info';
  category: string;
  message: string;
  suggestion?: string;
  context?: string;
}
