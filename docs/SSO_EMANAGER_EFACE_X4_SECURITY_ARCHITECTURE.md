# Architettura professionale di identità e accesso

## e-MANAGER ↔ eFace X4

**Stato:** progetto architetturale, non ancora implementato  
**Data:** 29 settembre 2026  
**Priorità:** sicurezza critica  
**Ambito:** login centralizzato, pairing impianti, autorizzazioni, recupero
password, MFA/passkey, sessioni, revoca, audit e continuità offline.

---

## 1. Obiettivo

Realizzare un sistema professionale nel quale e-MANAGER sia la fonte centrale
delle identità e delle autorizzazioni, mentre ogni installazione eFace X4
mantenga una sessione locale sicura e una modalità di recupero controllata.

Il sistema deve garantire:

- un solo account per accedere agli impianti autorizzati;
- nessuna condivisione di password o hash tra e-MANAGER ed eFace X4;
- isolamento completo tra clienti e installazioni;
- autenticazione forte con passkey/MFA;
- recupero password sicuro e verificabile;
- revoca rapida di utenti, dispositivi e sessioni;
- funzionamento locale durante brevi indisponibilità della VPS;
- account tecnico di emergenza separato;
- audit completo delle operazioni sensibili;
- migrazione graduale senza interrompere gli impianti esistenti.

## 2. Principi non negoziabili

1. **Zero password condivise.** eFace X4 non riceve mai la password e-MANAGER.
2. **Zero database condivisi.** eFace non accede direttamente a MySQL sulla VPS.
3. **Isolamento per installazione.** Un token valido per un impianto non deve
   essere valido per un altro.
4. **Chiavi asimmetriche.** Solo e-MANAGER possiede la chiave privata di firma;
   eFace conosce esclusivamente chiavi pubbliche.
5. **Privilegio minimo.** Ogni servizio, utente e token ha soltanto i permessi
   strettamente necessari.
6. **Deny by default.** In assenza di un'autorizzazione esplicita l'accesso viene
   negato.
7. **Nessun segreto nelle URL.** Token, codici e dati personali non devono
   comparire in query string o log.
8. **Recovery non più debole del login.** Il recupero password non deve diventare
   una scorciatoia per aggirare MFA e controlli dell'account.
9. **Revoca verificabile.** La disabilitazione deve propagarsi e produrre prova
   nel registro di audit.
10. **Rollback sempre disponibile.** Ogni fase di migrazione deve poter essere
    annullata senza perdere l'accesso locale all'impianto.

## 3. Stato attuale di eFace X4

eFace X4 dispone già di una base locale utile:

- utenti conservati in `/data/auth/users.json`;
- password derivate con `scrypt` e salt casuale;
- cookie di sessione firmati con HMAC-SHA256;
- file segreti e utenti scritti con permessi `0600`;
- sessioni revocabili tramite `session_version`;
- account attivi/disabilitati;
- ruoli locali `admin` e `user`;
- rate limiting sul login;
- controllo dell'origine per le richieste mutative;
- campi predisposti: `origin`, `external_id`, `provider`, `sync_status`;
- test automatici sull'autenticazione e sulle API protette.

La base locale non deve essere eliminata. Deve essere estesa per fidarsi in modo
controllato di identità emesse da e-MANAGER.

## 4. Architettura di riferimento

```text
                          ┌─────────────────────────────┐
                          │ e-MANAGER Identity Provider │
                          │                             │
                          │ account, MFA, autorizzazioni│
                          │ OIDC, pairing, revoche      │
                          │ audit e recupero password  │
                          └──────────────┬──────────────┘
                                         │ HTTPS/TLS
                        Authorization Code + PKCE / API mTLS
                                         │
             ┌───────────────────────────┼───────────────────────────┐
             │                           │                           │
             v                           v                           v
     ┌──────────────┐            ┌──────────────┐            ┌──────────────┐
     │ eFace X4 A   │            │ eFace X4 B   │            │ eFace X4 C   │
     │ installation│            │ installation│            │ installation│
     │ sessione    │            │ sessione    │            │ sessione    │
     │ locale      │            │ locale      │            │ locale      │
     └──────┬───────┘            └──────┬───────┘            └──────┬───────┘
            │                           │                           │
            v                           v                           v
        Impianto A                  Impianto B                  Impianto C
```

