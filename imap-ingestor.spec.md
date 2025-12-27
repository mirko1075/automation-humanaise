# IMAP Ingestor – Technical Specification (Edilcos)

## Scopo
Implementare un modulo di ingresso email basato su IMAP polling che sostituisce il Gmail Webhook.
Il modulo deve:
- recuperare nuove email in modo incrementale
- garantire deduplica e idempotenza
- normalizzare contenuto e allegati
- fungere da ingresso unico per la pipeline Edilcos

---

## Contesto Architetturale

Ingressi supportati:
- IMAP (primary)
- Gmail Webhook (fallback / future)

Pipeline:
IMAP Poller → Normalizer → Classifier → Dispatcher → Business Flow

Il modulo IMAP NON deve contenere logica di business.

---

## Requisiti Funzionali

### Connessione IMAP
- Supporto IMAP4 + SSL
- Configurazione per account:
  - host
  - port
  - username
  - password / app password
  - folder (default: INBOX)

### Fetch Incrementale
- Uso di UID + UIDVALIDITY
- Query:
  UID SEARCH UID {last_seen_uid+1}:*
- Download solo nuove email

### Deduplica
Chiave primaria consigliata:
- (imap_account_id, uidvalidity, uid)

Fallback:
- Message-ID header

Il sistema deve essere idempotente.

### Parsing Email
Estrarre:
- headers (From, To, Subject, Date, Message-ID)
- body:
  - preferenza: text/plain
  - fallback: text/html (sanitizzato)
- allegati:
  - nome file
  - MIME type
  - size
  - contenuto binario

### Allegati
- Upload su storage esterno (S3 / OneDrive / FS)
- Persistenza solo metadata + URL nel DB

---

## Requisiti Non Funzionali

- Polling configurabile (default: 3 minuti)
- Safe retry su errori di rete
- Timeout configurabile
- Logging strutturato
- Nessuna perdita di messaggi accettabile

---

## Modello Dati (minimo)

### imap_accounts
- id
- name
- host
- port
- username
- encrypted_password
- folder
- active

### imap_mailbox_state
- imap_account_id
- uidvalidity
- last_seen_uid
- last_checked_at

### ingested_messages
- id
- imap_account_id
- uid
- uidvalidity
- message_id
- subject
- from
- received_at
- raw_headers
- normalized_payload_ref

---

## Flusso di Esecuzione

1. Scheduler attiva poller
2. Connessione IMAP
3. Verifica UIDVALIDITY
4. Ricerca nuove email
5. Per ogni email:
   - deduplica
   - parsing
   - salvataggio
   - invio al Normalizer
6. Aggiornamento mailbox state

---

## Edge Cases da Gestire

- Reset UIDVALIDITY → full rescan controllato
- Email senza Message-ID
- Email solo HTML
- Allegati > size limite
- Connessione IMAP instabile

---

## Output verso pipeline
Payload normalizzato JSON compatibile con:
- Normalizer
- Classifier

Il modulo NON decide nulla.

# Appendix A — Normalizer Contract

## Obiettivo
Definire un payload di ingresso **stabile e agnostico dal canale**
che rappresenti qualunque messaggio in ingresso al sistema Edilcos
(email IMAP, Gmail webhook, WhatsApp, forward manuali, future integrazioni).

Questo contratto è il **confine architetturale** tra:
- Ingestor (responsabile di acquisizione, dedupe, parsing)
- Pipeline a valle (normalizer → classifier → dispatcher)

---

## Naming Canonico

Il payload si chiama:

InboundMessage

Ogni ingestor DEVE produrre un `InboundMessage`.
Nessun ingestor deve conoscere il business.

---

## Schema Logico (JSON)

```json
{
  "source": {
    "channel": "imap",
    "provider": "generic-imap",
    "account_id": "imap_account_1",
    "external_id": "UID:12345",
    "received_at": "2025-03-21T10:15:30Z"
  },

  "message": {
    "subject": "Richiesta preventivo ristrutturazione",
    "from": {
      "name": "Mario Rossi",
      "address": "mario.rossi@example.com"
    },
    "to": [
      {
        "name": "Edilcos",
        "address": "info@edilcos.it"
      }
    ],
    "body": {
      "type": "text/plain",
      "content": "Buongiorno, vorrei un preventivo per..."
    }
  },

  "attachments": [
    {
      "filename": "planimetria.pdf",
      "mime_type": "application/pdf",
      "size": 245678,
      "storage_url": "s3://edilcos/attachments/abc123.pdf"
    }
  ],

  "raw": {
    "headers_ref": "db://raw_headers/abc123"
  },

  "ingestion": {
    "ingested_at": "2025-03-21T10:15:45Z",
    "ingestor": "imap-ingestor",
    "version": "1.0.0"
  }
}
