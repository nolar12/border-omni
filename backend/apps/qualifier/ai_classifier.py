import json
import logging
import threading
from datetime import datetime, timedelta

from django.utils import timezone
from openai import OpenAI

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """\
Você é um classificador de intenção de leads para o canil Border Collie Sul.

Sua função é analisar a CONVERSA COMPLETA e retornar uma classificação estruturada.
Não responda ao cliente. Apenas classifique.

REGRA CENTRAL:
Sua análise deve ser baseada PRINCIPALMENTE nas mensagens do LEAD, não nas do atendente.
O que o atendente escreveu é apenas contexto. O que importa é o que o LEAD disse, perguntou e demonstrou.

CONTEXTO:
- Canil focado em vínculo, qualidade de criação e orientação — não venda agressiva
- Clientes com diferentes níveis de maturidade: alguns apenas curiosos
- Comprar um cachorro é uma decisão emocional — reconheça isso nos sinais

ANALISE O HISTÓRICO E RETORNE:

1. intencao_principal: curioso | pesquisando | interessado | pronto_para_comprar | pos_venda | suporte | invalido
2. tipo_interesse: emocional | racional | misto | indefinido
3. nivel_maturidade: frio | morno | quente | muito_quente
4. sensibilidade_preco: baixa | media | alta | indefinido
5. sinais_emocionais: lista de palavras-chave detectadas (ex: ["família", "presente", "criança"])
6. urgencia: baixa | media | alta
7. perfil_cliente: familia | individual | criador | indeciso | nao_identificado
8. probabilidade_conversao: 0-100 (baseado em clareza, profundidade, sinais de compromisso DO LEAD)
9. resumo_intencao: texto curto, 1 linha — o que o cliente quer
10. nivel_risco: nenhum | suspeito | alto_risco
11. motivo_risco: texto curto explicando o padrão de risco detectado (ou "" se nivel_risco = nenhum)

SINAIS POSITIVOS QUE AUMENTAM probabilidade_conversao:
- Futuro do indicativo ("quando eu buscar", "vou preparar") — sinal forte de decisão mental já tomada
- Lead continua engajado após saber o preço — o preço não é objeção
- Lead enviou 2+ mensagens após o preço ser mencionado sem levantar objeção → aceitação implícita do valor → quente (não exige que o lead diga "aceito" — a ausência de objeção e a continuidade da conversa já confirmam)
- Lead enviou 1 mensagem após o preço sem objeção → sem resistência ao valor, tendência quente
- Perguntas sobre LOGÍSTICA DE COMPRA (frete, entrega na cidade X, valor do transporte) → quente
- Perguntas sobre FORMA DE PAGAMENTO (cartão, parcelamento, entrada, PIX, restante) → quente
- Perguntas sobre vacinas, chip, documentação → pensamento de implementação → quente
- "ainda tem?", "pode reservar?" — aversão a perder → muito_quente
- 3+ perguntas do lead em sequência — micro-comprometimentos em cadeia → quente
- Lead respondeu rapidamente após mensagem do atendente — alto engajamento
- Lead enviou muitas mensagens (5+) com conteúdo real → alto engajamento
- "vou ver com minha esposa/família/marido" → decisão familiar em curso → quente (não é objeção, é processo)
- Lead perguntou sobre TANTO preço QUANTO logística na mesma conversa → muito_quente

SINAIS EMOCIONAIS ESPECÍFICOS DE PET:
- "é um presente para minha filha/esposa/filho" → alta intenção emocional
- "perdi meu cachorro", "faz tempo que quero" → vínculo emocional acumulado
- "minha família adorou a foto" → decisão coletiva em andamento
- linguagem de entusiasmo: "que lindo!", "sempre sonhei" → HOT emocional

REGRA DE MATURIDADE — USE COMO REFERÊNCIA:
- frio: apenas curiosidade inicial, sem perguntas específicas
- morno: já pesquisando, fez 1-2 perguntas sobre preço ou disponibilidade
- quente: perguntou sobre logística, pagamento, entrega, detalhes do filhote específico — PRÓXIMO DA DECISÃO
- muito_quente: falou em reserva, urgência, data, ou combinou próximo passo

SINAIS NEGATIVOS QUE DIMINUEM probabilidade_conversao:
- lead_replied_after_attendant = não → classificação MÁXIMA: frio, probabilidade máxima 15
- Lead enviou apenas 1 ou 2 mensagens e não fez perguntas reais → frio
- Atendente enviou 2+ mensagens no final da conversa sem nenhuma resposta do lead → conversa esfriou
- Lead só responde "ok", "entendi", "obrigado", "boa tarde" sem perguntar nada → engajamento superficial
- Respostas do lead com menos de 10 caracteres em média → desinteresse
- Longo silêncio do lead após apresentação de informações importantes → perda de interesse

PADRÃO DE ESCRITA — INDICADOR DE CAPACIDADE DE COMPRA:
O produto tem valor alto (R$ 3.000). A escrita do lead é um sinal indireto de perfil socioeconômico e portanto de capacidade de compra.

Use esta escala:
- Erros leves ou pontuais (1-2 por conversa, palavras parecidas, autocorrect) → normal, ignore completamente
- Erros moderados (3-4 erros, mas o sentido está claro) → leve sinal negativo, reduz probabilidade_conversao em até 10 pontos
- Erros graves e sistemáticos (palavras completamente deformadas, múltiplos erros por mensagem, padrão consistente de baixa literacia escrita) → sinal negativo forte
  → reduz probabilidade_conversao em 20-30 pontos
  → se a conversa for curta (≤ 4 mensagens do lead) E com erros graves → classificar como frio, probabilidade máxima 20
  → se a conversa for mais longa mas com erros graves → manter morno com probabilidade reduzida
  → registre no resumo_intencao: "Erros de escrita graves reduzem perfil de compra."

EXEMPLOS DE ERROS GRAVES (devem impactar a classificação):
- "Femia quau valor" em vez de "Fêmea qual o valor"
- "Quau indereço" em vez de "Qual o endereço"
- Palavras completamente irreconhecíveis, inversão de sílabas, ausência de estrutura
- Padrão de 2+ mensagens com esse nível de deformação ortográfica

EXEMPLOS DE ERROS NORMAIS (não impactam):
- Falta de acentuação ("voce" em vez de "você")
- Troca de uma letra ("entrnegar" em vez de "entregar")
- Abreviações de WhatsApp ("vc", "tb", "pq")

IMPORTANTE:
- Avalie o PADRÃO ao longo de toda a conversa, não um erro isolado
- Nunca use isso como único critério — combine sempre com os outros sinais
- Em caso de dúvida entre morno e frio com erros graves → prefira frio

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLASSIFICAÇÃO DE RISCO (campos nivel_risco e motivo_risco)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUANDO usar "alto_risco":
Exige PADRÃO CONSISTENTE ao longo da conversa, não mensagem isolada.
Classifique como "alto_risco" apenas se houver um ou mais dos seguintes:

COMPORTAMENTO DE RISCO FÍSICO:
- Pede visita ao canil de forma muito prematura (primeiras mensagens, sem contexto de compra estabelecido)
- Insiste em marcar visita imediata ("agora", "hoje") sem demonstrar intenção real de compra
- Pressiona por endereço exato ou localização do canil sem justificativa de compra clara
- Tenta acelerar o contato presencial forçando encontros fora do fluxo normal de venda

COMPORTAMENTO SUSPEITO:
- Ignora perguntas do atendente repetidamente (2+ vezes) e desvia para tópicos irrelevantes
- Respostas incoerentes ou desconexas com o contexto da conversa de forma consistente
- Padrão de comunicação artificial, robótico ou claramente gerado por script
- Combinação de comunicação confusa + urgência sem sentido lógico

BAIXA CONFIABILIDADE / MÁ-FÉ:
- Tentativa de extrair informações sensíveis (localização, endereço, horários do canil) sem progressão natural de compra
- Comportamento que sugere golpe, reconhecimento de padrão antes de agir, ou teste de vulnerabilidade

QUANDO NÃO usar "alto_risco":
- Não classifique por um único sinal fraco ou ambíguo
- Perguntas sobre transporte, entrega ou localização geral do estado → não são risco
- Curiosidade normal sobre como funciona uma visita → não é risco
- Em dúvida entre "suspeito" e "alto_risco" → use "suspeito"
- Em dúvida se é risco ou não → use "nenhum"

QUANDO usar "suspeito":
- Há 1-2 sinais de risco, mas sem padrão claro o suficiente para "alto_risco"
- Comportamento estranho pontual, mas pode ser apenas falta de habilidade de comunicação

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

REGRAS:
- Não invente informações ausentes na conversa
- Quando há sinais claros de quente (pagamento, logística, decisão em curso), classifique como quente — não seja conservador demais
- Analise a conversa COMO UM TODO, não só a última mensagem
- Não use linguagem emocional ou comercial na sua análise
- DANGER sobrescreve qualquer nível de maturidade — se nivel_risco = alto_risco, retorne isso mesmo que o lead pareça quente

MÉTRICAS DE ENGAJAMENTO OBSERVADAS:
{engagement_metrics}

HISTÓRICO DA CONVERSA (anotado com tempo de resposta):
{conversation_history}

Retorne APENAS JSON válido, sem markdown:
{{
  "intencao_principal": "",
  "tipo_interesse": "",
  "nivel_maturidade": "",
  "sensibilidade_preco": "",
  "sinais_emocionais": [],
  "urgencia": "",
  "perfil_cliente": "",
  "probabilidade_conversao": 0,
  "resumo_intencao": "",
  "nivel_risco": "nenhum",
  "motivo_risco": ""
}}"""

