import api from './api';
import type { Lead, LeadListItem, Message, Note, PaginatedResponse, LeadStats } from '../types';

export interface LeadFilters {
  tier?: string;
  status?: string;
  source?: string;
  is_ai_active?: boolean;
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

  async getMessages(id: number): Promise<Message[]> {
    const { data } = await api.get<Message[]>(`/leads/${id}/messages/`);
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

  async sendMessage(id: number, text: string): Promise<Message> {
    const { data } = await api.post<Message>(`/leads/${id}/send_message/`, { text });
    return data;
  },

  async addNote(id: number, text: string): Promise<Note> {
    const { data } = await api.post<Note>(`/leads/${id}/add_note/`, { text });
    return data;
  },

  async getStats(): Promise<LeadStats> {
    const { data } = await api.get<LeadStats>('/leads/stats/');
    return data;
  },
};
