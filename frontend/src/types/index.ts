export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  organization_name: string;
  plan_name: string;
  phone?: string;
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
export type LeadClassification = 'HOT_LEAD' | 'WARM_LEAD' | 'COLD_LEAD';
export type HousingType = 'HOUSE_Y' | 'HOUSE_N' | 'HOUSE' | 'APT' | 'OTHER';

export interface Lead {
  id: number;
  phone: string;
  facebook_psid: string | null;
  instagram_user_id: string | null;
  full_name: string | null;
  instagram_handle: string | null;
  city: string | null;
  state: string | null;
  housing_type: HousingType | null;
  daily_time_minutes: number | null;
  experience_level: 'FIRST_DOG' | 'HAD_DOGS' | 'HAD_HIGH_ENERGY' | null;
  budget_ok: 'YES' | 'NO' | 'MAYBE' | null;
  timeline: 'NOW' | 'THIRTY_DAYS' | 'SIXTY_PLUS' | null;
  purpose: 'COMPANION' | 'SPORT' | 'WORK' | null;
  has_kids: boolean;
  has_other_pets: boolean;
  score: number;
  tier: Tier | null;
  lead_classification: LeadClassification | null;
  is_archived: boolean;
  status: LeadStatus;
  source: LeadSource;
  channels_used: string;
  is_ai_active: boolean;
  assigned_to: AssignedUser | null;
  tags: string[];
  notes: Note[];
  conversation_state: string | null;
  conversations: Conversation[];
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
  lead_classification: LeadClassification | null;
  is_archived: boolean;
  score: number;
  status: LeadStatus;
  source: LeadSource;
  channels_used: string;
  is_ai_active: boolean;
  assigned_to: AssignedUser | null;
  tags: string[];
  last_message_direction: 'IN' | 'OUT' | null;
  created_at: string;
  updated_at: string;
}

export type ChannelType = 'whatsapp' | 'instagram' | 'facebook' | 'messenger';

export interface Conversation {
  id: number;
  channel: ChannelType;
  state: 'active' | 'closed' | 'pending';
  last_message_at: string | null;
  created_at: string;
}

export interface Message {
  id: number;
  direction: 'IN' | 'OUT';
  text: string;
  provider_message_id: string | null;
  msg_status: 'sent' | 'delivered' | 'read' | 'failed' | null;
  created_at: string;
}

export interface Note {
  id: number;
  text: string;
  author_name: string;
  created_at: string;
}

export interface QuickReplyCategory {
  id: number;
  name: string;
  sort_order: number;
  created_at: string;
}

export interface QuickReply {
  id: number;
  // New structured fields
  category_ref: number | null;
  category_name: string;
  title: string;
  body: string;
  sort_order: number;
  is_personal: boolean;
  // Legacy fields kept for backward compat
  category: string;
  text: string;
  shortcut: string;
  is_active: boolean;
  created_at: string;
}