MATURIDADE_TO_CLASSIFICATION = {
    'muito_quente': 'HOT_LEAD',
    'quente': 'HOT_LEAD',
    'morno': 'WARM_LEAD',
    'frio': 'COLD_LEAD',
}

# Palavras-chave que indicam possível risco — dispara análise completa mesmo em early-return.
# Inclui grafias erradas/fonéticas comuns para não ser driblado por erros de digitação.
_DANGER_KEYWORDS = [
    # endereço e variações de erro
    'endereço', 'endereco', 'indereço', 'indereco', 'endereço', 'edereco', 'endreço',
    # localização
    'localização', 'localizacao', 'localizaçao', 'onde fica exatamente', 'onde ficam',
    # visita presencial
    'posso ir aí', 'posso ir ai', 'posso ir até', 'posso ir ate',
    'quero ir buscar', 'vou buscar pessoalmente', 'vou ai', 'vou aí',
    'visita agora', 'visita hoje', 'ir buscar hoje', 'ir buscar agora',
    'ir até vocês', 'ir ate voces', 'ir buscar eu mesmo',
    # pedido de endereço
    'me passa o endereço', 'me passa o endereco', 'me manda o endereço',
    'qual o endereço', 'qual endereço', 'quau endereço', 'qual indereço',
    'quau indereço', 'quau indereco', 'qual o indereco',
]


