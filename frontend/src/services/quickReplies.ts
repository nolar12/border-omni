import api from './api';
import type { QuickReply } from '../types';

export const quickRepliesService = {
  async getAll(): Promise<QuickReply[]> {
    const { data } = await api.get<{ results: QuickReply[] } | QuickReply[]>('/quick-replies/');
    return Array.isArray(data) ? data : data.results;
  },

  resolveVariables(text: string, vars: Record<string, string>): string {
    return text.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? `{${key}}`);
  },
};