e-MANAGER assume il ruolo di OpenID Provider. eFace X4 è un client OIDC per la
singola installazione e converte l'identità centrale in una sessione locale.

## 5. Standard e protocolli

Utilizzare:

- OAuth 2.1 Authorization Code;
- PKCE con `S256`;
- OpenID Connect;
- `state` casuale per protezione CSRF;
- `nonce` casuale per impedire replay dell'ID token;
- discovery OIDC;
- JWKS con rotazione delle chiavi;
- token firmati EdDSA/Ed25519 oppure RS256;
- TLS 1.2 minimo, preferibilmente TLS 1.3;
- WebAuthn/passkey per autenticazione resistente al phishing;
- TOTP solo come secondo fattore alternativo;
- codici di recupero monouso conservati sotto forma di hash.

Non utilizzare implicit flow, Resource Owner Password Grant, token nella query
string o JWT firmati con una chiave HMAC distribuita agli impianti.

### Endpoint centrali previsti

```text
GET  /.well-known/openid-configuration
GET  /.well-known/jwks.json
GET  /oauth/authorize
POST /oauth/token
POST /oauth/revoke
POST /oauth/introspect              solo per servizi autorizzati
GET  /oidc/userinfo
POST /api/installations/pair/start
POST /api/installations/pair/complete
GET  /api/installations/{id}/users
GET  /api/installations/{id}/revocations
POST /api/installations/{id}/heartbeat
```

## 6. Identificativi

Gli username sono modificabili e non devono essere usati come chiavi primarie.

### Utente centrale

```text
user_id / OIDC sub = usr_<128 bit casuali>
```

### Installazione eFace

```text
installation_id = inst_<128 bit casuali>
```

### Browser o dispositivo attendibile

```text
device_id = dev_<128 bit casuali>
```

### Sessione centrale

```text
session_id = ses_<128 bit casuali>
```

Gli identificativi devono essere casuali, non sequenziali, non contenere dati
personali e non essere riutilizzati.

## 7. Pairing sicuro dell'installazione

### 7.1 Avvio su eFace X4

Al primo avvio eFace:

1. genera `installation_id` e coppia di chiavi locale;
2. conserva la chiave privata in `/data` con permessi `0600`;
3. genera un pairing code casuale monouso;
4. mostra codice, scadenza e impronta della chiave pubblica;
5. non espone credenziali permanenti nell'interfaccia.

Esempio visivo:

```text
Codice associazione: EKX4-739-281
Scadenza: 10 minuti
Impronta: 4E:19:8B:...:A7
```

### 7.2 Conferma su e-MANAGER

Un amministratore autenticato con MFA:

1. seleziona cliente, cartella e nodo;
2. inserisce il codice;
3. confronta l'impronta mostrata da eFace;
4. approva esplicitamente l'associazione;
5. assegna un nome all'installazione;
6. definisce utenti e permessi iniziali.

### 7.3 Requisiti del codice

- almeno 40 bit effettivi di entropia;
- durata massima 10 minuti;
- un solo utilizzo;
- massimo 5 tentativi;
- invalidazione dopo pairing riuscito;
- rate limiting per IP, installazione e account;
- nessuna registrazione del codice completo nei log.

### 7.4 Credenziale macchina

Dopo il pairing, e-MANAGER ed eFace utilizzano autenticazione macchina con una
coppia di chiavi dedicata. Preferire mTLS o richieste firmate. Una compromissione
di una singola installazione non deve consentire di impersonarne altre.

## 8. Login SSO dell'utente

### 8.1 Avvio

1. L'utente apre eFace X4.
2. eFace non trova una sessione valida.
3. L'utente seleziona **Accedi con e-MANAGER**.
4. eFace genera `state`, `nonce` e PKCE verifier/challenge.
5. I valori vengono memorizzati in una sessione server-side temporanea.
6. Il browser viene indirizzato a `/oauth/authorize`.

### 8.2 Autenticazione centrale

e-MANAGER:

1. autentica l'utente;
2. applica MFA/passkey quando richiesto;
3. verifica stato dell'account;
4. verifica che l'installazione sia attiva;
5. verifica l'assegnazione utente-installazione;
6. valuta scadenza, ruolo e condizioni di accesso;
7. mostra chiaramente l'impianto richiesto;
8. genera un authorization code monouso.

### 8.3 Callback

