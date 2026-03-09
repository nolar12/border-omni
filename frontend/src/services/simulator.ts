import axios from 'axios';

export const simulatorService = {
  async send(phone: string, text: string, orgKey: string) {
    const { data } = await axios.post('/api/webhooks/whatsapp/', {
      from_phone: phone,
      text,
      provider: 'SIMULATED',
      organization_key: orgKey,
    }, {
      headers: { 'X-ORG-KEY': orgKey },
    });
    return data as {
      received: boolean;
      replies: string[];
      lead: { id: number; tier: string | null; score: number; status: string; is_ai_active: boolean; conversation_state: string };
    };
  },
};
