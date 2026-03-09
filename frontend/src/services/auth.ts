import api from './api';
import type { AuthTokens, User } from '../types';

export const authService = {
  async login(email: string, password: string): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/login', { email, password });
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  },

  async register(payload: {
    email: string;
    password: string;
    first_name: string;
    last_name?: string;
    organization_name: string;
  }): Promise<AuthTokens> {
    const { data } = await api.post<AuthTokens>('/auth/register', payload);
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data;
  },

  async me(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
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