1. Il browser torna sulla redirect URI registrata.
2. eFace verifica `state` con confronto costante.
3. eFace scambia il codice tramite canale server-to-server.
4. e-MANAGER verifica PKCE e redirect URI esatta.
5. eFace verifica firma, `iss`, `aud`, `azp`, `nonce`, `iat` ed `exp`.
6. eFace verifica che `installation_id` coincida con la propria installazione.
7. eFace crea/aggiorna il profilo locale esterno.
8. eFace crea una sessione locale e cancella tutti i dati temporanei.

### 8.4 Token suggerito

```json
{
  "iss": "https://manager.ekonex.it",
  "sub": "usr_74fa8d...",
  "aud": "eface-x4-inst_32ab...",
  "azp": "client_inst_32ab...",
  "installation_id": "inst_32ab...",
  "username": "mario",
  "name": "Mario Rossi",
  "role": "resident",
  "permissions": ["eface:home", "eface:intercom", "eface:media"],
  "auth_time": 1790668800,
  "amr": ["pwd", "webauthn"],
  "nonce": "...",
  "iat": 1790668800,
  "exp": 1790669100,
  "jti": "tok_a9c..."
}
```

Durata ID/access token: 5 minuti. L'access token non viene conservato nel
browser; viene gestito dal backend eFace e sostituito dalla sessione locale.

## 9. Account e autorizzazioni

### 9.1 Ruoli centrali

- `platform_admin`: amministrazione globale e-MANAGER;
- `organization_admin`: gestione dell'organizzazione cliente;
- `installer`: assistenza tecnica autorizzata;
- `owner`: proprietario/responsabile dell'impianto;
- `resident`: utente ordinario dell'impianto;
- `guest`: accesso limitato e a scadenza.

### 9.2 Permessi granulari eFace

```text
eface:home
eface:lights
eface:climate
eface:security:view
eface:security:control
eface:intercom
eface:media
eface:routines
eface:tools:view
eface:tools:admin
eface:users:manage
```

Il ruolo è un insieme predefinito di permessi. Il backend deve verificare i
permessi per ogni operazione sensibile; nascondere un pulsante nel frontend non
costituisce un controllo di sicurezza.

### 9.3 Account locale risultante

```json
{
  "username": "mario",
  "name": "Mario Rossi",
  "role": "resident",
  "active": true,
  "origin": "external",
  "provider": "emanager",
  "external_id": "usr_74fa8d...",
  "sync_status": "active",
  "permissions_version": 7,
  "session_version": 3
}
```

La password centrale e i relativi hash non vengono copiati.

## 10. Password

### 10.1 Memorizzazione centrale

Per nuove password usare Argon2id con parametri calibrati sul server. bcrypt può
essere mantenuto temporaneamente e aggiornato ad Argon2id dopo un login riuscito.

Requisiti:

- minimo 12 caratteri;
- consentire password manager e passphrase fino ad almeno 128 caratteri;
- nessun obbligo di simboli artificiale;
- confronto con elenchi di password compromesse mediante k-anonymity o archivio
  locale, senza trasmettere la password;
- nessun cambio periodico obbligatorio in assenza di compromissione;
- cambio obbligatorio dopo reset amministrativo o incidente;
- messaggi che non rivelino se uno username/email esiste.

### 10.2 Cambio password autenticato

Richiede:

- sessione valida;
- password attuale oppure passkey recente;
- MFA step-up per account privilegiati;
- revoca delle altre sessioni selezionabile, predefinita per gli amministratori;
- notifica email/push dell'avvenuta modifica;
- audit con IP, dispositivo e risultato, mai con la password.

## 11. Recupero password professionale

### 11.1 Richiesta

Endpoint concettuale:

```text
POST /auth/password-recovery/request
```

L'utente fornisce email o username. La risposta è sempre identica:

```text
Se l'account esiste e può essere recuperato, riceverai le istruzioni.
```

Questo impedisce l'enumerazione degli account.

Controlli:

- rate limit per IP, account, dominio email e subnet;
- CAPTCHA adattivo dopo comportamento sospetto;
- ritardo uniforme della risposta;
- audit della richiesta;
- nessuna indicazione dell'esistenza dell'account.

### 11.2 Token di recupero

Generare almeno 256 bit casuali. Nel database salvare soltanto l'hash del token.

Proprietà:

- monouso;
- validità 15 minuti;
- invalidazione di token precedenti;
- associazione a utente e flusso specifico;
- invalidazione dopo cambio email, disabilitazione o reset riuscito;
- mai inserito nei log applicativi o analytics;
- pagina con `Referrer-Policy: no-referrer`;
- nessuna risorsa di terze parti sulla pagina di reset.

