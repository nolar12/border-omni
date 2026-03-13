import api from './api';
import type { QuickReply, QuickReplyCategory } from '../types';

export const quickRepliesService = {
  async getAll(): Promise<QuickReply[]> {
    const { data } = await api.get<{ results: QuickReply[] } | QuickReply[]>('/quick-replies/');
    return Array.isArray(data) ? data : data.results;
  },

  async getCategories(): Promise<QuickReplyCategory[]> {
    const { data } = await api.get<{ results: QuickReplyCategory[] } | QuickReplyCategory[]>(
      '/quick-reply-categories/'
    );
    return Array.isArray(data) ? data : data.results;
  },

  resolveVariables(text: string, vars: Record<string, string>): string {
    return text.replace(/\{(\w+)\}/g, (_, key: string) => vars[key] ?? `{${key}}`);
  },

  /** Returns the display text for a reply (body preferred over legacy text). */
  getDisplayBody(reply: QuickReply): string {
    return reply.body || reply.text || '';
  },

  /** Returns the display title for a reply (title preferred over legacy shortcut). */
  getDisplayTitle(reply: QuickReply): string {
    return reply.title || reply.shortcut || '';
  },
};
