export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  organization_name: string;
  plan_name: string;
}

export interface Plan {
  id: number;
  name: 'free' | 'pro' | 'enterprise';
  max_leads: number;
  max_agents: number;
  max_channels: number;
  price_monthly: number;
}

export interface Subscription {
  id: number;
  plan: Plan;
  organization_name: string;
  status: 'active' | 'trial' | 'expired' | 'cancelled';
  trial_ends_at: string | null;
  current_period_end: string | null;
  created_at: string;
}

export interface AssignedUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
}

export type Tier = 'A' | 'B' | 'C';
export type LeadStatus = 'NEW' | 'QUALIFYING' | 'QUALIFIED' | 'HANDOFF' | 'CLOSED';
export type LeadSource = 'INSTAGRAM_AD' | 'ORGANIC' | 'OTHER';

export interface Lead {
  id: number;
  phone: string;
  full_name: string | null;
  instagram_handle: string | null;
  city: string | null;
  state: string | null;
  housing_type: 'HOUSE' | 'APT' | 'OTHER' | null;
  daily_time_minutes: number | null;
  experience_level: 'FIRST_DOG' | 'HAD_DOGS' | 'HAD_HIGH_ENERGY' | null;
  budget_ok: 'YES' | 'NO' | 'MAYBE' | null;
  timeline: 'NOW' | 'THIRTY_DAYS' | 'SIXTY_PLUS' | null;
  purpose: 'COMPANION' | 'SPORT' | 'WORK' | null;
  has_kids: boolean;
  has_other_pets: boolean;
  score: number;
  tier: Tier | null;
  status: LeadStatus;
  source: LeadSource;
  channels_used: string;
  is_ai_active: boolean;
  assigned_to: AssignedUser | null;
  tags: string[];
  notes: Note[];
  conversation_state: string | null;
  created_at: string;
  updated_at: string;
}

export interface LeadListItem {
  id: number;
  phone: string;
  full_name: string | null;
  city: string | null;
  state: string | null;
  tier: Tier | null;
  score: number;
  status: LeadStatus;
  source: LeadSource;
  is_ai_active: boolean;
  assigned_to: AssignedUser | null;
  tags: string[];
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  direction: 'IN' | 'OUT';
  text: string;
  provider_message_id: string | null;
  created_at: string;
}

export interface Note {
  id: number;
  text: string;
  author_name: string;
  created_at: string;
}

export interface QuickReply {
  id: number;
  category: 'GREETING' | 'PRICING' | 'AVAILABILITY' | 'SCHEDULING' | 'INFO' | 'CLOSING';
  text: string;
  shortcut: string;
  is_active: boolean;
  created_at: string;
}

export interface ChannelProvider {
  id: number;
  provider: 'whatsapp' | 'instagram';
  app_id: string;
  phone_number_id: string;
  business_account_id: string;
  instagram_account_id: string;
  page_id: string;
  webhook_verify_token: string;
  webhook_url: string;
  is_active: boolean;
  is_simulated: boolean;
  verification_status: 'verified' | 'pending' | 'failed';
  last_verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface LeadStats {
  total: number;
  tier_a: number;
  tier_b: number;
  tier_c: number;
  handoff: number;
  qualifying: number;
  qualified: number;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}
