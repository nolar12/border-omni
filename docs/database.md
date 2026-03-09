# Database — Border Omni

Banco: **MySQL 8** — `border_leads`  
Host: `localhost:3306` — User: `root` / Senha: `cello12`

---

## Tabelas

### `organizations`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| name | varchar(200) | Nome da organização |
| api_key | char(32) | UUID usado como org_key no webhook |
| is_active | tinyint(1) | |
| created_at | datetime | |
| updated_at | datetime | |

### `user_profiles`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| user_id | bigint FK→auth_user | |
| organization_id | bigint FK→organizations | |
| role | varchar(50) | admin, agent |
| created_at | datetime | |

### `plans`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| name | varchar(50) | free, pro, enterprise |
| max_leads | int | Limite de leads |
| max_agents | int | Limite de agentes |
| max_channels | int | Limite de canais |
| price_monthly | decimal(10,2) | |
| is_active | tinyint(1) | |
| created_at | datetime | |

### `subscriptions`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| organization_id | bigint FK | OneToOne |
| plan_id | bigint FK | |
| status | varchar(20) | active, trial, expired, cancelled |
| trial_ends_at | datetime | |
| current_period_end | datetime | |
| created_at / updated_at | datetime | |

### `leads`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| organization_id | bigint FK | |
| phone | varchar(30) | Número WhatsApp |
| full_name | varchar(200) nullable | |
| instagram_handle | varchar(100) nullable | |
| city / state | varchar nullable | |
| housing_type | varchar(10) | HOUSE, APT, OTHER |
| daily_time_minutes | int nullable | |
| experience_level | varchar(20) | FIRST_DOG, HAD_DOGS, HAD_HIGH_ENERGY |
| budget_ok | varchar(10) | YES, NO, MAYBE |
| timeline | varchar(20) | NOW, THIRTY_DAYS, SIXTY_PLUS |
| purpose | varchar(20) | COMPANION, SPORT, WORK |
| has_kids / has_other_pets | tinyint(1) | |
| score | int | 0–100 |
| tier | varchar(1) | A, B, C |
| status | varchar(20) | NEW, QUALIFYING, QUALIFIED, HANDOFF, CLOSED |
| source | varchar(30) | INSTAGRAM_AD, ORGANIC, OTHER |
| channels_used | varchar(200) | |
| is_ai_active | tinyint(1) | |
| assigned_to_id | bigint FK→auth_user nullable | |
| conversation_state | varchar(50) nullable | Estado atual na máquina de estados |
| created_at / updated_at | datetime | |

### `lead_tags`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| organization_id | bigint FK | |
| name | varchar(100) | |
| color | varchar(20) | Hex color |
| created_at | datetime | |

### `lead_tag_assignments`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| lead_id | bigint FK | |
| tag_id | bigint FK | |
| created_at | datetime | |

### `notes`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| lead_id | bigint FK | |
| author_id | bigint FK→auth_user | |
| text | longtext | |
| created_at | datetime | |

### `conversations`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| lead_id | bigint FK (unique) | OneToOne |
| created_at / updated_at | datetime | |

### `messages`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| conversation_id | bigint FK | |
| direction | varchar(3) | IN (lead→sistema), OUT (sistema→lead) |
| text | longtext | |
| provider_message_id | varchar(200) nullable | ID retornado pela API do WhatsApp |
| created_at | datetime | |

### `quick_replies`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| organization_id | bigint FK | |
| category | varchar(20) | GREETING, PRICING, etc. |
| text | longtext | Suporta {lead_name}, {user_name} |
| shortcut | varchar(50) | Ex: /ola |
| is_active | tinyint(1) | |
| created_at | datetime | |

### `channels_channelprovider`
| Coluna | Tipo | Descrição |
|---|---|---|
| id | bigint PK | |
| organization_id | bigint FK | |
| provider | varchar(20) | whatsapp, instagram |
| app_id | varchar(200) | Meta App ID |
| app_secret | varchar(255) | Meta App Secret (legado) |
| access_token | longtext | Token de acesso permanente |
| phone_number_id | varchar(200) | WhatsApp Phone Number ID |
| business_account_id | varchar(200) | WhatsApp Business Account ID |
| instagram_account_id | varchar(200) | |
| page_id | varchar(200) | |
| webhook_verify_token | varchar(200) | Token de verificação do webhook |
| webhook_url | varchar(500) | URL pública do webhook |
| is_active / is_simulated | tinyint(1) | |
| verification_status | varchar(50) | verified, pending, failed |
| last_verified_at | datetime | |
| created_at / updated_at | datetime | |

---

## Relacionamentos principais

```
organizations
    ├── user_profiles (N)  →  auth_user
    ├── leads (N)
    │       ├── notes (N)
    │       ├── lead_tag_assignments (N)  →  lead_tags
    │       └── conversations (1)
    │               └── messages (N)
    ├── quick_replies (N)
    ├── channels_channelprovider (N)
    └── subscriptions (1)  →  plans
```

---

## Backup

```bash
# Dump completo
mysqldump -u root -pcello12 border_leads > backup_$(date +%Y%m%d).sql

# Restore
mysql -u root -pcello12 border_leads < backup_20260308.sql
```

---

## Notas sobre migração

A tabela `channels_channelprovider` ainda tem a coluna `app_secret` no banco (coluna legada). O model Django não a expõe, mas ela existe fisicamente. Não removê-la evita perda de dados.

As migrações `0002` de `channels`, `conversations` e `leads` foram aplicadas com `--fake` para não remover colunas com dados históricos.
