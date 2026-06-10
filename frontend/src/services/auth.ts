import api from './api';
import type { AuthTokens, User } from '../types';

function _saveTokens(data: AuthTokens) {
  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);
  localStorage.setItem('user', JSON.stringify(data.user));
}

export const authService = {
  async login(email: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/login', { email, password });
    _saveTokens(data);
    return data;
  },

  async register(payload: {
    name: string;
    email: string;
    password: string;
    phone?: string;
    first_name?: string;
    last_name?: string;
    organization_name?: string;
  }): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/register', payload);
    _saveTokens(data);
    return data;
  },

  async googleLogin(accessToken: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/google', { access_token: accessToken });
    _saveTokens(data);
    return data;
  },

  async me(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    localStorage.setItem('user', JSON.stringify(data));
    return data;
  },

  async updateProfile(payload: {
    first_name?: string;
    last_name?: string;
    phone?: string;
    kennel_cbkc_code?: string;
    kennel_fci_code?: string;
    kennel_prefix?: string;
    kennel_owner_name?: string;
    kennel_address_line?: string;
    kennel_neighborhood?: string;
    kennel_city?: string;
    kennel_state?: string;
    kennel_zip_code?: string;
    kennel_phone?: string;
    kennel_breed?: string;
    kennel_registry_date?: string | null;
    kennel_issue_date?: string | null;
  }): Promise<User> {
    const { data } = await api.patch<User>('/auth/me', payload);
    localStorage.setItem('user', JSON.stringify(data));
    return data;
  },

  logout() {
    localStorage.clear();
    window.location.href = '/login';
  },

  getCurrentUser(): User | null {
    const raw = localStorage.getItem('user');
    return raw ? (JSON.parse(raw) as User) : null;
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },
};