export interface ChannelProvider {
  id: number;
  name: string;
  provider: 'whatsapp' | 'instagram' | 'facebook' | 'messenger';
  app_id: string;
  app_secret?: string;
  access_token?: string;
  access_token_masked: string;
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

export interface InitialMessageMedia {
  id: number;
  url: string;
  media_type: 'image' | 'video';
  original_name: string;
  order: number;
  created_at: string;
}

export interface OrgSettings {
  bot_enabled: boolean;
  initial_message: string;
  sequence_message: string;
  [key: string]: unknown;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}

// ─── Contracts ───────────────────────────────────────────────────────────────

export type ContractStatus = 'draft' | 'sent' | 'buyer_filled' | 'approved' | 'signed';
export type PuppySex = 'M' | 'F';

export interface SaleContract {
  id: number;
  lead: number | null;
  lead_name: string;
  lead_phone: string;
  dog: number | null;
  dog_name: string;
  puppy_sex: PuppySex;
  puppy_sex_display: string;
  puppy_color: string;
  puppy_microchip: string;
  puppy_father: string;
  puppy_mother: string;
  puppy_birth_date: string | null;
  price: string | null;
  deposit_amount: string | null;
  buyer_name: string;
  buyer_cpf: string;
  buyer_marital_status: string;
  buyer_address: string;
  buyer_cep: string;
  buyer_email: string;
  status: ContractStatus;
  status_display: string;
  token: string;
  signature_data: string;
  signature_type: string;
  pdf_url: string | null;
  created_at: string;
  updated_at: string;
  buyer_filled_at: string | null;
  approved_at: string | null;
  signed_at: string | null;
}

export interface SaleContractPublic {
  id: number;
  token: string;
  puppy_sex: PuppySex;
  puppy_sex_display: string;
  puppy_color: string;
  puppy_microchip: string;
  puppy_father: string;
  puppy_mother: string;
  puppy_birth_date: string | null;
  price: string | null;
  deposit_amount: string | null;
  price_display: string;
  deposit_display: string;
  balance_display: string;
  buyer_name: string;
  buyer_cpf: string;
  buyer_marital_status: string;
  buyer_address: string;
  buyer_cep: string;
  buyer_email: string;
  status: ContractStatus;
  status_display: string;
  created_at: string;
}

// ─── Generic Notes ────────────────────────────────────────────────────────────

export type NoteColor = 'default' | 'yellow' | 'green' | 'blue' | 'pink' | 'purple';

export interface GenericNote {
  id: number;
  title: string;
  content: string;
  color: NoteColor;
  is_pinned: boolean;
  author_name: string;
  created_at: string;
  updated_at: string;
}

export type TemplateCategory = 'MARKETING' | 'UTILITY' | 'AUTHENTICATION';
export type TemplateStatus = 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'PAUSED' | 'DISABLED';
export type TemplateHeaderType = 'NONE' | 'TEXT' | 'IMAGE' | 'VIDEO' | 'DOCUMENT';

export interface MessageTemplate {
  id: number;
  name: string;
  language: string;
  category: TemplateCategory;
  status: TemplateStatus;
  status_display: string;
  header_type: TemplateHeaderType;
  header_type_display: string;
  header_text: string;
  header_media_url: string;
  body_text: string;
  footer_text: string;
  meta_template_id: string;
  rejection_reason: string;
  channel: number | null;
  channel_name: string;
  variable_count: number;
  created_at: string;
  updated_at: string;
}

// ─── Kennel ───────────────────────────────────────────────────────────────────

export type DogSex = 'M' | 'F';
export type DogStatus = 'available' | 'reserved' | 'sold' | 'own' | 'deceased';
export type HealthRecordType = 'vaccine' | 'deworming' | 'exam' | 'other';

export interface DogMedia {
  id: number;
  file: string;
  file_url: string | null;
  caption: string;
  uploaded_at: string;
}

export interface DogHealthRecord {
  id: number;
  dog: number;
  record_type: HealthRecordType;
  record_type_display: string;
  description: string;
  date: string;
  next_date: string | null;
  vet: string;
  notes: string;
  created_at: string;
}

export interface Dog {
  id: number;
  name: string;
  breed: string;
  sex: DogSex;
  sex_display: string;
  birth_date: string | null;
  color: string;
  pedigree_number: string;
  microchip: string;
  tattoo: string;
  status: DogStatus;
  status_display: string;
  price: string | null;
  father: number | null;
  father_name: string;
  mother: number | null;
  mother_name: string;
  origin_litter: number | null;
  cover_photo: string | null;
  notes: string;
  media: DogMedia[];
  health_records: DogHealthRecord[];
  created_at: string;
  updated_at: string;
}

export interface LitterMedia {
  id: number;
  file: string;
  file_url: string | null;
  caption: string;
  uploaded_at: string;
}

export interface LitterHealthRecord {
  id: number;
  litter: number;
  record_type: HealthRecordType;
  record_type_display: string;
  description: string;
  date: string;
  next_date: string | null;
  vet: string;
  notes: string;
  created_at: string;
}

export interface Litter {
  id: number;
  name: string;
  father: number | null;
  father_name: string;
  mother: number | null;
  mother_name: string;
  mating_date: string | null;
  expected_birth_date: string | null;
  birth_date: string | null;
  male_count: number;
  female_count: number;
  total_count: number;
  cbkc_number: string;
  notes: string;
  cover_photo: string | null;
  puppies: Dog[];
  media: LitterMedia[];
  health_records: LitterHealthRecord[];
  created_at: string;
  updated_at: string;
}
