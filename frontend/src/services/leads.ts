import api from './api';
import type { Lead, LeadListItem, Message, Note, PaginatedResponse, LeadStats } from '../types';

export interface LeadFilters {
  tier?: string;
  status?: string;
  source?: string;
  is_ai_active?: boolean;
  lead_classification?: string;
  is_archived?: boolean;
  search?: string;
  page?: number;
}

export const leadsService = {
  async getLeads(filters: LeadFilters = {}): Promise<PaginatedResponse<LeadListItem>> {
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v !== undefined && v !== '')
    );
    const { data } = await api.get<PaginatedResponse<LeadListItem>>('/leads/', { params });
    return data;
  },

  async getLead(id: number): Promise<Lead> {
    const { data } = await api.get<Lead>(`/leads/${id}/`);
    return data;
  },

  async updateLead(id: number, payload: Partial<Lead>): Promise<Lead> {
    const { data } = await api.patch<Lead>(`/leads/${id}/`, payload);
    return data;
  },

  async getMessages(id: number, channel?: string): Promise<Message[]> {
    const params = channel ? { channel } : {};
    const { data } = await api.get<Message[]>(`/leads/${id}/messages/`, { params });
    return data;
  },

  async assumeLead(id: number): Promise<Lead> {
    const { data } = await api.post<Lead>(`/leads/${id}/assume/`);
    return data;
  },

  async releaseLead(id: number): Promise<Lead> {
    const { data } = await api.post<Lead>(`/leads/${id}/release/`);
    return data;
  },

  async sendMessage(id: number, text: string, channel?: string): Promise<Message> {
    const { data } = await api.post<Message>(`/leads/${id}/send_message/`, { text, channel });
    return data;
  },

  async enhanceMessage(id: number, text: string): Promise<{ original: string; enhanced: string; changed: boolean }> {
    try {
      const { data } = await api.post<{ original: string; enhanced: string; changed: boolean }>(
        `/leads/${id}/enhance_message/`,
        { text },
      );
      return data;
    } catch {
      return { original: text, enhanced: text, changed: false };
    }
  },

  async sendFile(id: number, file: File, caption?: string): Promise<Message> {
    const form = new FormData();
    form.append('file', file);
    if (caption) form.append('caption', caption);
    const { data } = await api.post<Message>(`/leads/${id}/send_file/`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data;
  },

  async addNote(id: number, text: string): Promise<Note> {
    const { data } = await api.post<Note>(`/leads/${id}/add_note/`, { text });
    return data;
  },

  async closeLead(id: number): Promise<Lead> {
    const { data } = await api.post<Lead>(`/leads/${id}/close/`);
    return data;
  },

  async reopenLead(id: number): Promise<Lead> {
    const { data } = await api.post<Lead>(`/leads/${id}/reopen/`);
    return data;
  },

  async archiveLead(id: number): Promise<void> {
    await api.post(`/leads/${id}/archive/`);
  },

  async reclassifyLead(id: number): Promise<{ lead_classification: string; score: number; resumo_intencao: string }> {
    const { data } = await api.post(`/leads/${id}/reclassify/`);
    return data;
  },

  async reclassifyAll(): Promise<{ detail: string }> {
    const { data } = await api.post('/leads/reclassify_all/');
    return data;
  },

  async unarchiveLead(id: number): Promise<Lead> {
    const { data } = await api.post<Lead>(`/leads/${id}/unarchive/`);
    return data;
  },

  async deleteLead(id: number): Promise<void> {
    await api.delete(`/leads/${id}/delete/`);
  },

  async getStats(): Promise<LeadStats> {
    const { data } = await api.get<LeadStats>('/leads/stats/');
    return data;
  },

  async suggestResponse(id: number, message: string, channel?: string, brief?: string): Promise<string[]> {
    try {
      const { data } = await api.post<{ suggestions: string[] }>(
        `/leads/${id}/suggest_response/`,
        { message, channel: channel ?? 'whatsapp', brief: brief ?? '' },
      );
      return data.suggestions ?? [];
    } catch {
      return [];
    }
  },

  async approveSuggestion(id: number, message: string, suggestion: string, brief?: string): Promise<void> {
    try {
      await api.post(`/leads/${id}/approve_suggestion/`, {
        message,
        suggestion,
        brief: brief ?? '',
      });
    } catch { /* fire-and-forget, não bloqueia UX */ }
  },

  async sendTemplate(id: number, templateId: number, variables: string[], headerMediaUrl?: string): Promise<Message> {
    const { data } = await api.post<Message>(`/leads/${id}/send_template/`, {
      template_id: templateId,
      variables,
      ...(headerMediaUrl ? { header_media_url: headerMediaUrl } : {}),
    });
    return data;
  },

  async sendGalleryItem(leadId: number, galleryMediaId: number, caption?: string): Promise<Message[]> {
    const { data } = await api.post<{ messages: Message[] }>(`/leads/${leadId}/send_gallery_item/`, {
      gallery_media_id: galleryMediaId,
      caption: caption ?? '',
    });
    return data.messages;
  },
};
