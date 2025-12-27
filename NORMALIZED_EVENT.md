📘 NormalizedEvent — SPEC DEFINITIVA (v1)
1️⃣ Cos’è (definizione ufficiale)

NormalizedEvent è la rappresentazione strutturata, persistita e riprocessabile
di un evento grezzo (email, webhook, file, messaggio)
dopo classificazione, estrazione e applicazione delle regole.

Non è un’entità di business.
È un artefatto di pipeline.

2️⃣ Cosa NON è (importantissimo)

❌ Non è un preventivo

❌ Non è un cliente

❌ Non è un task

❌ Non è una “decisione finale”

👉 È input stabile per i flussi di business.

3️⃣ Confini concettuali
RawEvent
   ↓
[ Normalizer ]
   ↓
NormalizedEvent
   ↓
[ Router ]
   ↓
Business Flow


Il NormalizedEvent:

non decide

non esegue

non notifica

👉 descrive.

4️⃣ Rappresentazione DB (come lo implementiamo davvero)

Il NormalizedEvent non è una tabella singola, ma un insieme coerente:

🧱 Core
message_classification

campo	significato
message_id	riferimento al raw event
message_type	QUOTE_REQUEST / INFO / SPAM / OTHER
confidence	0–1
model_version	versione LLM
classified_at	timestamp
status	NEW / CONFIRMED / OVERRIDDEN
🧩 Features (estrazione strutturata)
message_features

campo	esempio
customer_name	"Mario Rossi"
email	"mario@…"
phone	"+39…"
location	"Cagliari"
job_type	"ristrutturazione"
budget	15000
raw_json	payload esteso

👉 schema flessibile, per settore.

🧠 Rules evaluation (opzionale ma consigliata)
message_rule_results

rule_id	result	score
R-QUOTE-MIN-FIELDS	pass	1.0
R-BUDGET-PRESENT	fail	0.2

Serve per:

explainability

audit

override manuali

5️⃣ Stati del NormalizedEvent

Non molti. Devono servire.

NEW           → creato dal normalizer
CONFIRMED     → accettato per routing
OVERRIDDEN    → modificato manualmente
DISCARDED     → scartato (spam, noise)


👉 Gli stati NON bloccano il raw event
👉 Servono solo a controllare il routing

6️⃣ Routing: come funziona davvero

Non una tabella.
Non una coda magica.

È una query.

Esempio:

SELECT *
FROM message_classification
WHERE
  message_type = 'QUOTE_REQUEST'
  AND status = 'CONFIRMED'
  AND processed = false;


👉 Questo è il “passaggio di coda”.

Cambiare stato = ripescare.

7️⃣ Perché questo è vendibile (opinione mia)

Mia opinione esplicita:

Questo modello è forte perché:

è provider-agnostic (email, WhatsApp, form)

è LLM-agnostic

è settore-agnostic

è reprocessabile

è auditabile

Puoi vendere:

“We normalize your inbound chaos into structured, explainable events.”

8️⃣ Contratto pubblico (da documentazione)

Ogni modulo downstream può assumere:

{
  "message_type": "QUOTE_REQUEST",
  "confidence": 0.92,
  "features": {
    "customer_name": "Mario Rossi",
    "location": "Cagliari",
    "job_type": "impianto elettrico"
  },
  "source": "email",
  "raw_event_id": "uuid"
}


Non serve sapere come è stato ottenuto.

🧠 ARCHITETTURA A STATI + WORKER (DEFINITIVA)
Principio guida (molto importante)

👉 Il DB è la coda
👉 I worker sono stateless
👉 Cambiare uno stato = riprocessare

Niente RabbitMQ.
Niente Kafka.
Niente magie.

🔁 Visione d’insieme
[ Mail Poller ]
      ↓
  raw_events
      ↓
[ Normalizer Worker ]
      ↓
 normalized_events
      ↓
[ Router Worker ]
      ↓
 business_intents
      ↓
[ Preventivi Worker ]
      ↓
 quotes / actions


Ogni blocco:

legge per stato

scrive nuovo stato

non parla col successivo direttamente

1️⃣ Mail Poller (già fatto ✅)
Input

Mail provider (Graph / IMAP)

Output

raw_events

Stato RawEvent
raw_events.status
-----------------
RECEIVED
FAILED


👉 Non c’è altro
Il poller non decide nulla.