Il link email può contenere il token nel fragment, oppure il frontend deve
scambiarlo immediatamente con una sessione di recovery e ripulire l'URL.

### 11.3 Verifica aggiuntiva

Per account con MFA:

- richiedere una passkey registrata, oppure
- TOTP, oppure
- un codice di recupero monouso.

Se tutti i fattori sono persi, entra in gioco il recupero assistito, non un
semplice bypass automatico.

### 11.4 Impostazione nuova password

Al completamento:

1. verificare token, scadenza e stato;
2. applicare la politica password;
3. aggiornare l'hash Argon2id;
4. consumare definitivamente il token;
5. incrementare `session_version`;
6. revocare refresh token e sessioni esistenti;
7. rimuovere dispositivi attendibili se richiesto dal rischio;
8. inviare notifica di sicurezza;
9. registrare l'evento nell'audit log.

### 11.5 Recupero assistito

Perdita contemporanea di password, email e MFA richiede procedura manuale:

- apertura ticket identificato;
- verifica da parte di almeno due operatori per account privilegiati;
- verifica del rapporto con cliente e impianto;
- nessuna richiesta di password esistente;
- emissione di link temporaneo, mai comunicazione di password permanente;
- obbligo di nuova password e nuova MFA;
- revoca completa di sessioni e dispositivi;
- audit con motivazione e operatori coinvolti;
- notifica al titolare attraverso un canale indipendente.

Il supporto non deve poter leggere o impostare direttamente una password nota.

## 12. MFA, passkey e codici di recupero

### 12.1 Passkey

Metodo preferito perché resistente al phishing. La registrazione richiede una
sessione già autenticata e, per account privilegiati, step-up recente.

Ogni credenziale deve registrare:

- credential ID;
- chiave pubblica;
- sign counter;
- nome assegnato dal proprietario;
- data di creazione e ultimo utilizzo;
- trasporti dichiarati;
- eventuale stato revocato.

Non registrare challenge, assertion completa o dati biometrici nei log.

### 12.2 TOTP

Alternativa secondaria:

- secret cifrato at-rest;
- QR mostrato una sola volta;
- conferma con due codici consecutivi prima dell'attivazione;
- tolleranza temporale minima;
- rate limiting rigoroso;
- revoca delle sessioni dopo sostituzione del secret.

### 12.3 Codici di recupero

- 10 codici casuali monouso;
- almeno 128 bit per codice;
- mostrati una sola volta;
- memorizzati esclusivamente come hash;
- rigenerazione invalida tutti i precedenti;
- utilizzo genera notifica immediata;
- per account amministrativi l'uso richiede revisione del rischio.

## 13. Sessioni

### 13.1 Cookie eFace

Usare:

```text
HttpOnly
Secure
SameSite=Lax oppure Strict dove compatibile
Path=/
nessun Domain condiviso
```

Il cookie deve contenere un identificativo opaco o una struttura firmata priva
di informazioni personali. Preferibile mantenere lo stato sensibile server-side.

### 13.2 Durate

- sessione normale: 12 ore;
- inattività massima: 30–60 minuti per pannelli amministrativi;
- dispositivo attendibile: massimo 30–90 giorni, non 5 anni;
- step-up amministrativo: massimo 10 minuti;
- authorization code: 60 secondi;
- access/ID token: 5 minuti;
- refresh token: massimo 30 giorni con rotazione a ogni uso.

### 13.3 Revoca

Revocare in caso di:

- logout globale;
- cambio/reset password;
- account disabilitato;
- ruolo ridotto;
- rimozione dall'impianto;
- revoca del dispositivo;
- pairing annullato;
- installazione compromessa;
- anomalia di sicurezza.

La revoca centrale viene sincronizzata con eFace. In caso di assenza rete, eFace
applica l'ultima politica valida e una finestra offline limitata.

## 14. Funzionamento offline

L'impianto locale non deve smettere di funzionare per una breve indisponibilità
della VPS.

Regole consigliate:

- sessioni già valide continuano per la loro durata locale;
- nessun nuovo utente centrale può entrare senza validazione online;
- permessi critici non possono essere aumentati offline;
- revoche note continuano a essere applicate;
- cache delle autorizzazioni firmata e con scadenza;
- dopo 24 ore senza contatto, richiedere online per operazioni amministrative;
- dopo una soglia configurata mostrare chiaramente stato degradato;
- account locale di emergenza disponibile soltanto secondo policy.

