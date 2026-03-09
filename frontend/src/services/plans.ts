import api from './api';
import type { Plan, Subscription } from '../types';

export const plansService = {
  async getPlans(): Promise<Plan[]> {
    const { data } = await api.get<{ results: Plan[] } | Plan[]>('/plans/');
    return Array.isArray(data) ? data : data.results;
  },

  async getSubscription(): Promise<Subscription> {
    const { data } = await api.get<Subscription>('/subscription/');
    return data;
  },

  async upgrade(planName: string): Promise<Subscription> {
    const { data } = await api.post<Subscription>('/subscription/upgrade', { plan: planName });
    return data;
  },
};