2️⃣ Normalizer Worker (LLM)
Query di ingresso
SELECT *
FROM raw_events
WHERE status = 'RECEIVED'
  AND normalized = false
LIMIT N;

Fa solo:

classificazione

estrazione features

valutazione regole

Scrive:
normalized_events

Stato NormalizedEvent
normalized_events.status
------------------------
NEW          → appena creato
CONFIRMED    → pronto per routing
DISCARDED    → spam / rumore
OVERRIDDEN   → umano ha corretto
ERROR        → LLM failure


👉 Questo è il cuore vendibile del sistema

3️⃣ Router Worker (zero business logic)

Questo worker non capisce il dominio.

Query
SELECT *
FROM normalized_events
WHERE status = 'CONFIRMED'
  AND routed = false;

Fa solo mapping:
QUOTE_REQUEST   → PREVENTIVI
INFO            → CRM
SUPPORT         → TICKETS

Scrive:
business_intents

4️⃣ BusinessIntent (coda logica)
Tabella
business_intents

campo	esempio
intent_type	PREVENTIVO
source_event_id	normalized_event.id
payload	JSON
status	PENDING
attempts	0
Stati
PENDING
PROCESSING
DONE
FAILED


👉 Questa è la vera “queue”

5️⃣ Preventivi Worker (business vero)
Query
SELECT *
FROM business_intents
WHERE intent_type = 'PREVENTIVO'
  AND status = 'PENDING';

Fa:

trova/crea cliente

crea preventivo

decide azioni (email, excel, whatsapp)

Scrive:

quotes

action_queue

aggiorna business_intents.status = DONE

6️⃣ Action Workers (n8n only here 👈)

Qui entra n8n, e SOLO qui.

action_queue
action_queue

type	payload
SEND_EMAIL	{...}
UPDATE_EXCEL	{...}
SEND_WHATSAPP	{...}
Worker BE:

legge PENDING

fa emit_to_n8n

segna DONE / FAILED

👉 n8n non decide, esegue

🔁 RIPROCESSING (killer feature)

Vuoi riprocessare?

Caso	Cosa fai
LLM sbaglia	normalized_events.status = NEW
Regola cambia	status = CONFIRMED
Preventivo errato	business_intents.status = PENDING
Excel sbagliato	action_queue.status = PENDING

Zero codice. Solo DB.

C) DB Preventivi (schema fino a “preventivo nuovo” + lifecycle)
Entità minime (MVP solido)

customers (anagrafica “light”)

quote_requests (richiesta grezza strutturata, derivata dal NormalizedEvent)

quotes (preventivo “lavorabile”)

quote_attachments (allegati collegati)

quote_events (audit timeline)

1) customers
customers
---------
id (uuid pk)
tenant_id

display_name
email
phone
tax_code     -- opzionale
vat_number   -- opzionale

address_line
city
province
zip
country

source_first_seen ENUM('email','whatsapp','manual','import')
first_seen_at
last_seen_at

created_at
updated_at

UNIQUE(tenant_id, email)  -- se email presente
UNIQUE(tenant_id, phone)  -- se phone presente (valuta)

2) quote_requests (il “NUOVO PREVENTIVO” che arriva)

È il ponte tra NormalizedEvent e dominio preventivi.

quote_requests
--------------
id (uuid pk)
tenant_id

normalized_event_id (fk)     -- oppure raw_event_id + classification_id
customer_id (fk nullable)    -- assegnato quando risolvi customer

status ENUM(
  'NEW',            -- appena creato dal preventivi worker
  'TRIAGED',        -- dati minimi ok / assegnato
  'NEEDS_INFO',     -- mancano info
  'CONVERTED',      -- trasformato in Quote
  'REJECTED'        -- non è un preventivo valido
)

urgency ENUM('LOW','MEDIUM','HIGH')
confidence FLOAT

contact_name
contact_email
contact_phone

job_type           -- es: "ristrutturazione", "impianto elettrico"
job_description TEXT
location_text      -- testo libero
address_line
city
province
zip

preferred_date_from
preferred_date_to
budget_min
budget_max

notes TEXT

created_at
updated_at

UNIQUE(tenant_id, normalized_event_id)
INDEX(tenant_id, status, created_at)

3) quotes (preventivo “gestibile”)
quotes
------
id (uuid pk)
tenant_id

quote_request_id (fk UNIQUE)  -- 1 request -> 1 quote (MVP)
customer_id (fk)