## 15. Account locale di emergenza

Ogni installazione mantiene un account `admin` locale break-glass:

- separato dagli account e-MANAGER;
- password casuale e unica per impianto;
- conservato nel password manager aziendale;
- accessibile preferibilmente solo dalla LAN o via canale tecnico protetto;
- MFA locale dove tecnicamente possibile;
- utilizzo sempre notificato e registrato;
- impossibile da disabilitare senza creare prima un secondo metodo di recupero;
- rotazione dopo ogni utilizzo di emergenza;
- mai sincronizzato o riutilizzato su altri impianti.

Non deve esistere una master password globale valida per tutti gli impianti.

## 16. Sincronizzazione utenti

e-MANAGER è fonte autorevole per le identità esterne. Sincronizzare solamente:

```json
{
  "external_id": "usr_74fa8d...",
  "username": "mario",
  "name": "Mario Rossi",
  "role": "resident",
  "active": true,
  "permissions": ["eface:home", "eface:intercom"],
  "permissions_version": 7,
  "valid_from": "2026-09-29T08:00:00Z",
  "valid_until": null
}
```

Ogni aggiornamento deve avere numero di versione monotono e firma. eFace rifiuta
aggiornamenti più vecchi per impedire rollback delle autorizzazioni.

Le password, gli hash password, i secret TOTP e le chiavi private non vengono
sincronizzati.

## 17. Accesso tecnico temporaneo

Un tecnico non deve ricevere un accesso permanente per impostazione predefinita.

L'amministratore definisce:

- impianto;
- permessi;
- motivo;
- inizio e fine validità;
- necessità di approvazione del cliente;
- numero massimo di sessioni;
- eventuale limitazione IP/rete.

Esempio:

```text
Tecnico: tecnico@ekonex.it
Impianto: Villa Rossi
Permessi: eface:tools:view, eface:tools:admin
Validità: 29/09/2026 09:00–11:00
Motivo: manutenzione videocitofono
```

Alla scadenza, refresh token e sessioni vengono revocati automaticamente.

## 18. Audit log

Registrare almeno:

- login riusciti e falliti;
- MFA/passkey riuscita o fallita;
- richieste e completamenti di recupero password;
- cambi password;
- creazione, modifica, disabilitazione ed eliminazione utenti;
- assegnazione e revoca impianti;
- pairing e unpairing;
- emissione e revoca di accessi tecnici;
- creazione/revoca dispositivi attendibili;
- uso dell'account di emergenza;
- cambi ruolo e permessi;
- revoche di sessione;
- modifiche alle chiavi di firma.

Campi minimi:

```text
event_id, timestamp UTC, actor_id, subject_id, installation_id,
action, result, reason, source_ip, user_agent_hash, correlation_id
```

Non registrare password, token completi, codici MFA, codici recovery, cookie,
chiavi private o contenuto sensibile dell'impianto.

L'audit deve essere append-only, protetto da manomissioni, esportato fuori dalla
VPS e soggetto a retention documentata.

## 19. Rate limiting e protezione dagli abusi

Applicare limiti combinati per IP, account, installazione e dispositivo:

| Operazione | Soglia iniziale suggerita |
|---|---:|
| Login password | 5 tentativi / 15 minuti |
| MFA | 5 tentativi / 10 minuti |
| Recovery richiesta | 3 / ora per account, 10 / ora per IP |
| Recovery completamento | 5 tentativi / token |
| Pairing | 5 tentativi / codice |
| Refresh token | rilevamento riuso immediato |

Usare backoff progressivo, allarmi e blocchi temporanei. Non bloccare in modo
permanente un account soltanto sulla base di traffico anonimo, per evitare
denial-of-service mirato.

## 20. Gestione delle chiavi

- chiavi di firma e-MANAGER conservate fuori dal repository;
- preferibile secret manager o HSM/KMS;
- chiave attiva identificata da `kid`;
- pubblicazione delle chiavi pubbliche via JWKS;
- rotazione pianificata almeno annuale e immediata dopo incidente;
- sovrapposizione temporanea tra vecchia e nuova chiave;
- backup cifrato e procedura di recupero verificata;
- chiavi delle installazioni individuali e revocabili;
- nessuna chiave privata nei log o nei backup non cifrati.

