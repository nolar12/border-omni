import api from './api';
import type { SaleContract, SaleContractPublic, PaginatedResponse } from '../types';

export interface ContractCreatePayload {
  lead?: number | null;
  dog?: number | null;
  puppy_sex: 'M' | 'F';
  puppy_color: string;
  puppy_microchip?: string;
  puppy_father?: string;
  puppy_mother?: string;
  puppy_birth_date?: string | null;
}

export const contractsService = {
  async list(lead?: number): Promise<PaginatedResponse<SaleContract>> {
    const params: Record<string, unknown> = {};
    if (lead) params.lead = lead;
    const { data } = await api.get<PaginatedResponse<SaleContract>>('/contracts/', { params });
    return data;
  },

  async get(id: number): Promise<SaleContract> {
    const { data } = await api.get<SaleContract>(`/contracts/${id}/`);
    return data;
  },

  async create(payload: ContractCreatePayload): Promise<SaleContract> {
    const { data } = await api.post<SaleContract>('/contracts/', payload);
    return data;
  },

  async update(id: number, payload: Partial<ContractCreatePayload>): Promise<SaleContract> {
    const { data } = await api.patch<SaleContract>(`/contracts/${id}/`, payload);
    return data;
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/contracts/${id}/`);
  },

  async send(id: number): Promise<SaleContract> {
    const { data } = await api.post<SaleContract>(`/contracts/${id}/send/`);
    return data;
  },

  async approve(id: number): Promise<SaleContract> {
    const { data } = await api.post<SaleContract>(`/contracts/${id}/approve/`);
    return data;
  },

  async generatePdf(id: number): Promise<Blob> {
    const { data } = await api.get(`/contracts/${id}/generate_pdf/`, {
      responseType: 'blob',
    });
    return data;
  },

  async previewHtml(id: number): Promise<string> {
    const { data } = await api.get<string>(`/contracts/${id}/preview_html/`);
    return data;
  },

  async sendWhatsapp(id: number, message?: string): Promise<void> {
    await api.post(`/contracts/${id}/send_whatsapp/`, { message: message ?? '' });
  },

  // ─── Endpoints públicos (sem autenticação) ───────────────────────────────

  async getPublic(token: string): Promise<SaleContractPublic> {
    const { data } = await api.get<SaleContractPublic>(`/contracts/public/${token}/`);
    return data;
  },

  async fillPublic(
    token: string,
    payload: {
      buyer_name: string;
      buyer_cpf: string;
      buyer_marital_status: string;
      buyer_address: string;
      buyer_cep: string;
      buyer_email: string;
    }
  ): Promise<SaleContractPublic> {
    const { data } = await api.post<SaleContractPublic>(
      `/contracts/public/${token}/fill/`,
      payload
    );
    return data;
  },

  async signPublic(
    token: string,
    payload: { signature_data: string; signature_type: 'canvas' | 'govbr' }
  ): Promise<SaleContractPublic> {
    const { data } = await api.post<SaleContractPublic>(
      `/contracts/public/${token}/sign/`,
      payload
    );
    return data;
  },
};
