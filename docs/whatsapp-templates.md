# Templates de Mensagem WhatsApp — Guia Completo

Templates são mensagens pré-aprovadas pela Meta usadas para iniciar conversas com clientes (janela de 24h expirada) e em campanhas em massa.

---

## Tipos de template e onde criar

| Tipo de cabeçalho | Criar no sistema | Criar no Business Manager |
|---|---|---|
| Sem cabeçalho | ✅ | ✅ |
| Texto no cabeçalho | ✅ | ✅ |
| **Imagem no cabeçalho** | ⚠️ via vinculação | ✅ |
| **Vídeo no cabeçalho** | ⚠️ via vinculação | ✅ |
| **Documento no cabeçalho** | ⚠️ via vinculação | ✅ |

> **Por que não funciona direto via API para mídia?**
> A API da Meta (v22.0) exige que templates com cabeçalho de mídia (imagem/vídeo/documento) usem um "media handle" obtido por um processo de upload específico (Resumable Upload API). Esse endpoint retorna erro com o tipo de token de acesso utilizado no plano atual. Templates de texto puro funcionam normalmente via API.

---

## Fluxo 1 — Template de texto (tudo aqui no sistema)

1. Acesse **Templates de Mensagem** no menu lateral
2. Clique em **Novo Template**
3. Preencha:
   - **Nome**: snake_case, apenas letras minúsculas e underscores (ex: `primeiro_envio`)
   - **Categoria**: Marketing / Utilidade / Autenticação
   - **Idioma**: Português (BR)
   - **Cabeçalho**: selecione `Texto` ou `Sem cabeçalho`
   - **Corpo**: texto principal — use `{{1}}`, `{{2}}` para variáveis dinâmicas
   - **Rodapé**: opcional
4. Clique em **Salvar rascunho** ou **Enviar para aprovação**
5. Se enviou para aprovação, o status muda para `Pendente`
6. A Meta aprova em minutos a algumas horas e o webhook atualiza o status automaticamente

---

## Fluxo 2 — Template com vídeo/imagem (Business Manager + vinculação)

### Passo 1 — Criar no sistema como rascunho

1. Acesse **Templates de Mensagem** → **Novo Template**
2. Preencha nome, categoria, idioma e corpo normalmente
3. No **Cabeçalho**, selecione `Vídeo` (ou Imagem/Documento)
4. Faça upload do arquivo de mídia usando o botão de anexo
5. Clique em **Salvar rascunho**

### Passo 2 — Criar no Meta Business Manager

1. Acesse [business.facebook.com](https://business.facebook.com)
2. Menu lateral → **WhatsApp Manager** → **Templates de mensagem**
3. Clique em **Criar template**
4. Use **exatamente o mesmo nome** que você usou no sistema (snake_case)
5. Selecione a mesma categoria e idioma
6. No cabeçalho, selecione **Vídeo** e faça upload do vídeo diretamente
7. Cole o mesmo texto do corpo no campo correspondente
8. Adicione rodapé se houver
9. Clique em **Enviar para aprovação**

### Passo 3 — Obter o ID da Meta

Após criar, o ID do template aparece em dois lugares:

**Opção A — URL do navegador:**
```
https://business.facebook.com/wa/manage/message-templates/?waba_id=...&template_id=1234567890123456
```
O número após `template_id=` é o ID.

**Opção B — API:**
```bash
curl "https://graph.facebook.com/v22.0/{business_account_id}/message_templates?fields=id,name,status" \
  -H "Authorization: Bearer {access_token}"
```

### Passo 4 — Vincular o ID no sistema

1. Volte para **Templates de Mensagem** no sistema
2. No card do template (status: Rascunho), clique em **Vincular ID da Meta**
3. Cole o ID numérico obtido no passo anterior
4. Clique em **Vincular**
5. O sistema consulta a API da Meta, verifica o template e atualiza o status automaticamente

Após vinculado, o template fica disponível para uso em campanhas assim que for aprovado pela Meta.

---

## Status dos templates

| Status | Cor | Descrição |
|---|---|---|
| `Rascunho` | Cinza | Salvo localmente, ainda não enviado à Meta |
| `Pendente` | Amarelo | Enviado para revisão, aguardando aprovação |
| `Aprovado` | Verde | Pronto para uso em campanhas |
| `Rejeitado` | Vermelho | Reprovado pela Meta (motivo exibido no card) |
| `Pausado` | Laranja | Pausado pela Meta (geralmente por baixa qualidade) |
| `Desativado` | Cinza escuro | Desativado permanentemente |

---

## Atualização automática de status (webhook)

Quando a Meta aprova, rejeita ou pausa um template, ela envia uma notificação via webhook para:

```
POST https://borderomni.ngrok.app/api/webhooks/whatsapp/
```

O sistema processa o campo `message_template_status_update` e atualiza o status no banco de dados automaticamente — sem precisar recarregar a página ou fazer nada manual.

Para que isso funcione, o Ngrok precisa estar ativo e o webhook deve estar configurado na Meta com a assinatura `message_template_quality_update`.

---

## Sincronização manual

Se precisar forçar a atualização de status:

- **Template individual**: clique no ícone de sincronização (↺) no card do template
- **Todos de uma vez**: clique em **Sincronizar todos** no topo da página

---

## Excluir templates

### No sistema (Border Omni)
Clique no ícone de lixeira no card. O template é removido localmente mas **continua existindo na Meta**.

### Na Meta (Business Manager)
Acesse **WhatsApp Manager → Templates de mensagem**, selecione o template e clique em excluir.

**Restrições da Meta:**
- Templates `APROVADOS` só podem ser excluídos **30 dias após a aprovação**
- O **nome** fica bloqueado por **30 dias** após a exclusão — não é possível criar outro template com o mesmo nome nesse período
- Templates `PENDENTES` ou `REJEITADOS` podem ser excluídos sem restrição de tempo

---

## Variáveis no corpo do template

Use `{{1}}`, `{{2}}`, `{{3}}` etc. no texto do corpo para criar variáveis dinâmicas:

```
Olá {{1}}, tudo bem?
Aqui é {{2}} da Border Collie Sul.
```

Na hora de enviar em campanhas, você preenche os valores de cada variável para cada lead.

A Meta exige que variáveis sejam numeradas sequencialmente começando em 1.

---

## Limites de tamanho

| Campo | Limite |
|---|---|
| Nome | 512 caracteres (snake_case) |
| Corpo | 1.024 caracteres |
| Rodapé | 60 caracteres |
| Cabeçalho texto | 60 caracteres |
| Imagem | JPEG/PNG, máx. 5 MB |
| Vídeo | MP4, máx. 16 MB |
| Documento | PDF, máx. 16 MB |

---

## Dicas

- **Nomes em snake_case**: use apenas letras minúsculas, números e underscores. Ex: `primeiro_envio_ninhada`, `boas_vindas_v2`
- **Não reutilize nomes deletados** nos primeiros 30 dias — a Meta bloqueia
- **Categorias**: prefira `MARKETING` para apresentações de produtos/serviços, `UTILITY` para confirmações e atualizações
- **Qualidade**: templates com muitos bloqueios dos destinatários são pausados ou desativados automaticamente pela Meta — mantenha o conteúdo relevante