## 21. Comunicazioni e rete

- HTTPS obbligatorio;
- HSTS dopo verifica del dominio;
- redirect URI esatte, senza wildcard;
- allowlist degli issuer;
- timeout brevi e limiti di dimensione;
- DNS e certificati monitorati;
- chiamate macchina autenticate con mTLS o firme;
- webhook firmati con protezione replay;
- ingressi remoti centralizzati tramite nginx, evitando porte pubbliche non
  necessarie;
- MySQL non esposto pubblicamente;
- endpoint amministrativi non disponibili senza autenticazione forte.

## 22. Privacy e dati personali

Conservare il minimo necessario:

- identificativo, nome visualizzato, contatto verificato;
- assegnazioni e ruoli;
- dispositivi/sessioni;
- audit di sicurezza.

Definire:

- base e finalità del trattamento;
- tempi di conservazione;
- esportazione e cancellazione dell'account;
- anonimizzazione dei log quando possibile;
- procedura di risposta a richieste dell'interessato;
- accesso ai dati limitato agli operatori autorizzati.

## 23. Threat model essenziale

### Minacce considerate

- furto password tramite phishing;
- credential stuffing;
- enumerazione utenti;
- furto cookie/sessione;
- replay di authorization code o token;
- compromissione di un singolo eFace;
- compromissione della VPS;
- insider con privilegi amministrativi;
- modifica dei permessi durante funzionamento offline;
- manomissione del pairing;
- abuso del recupero password;
- esposizione accidentale nei log;
- accesso incrociato tra clienti;
- dipendenze software compromesse.

### Contromisure principali

- passkey e MFA;
- PKCE, state e nonce;
- token brevi e audience per installazione;
- chiavi asimmetriche;
- sessioni HttpOnly/Secure;
- revoca e rotazione;
- rate limiting;
- audit append-only;
- isolamento tenant;
- pairing verificato;
- CI con scansione dipendenze e segreti;
- backup cifrati e disaster recovery.

## 24. Modifiche richieste a e-MANAGER

1. Correggere la registrazione WebAuthn non autenticata.
2. Centralizzare i controlli ruolo/cartella.
3. Aggiungere `user_id` immutabile e stato account.
4. Aggiungere email verificata e contatti di recovery.
5. Implementare Argon2id e migrazione trasparente da bcrypt.
6. Implementare MFA/passkey correttamente autenticata.
7. Implementare session store e revoca globale.
8. Implementare provider OIDC.
9. Aggiungere installazioni, client e redirect URI.
10. Aggiungere associazioni utente-installazione e permessi.
11. Implementare pairing e credenziali macchina.
12. Implementare recupero password e codici recovery.
13. Implementare audit e notifiche di sicurezza.
14. Spostare i token browser da `localStorage` a cookie sicuri.
15. Aggiungere rate limiting e protezione anti-enumerazione.

## 25. Modifiche richieste a eFace X4

1. Estendere `user_auth` per identità `origin="external"`.
2. Conservare `external_id`, provider, permessi e versione.
3. Aggiungere `installation_id` e chiave macchina.
4. Implementare procedura di pairing.
5. Implementare client OIDC Authorization Code + PKCE.
6. Implementare validazione JWKS e token.
7. Creare sessione locale dopo login centrale.
8. Ridurre la durata del trusted device.
9. Applicare permessi granulari nelle API.
10. Implementare sincronizzazione e revoca.
11. Mantenere account admin locale di emergenza.
12. Aggiungere indicatori online/offline/degradato.
13. Aggiungere audit locale e invio differito alla VPS.
14. Aggiungere test di sicurezza e compatibilità PWA.

## 26. Test obbligatori

### Unitari

- hashing e verifica password;
- scadenza e consumo recovery token;
- codici recovery monouso;
- validazione claim OIDC;
- isolamento `aud` per installazione;
- revoca tramite versione;
- verifica permessi;
- firma e versione della sincronizzazione.

### Integrazione

- login completo con PKCE;
- passkey e MFA;
- pairing valido, scaduto e riutilizzato;
- revoca utente mentre la sessione è attiva;
- cambio password e logout globale;
- rotazione chiavi JWKS;
- recovery completo;
- funzionamento offline e riconnessione;
- accesso tecnico a scadenza;
- tentativo di accesso incrociato tra impianti.