status ENUM(
  'DRAFT',          -- appena creato
  'SENT',           -- inviato al cliente
  'ACCEPTED',       -- accettato
  'REJECTED',       -- rifiutato
  'EXPIRED',        -- scaduto
  'CANCELLED'
)

title
summary TEXT
total_amount NUMERIC(12,2) NULL
currency TEXT DEFAULT 'EUR'

valid_until DATE NULL
assigned_to_user_id UUID NULL   -- se avrai utenti/operatori

external_ref_excel TEXT NULL    -- id riga excel, se usi excel come output
folder_path TEXT NULL           -- folder OneDrive creata dal BE

created_at
updated_at

INDEX(tenant_id, status, created_at)

4) quote_attachments

Qui l’ideale è salvare solo metadata + storage_url (OneDrive/S3). Se per ora hai raw in DB ok, ma meglio URL.

quote_attachments
-----------------
id (uuid pk)
tenant_id

quote_request_id (fk)
quote_id (fk NULL)

filename
mime_type
size_bytes
storage_url TEXT NULL
sha256 TEXT NULL

created_at

INDEX(tenant_id, quote_request_id)

5) quote_events (audit timeline)

Serve tantissimo per debug e per UI.

quote_events
------------
id (uuid pk)
tenant_id

quote_request_id (fk)
quote_id (fk NULL)

event_type TEXT         -- 'created', 'triaged', 'needs_info', 'converted', 'sent', ...
actor_type ENUM('system','user','n8n')
actor_id TEXT NULL

payload JSONB NULL
created_at

INDEX(tenant_id, quote_request_id, created_at)

Stati e flusso (C)
Creazione “nuovo preventivo”

input: business_intents(PREVENTIVO, PENDING)

worker: Preventivi Worker

output:

quote_requests(status=NEW)

quote_events(created)

Conversione a quote

trigger: operatore o regola

quote_requests.status = CONVERTED

crea quotes(status=DRAFT)

Azioni (n8n)

p.es. quotes.status = SENT quando action ok

log su quote_events(sent) + action_executions

D) Rules Engine configurabile (vendibile)
Obiettivo

regole per classificazione + routing + triage

custom per tenant

versionate

spiegabili (audit)

Livelli di regole (consiglio)

Normalization Rules (decidono type/urgency e completano campi)

Triage Rules (decidono: NEW vs NEEDS_INFO, assegnazione, priorità)

Action Rules (decidono quali azioni generare in execution_plans)

Tu hai chiesto “regole personalizzabili”: questa separazione è quella che ti fa vendere “moduli”.

Tabelle rules (core)
rulesets
rulesets
--------
id (uuid pk)
tenant_id
name
scope ENUM('NORMALIZATION','TRIAGE','ACTIONS')
active BOOLEAN
version INT
created_at

rules
rules
-----
id (uuid pk)
tenant_id
ruleset_id (fk)

name
priority INT
enabled BOOLEAN

match JSONB      -- condizioni (DSL)
actions JSONB    -- effetti (DSL)

created_at
updated_at

rule_runs (audit per evento)
rule_runs
---------
id (uuid pk)
tenant_id
normalized_event_id (fk)

ruleset_scope
ruleset_version
executed_at

result JSONB     -- matched rules + why

DSL minima (semplice e potente)
match esempio
{
  "all": [
    { "field": "message_type", "op": "eq", "value": "QUOTE_REQUEST" },
    { "field": "features.city", "op": "in", "value": ["Cagliari","Quartu"] }
  ],
  "any": [
    { "field": "features.budget_min", "op": "gte", "value": 5000 },
    { "field": "urgency", "op": "eq", "value": "HIGH" }
  ]
}

actions esempio (TRIAGE)
[
  { "set": { "quote_request.status": "TRIAGED" } },
  { "set": { "quote_request.urgency": "HIGH" } },
  { "tag": "area-sud" }
]

actions esempio (ACTIONS)
[
  { "enqueue": { "type": "UPDATE_EXCEL", "template": "quotes_v1" } },
  { "enqueue": { "type": "SEND_EMAIL", "template": "ack_v1" } }
]

Esecuzione rules (pattern)

input: normalized_event_id

carichi ruleset attivo per tenant+scope

eval in ordine priority

generi:

update campi (quote_requests)

execution_plans

rule_runs audit