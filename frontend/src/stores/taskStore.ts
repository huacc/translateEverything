/**
 * 任务状态管理Store
 * 使用Zustand管理任务列表和当前任务状态
 */

import { create } from 'zustand';
import { taskService } from '@/services/taskService';
import type { TranslationJob, CreateTaskData } from '@/types/task';

interface TaskStore {
  // 状态
  tasks: TranslationJob[];
  currentTask: TranslationJob | null;
  loading: boolean;
  error: string | null;

  // 操作
  fetchTasks: () => Promise<void>;
  fetchTaskDetail: (id: number) => Promise<void>;
  createTask: (data: CreateTaskData) => Promise<TranslationJob>;
  updateTask: (id: number, data: Partial<TranslationJob>) => void;
  deleteTask: (id: number) => Promise<void>;
  pauseTask: (id: number) => Promise<void>;
  resumeTask: (id: number) => Promise<void>;
  cancelTask: (id: number) => Promise<void>;
  clearError: () => void;
}

export const useTaskStore = create<TaskStore>((set, get) => ({
  // 初始状态
  tasks: [],
  currentTask: null,
  loading: false,
  error: null,

  // 获取任务列表
  fetchTasks: async () => {
    set({ loading: true, error: null });
    try {
      const { jobs } = await taskService.getTasks();
      set({ tasks: jobs, loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '获取任务列表失败';
      set({ error: errorMessage, loading: false });
    }
  },

  // 获取任务详情
  fetchTaskDetail: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const { job } = await taskService.getTaskDetail(id);
      set({ currentTask: job, loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '获取任务详情失败';
      set({ error: errorMessage, loading: false });
    }
  },

  // 创建任务
  createTask: async (data: CreateTaskData) => {
    set({ loading: true, error: null });
    try {
      const { job } = await taskService.createTask(data);
      set((state) => ({
        tasks: [job, ...state.tasks],
        loading: false,
      }));
      return job;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '创建任务失败';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  // 更新任务（本地更新）
  updateTask: (id: number, data: Partial<TranslationJob>) => {
    set((state) => ({
      tasks: state.tasks.map((task) =>
        task.id === id ? { ...task, ...data } : task
      ),
      currentTask:
        state.currentTask?.id === id
          ? { ...state.currentTask, ...data }
          : state.currentTask,
    }));
  },

  // 删除任务
  deleteTask: async (id: number) => {
    set({ loading: true, error: null });
    try {
      await taskService.deleteTask(id);
      set((state) => ({
        tasks: state.tasks.filter((task) => task.id !== id),
        currentTask: state.currentTask?.id === id ? null : state.currentTask,
        loading: false,
      }));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '删除任务失败';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  // 暂停任务
  pauseTask: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const { job } = await taskService.pauseTask(id);
      get().updateTask(id, job);
      set({ loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '暂停任务失败';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  // 继续任务
  resumeTask: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const { job } = await taskService.resumeTask(id);
      get().updateTask(id, job);
      set({ loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '继续任务失败';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  // 取消任务
  cancelTask: async (id: number) => {
    set({ loading: true, error: null });
    try {
      const { job } = await taskService.cancelTask(id);
      get().updateTask(id, job);
      set({ loading: false });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '取消任务失败';
      set({ error: errorMessage, loading: false });
      throw error;
    }
  },

  // 清除错误
  clearError: () => {
    set({ error: null });
  },
}));