### Sicurezza

- replay authorization code;
- state/nonce errati;
- redirect URI manipolata;
- JWT con algoritmo/issuer/audience errati;
- brute force e credential stuffing;
- enumerazione account;
- session fixation;
- CSRF;
- XSS e furto token;
- race condition sui token monouso;
- log leakage;
- compromissione simulata di un'installazione.

### Operativi

- backup e ripristino identità;
- perdita della chiave attiva;
- indisponibilità e-MANAGER;
- indisponibilità email;
- recupero con account break-glass;
- rollback alla versione precedente;
- migrazione di un utente locale esistente.

## 27. Osservabilità e allarmi

Metriche minime:

- login riusciti/falliti;
- failure rate per IP/account;
- MFA e recovery iniziati/completati;
- pairing iniziati/completati/falliti;
- token emessi/revocati;
- refresh token reuse;
- installazioni online/offline;
- ritardo sincronizzazione revoche;
- accessi tecnici attivi;
- utilizzi account di emergenza;
- errori di verifica firma/JWKS.

Allarmi immediati:

- riuso refresh token;
- firma token non valida ripetuta;
- pairing anomalo;
- molti recovery per lo stesso account;
- escalation privilegi;
- uso break-glass;
- accesso a più tenant incompatibili;
- modifica o perdita delle chiavi.

## 28. Piano di implementazione

### Fase 0 — Correzioni preliminari

- correggere criticità WebAuthn di e-MANAGER;
- uniformare autorizzazioni;
- introdurre sessioni revocabili;
- proteggere segreti e database;
- creare staging isolato.

### Fase 1 — Modello identità

- ID immutabili;
- account attivi/disabilitati;
- email verificata;
- ruoli e permessi;
- installazioni e associazioni;
- audit base.

### Fase 2 — Recovery e MFA

- recupero password;
- notifiche di sicurezza;
- passkey;
- TOTP;
- codici recovery;
- test anti-enumerazione.

### Fase 3 — Pairing

- identità installazione;
- codice monouso;
- approvazione amministrativa;
- credenziale macchina;
- heartbeat e stato.

### Fase 4 — OIDC/SSO

- discovery e JWKS;
- authorize/token/revoke;
- client PKCE in eFace;
- sessione locale;
- test end-to-end.

### Fase 5 — Sincronizzazione e revoca

- permessi firmati/versionati;
- revoca rapida;
- offline policy;
- accesso tecnico temporaneo;
- audit completo.

### Fase 6 — Pilota

- una singola installazione non critica;
- login locale mantenuto;
- osservazione per almeno due settimane;
- simulazione guasti e rollback;
- revisione delle metriche.

### Fase 7 — Migrazione graduale

- un cliente alla volta;
- conferma backup e recovery;
- verifica passkey/recovery;
- disattivazione progressiva del vecchio portale username-only;
- account break-glass verificato per ogni impianto.

## 29. Criteri di accettazione

Il sistema è pronto per la produzione quando:

- nessuna password/hash viene condivisa tra sistemi;
- ogni token è limitato a una singola installazione;
- pairing e authorization code sono monouso e resistono al replay;
- recupero password non consente enumerazione;
- reset password revoca tutte le sessioni previste;
- passkey/MFA funzionano con recovery verificato;
- un impianto compromesso non può firmare token;
- revoche raggiungono gli impianti entro la soglia definita;
- modalità offline non permette escalation privilegi;
- account break-glass è unico e testato;
- audit non contiene segreti ed è protetto da manomissioni;
- test unitari, integrazione e sicurezza sono superati;
- backup identità e chiavi è cifrato e ripristinabile;
- staging e produzione sono separati;
- rollback è stato provato;
- documentazione operativa e incident response sono disponibili.

## 30. Decisione architetturale

La soluzione approvata come direzione è:

> e-MANAGER diventa Identity Provider centrale OIDC. Ogni eFace X4 viene
> registrato come installazione isolata e usa Authorization Code con PKCE.
> eFace crea una sessione locale dopo la validazione e conserva un account
> amministrativo locale di emergenza. Password e hash non vengono mai
> sincronizzati. Recupero password, MFA, revoca e audit sono gestiti
> centralmente con procedure forti e verificabili.

L'implementazione deve iniziare soltanto dopo la correzione delle criticità
autenticative già individuate in e-MANAGER e la disponibilità di un ambiente di
staging completo.
