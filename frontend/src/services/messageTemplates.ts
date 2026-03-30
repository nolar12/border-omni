import api from './api';
import type { MessageTemplate, PaginatedResponse } from '../types';

export interface CreateTemplatePayload {
  name: string;
  language: string;
  category: string;
  header_type?: string;
  header_text?: string;
  header_media_url?: string;
  body_text: string;
  footer_text?: string;
  channel?: number | null;
  draft?: boolean;
}

export const messageTemplatesService = {
  list: async (): Promise<MessageTemplate[]> => {
    const { data } = await api.get<PaginatedResponse<MessageTemplate> | MessageTemplate[]>('/message-templates/');
    return Array.isArray(data) ? data : data.results;
  },

  create: (payload: CreateTemplatePayload) =>
    api.post<MessageTemplate>('/message-templates/', payload).then(r => r.data),

  update: (id: number, payload: Partial<CreateTemplatePayload>) =>
    api.patch<MessageTemplate>(`/message-templates/${id}/`, payload).then(r => r.data),

  remove: (id: number) =>
    api.delete(`/message-templates/${id}/`),

  sync: (id: number) =>
    api.post<MessageTemplate>(`/message-templates/${id}/sync/`).then(r => r.data),

  syncAll: () =>
    api.post<{ updated: string[]; imported: string[]; errors: string[] }>('/message-templates/sync-all/').then(r => r.data),

  submitForApproval: (id: number) =>
    api.post<import('../types').MessageTemplate>(`/message-templates/${id}/submit/`).then(r => r.data),

  linkMetaId: (id: number, metaTemplateId: string) =>
    api.post<MessageTemplate>(`/message-templates/${id}/link/`, { meta_template_id: metaTemplateId }).then(r => r.data),
};