class AILeadClassifier:
    def __init__(self, lead, agent_config):
        self.lead = lead
        self.agent_config = agent_config
        self._openai = None

    def _get_openai(self) -> OpenAI:
        if not self._openai:
            self._openai = OpenAI(api_key=self.agent_config.openai_api_key)
        return self._openai

    def classify(self) -> dict | None:
        try:
            from apps.conversations.models import Message
            messages = list(
                Message.objects
                .filter(conversation__lead=self.lead)
                .order_by('created_at')
                .values('direction', 'text', 'created_at')
            )

            if not messages:
                return None

            # --- Guarda pré-IA ---
            early_result = self._pre_classify_guard(messages)
            if early_result is not None:
                return early_result

            history = self._build_annotated_history(messages)
            if not history.strip():
                return None

            metrics = self._compute_engagement_metrics(messages)
            metrics_str = self._format_metrics(metrics)
            prompt = CLASSIFIER_SYSTEM_PROMPT.format(
                engagement_metrics=metrics_str,
                conversation_history=history,
            )
            response = self._get_openai().chat.completions.create(
                model='gpt-4o',
                messages=[{'role': 'system', 'content': prompt}],
                temperature=0.1,
                max_tokens=600,
                response_format={'type': 'json_object'},
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            return result
        except Exception as e:
            logger.warning(f'AILeadClassifier.classify error: {e}')
            return None

    def _has_danger_keywords(self, messages: list) -> bool:
        """Verifica se qualquer mensagem do lead contém palavras de risco."""
        all_text = ' '.join((m['text'] or '').lower() for m in messages if m['direction'] == 'IN')
        return any(kw in all_text for kw in _DANGER_KEYWORDS)

    def _pre_classify_guard(self, messages: list) -> dict | None:
        """
        Avalia condições simples que dispensam chamada à IA.
        Retorna resultado direto quando a situação é clara o suficiente.
        Nunca bloqueia quando há sinais de risco — deixa a IA analisar.
        """
        in_msgs = [m for m in messages if m['direction'] == 'IN']

        # Nenhuma mensagem do lead
        if not in_msgs:
            return None

        # Se há palavras-chave de risco, sempre deixa a IA avaliar
        if self._has_danger_keywords(messages):
            return None

        # Verifica se o lead respondeu alguma vez após uma mensagem do atendente
        lead_replied_after_attendant = False
        last_out_ts = None
        for m in messages:
            if m['direction'] == 'OUT':
                last_out_ts = m['created_at']
            elif m['direction'] == 'IN' and last_out_ts is not None:
                lead_replied_after_attendant = True
                break

        # Lead com apenas 1 mensagem e bot/atendente ainda não obteve resposta:
        # não classifica ainda — mantém como "novo" (null) aguardando interação real.
        if len(in_msgs) <= 1 and not lead_replied_after_attendant:
            return {}  # dict vazio = não atualizar classificação

        # Lead enviou até 2 mensagens curtas e nunca respondeu ao atendente
        if len(in_msgs) <= 2 and not lead_replied_after_attendant:
            avg_len = sum(len(m['text'] or '') for m in in_msgs) / len(in_msgs)
            if avg_len < 30:
                return {}  # dict vazio = não atualizar classificação

        return None  # Deixa passar para a IA

    def _build_annotated_history(self, messages: list) -> str:
        lines = []
        prev_out_time = None
        for msg in messages:
            ts = msg['created_at']
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)

            hour_min = ts.strftime('%H:%M')
            direction = msg['direction']
            text = (msg['text'] or '').strip()

            if not text or (text.startswith('[') and text.endswith(']')):
                continue

            if direction == 'IN' and prev_out_time is not None:
                delta_minutes = int((ts - prev_out_time).total_seconds() / 60)
                label = f'[{hour_min} +{delta_minutes}min] LEAD'
            elif direction == 'IN':
                label = f'[{hour_min}] LEAD'
            else:
                label = f'[{hour_min}] ATENDENTE'
                prev_out_time = ts

            lines.append(f'{label}: {text}')

        return '\n'.join(lines)

    def _compute_engagement_metrics(self, messages: list) -> dict:
        response_times = []
        msg_lengths_in = []
        engaged_after_price = False
        price_keywords = ['r$', 'reais', 'preço', 'valor', 'custa', 'custo']
        last_out_time = None
        lead_replied_after_attendant = False
        unanswered_tail = 0
        lead_messages_beyond_first = 0
        first_in_seen = False
        price_mentioned_in_conversation = False
        messages_after_price_mention = 0

        for msg in messages:
            ts = msg['created_at']
            direction = msg['direction']
            text = (msg['text'] or '').lower()

            if direction == 'OUT':
                last_out_time = ts
                unanswered_tail += 1
                if any(kw in text for kw in price_keywords):
                    price_mentioned_in_conversation = True
            elif direction == 'IN':
                unanswered_tail = 0  # Reset: lead respondeu
                msg_lengths_in.append(len(msg['text'] or ''))

                if not first_in_seen:
                    first_in_seen = True
                else:
                    lead_messages_beyond_first += 1

                if last_out_time is not None:
                    lead_replied_after_attendant = True
                    delta = (ts - last_out_time).total_seconds() / 60
                    response_times.append(delta)

                # Conta mensagens do lead após o preço ter sido mencionado em qualquer OUT
                if price_mentioned_in_conversation:
                    messages_after_price_mention += 1

        # Engajamento real após preço: 2+ mensagens sem objeção = aceitação implícita
        if price_mentioned_in_conversation and messages_after_price_mention >= 2:
            engaged_after_price = True

        avg_response_min = round(sum(response_times) / len(response_times), 1) if response_times else None
        avg_msg_length = round(sum(msg_lengths_in) / len(msg_lengths_in), 0) if msg_lengths_in else 0
        total_in = len(msg_lengths_in)

        return {
            'avg_response_min': avg_response_min,
            'avg_msg_length': int(avg_msg_length),
            'total_messages_from_lead': total_in,
            'engaged_after_price': engaged_after_price,
            'lead_replied_after_attendant': lead_replied_after_attendant,
            'unanswered_tail': unanswered_tail,
            'lead_messages_beyond_first': lead_messages_beyond_first,
            'price_mentioned_in_conversation': price_mentioned_in_conversation,
            'messages_after_price_mention': messages_after_price_mention,
        }

    def _format_metrics(self, metrics: dict) -> str:
        lines = []
        if metrics.get('avg_response_min') is not None:
            avg = metrics['avg_response_min']
            label = 'muito rápido' if avg < 5 else ('rápido' if avg < 15 else ('moderado' if avg < 60 else 'lento'))
            lines.append(f'- Tempo médio de resposta do lead: {avg} min ({label})')
        lines.append(f"- Comprimento médio das mensagens do lead: {metrics.get('avg_msg_length', 0)} caracteres")
        lines.append(f"- Total de mensagens enviadas pelo lead: {metrics.get('total_messages_from_lead', 0)}")
        lines.append(f"- Mensagens além da primeira (engajamento real): {metrics.get('lead_messages_beyond_first', 0)}")
        replied = metrics.get('lead_replied_after_attendant', False)
        lines.append(f"- Lead respondeu ao atendente: {'sim' if replied else 'NÃO — sinal negativo forte'}")
        tail = metrics.get('unanswered_tail', 0)
        if tail > 0:
            lines.append(f"- Mensagens do atendente sem resposta no final da conversa: {tail} — conversa esfriou")
        price_mentioned = metrics.get('price_mentioned_in_conversation', False)
        n_after = metrics.get('messages_after_price_mention', 0)
        engaged = metrics.get('engaged_after_price', False)
        if price_mentioned:
            if n_after >= 2:
                lines.append(
                    f"- Lead enviou {n_after} mensagens após o preço ser mencionado sem levantar objeção"
                    " — aceitação implícita do valor, sinal forte de intenção"
                )
            elif n_after == 1:
                lines.append(
                    "- Lead enviou 1 mensagem após o preço ser mencionado sem levantar objeção"
                    " — sem resistência ao valor, mas ainda inconclusivo"
                )
            else:
                lines.append("- Preço foi mencionado na conversa mas lead ainda não respondeu após isso")
        else:
            lines.append("- Preço não foi mencionado na conversa ainda")
        if engaged:
            lines.append("- Engajamento confirmado após preço: sim — sinal forte de intenção de compra")
        return '\n'.join(lines)

    def _map_to_db(self, result: dict):
        # Dict vazio = lead novo sem dados suficientes — não altera classificação
        if not result:
            logger.info(f'AILeadClassifier: lead {self.lead.pk} → sem classificação (aguardando interação)')
            return

        nivel = result.get('nivel_maturidade', '')
        nivel_risco = result.get('nivel_risco', 'nenhum')

        # DANGER sobrescreve qualquer classificação de maturidade
        if nivel_risco == 'alto_risco':
            classification = 'DANGER_LEAD'
        else:
            classification = MATURIDADE_TO_CLASSIFICATION.get(nivel)

        score = result.get('probabilidade_conversao')

        update_fields = {'ai_profile': result}
        if classification:
            update_fields['lead_classification'] = classification
        if score is not None:
            update_fields['score'] = int(score)

        from apps.leads.models import Lead
        Lead.objects.filter(pk=self.lead.pk).update(**update_fields)
        logger.info(
            f'AILeadClassifier: lead {self.lead.pk} → '
            f'{classification or "sem classificação"} '
            f'(prob={score}, maturidade={nivel}, risco={nivel_risco})'
        )


def run_ai_classification_async(lead, org):
    """Lança classificação em background thread — nunca bloqueia o webhook."""
    def _run():
        try:
            cfg = org.agent_config
            if not getattr(cfg, 'openai_api_key', None):
                return
            classifier = AILeadClassifier(lead, cfg)
            result = classifier.classify()
            if result:
                classifier._map_to_db(result)
        except Exception as e:
            logger.warning(f'run_ai_classification_async error: {e}')

    threading.Thread(target=_run, daemon=True).start()
