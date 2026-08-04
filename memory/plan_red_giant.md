# Red Giant — Piano di sviluppo

**Versione piano:** 1.2 (espansione ossessiva: motivazioni, implementazioni e criteri per ogni sottofase)
**Data:** 2026-08-01
**Specsheet di riferimento:** [small-model-powerhouse-specsheet.md](small-model-powerhouse-specsheet.md) (v0.1)
**Atlante della codebase:** [codebase_reference.md](codebase_reference.md) — aggiornato a ogni fine fase, mai dopo.
**Stato:** 🟢 **F3-bis COMPLETATA** (2026-08-03, `v4.3.0`) — micro-slice multi-dominio: 3/3 verificati al primo colpo su severino-sim (v. ESITO F3-bis). Prossima azione: **F4** (verifica continua e supervisione — Debugger, Supervisor, anti-loop, checkpoint git). Alle spalle: interludio planner-system CONCLUSO (2026-08-03, `v4.0.0`, PS0–PS7 di [`plan_planner_system.md`](plan_planner_system.md)) — il sistema S/M/J + Control Plane è **integrato ma gated OFF** (`[plansys] enabled=false`): l'A/B ufficiale PS6 l'ha bocciato per l'accensione di default (2/13 vs 6-8/13 baseline; 0/3 entrambi sui task larghi) ma promosso su onestà (forbice ~0) e costo dei fallimenti (−44% token; ablazioni: ogni gate contiene +50-76%). Verdetto riapribile: campagna thinking TH0–TH3 ([`plan_thinking_ab.md`](plan_thinking_ab.md)) → poi F6 (routing per taglia). **Scoperta di metodo dell'interludio**: varianza run-to-run anche su CPU (banda ±2/13, stato cache del server) → i verdetti futuri usano run multiple mediate. Prossima azione della roadmap: **F3-bis** (a `v4.1.0` — v. nota di riconciliazione versioni). Prima ancora, per decisione utente: campagna thinking. Il vecchio Planner in-loop di F3 resta OFF e deprecato (verdetto D11 originale: 2/10 vs 9/10).

---

## Come si legge questo documento

Questo piano è **il contratto di implementazione**. Non è una lista di intenzioni: ogni firma, percorso, tabella e chiave qui dentro è ciò che il codice dovrà essere. Le regole di lettura:

1. **Le firme sono vincolanti.** Se durante l'implementazione una firma deve cambiare, si cambia *prima* qui (con la ragione scritta accanto), poi nel codice. La direzione del vincolo è unica: piano → codice. Il motivo è meccanico: il rituale di fine fase esegue `scripts/check_reference.py`, che confronta le firme reali con l'atlante; se piano e codice potessero divergere in silenzio, l'atlante inseguirebbe invece di comandare, e a quel punto sarebbe solo un riassunto in ritardo.
2. **Ogni sottofase è un'unità chiusa**: ha un obiettivo, una motivazione, un'implementazione descritta, i casi limite, i criteri di accettazione. Una sottofase senza criteri osservabili non può dirsi finita — è la stessa regola che imponiamo al sistema (specsheet §14), applicata a noi stessi.
3. **Le sezioni 🧭 e le "Motivazioni" non sono decorazione.** Sono la memoria del *perché*: una riga di codice si rilegge, la ragione per cui è così no. Se una motivazione smette di essere vera, la decisione collegata va rimessa in discussione esplicitamente, non aggirata.
4. **Il piano è autosufficiente per costruzione.** Un implementatore (umano o agente) **senza alcun altro contesto** — senza questa conversazione, senza memoria pregressa — deve poter sviluppare il codice leggendo solo questo documento (più la specsheet per la visione e l'atlante per lo stato corrente). Se durante l'implementazione serve un'informazione che non sta scritta qui, quello è un difetto del piano da correggere *nel piano*, non un vuoto da colmare a memoria.
5. **Struttura:** §0 decisioni vincolanti (D1–D21, ciascuna con enunciato, perché, conseguenze operative e modi tipici di violarla per sbaglio) → §A architettura di riferimento (il progetto esecutivo trasversale) → rituale di fine fase → fasi F0–F8 → rischi → cosa non esiste.

**Legenda dei marcatori:** 🧑 richiede l'utente · 🤖 fa l'agente · 🔎 verifica di fase · ⚠️ criticità · 📌 da registrare nel codebase_reference

---

## 0. Decisioni vincolanti (esito del brainstorming 2026-08-01)

Integrano la specsheet e **prevalgono in caso di conflitto** con essa. Ogni decisione ha quattro campi: *enunciato* (cosa si fa), *perché* (la ragione tecnica o strategica), *conseguenze operative* (cosa cambia concretamente nel codice e nel processo), *violazione tipica* (l'errore in buona fede da cui guardarsi — servono a non farsi mordere due volte dalla stessa cosa).

### D1 — Modello: Gemma 4 E2B, Q4, GGUF

- **Enunciato:** il modello di lavoro è Gemma 4 E2B quantizzato Q4 in formato GGUF. E4B esiste nel progetto *solo* come punto di riferimento nei confronti dell'Evaluator (F8.2), mai come ripiego durante lo sviluppo.
- **Perché:** l'intero senso di Red Giant è dimostrare che la potenza sta nel sistema, non nel modello (specsheet §27). Se si sviluppa sul modello più piccolo possibile, ogni miglioramento misurato è attribuibile all'architettura; su E4B tutto sarà semplicemente più performante, gratis. Sviluppare su E4B e "sperare che regga su E2B" invertirebbe l'onere della prova.
- **Conseguenze operative:** tutti i prompt, gli schemi e i budget si tarano su E2B; quando qualcosa non funziona, la prima ipotesi da esplorare è "lo schema/prompt è troppo ambizioso per un E2B", non "serve un modello più grande". Il GGUF e la quantizzazione esatta sono pinnati (URL + SHA256 in `scripts/download-model.ps1`).
- **Violazione tipica:** debuggare un ruolo che fallisce provandolo "un attimo" su E4B o su un modello cloud per capire se è colpa del modello. È vietato non perché inutile, ma perché crea dipendenza diagnostica da risorse che il sistema finale non avrà. Il confronto con E4B è ammesso solo dentro l'Evaluator, tracciato (F8.2).

### D2 — Runtime: llama.cpp (`llama-server`)

- **Enunciato:** il runtime è `llama-server` di llama.cpp, usato tramite l'API HTTP nativa (`/completion`, `/props`, `/slots`) — non tramite il layer OpenAI-compatible, se quello nasconde campi che ci servono (timings dettagliati, `cache_prompt`, slot).
- **Perché:** ci servono tre leve che Ollama e i wrapper di alto livello nascondono o mediano: (1) il **guided decoding** (grammatiche GBNF / JSON Schema applicate al sampler); (2) il **controllo della KV cache** (riuso del prefisso via `cache_prompt`, gestione slot, `--slot-save-path` per salvare/ripristinare lo stato su disco); (3) i **timings separati** di prefill e generazione, senza i quali le metriche di F5 sono cieche. La versione di llama.cpp è pinnata (tag scritto in config e nell'atlante) perché il comportamento della cache e delle grammatiche cambia tra release.
- **Conseguenze operative:** il client HTTP è scritto da noi (`redgiant/llm/client.py`), sottile, senza SDK di terze parti. Ogni funzionalità del server che usiamo è verificata a mano in F0 prima di costruirci sopra.
- **Violazione tipica:** aggiornare llama.cpp "perché c'è una versione nuova" a metà fase. L'aggiornamento del runtime è una modifica di piattaforma: si fa a inizio fase, si ri-esegue il bench di F0.5, si registra nell'atlante.

### D3 — Constrained decoding obbligatorio

- **Enunciato:** ogni chiamata al modello che attende un output strutturato passa lo schema al server (guided decoding): il sampler **non può fisicamente** produrre output fuori schema. Unica eccezione: testo libero destinato all'utente (es. risposta finale discorsiva), comunque loggato come tale.
- **Perché:** con un modello da 2B effettivi, il "retry su output malformato" (specsheet §18) diventerebbe una tassa costante di token e tempo — su CPU, la risorsa più scarsa. Il constrained decoding elimina **per costruzione** un'intera categoria di errori della specsheet §12 ("mancato rispetto dello schema"). Su un modello piccolo è la differenza tra inutilizzabile e solido.
- **Conseguenze operative:** ogni ruolo dichiara `output_model` (Pydantic); `LlamaClient.complete` converte il modello in JSON Schema per il server e **rivalida comunque** il risultato con Pydantic (difesa in profondità: se il server ha un bug di grammatica, lo scopriamo noi e non l'Orchestrator a valle). Il contatore degli output invalidi sta in `llm_calls.outcome` e deve restare a zero: se sale, è un bug di piattaforma da fermare subito, non da riprovare.
- **Violazione tipica:** "per questo campo testuale lascio l'output libero e poi lo parso con una regex". No: se ha struttura, ha uno schema; se non ha struttura, è testo per l'utente.

### D4 — Formato di scambio: JSON (mai YAML nel runtime)

- **Enunciato:** tutti gli output strutturati del modello, lo stato serializzato e i payload interni sono JSON. YAML sopravvive solo nei documenti per umani. Gli esempi YAML della specsheet si leggono come JSON equivalente.
- **Perché:** il guided decoding di llama.cpp lavora su JSON Schema/GBNF; YAML è ostile alle grammatiche (indentazione significativa, mille modi di scrivere la stessa cosa) e i modelli piccoli lo sbagliano più spesso. Inoltre JSON ha un solo parser possibile, YAML ne ha troppi.
- **Conseguenze operative:** `redgiant/llm/schema.py` è l'unico punto di conversione Pydantic→JSON Schema; nessun altro modulo costruisce schemi a mano.
- **Violazione tipica:** file di configurazione dei task sintetici scritti in YAML "perché più leggibili". I file per umani (config, task.toml) sono TOML — un solo formato umano in tutto il repo, niente terzo incomodo.

### D5 — Hardware target: Severino

- **Enunciato:** il target di produzione è Severino (BOSGAME E5: Ryzen 3 5300U, Zen 2, 4 core / 8 thread @15W, CPU-only — la iGPU Vega è inutilizzabile: niente ROCm su quelle integrate, Vulkan marginale). Al tempo dell'MVP avrà 32 GB dual channel; a Red Giant + llama-server sono allocati **al massimo 4 core**, perché il resto dello stack homelab resta acceso.
- **Perché:** "sono capaci tutti a lavorare su uno Strix Halo con Gemma 4; io voglio lavorare sul PC di un non-prosumer" (l'utente). Il progetto esiste per minimizzare la forbice tra l'inferenza locale su hardware consumer e l'inevitabile scarsità di quello scenario. Il collo di bottiglia è il **tempo di CPU** (soprattutto prefill), non la RAM: E2B Q4 pesa ~3 GB e nei 32 GB sta comodo.
- **Conseguenze operative:** ogni scelta di design si giudica alla domanda "quanto costa su 4 core Zen 2?": numero di chiamate per sottofase, lunghezza dei prompt, frequenza delle verifiche. I budget della §A6 nascono dai bench di F0.5 fatti su risorse comparabili, non da stime.
- **Violazione tipica:** accettare una feature "che costa solo una chiamata in più per sottofase". Una chiamata in più per sottofase su un task da 20 sottofasi sono minuti di CPU: si accetta solo con un A/B che ne dimostri il valore (D11).

### D6 — Tre profili di esecuzione; metriche ufficiali solo CPU-only

- **Enunciato:** tre profili nominati: `dev-fast` (questo PC: RTX 4080 Super, Ryzen 9 9900X — solo per iterare sul codice), `severino-sim` (Docker CPU-only su questo PC: cpuset 4 core, RAM limitata — il proxy onesto), `severino` (il box reale, via Tailscale). Le **metriche ufficiali** (Evaluator, bench, verifiche di fase) si registrano **esclusivamente** su profili CPU-only; la validazione di fine fase gira su `severino-sim` o su Severino reale.
- **Perché:** il divario dev/prod è di ~50-100×. È il rischio numero uno del progetto: sviluppando sulla 4080, tutti i problemi di economia dei token restano invisibili fino al deploy, dove esplodono insieme. Il profilo `severino-sim` esiste perché Severino reale non è sempre disponibile e perché saturarlo coi bench disturberebbe lo stack di casa.
- **Conseguenze operative:** il profilo è un parametro esplicito ovunque (`--profile`, colonna `tasks.profile`, `eval_runs.profile`). I report dell'Evaluator rifiutano di dichiararsi "ufficiali" se il profilo è `dev-fast` (flag nel report).
- **Violazione tipica:** "il bench su dev-fast era buono, lo segno e lo rifaccio poi su severino-sim". Il poi non arriva mai: il numero non misurato su CPU **non esiste**.

### D7 — Batch, strettamente sequenziale; modello residente per task

- **Enunciato:** una sola inferenza alla volta in tutto il sistema. I task sono job asincroni: si lanciano, si chiude la pagina, si torna dopo. Il modello viene caricato all'inizio del task e scaricato alla fine; niente `keep_alive` corto durante un task.
- **Perché:** su Severino l'inferenza satura i 4 core allocati; due inferenze concorrenti si strozzano a vicenda e strozzano il resto del box (la specsheet homelab lo vieta esplicitamente: "solo uso occasionale/asincrono"). Il `keep_alive` corto della policy homelab è pensato per l'uso occasionale; un task Red Giant fa decine di chiamate consecutive e ricaricare il modello a ogni chiamata costerebbe più del task stesso. Il corollario positivo: la sequenzialità rende lo stato sempre coerente senza lock complicati, e la KV cache non viene mai contesa.
- **Conseguenze operative:** `JobQueue` (F2.1) ha un solo worker thread; `llama-server` gira con `--parallel 1`; l'avvio/arresto del server è legato al ciclo di vita del job. Niente asyncio nella pipeline cognitiva: il codice è sincrono e leggibile, la concorrenza è un non-problema per scelta.
- **Violazione tipica:** parallelizzare "solo le verifiche, che sono veloci". Le verifiche deterministiche (pytest ecc.) possono anche esserlo, ma appena una verifica chiama il modello è inferenza come le altre: passa dalla coda.

### D8 — Contesto piccolo by design (~4-8K token per chiamata)

- **Enunciato:** il regime normale di ogni chiamata è ~4-8K token di prompt (numero definitivo fissato in F0.6 dai bench), anche se il modello supporta finestre molto più grandi. Superare il budget di contesto è un errore del Context Builder, non un'opzione.
- **Perché:** su CPU il prefill costa tempo lineare (o peggio) nella lunghezza del prompt: un prompt da 32K che su GPU è istantaneo, su 4 core Zen 2 sono minuti — per singola chiamata. Inoltre la KV cache di contesti grandi mangia RAM che su Severino serve allo stack. Infine, ed è il punto della specsheet §9: un modello piccolo *ragiona peggio* su contesti lunghi; il contesto minimo non è solo un'ottimizzazione, è una condizione di qualità.
- **Conseguenze operative:** `llm.ctx_size` è un tetto duro del client (chiamata rifiutata prima di partire se lo sfora, con errore esplicito che dice *cosa* lo ha gonfiato); i budget per sezione (S5/S6) stanno in `ContextBudgets` (F5.1). Il "contesto massimo disponibile" del modello non va mai confuso col budget da consumare (specsheet §15).
- **Violazione tipica:** risolvere un fallimento del Worker dandogli "anche tutto il file, per sicurezza". Se il Worker fallisce per contesto mancante, la correzione sta nella *selezione* (Context Builder), non nella quantità.

### D9 — Prompt a prefisso comune, ordine S1→S7 stabile

- **Enunciato:** ogni prompt è assemblato nell'ordine fisso S1→S7 (§A4), con le parti statiche **byte-identiche** tra chiamate. Il preambolo (S1), le card di ruolo (S2), il catalogo tool (S3) e l'header del task (S4) non contengono mai contenuto volatile.
- **Perché:** `cache_prompt` di llama-server riusa la KV cache **solo per il prefisso comune** tra la chiamata precedente e la nuova: basta un byte diverso a monte per invalidare tutto ciò che segue. Con 8 ruoli e prompt ingenui il riuso sarebbe zero e ogni chiamata ripagherebbe l'intero prefill — su CPU, la morte del progetto. Questa è la parte più "ingegneristica" del progetto, ed è l'ispirazione presa da Dwarf Star di antirez: lavorare forte sul prefill per ridurne i tempi.
- **Conseguenze operative:** l'assemblaggio è centralizzato in `PromptAssembler` (nessun ruolo costruisce prompt a mano); un test unitario (F5.3) verifica che due chiamate consecutive dello stesso ruolo abbiano prefisso identico; `PromptParts.static_prefix_len()` alimenta la metrica di riuso.
- **Violazione tipica:** un timestamp nel preambolo ("Current date: …"), un contatore di step in S4, un path temporaneo in S3. Tutto ciò che varia vive da S5 in giù.

### D10 — Verifica deterministica ovunque possibile

- **Enunciato:** la verifica di un risultato usa prima gli oracoli meccanici (test runner, compilatore/linter, diff, exit code, esistenza di file, match di citazioni); il Verifier-modello interviene solo sul residuo che nessun oracolo copre. Corollario per il Phase Designer: **la decomposizione preferisce sottofasi meccanicamente verificabili** — la verificabilità è un criterio di design delle sottofasi, non un passo successivo.
- **Perché:** verificare la semantica di un risultato è difficile quanto produrlo: un Debugger basato sullo stesso E2B del Worker approverà errori plausibili con la stessa fiducia con cui il Worker li ha commessi. Gli oracoli meccanici non hanno questo problema: pytest non si fa convincere. Ogni volta che una sottofase è formulata in modo da avere un oracolo ("il test X passa" invece di "il codice è corretto"), il sistema guadagna un controllo che il modello non può aggirare.
- **Conseguenze operative:** `core/verify.py` gira **sempre** prima del Debugger (F4.1: due stadi); il Debugger riceve il verdetto deterministico come input, mai il contrario. Le card del Phase Designer contengono il criterio esplicitamente.
- **Violazione tipica:** chiedere al modello "i test passerebbero?" invece di eseguirli. Sembra assurdo scritto qui; sotto pressione di budget è una tentazione reale.

### D11 — Ogni ruolo cognitivo si guadagna il posto coi numeri

- **Enunciato:** nessun ruolo della specsheet entra in pipeline per fede. Ogni ruolo (Planner, Debugger-modello, Supervisor, Classifier…) viene aggiunto in una fase dedicata e **confrontato A/B nell'Evaluator** contro la pipeline senza di esso; resta solo se migliora completion rate o token-utili. Metrica guida: **token utili / token totali**.
- **Perché:** è l'anti-paradosso dell'overhead. La pipeline completa fa pagare a ogni sottofase 4-8 chiamate; su CPU il rischio concreto è un sistema che spende più in governance che in lavoro. La specsheet lo intuisce (§5, pipeline ridotte); qui lo si rende falsificabile: se il Planner non paga il proprio costo, il Planner esce. Vale anche per i ruoli *della specsheet* — per questo il Final Reviewer parte assorbito (v. "Cosa non esiste").
- **Conseguenze operative:** l'Evaluator nasce in F1 (prima dei ruoli cognitivi) proprio per fare da giudice; ogni fase che aggiunge un ruolo include la sottofase di A/B (F3.5, F4.6, F6.4) e il risultato va nell'atlante.
- **Violazione tipica:** tenere un ruolo che perde l'A/B "perché concettualmente giusto" o perché è nella specsheet. La specsheet descrive il sistema massimo; il sistema reale è quello che i numeri sostengono.

### D12 — Python; GUI FastAPI + HTMX + SQLite, processo unico

- **Enunciato:** tutto il deterministico è Python ≥3.12. La GUI è FastAPI + Jinja2 + HTMX (file `htmx.min.js` vendorizzato), stato su SQLite, **un solo processo** (`uvicorn` singolo, JobQueue interna). Zero build frontend, zero Node.
- **Perché:** Python per comodità dell'utente (sua scelta) e per l'ecosistema di test. La GUI web esiste perché l'utente è stato esplicito: "se l'interfaccia CLI è troppo complessa da usare non la testerò a fondo" — e un sistema non testato dall'utente è un sistema non testato. HTMX perché il fabbisogno reale è: form, tabelle, un albero che si aggiorna — niente che giustifichi una toolchain JS. SQLite perché lo stato è già lì (D7 rende la concorrenza banale) e un DB server sarebbe un altro processo da amministrare su Severino.
- **Conseguenze operative:** una sola porta (`web.port`), un solo comando di avvio; il deploy su Severino (F8.3) è un container che esegue quel comando.
- **Violazione tipica:** aggiungere un endpoint JSON "per il futuro frontend". Il frontend è questo; API pubbliche non esistono finché un bisogno reale non le chiede.

### D13 — Prompt interni in inglese; utente e documentazione in italiano

- **Enunciato:** preambolo, card di ruolo, descrizioni dei tool, schemi: tutto in inglese. L'interazione con l'utente (GUI, risposte finali) e la documentazione del progetto sono in italiano.
- **Perché:** i modelli piccoli rendono sensibilmente meglio in inglese (più dati di addestramento, tokenizzazione più efficiente: lo stesso contenuto costa meno token). Sul budget di D8, anche il costo di tokenizzazione conta.
- **Conseguenze operative:** `prompts/` è tutto inglese; la risposta finale al task viene prodotta nella lingua della richiesta dell'utente (istruzione nel preambolo).
- **Violazione tipica:** infilare nel contesto S6 messaggi d'errore italiani prodotti dalla nostra GUI. Gli errori che il modello deve leggere sono in inglese alla fonte.

### D14 — Pinning rigoroso; vendoring solo di ciò che si modifica

- **Enunciato:** dipendenze pinnate a versione esatta (`requirements.lock` via pip-compile); si vendorizza (copia dei sorgenti nel repo) **solo** la libreria che dobbiamo modificare, nel momento in cui la modifichiamo, con la modifica documentata nell'atlante.
- **Perché:** l'utente vuole poter mettere mano a qualunque dipendenza ("se voglio modificare qualcosa di una libreria devo poterlo fare") senza il peso di vendorizzare tutto ab origine. Il pinning esatto dà riproducibilità; il vendoring selettivo dà controllo dove serve davvero.
- **Conseguenze operative:** la lista dipendenze è corta per design (§A2: niente ORM, niente SDK LLM, niente framework di agenti — l'orchestrazione deterministica È il progetto); ogni aggiunta di dipendenza va motivata nel commit che la introduce.
- **Violazione tipica:** `pip install` di una utility "piccola" per risparmiare 30 righe di codice nostro. Trenta righe nostre sono trasparenti e modificabili; una dipendenza è un contratto.

### D15 — Git: doppia remote, branch = versioni

- **Enunciato:** remote `origin` = Gitea `https://git.home.varitest.ovh/smp-webmaster/RedGiant.git` (push-to-create), remote `github` = `https://github.com/Frostmoore/RedGiant.git`. Ogni push va su **entrambe**. I branch si chiamano come le versioni, da `v1.0.0`, e la numerazione avanza a ogni commit secondo l'entità (piccola `+0.0.1`, media `+0.1.0`, grande `+1.0.0`); modifiche solo-documentali contano come piccole.
- **Perché:** tracciabilità totale della progressione (istruzioni globali dell'utente): documenti sempre allineati al codice, storia git leggibile per versioni, colpo d'occhio a fine fase su cosa è fatto. Gitea è il primario di casa; GitHub è la copia pubblica/di scambio.
- **Conseguenze operative:** la tabella versioni-per-fase sta nella sezione "Rituale"; `redgiant.__version__` è allineata al branch corrente.
- **Violazione tipica:** pushare solo su `origin` "e su GitHub poi". Il rituale elenca entrambe; entrambe o il rituale non è concluso.

### D16 — Nessuna API LLM esterna, mai

- **Enunciato:** nessun componente, in nessuna fase, per nessun motivo, chiama un LLM esterno (cloud o remoto che non sia il llama-server del profilo). Se Gemma non basta, il sistema risponde onestamente di non farcela o fa escalation all'utente.
- **Perché:** è la policy del homelab ("never auto-calls external cloud LLMs") ed è la tesi stessa del progetto: un sistema che nei casi difficili scappa verso un modello grande non dimostra nulla. Il fallimento esplicito è un risultato scientificamente utile; il successo dopato no.
- **Conseguenze operative:** i tool di rete (F7) hanno una whitelist di domini per il *fetch di contenuti*; nessun endpoint di inferenza esterno esiste nel codice, nemmeno dietro flag.
- **Violazione tipica:** "solo per generare i task sintetici dell'Evaluator uso un modello grande". I task sintetici li scrivo io (l'agente di sviluppo) come codice: fanno parte del repo, non dell'inferenza di runtime. La distinzione è: ciò che gira *dentro* Red Giant è solo Gemma.

### D17 — Domini in ordine: coding → ricerca locale → ricerca web → consigli

- **Enunciato:** la stessa pipeline serve tutti i domini; l'ordine di implementazione è: coding (F1–F6), poi ricerca locale, ricerca web e consigli (F7). Per ricerca e consigli la verifica è **per fonti e triangolazione** (citazioni verificate meccanicamente), non per oracoli di correttezza.
- **Perché:** il coding ha l'oracolo gratis (test, compilatore): permette di validare l'impianto — orchestrazione, stato, retry, budget — senza dover *contemporaneamente* inventare la verifica non-deterministica. Ma Red Giant **non è un coding assistant**: l'utente è stato esplicito. La generalità si dimostra in F7, quando l'impianto è già solido.
- **Conseguenze operative:** nessuna scorciatoia coding-specifica nei componenti core: `SubtaskSpec`, `Verdict`, `ToolRouter` sono neutri rispetto al dominio già da F1 (il dominio è un campo, non un ramo di codice).
- **Violazione tipica:** hardcodare "pytest" dove serve "il comando di verifica della sottofase".

### D18 — Benchmark: sintetici prima, chatbot Laravel 13 poi

- **Enunciato:** l'Evaluator parte con mini-progetti sintetici costruiti ad hoc (repo piccoli con bug noti e test, `T001+`); il benchmark reale è il **chatbot Laravel 13** che l'utente costruirà con l'agente **in un altro scenario** e caricherà su Severino quando completo. Arriva in F8; Red Giant non lo aspetta.
- **Perché:** i due progetti non devono bloccarsi a vicenda. I sintetici hanno un vantaggio in più: conoscendo il bug esatto, sappiamo *perché* il sistema fallisce, non solo *che* fallisce.
- **Conseguenze operative:** i task sintetici sono nel repo (`redgiant/eval/tasks/`), versionati: un cambiamento a un task invalida i confronti storici e va segnato.
- **Violazione tipica:** "aggiusto" un task sintetico che il sistema non passa. I task si estendono, non si ammorbidiscono; se un task era sbagliato, la correzione va documentata e i numeri storici marcati come non confrontabili.

### D19 — Deploy finale: Docker su Severino

- **Enunciato:** Red Giant in produzione gira **su** Severino, container Docker accanto a llama-server, resource limits secondo §6.8 della specsheet homelab, esposto solo sulla tailnet via Caddy.
- **Perché:** confermato dall'utente. Il sistema deve vivere sull'hardware per cui è progettato; un Red Giant che gira sul PC e comanda Severino da remoto reintrodurrebbe una dipendenza dal PC acceso.
- **Conseguenze operative:** nessuna dipendenza da Windows nel codice di runtime (gli script `.ps1` sono comodità di sviluppo; ogni funzione ha un equivalente invocabile da Python/Linux); path sempre via `pathlib`.
- **Violazione tipica:** path hardcodati stile `E:\...` fuori dai file di profilo.

### D20 — Worker = ReAct a passo singolo vincolato

- **Enunciato:** il Worker non produce piani d'azione né script di tool call multiple: a ogni step emette **un solo** oggetto `WorkerStep` (schema chiuso: o una tool call, o la chiusura con `FinishReport`). Il risultato del tool viene appeso in coda al contesto e si genera lo step successivo. La conversazione cresce **solo in append**.
- **Perché:** due ragioni convergenti. (1) Cognitiva: un E2B che pianifica 5 azioni in anticipo ne sbaglia 3; decidere un'azione alla volta, vedendo il risultato della precedente, è il regime dove i modelli piccoli sono meno fragili. (2) Meccanica: l'append puro massimizza il riuso della KV cache — a ogni step il server ripaga solo il delta (risultato del tool + step precedente), mai il prefisso. Le due ragioni si rinforzano: il pattern giusto per la qualità è anche quello giusto per la performance.
- **Conseguenze operative:** `worker.max_steps` limita il loop; `thought` è vincolato a 300 caratteri (pensiero corto, non saggio — la verbosità non è ragionamento, specsheet §3); il `finish` del Worker **non chiude la sottofase**: la chiude solo la verifica (D10).
- **Violazione tipica:** far riassumere al Worker "cosa ha fatto finora" dentro il loop: riscrive il contesto, invalida la cache, e il riassunto è il lavoro del Compressor (F5.5), non suo.

### D21 — Un ruolo = uno schema piccolo, enum chiusi

- **Enunciato:** ogni ruolo ha **un** modello Pydantic di output, piccolo, con enum chiusi e campi obbligatori; mai mega-oggetti annidati profondi. Se un output è concettualmente grande (un piano), si spezza in chiamate (piano → poi una fase alla volta).
- **Perché:** un E2B riempie bene 8 campi con enum; ne riempie male 40 con testo libero. Ogni schema è anche il contratto della grammatica (D3): più piccolo lo schema, più stretta la grammatica, meno spazio d'errore. È la stessa logica della decomposizione dei task, applicata agli output.
- **Conseguenze operative:** limiti espliciti nei modelli (`max_length` sui testi, `max_items` sulle liste: fasi ≤7, sottofasi per fase ≤6); la separazione decisione/spiegazione della specsheet §18 si realizza con campi distinti (`decision` enum + `reason` testo corto).
- **Violazione tipica:** aggiungere "solo un campo opzionale" a uno schema esistente a ogni nuova esigenza, fino al mega-oggetto. Un campo nuovo si giustifica come una dipendenza nuova.

### Metriche cardine

Raccolte dall'Evaluator fin da F1, sempre su profilo CPU-only (D6). Sono **cinque numeri**, scelti perché ognuno punisce una patologia specifica:

1. **Token utili / token totali** — punisce l'overhead di governance (D11). Definizione operativa v0 in F1.10, raffinata quando esistono più ruoli.
2. **Completion rate con evidenza** — punisce i successi dichiarati (specsheet §3: mai valido solo perché il modello dice di aver finito).
3. **Tempo di parete per task e per sottofase su `severino-sim`** — punisce la lentezza reale, quella che l'utente sente.
4. **Prefill riusato / riprocessato** (`reuse_ratio`) — punisce le violazioni di D9; è la metrica-obiettivo di F5.
5. **Token per task, retry medi, loop fermati** — punisce lo spreco e misura la stabilità (specsheet §21).

---

## A. Architettura di riferimento

Questa sezione è il progetto esecutivo trasversale: tutto ciò che più fasi condividono sta qui, una volta sola; le fasi la costruiscono pezzo per pezzo e vi rimandano. **Un implementatore senza altro contesto deve poter lavorare leggendo questa sezione + la sottofase corrente.**

### A1. Albero del repository (a regime — con la fase in cui nasce ogni voce)

```text
RedGiant/                              (root = e:\coding\XAMPP\htdocs\Red Giant)
├── pyproject.toml                     F0.1 — metadati, deps pinnate, entry point `rg`
├── requirements.lock                  F0.1 — lockfile esatto (pip-compile)
├── README.md                          F0.1 — cos'è, profili, comandi base
├── .gitignore                         F0.1 — models/, data/, bench/results/raw/, __pycache__/, .venv/
├── memory/
│   ├── small-model-powerhouse-specsheet.md   (esiste — v0.1, scritta dall'utente)
│   ├── plan_red_giant.md                     (questo file)
│   └── codebase_reference.md                 (esiste — atlante, aggiornato ogni fine fase)
├── config/
│   ├── default.toml                   F0.1 — tutte le chiavi con default (contenuto integrale in §A6)
│   └── profiles/
│       ├── dev-fast.toml              F0.1 — override endpoint GPU locale
│       ├── severino-sim.toml          F0.4 — override endpoint Docker CPU
│       └── severino.toml              F0.4 — override endpoint Tailscale
├── docker/
│   ├── severino-sim/compose.yml       F0.4 — llama-server CPU, cpuset 4 core, mem limit
│   └── deploy/                        F8.3 — immagine Red Giant + compose per Severino
├── scripts/
│   ├── start-llama.ps1                F0.2 — avvia llama-server per profilo (dev Windows)
│   ├── download-model.ps1             F0.2 — scarica il GGUF in models/ (URL+SHA256 nel file)
│   ├── download-llama.ps1             F0.2 — scarica i binari llama.cpp pinnati in bin/ (gitignored)
│                                      #      [aggiunto in implementazione: i binari sono artefatti
│                                      #       riproducibili come il modello, meritano lo stesso script]
│   └── check_reference.py             F0.7 — verifica meccanica firme ↔ codebase_reference
├── bench/
│   ├── run_bench.py                   F0.5 — baseline prefill/gen/cache
│   └── results/                       F0.5 — CSV+MD committati (raw/ gitignored)
├── models/                            F0.2 — GGUF (gitignored, ricreabile da script)
├── data/                              F1 — redgiant.db, data/tasks/<id>/, data/slots/ (gitignored)
├── redgiant/
│   ├── __init__.py                    F0.1 — __version__: str allineata al branch
│   ├── config.py                      F0.1 — caricamento TOML + dataclass di config
│   ├── cli.py                         F1.9 — CLI dev (`rg run|status|eval|bench`)
│   ├── llm/
│   │   ├── client.py                  F1.2 — LlamaClient (HTTP nativo llama-server)
│   │   └── schema.py                  F1.2 — Pydantic → JSON Schema per guided decoding
│   ├── prompts/
│   │   ├── assemble.py                F1.3 — PromptAssembler, PromptParts
│   │   ├── preamble.md                F1.3 — S1: preambolo comune (EN, statico)
│   │   └── roles/                     F1.3+ — worker.md; F3: planner.md, phase_designer.md;
│   │                                          F4: debugger.md, supervisor.md; F6: classifier.md, assessor.md
│   ├── state/
│   │   ├── models.py                  F1.1 — tutti i modelli Pydantic dello stato
│   │   └── store.py                   F1.1 — StateStore (SQLite, DDL §A5)
│   ├── tools/
│   │   ├── base.py                    F1.4 — ToolSpec, ToolResult, Scope, ScopeError
│   │   ├── router.py                  F1.4 — ToolRouter
│   │   ├── fs.py                      F1.4 — read_file, list_files, write_patch
│   │   ├── search.py                  F1.4 — search_code (ripgrep --json)
│   │   ├── proc.py                    F1.4 — run_tests, git_status, git_diff (whitelist)
│   │   └── web.py                     F7.2 — web_search, fetch_url
│   ├── roles/
│   │   ├── base.py                    F1.5 — Role, RoleContext
│   │   ├── worker.py                  F1.5 — Worker (ReAct vincolato, D20)
│   │   ├── planner.py                 F3.1
│   │   ├── phase_designer.py          F3.2
│   │   ├── debugger.py                F4.1
│   │   ├── supervisor.py              F4.2
│   │   ├── classifier.py              F6.2
│   │   └── assessor.py                F6.2
│   ├── core/
│   │   ├── orchestrator.py            F1.7 — v0; F3.3 — v1 (piano dinamico); F6.3 — pipeline ridotte
│   │   ├── verify.py                  F1.6 — oracoli deterministici; F4.1 e F7.1 — estensioni
│   │   ├── budget.py                  F1.7 — BudgetTracker; F4.5 — BudgetManager completo
│   │   ├── loopguard.py               F4.3 — LoopGuard
│   │   ├── checkpoint.py              F4.4 — CheckpointManager (git; slot KV da F5.4)
│   │   ├── context_builder.py         F5.1 — ContextBuilder (prima: assemblaggio semplice)
│   │   ├── cache_probe.py             F5.2 — metriche riuso KV
│   │   ├── slots.py                   F5.4 — SlotManager (--slot-save-path)
│   │   ├── compressor.py              F5.5 — StateCompressor
│   │   └── routing.py                 F6.1 — segnali deterministici + scelta pipeline
│   ├── eval/
│   │   ├── harness.py                 F1.10 — discover/run
│   │   ├── report.py                  F1.10 — report MD+CSV
│   │   └── tasks/                     F1.10+ — T001…/task.toml + repo/
│   └── web/
│       ├── app.py                     F2.1 — create_app()
│       ├── jobs.py                    F2.1 — JobQueue (1 inferenza alla volta)
│       ├── routes/                    F2.2 — tasks.py, approvals.py, metrics.py
│       ├── templates/                 F2.4 — Jinja2 (base.html, index.html, task.html, tree.html, …)
│       └── static/htmx.min.js         F2.4 — vendorizzato, versione fissata
└── tests/
    ├── unit/                          F1+ — senza modello né rete
    └── integration/                   F1+ — contro llama-server reale (marker `@pytest.mark.llm`)
```

### A2. Dipendenze (pinnate in F0.1)

| Pacchetto | Ruolo | Perché questo e non altro |
|---|---|---|
| `pydantic` v2 | schemi di stato e di output dei ruoli | validazione + generazione JSON Schema per il guided decoding (D3): un solo formalismo per entrambe le cose |
| `httpx` | client HTTP verso llama-server | sincrono (D7: niente asyncio nella pipeline), timeouts espliciti, niente magia |
| `fastapi` + `uvicorn` | GUI web | D12; si usa la parte sincrona (def, non async def, dove possibile) |
| `jinja2` | template GUI | standard, zero build |
| `pytest` | test | standard |
| `pip-tools` (solo dev) | lockfile | `pip-compile` genera `requirements.lock` con hash |

**Esclusioni deliberate:** niente ORM (SQL a mano su `sqlite3` stdlib: il DDL è nostro e lo dobbiamo capire byte per byte), niente SDK LLM (il client è nostro, D2), niente framework di agenti (l'orchestrazione È il progetto), niente libreria CLI (argparse basta). Ripgrep è un **binario di sistema** (path in `paths.ripgrep`), non una dipendenza Python.

### A3. Flusso di un task (a regime, F6+; nelle fasi intermedie i pezzi mancanti sono bypassati)

```text
POST /tasks (o `rg run`)
  → StateStore.create_task (status=queued, budget dai default o dal form)
  → JobQueue.submit
[JobQueue worker thread — uno solo, D7]
  → avvio/verifica llama-server del profilo (modello residente per tutto il task)
  → routing (F6): deterministic_signals → [se ambiguo] Classifier/Assessor → pipeline direct|short|full
  → pipeline "full":
      Planner → Plan v1 (salvato con reason="initial")
      loop sulle fasi eleggibili (dipendenze soddisfatte, ordine del piano):
        Phase Designer → sottofasi della sola fase corrente
        loop sulle sottofasi:
          Context Builder (F5; prima: assemblaggio semplice) → contesto minimo
          Worker (loop WorkerStep, D20; tool via ToolRouter; tutto loggato)
          verify.py (oracoli deterministici, D10)
          Debugger (F4; solo sul residuo non coperto dagli oracoli)
          Supervisor (F4) → decisione ∈ enum chiuso → l'Orchestrator la applica SOLO se legale
          CheckpointManager.checkpoint(post_subtask) se accettata
          BudgetManager.check → stop esplicito se sforato
          LoopGuard → se loop rilevato, escalation forzata
      fase completata quando i suoi completion_criteria risultano soddisfatti
  → verifica finale contro i success_criteria del piano
  → status finale ∈ {completed, partial, failed} — MAI senza evidenze registrate
  → arresto llama-server (rilascio RAM su Severino)
```

Esiti di sottofase (enum unico in tutto il sistema, specsheet §11): `completed`, `completed_with_warnings`, `retry`, `repair`, `blocked`, `failed`, `skipped` (+ `pending`, `running` come stati transitori).

### A4. Convenzione dei prompt (D9, D13, D20 — fissata in F1.3, immutabile senza revisione di questo piano)

Ogni prompt inviato al modello è la concatenazione **nell'ordine S1→S7** delle sezioni seguenti, separate da `\n\n### <SECTION_NAME>\n\n` (separatore esatto, byte-stabile). Le parti statiche devono essere **byte-identiche** tra chiamate: la KV cache riusa solo prefissi identici.

| Sez. | Nome | Contenuto | Stabilità | Chi la produce |
|---|---|---|---|---|
| S1 | `PREAMBLE` | identità del sistema, regole universali (EN), formato delle evidenze, "you are one role in a pipeline; propose, don't decide" | statica globale (cambia solo con bump di versione) | `prompts/preamble.md` |
| S2 | `ROLE` | card del ruolo: responsabilità, cosa NON deve fare, esempi minimi | statica per ruolo | `prompts/roles/<role>.md` |
| S3 | `TOOLS` | catalogo dei tool autorizzati al ruolo per questo dominio: nome, descrizione, schema argomenti; ordinato alfabeticamente | statica per (ruolo, dominio) | generata da `ToolRouter.allowed_for` |
| S4 | `TASK` | richiesta utente verbatim, goal, vincoli, dominio | statica per task | `PromptAssembler` |
| S5 | `STATE` | piano sintetico (id+titolo+stato delle fasi), fase corrente, decisioni durature rilevanti | cambia per fase | `ContextBuilder` (F5; prima: assembler) |
| S6 | `CONTEXT` | sottofase corrente (spec completa), file selezionati, errori aperti, e — per il Worker — la sequenza append-only degli step precedenti e dei risultati tool | volatile, **solo append** durante un loop Worker | `ContextBuilder` + loop del ruolo |
| S7 | `OUTPUT` | istruzione di output: nome dello schema, "emit exactly one JSON object" | statica per ruolo | `PromptAssembler` |

**Scheletro concreto** (i contenuti esatti dei file card si scrivono in F1.3 e seguenti; questo è il formato):

```text
### PREAMBLE
You are a component of Red Giant, a deterministic pipeline that operates a small
local model. You perform exactly one role, defined below. You never invent tool
outputs. You never claim success without evidence. Keep every free-text field short.
[...regole universali...]

### ROLE
You are the WORKER. You execute one subtask at a time. [...]

### TOOLS
- read_file(path, start_line=1, end_line=null): read a file slice. [...]
- run_tests(cmd_id): run a whitelisted test command. [...]

### TASK
User request: "Fix the failing test in the billing module"
Domain: coding | Constraints: [...]

### STATE
Plan v2 — P1 done, P2 done, P3 current (Implement changes), P4 pending.

### CONTEXT
Subtask P3.S1 — "Modify service layer" [...spec completa...]
[STEP 1] {"thought": "...", "action": "tool", ...}
[STEP 1 RESULT] tool=read_file ok=true [...]

### OUTPUT
Emit exactly one JSON object matching schema WorkerStep.
```

**Regole non negoziabili:** mai contenuto volatile (timestamp, contatori, path temporanei, esiti) in S1–S4; il loop del Worker appende in coda a S6 e non tocca mai nulla a monte; l'assemblaggio avviene **solo** in `PromptAssembler` (nessun ruolo concatena stringhe per conto suo); un test unitario (F5.3) fallisce se due chiamate consecutive dello stesso ruolo differiscono nel prefisso S1–S4.

### A5. Schema del database (SQLite, `data/redgiant.db`)

DDL integrale — `StateStore.init_schema` esegue esattamente questo (con `PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;`). Le tabelle marcate (F2)(F4)(F6) vengono aggiunte da migrazioni additive nelle fasi indicate; la migrazione è "CREATE TABLE IF NOT EXISTS" — mai ALTER distruttivi.

```sql
CREATE TABLE IF NOT EXISTS tasks (
  id          TEXT PRIMARY KEY,            -- ULID, ordinabile per tempo
  created_at  TEXT NOT NULL,               -- ISO-8601 UTC
  request     TEXT NOT NULL,               -- richiesta utente verbatim
  target_dir  TEXT NOT NULL,               -- root dello Scope del task
  domain      TEXT NOT NULL DEFAULT 'coding',
  status      TEXT NOT NULL CHECK (status IN
              ('queued','running','blocked','completed','partial','failed','cancelled')),
  profile     TEXT NOT NULL,               -- dev-fast | severino-sim | severino
  pipeline    TEXT,                        -- direct | short | full (F6; prima sempre 'full')
  error       TEXT                         -- spiegazione se failed/partial
);
CREATE TABLE IF NOT EXISTS plans (
  task_id  TEXT NOT NULL REFERENCES tasks(id),
  version  INTEGER NOT NULL,               -- 0 = piano statico F1; 1+ = Planner
  actor    TEXT NOT NULL,                  -- 'planner' | 'system' | 'user'
  reason   TEXT NOT NULL,                  -- perché questa versione esiste
  json     TEXT NOT NULL,                  -- Plan serializzato (Pydantic model_dump_json)
  PRIMARY KEY (task_id, version)
);
CREATE TABLE IF NOT EXISTS subtasks (
  task_id     TEXT NOT NULL REFERENCES tasks(id),
  subtask_id  TEXT NOT NULL,               -- es. 'P3.S1'
  phase_id    TEXT NOT NULL,
  title       TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN
              ('pending','running','completed','completed_with_warnings',
               'retry','repair','blocked','failed','skipped')),
  spec        TEXT NOT NULL,               -- SubtaskSpec JSON
  result      TEXT,                        -- FinishReport + Verdict JSON
  attempts    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (task_id, subtask_id)
);
CREATE TABLE IF NOT EXISTS llm_calls (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id       TEXT NOT NULL,
  subtask_id    TEXT,
  role          TEXT NOT NULL,
  schema_name   TEXT,                      -- NULL solo per testo libero finale
  t_start       TEXT NOT NULL,
  prompt_tokens INTEGER NOT NULL,
  cached_tokens INTEGER NOT NULL,          -- dai timings del server: base del reuse_ratio
  gen_tokens    INTEGER NOT NULL,
  prefill_ms    REAL NOT NULL,
  gen_ms        REAL NOT NULL,
  outcome       TEXT NOT NULL CHECK (outcome IN ('ok','timeout','error','invalid'))
);                                         -- 'invalid' = fallita la rivalidazione Pydantic: deve restare 0
CREATE TABLE IF NOT EXISTS tool_calls (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id     TEXT NOT NULL,
  subtask_id  TEXT,
  tool        TEXT NOT NULL,
  args        TEXT NOT NULL,               -- JSON
  ok          INTEGER NOT NULL,            -- 0/1
  evidence    TEXT NOT NULL,               -- JSON list di stringhe
  duration_ms REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  actor      TEXT NOT NULL,                -- 'supervisor' | 'orchestrator' | 'user' | ...
  decision   TEXT NOT NULL,
  reason     TEXT NOT NULL,
  target     TEXT,                         -- es. subtask_id
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS budgets (
  task_id   TEXT NOT NULL,
  key       TEXT NOT NULL CHECK (key IN ('tokens','tool_calls','retries','wall_s')),
  limit_val INTEGER NOT NULL,
  used      INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (task_id, key)
);
CREATE TABLE IF NOT EXISTS eval_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at  TEXT NOT NULL,
  profile     TEXT NOT NULL,
  git_ref     TEXT NOT NULL,               -- commit del codice misurato
  report_path TEXT NOT NULL
);
-- (F2)
CREATE TABLE IF NOT EXISTS approvals (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id  TEXT NOT NULL,
  kind     TEXT NOT NULL CHECK (kind IN ('irreversible_op','clarification')),
  payload  TEXT NOT NULL,                  -- JSON: cosa si chiede, con contesto
  status   TEXT NOT NULL CHECK (status IN ('pending','answered','expired')),
  answer   TEXT
);
-- (F4)
CREATE TABLE IF NOT EXISTS checkpoints (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  kind       TEXT NOT NULL CHECK (kind IN ('post_plan','post_subtask','pre_risky','pre_replan')),
  git_ref    TEXT,                         -- commit sul branch di lavoro del target
  slot_file  TEXT,                         -- (F5) file KV salvato, se esiste
  created_at TEXT NOT NULL
);
-- (F6)
CREATE TABLE IF NOT EXISTS routing_log (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id    TEXT NOT NULL,
  signals    TEXT NOT NULL,                -- RoutingSignals JSON
  classifier TEXT,                         -- ClassifierOutput JSON (NULL se decisione deterministica)
  pipeline   TEXT NOT NULL,
  outcome    TEXT                          -- riempito a fine task: base della calibrazione
);
CREATE INDEX IF NOT EXISTS idx_subtasks_status ON subtasks(task_id, status);
CREATE INDEX IF NOT EXISTS idx_llm_calls_task  ON llm_calls(task_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_st   ON tool_calls(task_id, subtask_id);
CREATE INDEX IF NOT EXISTS idx_approvals_pend  ON approvals(status);
```

**Semantica di scrittura:** ogni mutazione passa da `StateStore` (nessun SQL fuori da `store.py`), in transazione, con `actor` obbligatorio sulle tabelle che lo prevedono; gli artefatti grandi (contenuti file, diff lunghi) NON vanno nel DB ma su disco in `data/tasks/<id>/` con riferimento nel JSON (specsheet §8: artefatti separati).

### A6. Configurazione — contenuto integrale di `config/default.toml`

I profili in `config/profiles/*.toml` sovrascrivono solo le chiavi che differiscono (merge superficiale per sezione). Caricamento: `Config.load(profile_name)` legge default + profilo, valida con dataclass tipizzate, fallisce rumorosamente su chiavi sconosciute.

```toml
[llm]
base_url = "http://127.0.0.1:8080"   # endpoint llama-server del profilo
ctx_size = 8192                      # tetto duro per chiamata (D8; rivisto in F0.6 coi numeri)
timeout_s = 600                      # alto: su CPU una chiamata lunga è normale, non un errore
temperature = 0.2                    # default; override per ruolo in [roles.<name>]
max_tokens_default = 1024            # tetto generazione se il ruolo non specifica
# llama.cpp version pin: <TAG SCRITTO IN F0.2> — cambiarlo = rifare bench F0.5

[paths]
db = "data/redgiant.db"
models_dir = "models/"
tasks_dir = "data/tasks/"            # log e artefatti per task
slots_dir = "data/slots/"            # (F5) KV salvate
ripgrep = "rg"                       # binario di sistema

[budget]                             # default per task; l'Assessor (F6) li modula
max_total_tokens = 32000
max_tool_calls = 100
max_retries_per_subtask = 2          # specsheet §13
max_wall_s = 7200

[worker]
max_steps = 20                       # passi ReAct per sottofase (D20)
step_max_tokens = 768                # tetto di generazione per step (F2.5: 512 troncava
                                     # gli edit_file lunghi; il troncamento in-loop e' un
                                     # dato, non un abort del tentativo)

[web]
host = "127.0.0.1"
port = 8090

[security]
writable_globs = []                  # riempito per task, mai globale
shell_whitelist = ["pytest", "php", "composer", "git"]   # eseguibili ammessi da proc.py

[eval]
tasks_dir = "redgiant/eval/tasks"
```

| Perché queste chiavi | |
|---|---|
| `llm.ctx_size` duro e non "soft" | un prompt fuori budget su CPU costa minuti: meglio un errore immediato con diagnosi (chi ha gonfiato cosa) che una chiamata lenta "riuscita" |
| `timeout_s = 600` | su 4 core Zen 2 una generazione lunga è fisiologica; un timeout basso produrrebbe falsi errori e retry (= altro tempo) |
| `security.writable_globs` vuoto di default | lo scope di scrittura è una proprietà del task, mai dell'installazione: il default sicuro è "nessuna scrittura" |
| `budget.*` come default e non costanti | l'Assessor (F6.3) li modula per task; prima di F6 valgono i default |

### A7. Catalogo tool — contratto comportamentale completo (F1.4; `web.*` in F7.2)

Ogni tool: modello Pydantic degli argomenti (omonimo, in `tools/*.py`), handler puro, esecuzione SOLO via `ToolRouter.dispatch` (che applica Scope, timeout, logging, policy di approvazione). L'output testuale dei tool entra nel contesto S6 **come blocco dati citato**, mai come istruzioni (specsheet §17: prompt-injection dai contenuti).

| Tool | Firma handler | Rischio | Comportamento esatto |
|---|---|---|---|
| `read_file` | `read_file(path: str, start_line: int = 1, end_line: int \| None = None) -> ToolResult` | low | Scope.check_read; legge testo (UTF-8, errori sostituiti); max 400 righe per chiamata — se il file è più lungo tronca e scrive in `data` `{"truncated": true, "total_lines": N}`: il modello DEVE vedere che manca qualcosa. Evidenza: `"read <path>:<a>-<b> (<n> lines)"`. Errori: file inesistente → `ok=false, error="not_found"`; binario → `error="binary_file"`. |
| `list_files` | `list_files(glob: str, max_results: int = 200) -> ToolResult` | low | glob relativo alla root dello Scope; ritorna path ordinati; oltre il limite → tronca e lo dichiara. Mai directory fuori Scope, nemmeno in lettura. |
| `search_code` | `search_code(pattern: str, glob: str \| None = None, max_results: int = 50) -> ToolResult` | low | esegue `rg --json -e <pattern>` (niente shell: lista argv, mai stringa); ritorna `{path, line, text}` per match; regex invalida → `ok=false, error="bad_pattern", detail=<stderr rg>`. |
| `write_patch` | `write_patch(path: str, unified_diff: str) -> ToolResult` | medium | Scope.check_write; applica un diff unificato al file (implementazione nostra, no `patch` di sistema); hunks non applicabili → li elenca in `data.rejected` con contesto atteso vs reale, `ok=false` se TUTTI respinti; il file viene riscritto atomicamente (tmp+rename). Evidenza: righe aggiunte/rimosse. È reversibile via git (checkpoint F4.4). |
| `write_file` | `write_file(path: str, content: str) -> ToolResult` | medium | **Aggiunto in F1.11 su evidenza empirica** (T006): edit_file non crea file nuovi e i diff puri-additivi sono fragili; la creazione robusta per un E2B è il contenuto completo. Scope-checked, scrittura atomica, evidenza con conteggio righe. |
| `edit_file` | `edit_file(path: str, old_string: str, new_string: str, replace_all: bool = False) -> ToolResult` | medium | **Aggiunto in F1.11 su evidenza empirica**: i diff unificati sono ostili ai modelli piccoli (contesto sbagliato di una riga vuota = hunk respinto, osservato ripetutamente su fix logicamente corretti). Sostituzione esatta di stringa: `old_string` deve occorrere esattamente una volta (o `replace_all`); 0 occorrenze → `not_found_in_file`, >1 → `not_unique` con conteggio. Scrittura atomica. È lo strumento di editing PRIMARIO nella card del Worker; `write_patch` resta per edit multi-punto. |
| `run_tests` | `run_tests(cmd_id: str) -> ToolResult` | medium | esegue il comando registrato sotto `cmd_id` nella whitelist del task (definita nell'onboarding del task / task.toml dell'Evaluator) — MAI una stringa libera dal modello. Cwd = root Scope; timeout dal ToolSpec; evidenza = `exit_code` + ultime 50 righe stdout+stderr (il tail, perché è lì che pytest riassume). |
| `register_test_command` | `register_test_command(cmd_id: str, argv: list[str]) -> ToolResult` | medium | **Aggiunto in F2 su richiesta utente** ("i comandi di test li deve decidere l'AI, non io: io do solo istruzioni"): il Worker registra un comando di test scoperto leggendo il repo. Guardia invariata: `argv[0]` DEVE stare in `security.shell_whitelist` (il confine umano resta sugli eseguibili); persiste in `task_config.json` per le riprese. Complementare alla **scoperta deterministica** `discover_test_commands(root)` eseguita all'avvio di ogni job (test_*.py⇒pytest, test.php⇒php, composer.json scripts.test⇒composer): la config utente, se presente, vince; il pre-flight bloccante di F2.4-bis decade (una verifica non risolvibile a creazione può esserlo a runtime). |
| `git_status` / `git_diff` | `git_status() -> ToolResult` / `git_diff(ref: str = "HEAD") -> ToolResult` | low | sul repo del target; output porcelain/unified troncato a 400 righe; servono al Verifier e al Supervisor come evidenza di "cosa è cambiato davvero". |
| `web_search` (F7) | `web_search(query: str, max_results: int = 8) -> ToolResult` | low | motore deciso in F7.2 (SearXNG self-hosted vs API di sola-search — decisione 🧑); ritorna `{title, url, snippet}`; nessun contenuto di pagina (per quello c'è fetch_url). |
| `fetch_url` (F7) | `fetch_url(url: str) -> ToolResult` | medium | GET con timeout e size-cap; estrazione testo (strip HTML); cache su disco in `data/tasks/<id>/fetch/` (hash URL → file) perché la verifica citazioni (F7.1) deve rileggere LA STESSA copia che il modello ha visto; URL non-http(s) → rifiutato. |

**Syntax gate (aggiunto 2026-08-01 su richiesta dell'utente, pre-F2):** ogni tool di scrittura verifica la sintassi del **contenuto risultante** PRIMA della scrittura atomica — `.py` via `ast.parse` (in-process), `.php` via `php -l` (se il binario esiste, altrimenti skip dichiarato), `.json` via `json.loads`, `.toml` via `tomllib`; altre estensioni non verificate. Sintassi rotta ⇒ scrittura **rifiutata** con `error="syntax_error"` e dettaglio (riga + messaggio): il file su disco non entra mai in uno stato sintatticamente invalido, e il modello riceve il perché come dato immediato invece di scoprirlo due step dopo dai test. Motivazione: nel collaudo F1.11 i loop più costosi nascevano da file corrotti scoperti tardi; questo sposta l'oracolo al punto più economico.

**Policy trasversali (ToolRouter):** tool di lettura → sempre ammessi nello Scope; scrittura → solo `writable_globs` del task; `requires_approval=true` → il dispatch crea una riga `approvals`, mette il task in `blocked` e NON esegue finché l'utente non approva (F2.3); ogni dispatch logga su `tool_calls` con evidenze e durata; un tool che lancia un'eccezione non prevista → `ok=false, error="internal:<classe>"` e il task NON muore (il fallimento del tool è un dato per il modello, non un crash del sistema).

---

## Rituale di fine fase (obbligatorio, identico per ogni fase, eseguito senza che l'utente lo chieda)

Si esegue al completamento dell'ultima sottofase 🔎 di una fase. È una procedura, non una lista di buone intenzioni: i passi sono ordinati e ognuno è bloccante per il successivo.

**Passo 1 — Aggiornare `memory/plan_red_giant.md`.** Spuntare i checkbox della fase e delle sottofasi; aggiornare il campo **Stato** in testa al file (fase completata + prossima azione); se una firma o un comportamento sono cambiati in corso d'opera, la modifica è già stata scritta qui *prima* del codice (regola di direzione) — verificare che sia così, con la ragione annotata nella riga della sottofase.

**Passo 2 — Aggiornare `memory/codebase_reference.md`.** Per ogni elemento nuovo o cambiato nella fase: classi con ogni metodo e firma completa, tabelle DB con ogni colonna, endpoint con input/output/errori, chiavi di config, test con cosa dimostra ciascuno. Aggiornare le sezioni: "Cosa NON esiste ancora" (rimuovere ciò che ora esiste), "Trappole già disinnescate" (aggiungere ogni problema incontrato, con la **causa tecnica**), "Debito tecnico aperto" (con il perché è rimandato e quando va affrontato), "Il perché delle scelte non ovvie".

**Passo 2-bis — Rileggere e riscrivere `README.md`** (regola specifica di questo progetto, richiesta dall'utente il 2026-08-01). Il README è in inglese, pensato per essere trovato e capito da persone e agenti AI che fanno ricerca: a ogni fine fase va riletto per intero e aggiornato — stato, roadmap (checkbox), decisioni tecniche rilevanti aggiunte nella fase, findings empirici nuovi, comandi. Un README fermo a due fasi fa è un documento che mente.
**Integrazione (richiesta utente, 2026-08-02):** la Roadmap del README porta, per OGNI fase, la **retrospettiva onesta**: com'è andata, cosa si è scoperto, cosa si è corretto, perché è stata fatta così, il debito, le prospettive. "Si deve capire di cosa stiamo parlando" — è lo stato dell'unione del progetto, e va tenuta aggiornata a ogni chiusura di fase.

**Passo 3 — Verifica meccanica dell'atlante.** Eseguire:

```powershell
python scripts/check_reference.py
```

Il programma estrae via AST tutte le classi e le funzioni di `redgiant/` con le firme reali e le confronta con quelle documentate nell'atlante. Exit code ≠ 0 → il rituale **si ferma qui** finché atlante e codice non coincidono. Un atlante sbagliato è peggio di nessun atlante.

**Passo 4 — Messaggio ESTREMAMENTE DETTAGLIATO all'utente**, contenente: (a) lo stato dell'implementazione; (b) i checkbox della fase e di tutte le sottofasi; (c) un commento sullo stato generale del progetto e uno specifico sulla fase (cosa è andato liscio, cosa ha morso, cosa è stato deciso strada facendo); (d) i numeri, se la fase ne ha prodotti (bench, A/B, metriche).

**Passo 5 — Commit e push su branch versionato.**

```powershell
git checkout -b vX.Y.Z
git add -A
git commit -m "vX.Y.Z — F<n>: <sintesi della fase>"
git push -u origin vX.Y.Z
git push -u github vX.Y.Z
```

Il numero `vX.Y.Z` viene dalla tabella sotto per i completamenti di fase; i commit intermedi durante una fase avanzano di `+0.0.1` (piccoli, incluse modifiche solo-documentali) o `+0.1.0` (medi), sempre su branch nominato come la versione. `redgiant/__init__.py::__version__` va allineata nello stesso commit.

**Regola `main` (richiesta dall'utente, 2026-08-01):** a ogni **bump MAJOR** (`x.y.z` → `(x+1).0.0`), dopo il push del branch versionato, **mergeare tutto in `main`** e pushare `main` su entrambe le remote. `main` rappresenta sempre l'ultima major stabile (creato alla `v1.1.0` come baseline).

| Evento | Versione | Entità |
|---|---|---|
| Piano iniziale (fatto) | `v1.0.0` | — |
| Riscritture del piano pre-F0 | `v1.0.x` | piccola |
| Fine F0 | `v1.1.0` | media |
| Fine F1 | `v2.0.0` | grande |
| Fine F2 | `v2.1.0` | media |
| Fine F3 | `v3.0.0` | grande |
| *Interludio planner-system (PS0–PS7, 2026-08-02/03)* | `v3.1.0` → `v4.0.0` | v. `plan_planner_system.md` |
| *Campagna thinking (TH0–TH3, 2026-08-03)* | `v4.1.0` → `v4.2.0` | v. `plan_thinking_ab.md` |
| Fine F3-bis (micro-slice multi-dominio) | `v4.3.0` | media |
| *Campagna LADDER (attribuzione modello↔workflow, 2026-08-03/04)* | `v4.4.0` → `v5.0.0` | v. §LADDER — `v5.0.0` = verdetto TH3 ribaltato da LAD.14 |
| **Fine F5** (contesto e KV cache) — **anticipata prima di F4** | `v6.0.0` | grande |
| **Fine F4** (verifica continua e supervisione) | `v7.0.0` | grande |
| Fine F6 (routing adattivo) | `v7.1.0` | media |
| Fine F7 (domini non-coding completi) | `v8.0.0` | grande |
| Fine F8 (benchmark reali + deploy) | `v9.0.0` | grande |

*(Coda rinumerata il 2026-08-04 con l'inversione F5↔F4: prima F4 e F7 collidevano entrambe su
`v7.0.0`. Gli header delle sezioni-fase riportano ancora i numeri vecchi — **questa tabella è
la fonte di verità**.)*

**Nota di riconciliazione (PS7.3 + TH3, 2026-08-03):** interludio planner-system =
`v3.1.0`–`v4.0.0`; campagna thinking = `v4.1.0`–`v4.2.0`; F3-bis slitta a `v4.3.0`. Il
routing di **F6** userà i dati di PS6 come input (quando pianificare: i micro-task NON si
pianificano — misurato due volte; i task larghi solo se il plansys converte post-thinking).

## 🔬 LA MATRICE DI MISURA — regola di metodo PERMANENTE e NON NEGOZIABILE

**(decisione utente, 2026-08-03: "da adesso in poi tutti i test dovranno essere svolti come
quelli del coding")** — un verde non vale nulla da solo. **Ogni** batteria di task, in
**ogni** fase futura (F4, F6, F7, F8, ladder, benchmark pubblici, retest dei verdetti
aperti), si misura sulla matrice completa a DUE ASSI:

| | **senza thinking** | **con thinking** |
|---|---|---|
| **NUDO** (materiali inline, 1 completion, zero tool/loop/retry) | **B1** — quanto è merito del *modello* | **B3** — quanto è merito del *ragionamento puro* |
| **WORKFLOW** (+ ablazioni) | **B2** — quanto sale il *pavimento*, e per merito di *quale pezzo* | **B4** — se ragionamento e impalcatura si sommano, si annullano o si ostacolano |

**Le sotto-varianti sono obbligatorie, non facoltative:**
- **B2 — ablazioni** (`RG_WORKER_ABLATE` ∈ {search, verify, retry, calc, coherence}; per il
  plan compiler `RG_PLANSYS_ABLATE` ∈ {oracle, ledger, entry}): senza, "il workflow funziona"
  è una frase, non una misura — il delta va attribuito al **componente**. **Ogni componente
  nuovo nasce con la sua leva di ablazione**: se non è ablabile, il suo contributo non è
  attribuibile e la misura non vale.
- **B4 — collocazione del thinking** (`RG_THINKING_ROLES`): TUTTE le varianti pertinenti al
  percorso in prova. Percorso diretto: solo Giano. Plan compiler: almeno solo-Giano,
  solo-pianificazione, tutti, e le combinazioni che i dati suggeriscono (TH1 ha mostrato che
  la *collocazione* conta più della quantità, F20).
- **B4 porta le ABLAZIONI come B2** (precisazione utente): il blocco col thinking si esegue
  anche `-search`, `-verify`, `-retry` — **simmetria obbligatoria**. Serve a rispondere alla
  domanda che nessun altro braccio pone: *il ragionamento SOSTITUISCE un componente
  mancante?* (es. un Giano che pensa compensa l'assenza di verifica, o di ricerca?). Senza
  la simmetria si può solo dire "col thinking va meglio/peggio", mai *perché*.

**Le tre letture che solo la matrice completa consente:** (a) **B2−B1** = valore
dell'impalcatura; (b) **B3−B1** = valore del ragionamento a parità di impalcatura (zero);
(c) **B4−B2 vs B3−B1** = se il ragionamento paga *di più* dentro o fuori dal workflow.
Nessuna di queste è deducibile da un braccio solo.

**Corollario di disegno (ladder):** se **B1 passa**, il task non misura niente di nostro e va
reso più largo finché il nudo non cade (asse dell'ampiezza: materiali oltre il contesto,
aggregazione, catene). Si misurano col workflow SOLO i gradini dove il nudo è caduto.

**Strumenti:** `bench/ladder/generate.py` (corpus a difficoltà crescente, seed fisso) ·
`bench/ladder/run_naked.py [--think]` (B1/B3) · `bench/ladder/run_agentic.py` (B2/B4, bracci
e ablazioni da CLI) · `bench/naked_probe.py` (braccio nudo dei task non-ladder).

**RETEST OBBLIGATORI A FINE PERCORSO (decisione utente, 2026-08-03 — i verdetti D11 e TH3
sono APERTI, non tombali):**
1. **Retest planner+thinking col router attivo (dopo F6/F7):** entrambi i verdetti negativi
   sono stati misurati SOLO su coding sintetico senza routing. Col router per taglia attivo
   e i domini everyday/ricerca/matematica in piedi, vanno rimisurati: il thinking potrebbe
   non pagare sul codice ma pagare sull'everyday o sulla matematica — non lo sappiamo, e
   "non lo sappiamo" si risolve misurando, non presumendo. Config attuale: entrambi OFF di
   default (`[plansys] enabled=false`, `RG_THINKING_ROLES` non settata), riattivabili in
   qualunque momento senza toccare codice.
2. **Benchmark pubblici (fine progetto, pre/post F8):** eseguire i benchmark più utilizzati
   e pertinenti (candidati in `memory/ambition.md` §2: BFCL per function calling,
   structured-output benchmarks, GSM8K-class per la matematica col thinking) per avere
   **valori pubblicamente comparabili** — le batterie interne dimostrano i delta, solo i
   benchmark pubblici dimostrano la posizione assoluta.

---

## Mappa delle fasi e gate d'ingresso

| Fase | Titolo | Dipende da | Gate d'ingresso (verificabile) |
|---|---|---|---|
| F0 | Fondazioni e misure di base | — | — |
| F1 | Nucleo deterministico + Worker | F0 | numeri F0.6 scritti nell'atlante e approvati |
| F2 | GUI web minima | F1 | F1.11 verde (walking skeleton dimostrato) |
| F3 | Pianificazione | F1 | Evaluator v0 operativo con baseline registrata |
| F4 | Verifica continua e supervisione | F3 | F3.6 verde (piano dinamico + replanning) |
| F5 | Contesto e KV cache | F4 | pipeline completa misurabile (F4.7 verde) |
| F6 | Routing adattivo | F4 | metriche per-pipeline disponibili |
| F7 | Domini non-coding | F6 | routing per dominio attivo |
| F8 | Benchmark reale + deploy | F5, F7 | chatbot Laravel disponibile su Severino |

L'ordine di esecuzione è strettamente sequenziale (F2 prima di F3 anche se concettualmente indipendenti: da F2 in poi l'utente testa dalla GUI, e il suo feedback deve arrivare *prima* che la pipeline si complichi).

---

## Fase 0 — Fondazioni e misure di base → `v1.1.0`

📎 **Specsheet:** §15 (budget), §16 (KV cache), §23 (MVP) · **Decisioni:** D1, D2, D3, D5, D6, D8, D14, D15
🎯 **Scope:** repo + ambiente Python, llama-server operativo nei tre profili, Gemma 4 E2B Q4 verificato (constrained decoding incluso), numeri di baseline che fissano i budget, strumento di verifica dell'atlante.
🧭 **Perché questa fase, perché prima di tutto:** ogni decisione a valle (budget di contesto, timeout, dimensione del preambolo, perfino la fattibilità del progetto) dipende da misure che oggi non abbiamo. E il rischio più concreto dell'intero progetto — che il supporto di llama.cpp per un modello nuovissimo sia acerbo (la specsheet homelab lo segnala esplicitamente in §16.3) — va scoperto quando cambiare rotta costa zero righe di codice. F0 non scrive pipeline: F0 compra certezze.

#### F0.1 — Struttura repo e progetto Python

- [x] 🤖 **Obiettivo:** un progetto Python installabile e riproducibile, con la struttura di §A1 (le sole parti F0).
- **Motivazione:** tutto ciò che segue importa `redgiant.*` e legge `config/`; farlo per primo evita ristrutturazioni. Il lockfile da subito perché la riproducibilità non si retrofitta (D14).
- **Implementazione:**
  - `pyproject.toml`: `[project] name="redgiant"`, `requires-python=">=3.12"`, dipendenze §A2 con versione esatta (`==`), `[project.scripts] rg = "redgiant.cli:main"` (il modulo `cli` arriva in F1.9: fino ad allora l'entry point può puntare a uno stub che stampa versione e aiuto).
  - `requirements.lock` generato con `pip-compile --generate-hashes`; ambiente in `.venv/` (gitignored).
  - `redgiant/__init__.py`: `__version__: str = "1.1.0"` (aggiornata nel commit di fine fase).
  - `redgiant/config.py`: caricamento TOML di §A6.
    ```python
    @dataclass(frozen=True)
    class LlmProfileCfg:  base_url: str; ctx_size: int; timeout_s: float; temperature: float; max_tokens_default: int
    @dataclass(frozen=True)
    class PathsCfg:       db: Path; models_dir: Path; tasks_dir: Path; slots_dir: Path; ripgrep: str
    @dataclass(frozen=True)
    class BudgetCfg:      max_total_tokens: int; max_tool_calls: int; max_retries_per_subtask: int; max_wall_s: int
    @dataclass(frozen=True)
    class WebCfg:         host: str; port: int
    @dataclass(frozen=True)
    class SecurityCfg:    writable_globs: tuple[str, ...]; shell_whitelist: tuple[str, ...]
    @dataclass(frozen=True)
    class Config:
        profile_name: str; llm: LlmProfileCfg; paths: PathsCfg; budget: BudgetCfg
        web: WebCfg; security: SecurityCfg; worker_max_steps: int; eval_tasks_dir: Path
        @classmethod
        def load(cls, profile_name: str, config_dir: Path | None = None) -> "Config"
    ```
    Merge: `default.toml` + `profiles/<nome>.toml` (override per sezione, superficiale). Chiave sconosciuta in un TOML → `ValueError` con il nome della chiave: gli errori di config si pagano subito, non a runtime.
  - `config/default.toml` col contenuto integrale di §A6; `config/profiles/dev-fast.toml` con l'endpoint del server GPU locale.
  - `README.md`: cos'è Red Giant (3 righe), i tre profili, come si avvia il server, come si lancia un bench.
- **Casi limite:** Python di sistema ≠ 3.12 → il README documenta l'uso di `py -3.12`; TOML malformato → errore di caricamento con path del file.
- **Accettazione:** `pip install -e .` pulito in un venv nuovo; `python -c "from redgiant.config import Config; print(Config.load('dev-fast'))"` stampa la config; `rg --help` (stub) risponde.

#### F0.2 — llama.cpp e modello

- [x] 🤖 **Obiettivo:** llama-server funzionante su questo PC in build CUDA e in build CPU pura, con Gemma 4 E2B Q4 scaricato e generante.
- **Motivazione:** D2 e D6. Servono *due* build locali perché `dev-fast` (iterazione) e la modalità CPU (misure oneste, anche fuori dal Docker di F0.4) sono entrambe quotidiane. La versione di llama.cpp va **pinnata** subito: il comportamento di cache e grammatiche cambia tra release, e un bench fatto su una versione diversa non è confrontabile.
- **Implementazione:**
  - Scaricare/compilare due binari llama.cpp alla **stessa release** (tag annotato in `config/default.toml` come commento e nell'atlante): variante CUDA e variante CPU (AVX2).
  - `scripts/download-model.ps1`: scarica il GGUF di Gemma 4 E2B Q4 in `models/`; URL e SHA256 **scritti nel file**; verifica hash dopo il download; idempotente (se il file c'è e l'hash torna, esce).
  - `scripts/start-llama.ps1 -Profile dev-fast|severino-sim|severino -Ctx <int>`:
    - `dev-fast` → binario CUDA, `--n-gpu-layers 999`;
    - `severino-sim` → delega a `docker compose -f docker/severino-sim/compose.yml up` (da F0.4);
    - `severino` → messaggio: il server su Severino si gestisce dal box (F8); il profilo client punta all'endpoint Tailscale.
    - Flag comuni: `--model models/<gguf>`, `--ctx-size`, `--parallel 1`, `--slot-save-path data/slots/` (predisposto da subito: serve in F0.5 per la prova slot), porta dal profilo.
  - Smoke test documentato nel README: `GET /props` risponde; una completion breve genera testo sensato.
- **Casi limite:** VRAM/quantizzazione incompatibili → annotare nell'atlante la configurazione funzionante esatta; il server non espone un campo atteso nei timings → annotare la versione e il campo mancante (impatta F0.5 e F5.2).
- **Accettazione:** entrambe le build avviabili da script; `/props` risponde su entrambe; generazione di prova ok; tag llama.cpp e SHA256 del modello scritti dove previsto.

#### F0.3 — ⚠️ Verifica del constrained decoding su Gemma 4 E2B

- [x] 🤖 **Obiettivo:** dimostrare (o smentire) che il guided decoding di llama-server con questo modello produce il 100% di output validi su schemi realistici, e misurarne il costo.
- **Motivazione:** D3 è una scommessa fondativa: l'intera architettura assume che "output malformato" sia una categoria di errori estinta. Se il supporto per un modello nuovissimo è rotto (tokenizer, template di chat, bug di grammatica — tutte cose viste all'uscita di modelli nuovi), va saputo ORA: il fallback cambia la fase, non una riga.
- **Implementazione — protocollo esatto:**
  1. Tre schemi di prova, scritti come modelli Pydantic in un modulo usa-e-getta `bench/schemas_probe.py` (diventeranno la base dei veri schemi):
     - `ProbeDecision` — enum di decisione a 9 valori + `reason: str (max 200)` (simula `SupervisorDecision`);
     - `ProbePlan` — oggetto annidato: `goal`, `success_criteria: list[str] (max 5)`, `phases: list[{id,title,depends_on,completion_criteria}] (max 5)` (simula `PlannerOutput`);
     - `ProbeSubtasks` — lista di 4 oggetti con 8 campi ciascuno (simula `PhaseDesign`).
  2. Per ogni schema: **20 generazioni** con prompt realistico (una richiesta di refactoring plausibile), `temperature 0.2`, su build CPU.
  3. Registrare per ogni run: JSON valido? Schema rispettato (rivalidazione Pydantic)? Contenuto sensato (giudizio umano a campione su 5/20)? tok/s con grammatica vs stesso prompt senza grammatica (il guided decoding ha un costo per token: va conosciuto).
  4. Output: `bench/results/f0_constrained_decoding.md` con tabella e conclusione.
- **Matrice di fallback (in ordine, si scende solo se il livello sopra fallisce):** (1) quantizzazione diversa (Q5/Q8: alcuni bug mordono solo certe quant); (2) release diversa di llama.cpp (anche più vecchia); (3) modello ponte più maturo della stessa taglia — **decisione da prendere con l'utente**, perché tocca D1.
- **Accettazione:** validità 100% (60/60) o, se no, diagnosi scritta + fallback deciso; costo della grammatica quantificato; 📌 esito, versioni e configurazione esatta nell'atlante.

#### F0.4 — Profilo `severino-sim`

- [x] 🤖 **Obiettivo:** un container Docker che replica il vincolo di risorse di Severino (D5) per misure oneste sul PC di sviluppo.
- **Motivazione:** D6. Severino reale non è sempre disponibile e i bench lo saturerebbero disturbando lo stack di casa; il simulatore rende le misure ripetibili e quotidiane. Non simula la *microarchitettura* (Zen 4 ≠ Zen 2 a parità di core), quindi i numeri vanno trattati come proxy ottimista: la taratura finale contro Severino reale avviene a ogni fine fase quando possibile e sistematicamente in F8.
- **Implementazione:** `docker/severino-sim/compose.yml` — servizio `llama-cpu`: immagine llama.cpp server CPU (stessa release pinnata di F0.2), `cpuset: "0-3"`, `mem_limit` concordata 🧑, `--threads 4 --parallel 1 --ctx-size` dal profilo, volume `./models:/models:ro`, volume slot, porta mappata su quella di `config/profiles/severino-sim.toml`. Healthcheck su `/props`.
- 🧑 **Richiede l'utente:** conferma dei numeri di allocazione **prima del freeze**: tutti i bench successivi dipendono da questi numeri e cambiarli dopo invalida i confronti storici. → **DECISO (2026-08-01): 2 core + 10 GB sul PC di sviluppo** (un core Zen 4 @5.3GHz vale ~2× un core Zen 2 @15W: 2 core qui approssimano i 4 di Severino); su Severino reale: 4 core. Un bench parziale a 4 core è stato scartato per questo motivo.
- **Casi limite:** cpuset su Windows/WSL2 — verificare che il limite morda davvero (stress test e lettura di `docker stats`); se WSL2 non onora `cpuset`, fallback `cpus: 4.0` (quota equivalente) con annotazione nell'atlante della differenza (quota ≠ affinità).
- **Accettazione:** container su e healthy; `docker stats` mostra il tetto CPU rispettato sotto carico; profilo `severino-sim.toml` punta al container e una generazione di prova completa.

#### F0.5 — Benchmark di baseline

- [x] 🤖 **Obiettivo:** i numeri fondamentali del progetto: quanto costa il prefill, quanto la generazione, quanto salva la cache, su `dev-fast` e `severino-sim`.
- **Motivazione:** D8 parla di "~4-8K token" per fede ragionata; questa sottofase lo trasforma in un numero difendibile. Inoltre F5 avrà bisogno di un "prima" onesto: questo è il prima.
- **Implementazione:** `bench/run_bench.py`, riproducibile con un comando.
  ```python
  def run(profile: str, ctx_sizes: list[int], repeats: int, out_dir: Path) -> Path
  def main() -> int   # argparse: --profile, --ctx 1024 4096 8192 16384, --repeats 3, --out bench/results/
  ```
  Misure, ciascuna ripetuta `repeats` volte con media e deviazione:
  1. **Prefill puro:** prompt sintetico deterministico (testo fisso ripetuto, MAI random — riproducibilità) di N token, `max_tokens=1`, leggere `prompt_ms` dai timings → tok/s di prefill per ctx ∈ {1K, 4K, 8K, 16K}.
  2. **Generazione:** prompt corto fisso, `max_tokens=256` → tok/s di generazione.
  3. **Riuso del prefisso:** chiamata A con prompt P (ctx 4K), poi chiamata B con P + 200 token in coda, `cache_prompt=true` → leggere i token riprocessati; il risparmio atteso è ~P. Poi chiamata C con un byte cambiato A METÀ di P → dimostrare che il riuso si ferma lì (questa è la prova empirica che giustifica D9, da citare nell'atlante).
  4. **Slot save/restore:** salvare la KV dopo A (`POST /slots/{id}?action=save`), riavviare il server, ripristinare, rifare B → misurare il tempo risparmiato vs prefill freddo. Stabilisce la **soglia di convenienza** dello slot-save (sotto quanti token di prefisso non vale la pena).
  5. Output: CSV grezzi in `bench/results/raw/` (gitignored) + `bench/results/f0_baseline.md` con le tabelle (committato).
- **Casi limite:** timings assenti o con nomi diversi nella release pinnata → adattare la lettura e annotare; 16K fuori memoria sul container → registrare il fallimento come dato (è un vincolo reale di Severino, non un errore del bench).
- **Accettazione:** `python bench/run_bench.py --profile severino-sim` produce il report senza intervento; le 4 misure hanno numeri con deviazione; il report dichiara profilo, versione llama.cpp, quantizzazione, data.

#### F0.6 — 📌 Decisioni derivate dai numeri

- [x] 🤖 **Obiettivo:** trasformare i numeri di F0.5 in vincoli di configurazione scritti e motivati.
- **Motivazione:** è il punto in cui il piano smette di dire "circa" e inizia a dire quanto. Scriverle nell'atlante *con le misure accanto* le rende contestabili in futuro: se un numero cambia (nuovo llama.cpp, RAM aggiunta), si sa quale decisione rivedere.
- **Implementazione — decisioni da fissare, ciascuna con la misura che la giustifica:**
  1. `llm.ctx_size` definitivo (D8): il ctx oltre il quale il prefill freddo su `severino-sim` supera una soglia di tollerabilità (proposta: 60s; 🧑 conferma).
  2. Budget di generazione per ruolo (`max_tokens` per Worker step, Planner, ecc.) dai tok/s di generazione.
  3. Dimensione massima del preambolo S1–S3 (in token): quanto prefisso statico possiamo permetterci dato il riuso misurato.
  4. `llm.timeout_s` reale: 2× il caso peggiore osservato.
  5. Soglia di convenienza dello slot-save (da F0.5.4), userà `checkpoints.slot_file` solo sopra soglia.
  6. Prima definizione della soglia di `reuse_ratio` accettabile (servirà a F5.6).
  Aggiornare `config/default.toml` e l'atlante (sezione dedicata "Numeri di baseline e budget derivati").
- **Accettazione:** ogni valore in `config/default.toml` che deriva da una misura ha, nell'atlante, la misura accanto; l'utente ha visto e approvato la tabella (gate d'ingresso di F1).

#### F0.7 — `scripts/check_reference.py`

- [x] 🤖 **Obiettivo:** lo strumento che rende l'atlante meccanicamente verificabile (usato dal Passo 3 del rituale, da fine F0 in poi).
- **Motivazione:** le istruzioni globali dell'utente lo richiedono ("verifica meccanicamente che le firme documentate corrispondano al codice reale"); automatizzarlo lo rende non-negoziabile anche sotto fretta.
- **Implementazione:**
  ```python
  def extract_signatures(pkg_dir: Path) -> dict[str, list[str]]
      # AST di ogni .py in redgiant/: per modulo, "class Nome" e "def nome(argomenti_tipizzati) -> ritorno"
      # (normalizzati: niente spazi doppi, default abbreviati)
  def extract_documented(md_path: Path) -> dict[str, list[str]]
      # parse dei blocchi ```python nell'atlante, sezione "Classi e metodi": stesse normalizzazioni
  def compare(real: dict, doc: dict) -> list[str]
      # differenze in tre categorie: nel codice ma non documentato (atlante rotto),
      # documentato ma non nel codice (peggio), firma divergente
  def main() -> int   # stampa il diff leggibile per categoria; exit 1 se differenze
  ```
  Esclusioni dichiarate nel file: metodi `_privati` (documentarli è facoltativo ma se documentati devono coincidere), `tests/`, `bench/`.
- **Casi limite:** file con errori di sintassi → il check fallisce con il path (giusto così: codice rotto = rituale fermo); overload/decoratori → si confronta la firma della definizione.
- **Accettazione:** eseguito su una discrepanza artificiale (metodo aggiunto e non documentato) la rileva e ritorna 1; su repo allineato ritorna 0.

#### F0.8 — 🔎 Verifica di fase

- [x] Condizioni, tutte insieme: i tre profili si avviano dai rispettivi script/compose; `bench/run_bench.py` produce il report con un comando; il constrained decoding è dimostrato sui 3 schemi con i numeri (o il fallback è stato deciso e documentato); `check_reference.py` funziona nei due sensi; i numeri F0.6 sono nell'atlante e approvati dall'utente.

**Rituale di fine fase** → `v1.1.0`. Il codebase_reference, da questa fase, fotografa: struttura repo, config con i valori derivati, script, bench e le sue tabelle, esiti F0.3, trappole incontrate (ce ne saranno).

> **ESITO F0 (2026-08-01, `v1.1.0`).** Tutte le sottofasi verificate. Numeri chiave (severino-sim = 2 core 9900X ≈ 4 core Severino, decisione utente): prefill freddo 1K/4K/8K/16K = 6.8/30.7/69.6/173.6s · generazione 35.8 tok/s (memory-bound: quasi invariata vs 24 thread) · riuso prefisso: 65 token riprocessati in append vs 7971 con 1 byte cambiato a metà (D9 provata empiricamente, fattore ~120×) · constrained decoding 60/60 forma + 60/60 contenuto, overhead grammatica 0.4–9.8% (D3 confermata). **Deviazioni dal piano:** (a) pin del runtime = digest dell'immagine Docker b10200 + binari Windows b10217 (ghcr non pubblica tag per-release; b10200 non ha asset Windows); (b) F0.5.4: slot save/restore con API integra ma riuso post-restore NON funzionante su b10200 → soglia di convenienza slot-save NON fissabile, rinviata a F5.4 su build successiva (registrata come debito). **Lezioni fondative per F1** (dettagli nell'atlante): la grammatica vincola ma non informa (lo schema va nel prompt → S7); template di turno Gemma obbligatorio anche su /completion; stop reason `limit` = errore esplicito nel LlamaClient; JSON compatto obbligatorio (pretty-print = 20-30% di token sprecati).

---

## Fase 1 — Nucleo deterministico + Worker (walking skeleton) → `v2.0.0`

📎 **Specsheet:** §6.5 (Worker), §7 (Orchestrator), §8 (stato), §11 (ciclo), §17 (tool), §23 (MVP) · **Decisioni:** D3, D7, D9, D10, D20, D21
🎯 **Scope:** la catena minima che risolve un bugfix sintetico end-to-end: piano statico → Worker → tool → verifica deterministica → stato aggiornato. Più l'Evaluator v0 che la misura e la CLI di sviluppo per pilotarla.
🧭 **Perché questa fase, perché così:** walking skeleton prima dei ruoli cognitivi. L'impianto (stato, tool, evidenze, misura) va validato dove la verifica è gratis (coding con test, D17), con la pipeline più corta possibile: se il sistema non sa nemmeno eseguire una sottofase già scritta, aggiungere il Planner sopra sarebbe costruire sul vuoto. Da qui in poi ogni ruolo cognitivo dovrà **battere questa baseline** nell'Evaluator (D11) — F1 non è solo codice: è il gruppo di controllo dell'intero progetto.

#### F1.1 — Stato: modelli e StateStore

- [x] 🤖 **Obiettivo:** lo stato strutturato della specsheet §8: modelli Pydantic + persistenza SQLite (§A5), atomica, attribuita, riprendibile.
- **Motivazione:** "lo stato strutturato è più importante della cronologia" (specsheet §25.3) è LA scelta che distingue Red Giant da un agente chat-based. Va costruito per primo perché tutti gli altri componenti vi leggono e scrivono; e va costruito bene perché la GUI (F2), la ripresa dei task (F5.4) e le metriche (tutte) sono solo viste su questo stato.
- **Implementazione:** `redgiant/state/models.py` — modelli con `model_config = ConfigDict(extra="forbid")` (un campo inatteso è un bug, non una tolleranza):
  ```python
  TaskStatus  = Literal["queued","running","blocked","completed","partial","failed","cancelled"]
  SubtaskStatus = Literal["pending","running","completed","completed_with_warnings",
                          "retry","repair","blocked","failed","skipped"]
  class Budget(BaseModel):     max_total_tokens: int; max_tool_calls: int; max_retries_per_subtask: int; max_wall_s: int
  class BudgetUsed(BaseModel): tokens: int = 0; tool_calls: int = 0; wall_s: float = 0.0
  class SubtaskSpec(BaseModel):
      id: str; phase_id: str; title: str; objective: str
      inputs: list[str]; tools: list[str]; expected_outputs: list[str]
      completion_criteria: list[str]; verification: list[str]   # nomi di check per verify.py
  class PhaseSpec(BaseModel):  id: str; title: str; depends_on: list[str]; completion_criteria: list[str]
  class Plan(BaseModel):       version: int; goal: str; success_criteria: list[str]; phases: list[PhaseSpec]
  class TaskState(BaseModel):
      id: str; request: str; target_dir: str; domain: str; status: TaskStatus
      plan: Plan | None; current_phase: str | None; current_subtask: str | None
      budget: Budget; used: BudgetUsed
  class LlmCallRow(BaseModel):  # riga di llm_calls, usata da client e store
      role: str; subtask_id: str | None; schema_name: str | None; t_start: str
      prompt_tokens: int; cached_tokens: int; gen_tokens: int
      prefill_ms: float; gen_ms: float; outcome: Literal["ok","timeout","error","invalid"]
  class ToolCallRow(BaseModel):
      subtask_id: str | None; tool: str; args: dict; ok: bool; evidence: list[str]; duration_ms: float
  ```
  `redgiant/state/store.py` — unico punto di accesso al DB (nessun SQL altrove), DDL esatto di §A5:
  ```python
  class StateStore:
      def __init__(self, db_path: Path) -> None
      def init_schema(self) -> None
      def create_task(self, request: str, target_dir: str, profile: str, budget: Budget) -> str
      def load_task(self, task_id: str) -> TaskState
      def list_tasks(self, limit: int = 50) -> list[dict]
      def set_task_status(self, task_id: str, status: TaskStatus, *, actor: str, error: str | None = None) -> None
      def save_plan(self, task_id: str, plan: Plan, *, actor: str, reason: str) -> None
      def upsert_subtask(self, task_id: str, spec: SubtaskSpec, *, actor: str) -> None
      def set_subtask_status(self, task_id: str, subtask_id: str, status: SubtaskStatus,
                             *, actor: str, result: dict | None = None) -> None
      def add_decision(self, task_id: str, *, actor: str, decision: str, reason: str, target: str | None = None) -> None
      def log_llm_call(self, task_id: str, row: LlmCallRow) -> None
      def log_tool_call(self, task_id: str, row: ToolCallRow) -> None
      def budget_used(self, task_id: str) -> BudgetUsed
      # aggiunti in implementazione (2026-08-01): servono a Orchestrator (spec+attempts)
      # e a GUI/CLI (albero) — letture pure, nessun nuovo write-path
      def get_subtask(self, task_id: str, subtask_id: str) -> tuple[SubtaskSpec, SubtaskStatus, int]
      def list_subtasks(self, task_id: str) -> list[dict]
      # anticipati da F2 (il dispatch §A7 li richiede gia' in F1.4):
      def add_approval(self, task_id: str, *, kind: str, payload: str) -> int
      def pending_approvals(self, task_id: str | None = None) -> list[dict]
  ```
  Dettagli di comportamento: `create_task` genera l'ULID, scrive `tasks` + le 4 righe `budgets` in una transazione; `set_subtask_status` incrementa `attempts` quando lo stato entra in `retry`/`repair`; `load_task` ricostruisce `TaskState` dall'ultima versione del piano + aggregati (è LA funzione di ripresa: un processo ucciso a metà task deve poter ripartire da qui); `budget_used` aggrega da `llm_calls`/`tool_calls` — i contatori non si tengono in RAM, si leggono dal DB: una sola fonte di verità.
- **Casi limite:** doppio `upsert_subtask` sullo stesso id → aggiorna spec, non duplica; DB inesistente → `init_schema` alla prima apertura; task inesistente → `KeyError(task_id)` esplicito.
- **Accettazione:** unit test per: creazione+rilettura task (round-trip Pydantic identico), atomicità (transazione interrotta artificialmente non lascia stato parziale), `attempts` che incrementa, `budget_used` che aggrega. `check_reference.py` verde.

#### F1.2 — Model client

- [x] 🤖 **Obiettivo:** l'unico punto del sistema che parla con llama-server: constrained decoding, conteggi, timings, logging — tutto qui.
- **Motivazione:** D2/D3. Centralizzare la chiamata rende il constrained decoding non aggirabile (non esiste un'altra strada per parlare col modello) e le metriche complete per costruzione (ogni chiamata è loggata perché è il client a loggarla).
- **Implementazione:** `redgiant/llm/client.py` + `redgiant/llm/schema.py`:
  ```python
  class LlmError(Exception): ...
  class LlmTimeout(LlmError): ...
  class ContextOverflow(LlmError):  # prompt oltre ctx_size: rifiutato PRIMA di chiamare
      def __init__(self, prompt_tokens: int, ctx_size: int, sections: dict[str, int]) -> None
  @dataclass
  class LlmResult:
      text: str; parsed: BaseModel | None
      prompt_tokens: int; cached_tokens: int; gen_tokens: int
      prefill_ms: float; gen_ms: float; raw_timings: dict
  class LlamaClient:
      def __init__(self, cfg: LlmProfileCfg, store: StateStore | None = None) -> None
      def complete(self, parts: PromptParts, *, role: str,
                   schema: type[BaseModel] | None = None,
                   max_tokens: int, temperature: float | None = None,
                   task_id: str | None = None, subtask_id: str | None = None,
                   cache_prompt: bool = True) -> LlmResult
      def count_tokens(self, text: str) -> int      # via /tokenize del server
      def health(self) -> bool
      def props(self) -> dict
  # schema.py
  def to_llama_schema(model: type[BaseModel]) -> dict   # model_json_schema() + aggiustamenti per llama.cpp
  ```
  Comportamento esatto di `complete`: (1) `render()` delle parti; (2) `count_tokens` → se > `ctx_size - max_tokens`, solleva `ContextOverflow` **con il conteggio per sezione** (S1..S7): chi diagnostica deve vedere subito cosa è gonfio; (3) POST `/completion` con `cache_prompt`, `json_schema` se presente, `temperature` (default dal profilo); (4) rivalidazione Pydantic del testo → `parsed` (fallita = `outcome="invalid"`, loggata, eccezione: con D3 attivo non deve succedere MAI — se succede è un bug di piattaforma da fermare, non da riprovare); (5) log su `llm_calls` sempre, anche su errore/timeout (le chiamate fallite costano tempo reale: invisibili = metriche false).
  Retry: **solo** su errori di trasporto (connessione rifiutata, reset), max 2, backoff fisso 2s; MAI su timeout (su CPU un timeout è informazione, non sfortuna) né su `invalid`.
- **Casi limite:** server spento → `health()` false, l'Orchestrator decide (in F2 il JobQueue avvia il server prima del task); risposta non-JSON con schema attivo → `invalid` (v. sopra).
- **Accettazione:** integration test (marker `llm`): completion con schema banale → `parsed` valido, riga in `llm_calls` con token e timings; `ContextOverflow` scatta con un prompt costruito oltre soglia e riporta le sezioni; unit test per la conversione `to_llama_schema` sui tre schemi di F0.3.

#### F1.3 — ⚠️ Prompt: assembler e convenzione S1→S7

- [x] 🤖 **Obiettivo:** l'implementazione della convenzione §A4 + il preambolo e la prima card (`worker.md`).
- **Motivazione:** D9 è la scommessa di performance del progetto e va cablata *prima* che esistano più ruoli: retrofittare la stabilità dei prefissi dopo è doloroso (ogni ruolo andrebbe rivisitato). La sottofase è marcata ⚠️ perché un errore qui non rompe i test — rompe silenziosamente il riuso della cache, e lo si scoprirebbe solo in F5 coi numeri.
- **Implementazione:** `redgiant/prompts/assemble.py`:
  ```python
  @dataclass(frozen=True)
  class PromptParts:
      preamble: str; role_card: str; tool_card: str
      task_header: str; durable_state: str; volatile_context: str; output_instruction: str
      def render(self) -> str               # ordine S1→S7, separatore esatto §A4
      def section_tokens(self, counter: Callable[[str], int]) -> dict[str, int]  # per ContextOverflow e metriche
      def static_prefix_len(self) -> int    # len(render di S1..S4): base della metrica di riuso (F5.2)
  class PromptAssembler:
      def __init__(self, prompts_dir: Path) -> None   # carica e cachea preamble.md e roles/*.md all'avvio
      def build(self, role: str, *, task: TaskState, subtask: SubtaskSpec | None,
                tools: list[ToolSpec], volatile: str) -> PromptParts
  ```
  Contenuto di `preamble.md` (EN — requisiti, la stesura esatta è parte della sottofase): identità ("component of Red Giant, a deterministic pipeline operating a small local model"); regole universali: mai inventare output di tool, mai dichiarare successo senza evidenza, testo libero sempre corto, l'output è JSON secondo lo schema in OUTPUT, "you propose — the orchestrator decides"; formato delle evidenze (stringhe brevi, fattuali, verificabili). Contenuto di `roles/worker.md`: responsabilità (§6.5), regole (una azione per step; fermati a `blocked` se manca un'informazione o un permesso: non aggirare MAI un ostacolo inventando), 1-2 esempi minimi di `WorkerStep` ben formati.
  `build` per il Worker: S6 = spec della sottofase + blocco append degli step (formato: `[STEP k]` JSON dello step, `[STEP k RESULT]` esito tool serializzato compatto). Nessun altro modulo concatena prompt: i ruoli ricevono `PromptParts` già pronti.
- **Casi limite:** card mancante per un ruolo → errore all'avvio (non alla prima chiamata); tool_card per lista vuota → sezione presente ma "No tools available" (la sezione c'è sempre: l'ordine S1→S7 non è condizionale, o il prefisso cambierebbe forma tra chiamate).
- **Accettazione:** unit test: due `build` consecutivi per lo stesso (ruolo, task, sottofase) → prefisso S1–S4 byte-identico; `render` contiene i 7 separatori esatti nell'ordine; `section_tokens` somma al totale.

#### F1.4 — Tool layer

- [x] 🤖 **Obiettivo:** Scope, catalogo e router: le mani del sistema, con le manette giuste (§A7).
- **Motivazione:** specsheet §17 + D10: i tool sono la fonte delle *evidenze*, e le evidenze sono ciò che separa un risultato verificato da una dichiarazione. La sicurezza (Scope) entra ora e non dopo perché il primo Worker che scrive un file fuori scope non deve poter esistere nemmeno in sviluppo.
- **Implementazione:** `tools/base.py`, `router.py`, `fs.py`, `search.py`, `proc.py` — comportamento esatto per tool in §A7; firme:
  ```python
  class ScopeError(Exception): ...
  class Scope:
      def __init__(self, root: Path, writable_globs: list[str]) -> None
      def check_read(self, p: str) -> Path    # resolve() reale; dentro root; symlink che esce → ScopeError
      def check_write(self, p: str) -> Path   # come sopra + match su writable_globs
  @dataclass(frozen=True)
  class ToolSpec:
      name: str; description: str; risk: Literal["low","medium","high"]
      reversible: bool; requires_approval: bool; timeout_s: float
      input_model: type[BaseModel]
      handler: Callable[..., "ToolResult"]
  @dataclass
  class ToolResult:
      ok: bool; data: dict; evidence: list[str]; error: str | None = None
  def default_catalog(cfg: Config, scope: Scope, test_commands: dict[str, list[str]]) -> dict[str, ToolSpec]
  class ToolRouter:
      def __init__(self, catalog: dict[str, ToolSpec], scope: Scope, store: StateStore) -> None
      def allowed_for(self, role: str, domain: str) -> list[ToolSpec]
      def render_tool_card(self, specs: list[ToolSpec]) -> str   # S3, ordinata, stabile
      def dispatch(self, task_id: str, subtask_id: str, name: str, args: dict) -> ToolResult
  ```
  `dispatch`, in ordine: tool esistente? args validi per `input_model`? (no → `ToolResult(ok=false, error="bad_args", data={"detail": <errori pydantic>})` — il modello deve poter correggere il tiro); `requires_approval` → riga in `approvals` + task `blocked` + ritorno `error="awaiting_approval"` (in F1, senza GUI, la CLI stampa e attende input — implementazione provvisoria dichiarata); esecuzione con timeout del ToolSpec; eccezione imprevista → `ok=false, error="internal:<ClassName>"` e il task vive (il fallimento del tool è un dato per il modello); log su `tool_calls` SEMPRE.
  `run_tests`: i comandi arrivano da `test_commands` (dal task.toml dell'Evaluator o dall'onboarding del task), argv-list; l'eseguibile (`argv[0]`) deve appartenere a `security.shell_whitelist`.
  `write_patch`: parser di diff unificato nostro (niente `patch` di sistema: il comportamento deve essere identico su Windows e Linux, D19); applicazione hunk per hunk con contesto esatto; scrittura atomica tmp+rename; `data.rejected` con "expected vs found" per hunk respinto.
- **Casi limite:** già in §A7 per tool; in più: `Scope` con root inesistente → errore alla costruzione; glob di scrittura che matcha fuori root → impossibile per costruzione (si applica dopo `check_read`-style resolve).
- **Accettazione:** unit test per: Scope (path traversal `..`, symlink esterno, glob scrittura), write_patch (applicazione pulita, hunk respinto, atomicità simulando crash), run_tests (comando fuori whitelist rifiutato), dispatch (args invalidi → bad_args loggato). Nessun test tocca il modello.

#### F1.5 — Worker (ReAct a passo singolo vincolato)

- [x] 🤖 **Obiettivo:** il primo ruolo cognitivo: esegue UNA sottofase col loop di D20.
- **Motivazione:** D20 (le due ragioni convergenti: qualità del passo singolo + riuso della cache in append). Il Worker è volutamente *stupido*: non pianifica, non giudica il proprio lavoro (D10: lo giudica la verifica), non tocca il piano (specsheet §6.5). Ogni intelligenza in più che si è tentati di dargli appartiene a un altro ruolo o a nessuno.
- **Implementazione:** `roles/base.py` + `roles/worker.py`:
  ```python
  class RoleContext(BaseModel):
      task: TaskState; subtask: SubtaskSpec | None; volatile: str
  class Role(ABC):
      name: ClassVar[str]; output_model: ClassVar[type[BaseModel]]
      def __init__(self, llm: LlamaClient, assembler: PromptAssembler, router: ToolRouter) -> None
  # worker.py
  class ToolCallSpec(BaseModel): tool: str; args: dict
  class FinishReport(BaseModel):
      status: Literal["done","blocked"]; summary: str = Field(max_length=600)
      evidence: list[str]; verification_requested: list[str]
  class WorkerStep(BaseModel):
      thought: str = Field(max_length=300)          # pensiero corto, non saggio (specsheet §3)
      action: Literal["tool","finish"]
      tool_call: ToolCallSpec | None = None
      finish: FinishReport | None = None
  class Worker(Role):
      name = "worker"; output_model = WorkerStep
      def run(self, ctx: RoleContext, *, max_steps: int) -> FinishReport
  ```
  Loop esatto di `run` (pseudocodice normativo):
  ```text
  parts = assembler.build("worker", task, subtask, tools=router.allowed_for("worker", domain), volatile=spec_iniziale)
  for k in 1..max_steps:
      step = llm.complete(parts, role="worker", schema=WorkerStep, max_tokens=<da F0.6>).parsed
      se step.action == "finish": return step.finish
      result = router.dispatch(task_id, subtask_id, step.tool_call.tool, step.tool_call.args)
      se result.error == "awaiting_approval": return FinishReport(status="blocked", summary="awaiting approval", ...)
      parts = parts con volatile_context += "\n[STEP k] " + step.json_compatto
                                          + "\n[STEP k RESULT] " + serializza(result, max_400_righe)
  # esauriti i passi:
  return FinishReport(status="blocked", summary="step budget exhausted", evidence=[], verification_requested=[])
  ```
  Vincoli: coerenza `action`/campi (validator Pydantic: `action="tool"` ⇒ `tool_call` presente e `finish` assente, e viceversa); il risultato tool viene serializzato compatto e troncato (il troncamento è dichiarato nel blocco); **il Worker non decide mai di aver finito il task** — `finish.status="done"` significa solo "chiedo la verifica".
- **Casi limite:** tool inesistente richiesto → il `bad_args`/`unknown_tool` torna come RESULT e il modello può correggersi (conta come step); due step identici consecutivi (stesso tool, stessi args) → il loop inserisce nel RESULT un avviso "identical call repeated — change approach or finish" (pre-LoopGuard minimale, il vero anti-loop è F4.3).
- **Accettazione:** integration test: su un mini-repo con un bug a una riga e la sottofase scritta a mano, il Worker legge, patcha, esegue i test e chiude con evidenze; unit test del validator di coerenza e del comportamento a `max_steps`.

#### F1.6 — Verifica deterministica

- [x] 🤖 **Obiettivo:** `core/verify.py`: l'oracolo meccanico che decide se una sottofase è accettabile (D10).
- **Motivazione:** è il "trust boundary" del sistema: tutto ciò che sta a monte (Worker incluso) *propone*; questo modulo *constata*. In F1 è volutamente semplice — la sofisticazione (Debugger a due stadi, classificazione errori) arriva in F4 sopra questa base.
- **Implementazione:**
  ```python
  class CheckResult(BaseModel): name: str; ok: bool; detail: str
  class Verdict(BaseModel):     verdict: Literal["pass","fail"]; checks: list[CheckResult]
  def verify_subtask(spec: SubtaskSpec, report: FinishReport, scope: Scope,
                     router: ToolRouter, task_id: str) -> Verdict
  ```
  Check eseguiti, nell'ordine, tutti sempre (non si ferma al primo fallito — il quadro completo serve alla diagnosi): (1) `report.status == "done"` (un blocked non passa mai di qui); (2) evidenze non vuote; (3) ogni `expected_outputs` esiste (file → esistenza via Scope); (4) ogni voce di `spec.verification` che corrisponde a un `cmd_id` di test → `run_tests` con exit 0; (5) voci di `verification` sconosciute → `ok=false, detail="unknown check"` (una verifica non eseguibile è una verifica fallita, non saltata — silenzio ≠ successo).
- **Accettazione:** unit test con router finto per i 5 percorsi; integration nel test end-to-end di F1.5.

#### F1.7 — Orchestrator v0 + BudgetTracker

- [x] 🤖 **Obiettivo:** il motore deterministico minimo: esegue le sottofasi di un piano *statico* in sequenza, applica la verifica, aggiorna lo stato, si ferma bene.
- **Motivazione:** specsheet §7: "il modello propone, l'Orchestrator decide". In F1 le decisioni sono banali (pass → next, fail → retry entro budget → failed) di proposito: la sofisticazione decisionale è il Supervisor (F4) e dovrà giustificarsi contro questa semplicità (D11).
- **Implementazione:**
  ```python
  class Orchestrator:
      def __init__(self, cfg: Config, store: StateStore, llm: LlamaClient,
                   router: ToolRouter, assembler: PromptAssembler) -> None
      def run_task(self, task_id: str) -> TaskState     # bloccante; F2 lo mette nel JobQueue
      def _next_subtask(self, state: TaskState) -> SubtaskSpec | None   # prima 'pending' in ordine piano
      def _execute_subtask(self, state: TaskState, spec: SubtaskSpec) -> Verdict
      def _finalize(self, state: TaskState) -> TaskState
  class BudgetTracker:
      def __init__(self, store: StateStore, budget: Budget, task_id: str) -> None
      def charge_llm(self, r: LlmResult) -> None
      def charge_tool(self) -> None
      def exceeded(self) -> str | None                  # 'tokens'|'tool_calls'|'wall_s'|None
  ```
  `run_task`: carica lo stato (ripresa inclusa: se c'è una sottofase `running` orfana di un processo morto → torna `pending`, decisione loggata con actor `orchestrator`); loop `_next_subtask` → `_execute_subtask` (Worker → verify) → `pass` ⇒ `completed`; `fail` ⇒ `retry` finché `attempts < max_retries_per_subtask`, poi `failed` ⇒ task `failed` con `error` che dice quale sottofase e perché. `BudgetTracker.exceeded` controllato a ogni giro: sforamento ⇒ stop con status `partial` se almeno una sottofase è `completed`, altrimenti `failed` — sempre con spiegazione (specsheet §14: fallire in modo esplicito).
  Piano statico: file `plan.json` accanto al task (formato = `Plan` serializzato), caricato in `plans` con `version=0, actor="system", reason="static plan (F1)"`.
- **Casi limite:** verifica che solleva eccezione → sottofase `failed` con detail, task prosegue la policy normale; nessuna sottofase `pending` ma task non finito → stato incoerente: task `failed` con errore "inconsistent plan state" (mai loop silenzioso).
- **Accettazione:** end-to-end su T001 (v. F1.10) da CLI; test di ripresa: processo ucciso a metà → rilancio → il task riparte dalla sottofase giusta; sforamento budget simulato (budget minuscolo) → `partial`/`failed` con spiegazione.

#### F1.8 — Log leggibile per task

- [x] 🤖 **Obiettivo:** oltre alle tabelle, un log testuale umano per task: `data/tasks/<id>/task.log`.
- **Motivazione:** specsheet §20. Il DB è per le macchine e le metriche; il log è per l'utente che chiede "che sta facendo?". La GUI (F2) lo mostrerà con un tail.
- **Implementazione:** righe `HH:MM:SS | role/tool | sintesi ≤120c | esito | token/durata`, scritte dagli stessi punti che loggano su DB (Client e Router: nessun punto di log nuovo da ricordare); append-only, flush per riga.
- **Accettazione:** dopo il run end-to-end, il log racconta la storia del task in modo comprensibile a un umano che non ha visto il codice.

#### F1.9 — CLI di sviluppo

- [x] 🤖 **Obiettivo:** pilotare il sistema senza GUI: `rg run|status|eval|bench`.
- **Motivazione:** serve *adesso* per sviluppare e per gli integration test; NON è l'interfaccia utente (quella è F2, per dichiarazione esplicita dell'utente sulla testabilità). Si tiene minima di proposito.
- **Implementazione:** `redgiant/cli.py`, argparse puro:
  ```python
  def main(argv: list[str] | None = None) -> int
  # rg run --target DIR --prompt "..." [--plan plan.json] [--profile dev-fast] [--domain coding]
  # rg status TASK_ID           → albero testuale stile specsheet §20 + budget
  # rg eval [--profile P] [--only T001,T003]
  # rg bench --profile P [--ctx ...]
  ```
- **Accettazione:** i 4 sottocomandi funzionano; `rg status` su task finito mostra l'albero con gli esiti.

#### F1.10 — Evaluator v0 + primi 6 task sintetici

- [x] 🤖 **Obiettivo:** il giudice del progetto: harness che esegue task sintetici e produce il report delle metriche cardine.
- **Motivazione:** D11 richiede un giudice *prima* degli imputati: l'Evaluator nasce ora, prima di Planner/Debugger/Supervisor, così ogni ruolo aggiunto avrà un confronto onesto. I task sono sintetici e a bug noto (D18): quando il sistema fallisce, sappiamo *perché*.
- **Implementazione:** `eval/harness.py`, `eval/report.py`:
  ```python
  class EvalTask(BaseModel):
      id: str; domain: str; prompt: str; repo_dir: Path
      plan_file: Path | None; success_cmd: str; timeout_s: int; tags: list[str]
  class EvalResult(BaseModel):
      task_id: str; completed: bool; verified: bool
      total_tokens: int; useful_tokens: int; wall_s: float
      llm_calls: int; tool_calls: int; retries: int
  def discover_tasks(tasks_dir: Path) -> list[EvalTask]     # ogni sottocartella con task.toml
  def run_eval(profile: str, only: list[str] | None, out_dir: Path) -> Path
  def write_report(results: list[EvalResult], profile: str, git_ref: str, out_dir: Path) -> Path
  ```
  Esecuzione di un task: copia di `repo/` in una dir temporanea (il repo sorgente non si sporca MAI; ogni run parte identica), `create_task` + run, poi **verifica esterna**: `success_cmd` eseguito dall'harness sulla copia — `verified` è vero solo se passa. La distinzione `completed` (il sistema dice di aver finito) vs `verified` (il giudice esterno conferma) È la metrica anti-bugia: la forbice tra le due deve essere zero.
  Formato `task.toml` (esempio integrale, contratto per tutti i task presenti e futuri):
  ```toml
  id = "T001"
  domain = "coding"
  prompt = "The test suite fails. Find the bug and fix it without changing the tests."
  success_cmd = "pytest -q"        # eseguito DALL'HARNESS, fuori dal sistema
  timeout_s = 1800
  tags = ["bugfix", "python", "single-file"]
  plan_file = "plan.json"          # F1: piano statico; da F3 si omette (lo genera il Planner)
  [test_commands]                  # whitelist run_tests per questo task
  pytest = ["pytest", "-q"]
  ```
  I 6 task iniziali (ognuno = `task.toml` + `repo/` + `plan.json` scritto a mano): **T001** bugfix Python 1-file (off-by-one con test rosso) · **T002** bugfix Python 2-file (bug nel chiamante, sintomo nel chiamato: costringe a navigare) · **T003** bugfix PHP 1-file (il dominio target dell'utente; verifica con `php` da whitelist) · **T004** feature piccola con test forniti rossi · **T005** test rosso da far passare senza rompere gli altri 10 verdi (punisce il fix brutale) · **T006** ricerca in codebase ("dov'è definita la funzione X e chi la chiama?" — risposta attesa in un file di output confrontato da `success_cmd` con grep).
  **Definizione operativa di `useful_tokens` (v0):** somma dei token delle chiamate LLM dei passi che hanno prodotto una tool call accettata (`ok=true`) o il finish accettato dalla verifica; tutto il resto (step falliti, retry, chiamate di sottofasi poi fallite) è overhead. Rozza ma stabile; si raffina quando esistono più ruoli (annotato come debito tecnico).
- **Casi limite:** task in timeout → `completed=false` con causa `timeout` nel report; harness che non trova `success_cmd` → errore di configurazione del task, non del sistema.
- **Accettazione:** `rg eval --profile severino-sim` esegue i 6 task e produce `eval/report_<data>.md` + CSV con: le 5 metriche cardine, esito per task, riga in `eval_runs`. 📌 Questo report è **la baseline storica del progetto**: va citato nell'atlante.

#### F1.11 — 🔎 Verifica di fase

- [x] Tutte insieme: ≥4/6 task sintetici `verified` su `severino-sim` senza intervento umano; forbice `completed`≠`verified` = 0 (nessuna bugia); zero righe `llm_calls.outcome='invalid'` sull'intera run; `pytest tests/unit` verde; report Evaluator committato e citato nell'atlante; test di ripresa (F1.7) passato.

**Rituale di fine fase** → `v2.0.0`.

> **ESITO F1 (2026-08-01, `v2.0.0`).** Gate superato sulla run UFFICIALE severino-sim (2 core): **4/6 verified** (T001, T003, T004, T005 — tutti 100% token utili, 0 retry, 5-8 chiamate, 45-65s l'uno), **forbice completed≠verified = 0 su tutte le 8 run** della fase (il sistema non ha mai mentito), zero `invalid` nella run ufficiale, 33 unit test verdi. **Fallimenti onesti e diagnosticati:** T002 (il modello non capovolge "lib off-limits ⇒ bug nel chiamante" — limite di ragionamento, atteso il `retry_strategy` del Supervisor F4) e T006 (dichiara azioni non eseguite / pattern di ricerca fragili al retry — idem). **Baseline per D11:** ogni ruolo di F3/F4 dovrà battere questi numeri. **Il collaudo e2e ha prodotto 10 trappole disinnescate** (dettaglio nell'atlante §9), quasi tutte della stessa famiglia — l'interfaccia modello↔ambiente: i formati che il modello non sa serializzare (diff unificati), ciò che copia sempre (prefissi N-TAB, echo del nome tool), ciò che dichiara senza fare (la verifica lo becca), il determinismo che non attraversa i backend (seed fisso ≠ stessa traiettoria su CUDA vs CPU). **Evoluzioni contrattuali** (tutte registrate in §A7/F1 con la ragione): `edit_file` primario, `write_file` per la creazione, normalizzazione N-TAB su tutti i writer, step-log del Worker.

---

## Fase 2 — GUI web minima → `v2.1.0`

📎 **Specsheet:** §20 (osservabilità) · **Decisioni:** D7, D12
🎯 **Scope:** l'interfaccia con cui l'utente testa davvero: coda di job asincroni, albero di esecuzione live, coda di approvazioni e chiarimenti, form di avvio.
🧭 **Perché questa fase, perché ora:** l'utente è stato esplicito — senza un'interfaccia comoda non testerà a fondo, e il feedback dell'utente deve arrivare *prima* che la pipeline si complichi (F3+), quando cambiare è ancora economico. La GUI legge lo stato dal DB (F1.1) e quindi è strutturalmente disaccoppiata dall'evoluzione della pipeline: ciò che si costruisce qui non andrà rifatto quando arriveranno Planner e Supervisor — si aggiungeranno righe all'albero, non pagine.

#### F2.1 — App e JobQueue

- [x] 🤖 **Obiettivo:** processo unico FastAPI con la coda che garantisce "una inferenza alla volta" (D7).
- **Motivazione:** la serialità non è un limite da nascondere ma un contratto da esporre: l'utente vede la coda, capisce perché il suo task aspetta, e il box non muore mai per contesa.
- **Implementazione:** `web/app.py`, `web/jobs.py`:
  ```python
  def create_app(cfg: Config) -> FastAPI     # monta routes, static, templates; istanzia StateStore e JobQueue
  class JobQueue:
      def __init__(self, make_orchestrator: Callable[[], Orchestrator]) -> None
      def submit(self, task_id: str) -> None         # accoda; il worker thread è UNO
      def cancel(self, task_id: str) -> bool         # cooperativo: flag che l'Orchestrator controlla tra sottofase e sottofase
      def current(self) -> str | None
      def queue_snapshot(self) -> list[str]
  ```
  Il worker thread, per ogni job: verifica/avvia llama-server del profilo (via lo script di F0.2 o, se già su, `health()`); esegue `run_task`; a fine task (o crash) arresta il server se lo aveva avviato lui (D7: rilascio RAM). Un'eccezione non gestita nel job → task `failed` con l'errore, la coda sopravvive e passa al prossimo. `cancel` è cooperativo di proposito: uccidere un Worker a metà patch lascerebbe il target sporco; il flag viene onorato al confine tra sottofasi (e in F4 anche il rollback diventa possibile).
- **Casi limite:** submit di task già in coda → no-op idempotente; crash del processo GUI con task `running` → alla riaccensione la ripresa di F1.7 lo rimette in careggiata (nessun lavoro perso oltre la sottofase corrente).
- **Accettazione:** due submit consecutivi → esecuzione strettamente seriale (osservabile da `llm_calls.t_start`); cancel a metà task → stato `cancelled`, coda viva.

#### F2.2 — Rotte

- [x] 🤖 **Obiettivo:** le pagine e i frammenti HTMX. Tutte HTML: nessuna API JSON pubblica (D12).
- **Implementazione:** `web/routes/tasks.py`, `approvals.py`, `metrics.py` — tabella contrattuale:

  | Metodo e path | Input | Output | Errori |
  |---|---|---|---|
  | `GET /` | — | lista task: id, stato (badge colore), dominio, profilo, budget residuo %, età | — |
  | `GET /tasks/new` | — | form: prompt (textarea), target_dir, profilo (select), dominio, limiti opzionali | — |
  | `POST /tasks` | form | 303 → `/tasks/{id}` dopo create+submit | 400 campo mancante/dir inesistente; 409 profilo non disponibile |
  | `GET /tasks/{id}` | — | dettaglio: albero fasi/sottofasi, budget, decisioni, link log | 404 |
  | `GET /tasks/{id}/tree` | — | **frammento** albero (polling HTMX `every 2s` finché status ∈ {queued,running,blocked}) | 404 |
  | `GET /tasks/{id}/log` | `?tail=200` | `<pre>` del task.log | 404 |
  | `POST /tasks/{id}/cancel` | — | 303 → dettaglio | 404; 409 non attivo |
  | `GET /approvals` | — | coda `pending`: approvazioni e chiarimenti, con contesto (payload reso leggibile) | — |
  | `POST /approvals/{id}` | form `answer` (per approvazioni: `yes`/`no`; per chiarimenti: testo) | 303 → `/approvals`; il task riparte | 404; 409 già risposta |
  | `GET /metrics` | — | metriche cardine dell'ultima eval + tabella task recenti (token, tempo, esito) | — |
- **Motivazione delle scelte:** polling e non SSE/WebSocket: con UN task attivo alla volta e aggiornamenti ogni 2s, il polling è indistinguibile all'uso e costa zero complessità (niente connessioni da gestire, niente riconnessione); si riconsidera solo se l'uso reale lo smentisce (annotarlo come debito solo in quel caso).
- **Accettazione:** ogni rotta risponde come da tabella, inclusi i codici d'errore (test con `TestClient`); l'albero si aggiorna da solo durante un run.

#### F2.3 — Protocollo umano (approvazioni e chiarimenti)

- [x] 🤖 **Obiettivo:** il canale formale con cui il sistema chiede all'umano (specsheet §6.7 "chiedere chiarimenti"; §19 approvazioni).
- **Motivazione:** un sistema batch (D7) non può fare domande a un terminale: deve *parcheggiarsi* bene. Il parcheggio è uno stato di prima classe (`blocked`), visibile, con ripartenza pulita — non un prompt bloccante sepolto in un log.
- **Implementazione:** flusso completo: il componente che ha bisogno (ToolRouter per `requires_approval`; da F4 il Supervisor per `ask_user`) scrive in `approvals` (payload JSON: cosa chiede, perché, contesto minimo per decidere), mette il task `blocked` e ritorna; il worker thread del JobQueue vede `blocked` e passa oltre; `POST /approvals/{id}` scrive la risposta, rimette il task in coda; alla ripresa, la risposta viene consegnata: per un'approvazione → il ToolRouter ri-esegue il dispatch sospeso (idempotente: la richiesta originale è nel payload); per un chiarimento → il testo entra nel contesto S6 della sottofase corrente come blocco `[USER ANSWER]`. La risposta dell'utente si logga anche in `decisions` (actor `user`).
- 🧑 **Decisione utente:** collegare ntfy del homelab per notificare i `blocked` (opzionale; se sì, è un POST HTTP alla creazione della riga — niente dipendenze nuove).
- **Casi limite:** risposta a task nel frattempo cancellato → `expired`; due `pending` per lo stesso task → ammesso (l'ordine di risposta non conta: si riparte quando non restano `pending`).
- **Accettazione:** test end-to-end: task con tool `requires_approval` → si blocca → risposta `yes` da GUI → completa; risposta `no` → la sottofase riceve il rifiuto come RESULT e il flusso normale (verifica/retry) prosegue.

#### F2.4 — Template e albero

- [x] 🤖 **Obiettivo:** le viste Jinja2 + HTMX vendorizzato; l'albero di esecuzione stile specsheet §20.
- **Implementazione:** `templates/base.html` (layout, niente CSS framework: un foglio nostro minimo), `index.html`, `task_new.html`, `task.html`, `tree.html` (frammento riusato dalla pagina e dal polling), `approvals.html`, `metrics.html`; `static/htmx.min.js` copiato nel repo con versione annotata nell'atlante (è l'unica eccezione JS, ed è vendorizzata per D14/D16: niente CDN, la CSP del futuro deploy ringrazia). Albero: fase → sottofasi con stato, tentativi, durata; i simboli seguono §20 (`completed` ✓, `failed` ✗, `running` ▶, `blocked` ⏸).
- **Accettazione:** le pagine sono usabili da browser senza console errors; l'albero di un task reale è leggibile a colpo d'occhio.

#### F2.4-bis — Post-mortem e ripartenza guidata (aggiunta su richiesta utente, 2026-08-01)

- [x] 🤖 **Obiettivo:** un fallimento non è un vicolo cieco: la pagina di un task `failed`/`partial` mostra **perché** (check falliti con dettaglio, errore del task, link al log) e offre **"riparti con istruzioni aggiuntive"** — un form che clona il task (stessa config, stesso piano, stesso target) con la guida dell'utente appesa alla richiesta.
- **Motivazione (parole dell'utente):** "i fallimenti non devono essere totalmente blocking… il sistema deve restituirmi le motivazioni del fail e la possibilità di farlo ripartire magari con istruzioni diverse". Questa è la versione leggera (nuovo task guidato); la ripresa *in place* con strategia è F4.2 (`retry_strategy`/`ask_user` del Supervisor), che eredita questo requisito come criterio di accettazione.
- **Implementazione:** rotta `POST /tasks/{id}/relaunch` (form `guidance`); prompt del clone = richiesta originale + `[USER GUIDANCE] …`; config per-task copiata; pannello fallimento costruito dai `result` delle sottofasi (verdict → check non-ok) **+ `t.error` sempre mostrato; il Riparti c'è per OGNI failed/partial** (anche morte per budget senza check).
- **Estensioni dal collaudo utente (2026-08-01):** (a) **consenso permanente per (tool, path) nel task** — approvare "scrivi su X" vale per tutto il task, il modello itera sul file concesso; un no è permanente uguale; (b) **override/revoca delle grant** dalla pagina approvazioni (no→sì riaccoda un task bloccato); (c) **budget esaurito = checkpoint di consenso, non ghigliottina**: il task si blocca e chiede l'estensione (+50% one-shot, ogni esaurimento ri-chiede; Nega = fallimento per decisione esplicita). Default `max_total_tokens` 32k→64k come tampone dichiarato; taratura seria in F6.

#### F2.5 — 🔎 Verifica di fase

- [x] 🧑 L'utente, dalla GUI: lancia `T004`, chiude la pagina, torna, vede l'albero completato; lancia un task con approvazione, risponde, lo vede ripartire; consulta `/metrics`. **Ogni scomodità segnalata si sistema in questa fase**, non dopo: è il criterio di uscita, non un sondaggio.

**Rituale di fine fase** → `v2.1.0`.

> **ESITO F2 (2026-08-02, `v2.1.0`).** Fase completata dopo la campagna di collaudo più dura del progetto: 3 giri di collaudo manuale dell'utente + batteria automatizzata di 5 task + 4 retest mirati. **Esito finale: 4/5 task-tipo verificati** (incluso il refactoring 2-sottofasi T007, promosso a task permanente dell'Evaluator), 1 fallimento onesto (trappola di ragionamento cross-file → F4). **15 difetti trovati e corretti** (dettaglio nell'atlante §9, batch F2): i capitali sono la race submit/ripresa, il consenso a gettone → **grant permanenti per (famiglia-scrittura, file) con override/revoca**, il **derail da apice** (doppio apice non escapato chiude la stringa JSON → union discriminata: il ramo incoerente non è più generabile, probe 8/8), la contabilità budget rotta dalla cache, la **simmetria degli oracoli** (i check oggettivi verdi battono un worker che si crede blocked → `completed_with_warnings`). **Evoluzioni contrattuali su richiesta utente**: budget = checkpoint di consenso (+50% su Approva, mai ghigliottina; default 64k tampone), spegnimento server a 30' di idle, i comandi di test li trova il sistema (scoperta deterministica + `register_test_command`), ripresa **in-place** post-approvazione (contesto salvato, KV calda), post-mortem + ripartenza guidata su ogni failed/partial, diff-preview nelle approvazioni. **Nota metodologica**: le descrizioni originali di F1.5/F1.6 (coerenza come dato in-loop, verifica solo-claim) sono superate dalle evoluzioni di questa fase — fa fede l'atlante. **Debiti registrati con destinazione**: T002-ragionamento (F4.2), D-laborioso/41-chiamate (F4+F5), registro delle tolleranze modello-specifiche da A/B-are (F6/F8), task sintetico "sporco" pre-F8, varianza multi-seed nell'Evaluator (F6), task_config.json→DB (con la GUI di F4), protocollo umano come dialogo vero (F4).

---

## Fase 3 — Pianificazione: Planner + Phase Designer → `v3.0.0`

📎 **Specsheet:** §6.3, §6.4, §10, §11 · **Decisioni:** D10, D11, D21
🎯 **Scope:** dal piano statico al piano generato: Planner (macrofasi sintetiche, versionate) e Phase Designer (espansione della sola fase corrente), Orchestrator v1 guidato dal piano, replanning minimale, A/B contro la baseline F1.
🧭 **Perché questa fase, perché ora:** è il primo ruolo cognitivo "vero" e arriva DOPO il giudice (Evaluator, F1.10) per la ragione di D11: deve dimostrare coi numeri di valere il proprio costo sui task multi-step, dove la lista statica non arriva. L'ordine interno (prima Planner, poi Phase Designer, poi Orchestrator v1) segue il flusso dei dati: non si può eseguire un piano che non esiste.

#### F3.1 — Planner

- [x] 🤖 **Obiettivo:** genera la mappa del lavoro: goal, criteri, macrofasi con dipendenze (specsheet §6.3). Sintetico per contratto. *(fatto; in corso d'opera: `normalize_plan` per i sentinelli in `depends_on` — "none", auto-dipendenza — e richiamata correttiva che CITA le regole violate, non solo i sintomi)*
- **Motivazione:** "pianificazione globale, esecuzione locale" (specsheet §1). Il piano è una *mappa*, non un romanzo: il limite di token è un vincolo di qualità (un piano corto si aggiorna; uno lungo si abbandona) oltre che di costo (D8).
- **Implementazione:** `roles/planner.py` + `prompts/roles/planner.md`:
  ```python
  class PlannerOutput(BaseModel):        # = Plan senza version (la assegna StateStore.save_plan)
      goal: str = Field(max_length=300)
      success_criteria: list[str] = Field(max_length=6)
      phases: list[PhaseSpec] = Field(max_length=7)     # D21: tetto duro
  class Planner(Role):
      name = "planner"; output_model = PlannerOutput
      def run(self, ctx: RoleContext) -> PlannerOutput
  ```
  Card (`planner.md`): definisci fasi *osservabili* (ogni `completion_criteria` deve essere constatabile); dipendenze solo se reali; NON descrivere le operazioni (quello è il Phase Designer); NON includere fasi di cerimonia ("setup", "wrap-up") senza criteri concreti. Validazioni deterministiche post-parse (in `save_plan` o helper): id fase univoci, `depends_on` esistenti e aciclici (DFS), almeno una fase senza dipendenze — violazione = una sola richiamata con l'errore nel contesto, poi `failed` (niente loop di replanning sull'output malformato: con D3 la *forma* è garantita, qui si valida la *logica*).
- **Casi limite:** richiesta banale che non merita fasi → il Planner può legittimamente produrre 1 fase (il routing di F6 eviterà proprio di chiamarlo, ma fino ad allora 1 fase è la risposta giusta).
- **Accettazione:** su T007 (multi-step) produce un piano valido alle validazioni; il piano sta nel budget token di F0.6; versione e reason salvate.

#### F3.2 — ⚠️ Phase Designer

- [x] 🤖 **Obiettivo:** converte UNA macrofase in sottofasi operative eseguibili dal Worker (specsheet §6.4). *(fatto, con la REVISIONE sotto; trappola pagata: la regola 2 della card riscritta perdendo "cmd id esatti" ha ucciso 6 task su 10 — prompt e validatore sono un artefatto solo)*
- **Motivazione:** è il punto di massima leva della qualità: qui si decide la *forma* del lavoro. La marca ⚠️ sta nel criterio D10: **la decomposizione preferisce sottofasi meccanicamente verificabili** — è la scelta di design che rende tutto il resto del sistema onesto, e se il Phase Designer la ignora, il Debugger (F4) erediterà verifiche impossibili.
- **Implementazione:** `roles/phase_designer.py` + card:
  ```python
  class PhaseDesign(BaseModel):
      phase_id: str
      subtasks: list[SubtaskSpec] = Field(max_length=6)   # D21
  class PhaseDesigner(Role):
      name = "phase_designer"; output_model = PhaseDesign
      def run(self, ctx: RoleContext) -> PhaseDesign
  ```
  Card: ogni sottofase deve stare in una sessione Worker (`worker.max_steps`); ogni sottofase DEVE avere almeno una voce di `verification` eseguibile (un `cmd_id` di test quando esiste); `tools` solo dal catalogo fornito in S3; vietato ridisegnare fasi già completate. Validazioni deterministiche: `phase_id` = fase corrente, id sottofasi `P<x>.S<n>` univoci, `verification` non vuota (il criterio D10 qui è *hard*: sottofase senza verifica = design respinto con richiamata singola, come F3.1).
  **REVISIONE (2026-08-02, concordata con l'utente dopo lo smoke T009):** (a) la verifica è accettabile anche come `expected_outputs` non vuoto (l'esistenza è un oracolo) — serve per le sottofasi preparatorie; (b) **il perimetro e la verifica devono coincidere**: in una fase multi-sottofase, la verifica a suite intera (`cmd_id` di test) è ammessa SOLO sull'ultima sottofase — le intermedie si verificano su ciò che possiedono (49 riscritture di `util.py` nel churn T009: il Worker era punito da test rossi fuori dal suo confine, che gli era vietato toccare). Regola gemella nella card del Worker: test rossi fuori dal tuo perimetro → chiudi `done` con le evidenze dei TUOI criteri. (c) L'ancoraggio al contratto: Planner, replanning e Designer ricevono gli estratti dei file di test ("copia gli identificatori, non inventarli").
- **Casi limite:** fase che non si riesce a decomporre (il modello produce 0 sottofasi) → escalation: in F3 = task `failed` esplicito; da F4 = decisione del Supervisor.
- **Accettazione:** su un piano di T007, ogni sottofase generata ha verifica eseguibile e il Worker le esegue senza modifiche manuali.

#### F3.3 — Orchestrator v1 (piano dinamico)

- [x] 🤖 **Obiettivo:** `run_task` guidato dal piano generato: fasi eleggibili per dipendenze, espansione lazy, stati §11 completi. *(fatto; aggiunto post-verdetto: gate D11 — `planner.enabled=false` di default → `_naive_plan` deterministico, zero LLM)*
- **Motivazione:** "solo la fase corrente viene dettagliata" (specsheet §25.5): l'espansione lazy non è un'ottimizzazione ma un principio — le fasi future cambieranno alla luce di quelle passate, dettagliarle ora sarebbe lavoro da buttare e contesto da pagare.
- **Implementazione:** modifiche a `orchestrator.py`: `run_task` = [se manca il piano] Planner → save_plan; loop: prossima fase eleggibile (tutte le `depends_on` completate, ordine del piano) → [se non espansa] PhaseDesigner → upsert delle sottofasi → loop sottofasi come F1; fase completata quando tutte le sottofasi sono `completed`/`completed_with_warnings` — più il check dei `completion_criteria` di fase dove constatabili; `current_phase`/`current_subtask` sempre aggiornati (la GUI li mostra). Nuovo metodo: `def _eligible_phase(self, state: TaskState) -> PhaseSpec | None`.
- **Casi limite:** dipendenze che diventano insoddisfacibili (fase `failed` a monte) → le fasi a valle diventano `skipped` con decisione loggata; il task chiude `partial` se qualcosa di utile è stato completato.
- **Accettazione:** T007 gira col piano generato end-to-end; il test di ripresa (F1.7) vale anche a metà di una fase espansa.

#### F3.4 — Replanning minimale

- [x] 🤖 **Obiettivo:** richiamare il Planner quando il piano non è più vero (specsheet §10), senza replanning-mania. *(fatto; max 2 replan, fasi completate immutabili; col gate D11 il replanning è rifiutato a Planner spento — fallimento esplicito)*
- **Motivazione:** la specsheet è netta: "il replanning non deve avvenire per ogni piccolo errore locale". In F3 i trigger sono pochi e deterministici; il raffinamento decisionale è del Supervisor (F4).
- **Implementazione:** trigger (tutti deterministici in F3): sottofase `failed` oltre i retry → la fase va in `failed` → replanning; budget totale sotto il 25% con >50% delle fasi pending → replanning "descope" (il Planner riceve l'istruzione di ridurre l'ambizione ai criteri minimi); `_eligible_phase` = None ma piano incompleto (incoerenza) → replanning. Meccanica: contesto al Planner = piano corrente + cosa è fallito e perché (dal Verdict) + cosa è già `completed` (IMMUTABILE: le fasi completate non si toccano — validazione deterministica sulla nuova versione); `save_plan` con `reason` esplicita; le sottofasi pending della vecchia versione → `skipped`.
- **Accettazione:** T010 (piano-trappola: il `plan` iniziale porta a un vicolo cieco progettato) esegue almeno un replanning e completa; le fasi completate risultano intatte tra le versioni.

#### F3.5 — 📌 A/B: il Planner si guadagna il posto

- [x] 🤖 **Obiettivo:** la sottofase che decide se F3 resta. *(fatto: report committati, conclusione = ESCE dal default — v. ESITO F3)*
- **Motivazione:** D11 applicato per la prima volta. Il confronto è contro una baseline *degradata ma onesta*: F1 non sa fare multi-step senza piano scritto a mano, quindi la baseline per i nuovi task è "piano statico ingenuo" = una sola fase con una sola sottofase "do everything", che rappresenta ciò che farebbe un agente naive.
- **Implementazione:** nuovi task multi-step: **T007** refactoring 3-file con test · **T008** feature cross-module · **T009** fix con migrazione dati fittizia (ordine obbligato: prima lo script, poi il codice) · **T010** piano-trappola per il replanning. Eval su tutto il set (T001–T010) in due configurazioni: `--ab no-planner` (piano ingenuo) vs pipeline F3, stesso profilo, stesso commit. Report di confronto per le 5 metriche.
- **Accettazione:** report A/B committato e nell'atlante con la conclusione scritta (resta / esce / resta con riserva su X).

#### F3.5-nota — Decisioni utente sul verdetto (2026-08-02)

Concordato prima dei numeri ufficiali: (1) il fix perimetro/verifica di F3.2-REVISIONE si applica comunque; (2) **quando usare il Planner è materia di F6** (routing) — in F3 conta solo che *funzioni*; (3) **il test vero del Planner è il chatbot Laravel (F8)**: il cassetto attuale non contiene task che superino una singola sessione Worker, quindi l'A/B locale misura bene il costo ma può sottostimare il valore — il verdetto D11 definitivo sul ruolo si firma in F8.

#### F3.6 — 🔎 Verifica di fase

- [x] T007–T009 `verified` con piano generato; T010 replanning corretto; A/B documentato; nessun piano oltre budget; forbice completed/verified ancora zero. *(eseguita, esito NEGATIVO sui criteri originali: col piano generato solo 2/10 verified — il criterio vero di questa sottofase era il verdetto D11, ed è stato emesso: v. ESITO F3. Forbice = 0 in entrambe le run: il sistema non si è mai auto-illuso.)*

#### ESITO F3 (2026-08-02) — il Planner perde l'A/B e esce dal default

**Numeri ufficiali** (severino-sim, 10 task T001–T010, stesso profilo):

| Run | Commit | Verified | Token totali | Tempo | Forbice |
|---|---|---|---|---|---|
| Baseline (piano statico ingenuo) | `32569a5` | **9/10** (unico caduto: T008) | 710.106 | ~27,5 min | 0 |
| Planner (prima run) | `32569a5` + tree sporco | 0/10 — **INVALIDA** | 478.818 | ~34 min | 0 |
| Planner (rerun, prompt fixato) | `611d894` | **2/10** (T001, T004) | 814.646 | ~44 min | 0 |

**Verdetto D11 (deciso dall'utente): il Planner NON si guadagna il posto sui micro-task — default OFF, gated.** Implementazione: `planner.enabled = false` in `config/default.toml`; a Planner spento l'Orchestrator genera `_naive_plan` (il piano della baseline vincente, deterministico, zero LLM) e il replanning è rifiutato; riaccensione esplicita via `rg eval --planner` (l'harness fa `dataclasses.replace(cfg, planner_enabled=True)`).

**Perché ha perso** (autopsia nei log e in atlante §9): (1) logica spazzatura residua del Planner (auto-dipendenze `P1→P1`, troncamenti) — 3 task morti in <3 chiamate; (2) **fasi ridondanti** che ripetono lavoro già fatto — il volto strutturale dell'overhead di governance, non un bug puntuale; (3) **sottofasi-analisi artificiali** indotte dalla revisione scoped (expected_outputs-compiti-in-classe che il Worker non produce); (4) retry fotocopia senza diagnosi; (5) interazione col guard `identical_repeat` appena introdotto (run_tests poi esentato). La prima run è stata invalidata da un mio errore di metodo: **A/B su working tree sporco con una frase cancellata dalla card del Designer** → 2 trappole permanenti: *prompt e validatore sono un artefatto solo*; *run ufficiali solo da codice committato*.

**Limite dichiarato del verdetto:** vale su QUESTA batteria (micro-task 2–4 file, dove pianificare non serve per costruzione). L'ipotesi di valore su task larghi non è smentita: non è testabile col cassetto attuale (F3.5-nota, punto 3 — il giudizio definitivo resta F8).

**Diagnosi condivisa con l'utente (2026-08-02): il thrashing era dei GATE, non del proponente** — retry identici, nessun gate d'ingresso fase, replan non diffati. Decisione utente: il rework della pianificazione è un **sistema a sé stante** con piano dedicato — [`plan_planner_system.md`](plan_planner_system.md) (il Planner come *autore* del piano-documento, plan-as-artifact, gate deterministici a zero token, ledger di task, Supervisor solo per diagnosi residua). **Lo sviluppo di questo piano generale è IN PAUSA finché quel sistema non è costruito e A/B-ato**; poi si riprende da F3-bis. Riferimenti: report in `bench/results/eval_severino-sim_{static,planner}_*.md`; trappole nuove in atlante §9 (batch A/B + batch rerun); fix di fase: scoped verification (F3.2-REVISIONE), contract anchoring, `normalize_plan`, richiamate correttive che citano le regole, `no_op_edit`, guard `identical_repeat` (run_tests esente), gate D11.

**Rituale di fine fase** → `v3.0.0`.

---

## Fase 3-bis — Micro-slice multi-dominio → `v3.1.0` (aggiunta su richiesta utente, 2026-08-02)

📎 **Specsheet:** §5 (pipeline per dominio), anticipo leggero di F7 · **Decisioni:** D16, D17
🎯 **Scope:** una fetta verticale SOTTILE dei domini non-coding, prima di F4: analisi di documenti locali, una chiamata HTTP a un servizio esterno (**mai LLM** — snaturerebbe il progetto, parole dell'utente), verifica meccanica degli esiti. NON è F7 (che resta la fase completa con citazioni/triangolazione/web search): è lo smoke che dimostra che l'engine non è un coding assistant.
🧭 **Perché qui:** (motivazione utente) "l'agentic engine deve lavorare anche negli altri domini di uso quotidiano". E perché *prima* di F4: Supervisor e Debugger vanno progettati conoscendo anche i modi di fallire non-coding, non solo pytest-rosso.

- [x] **F3b.1** 🤖 Tool `http_get(url) -> ToolResult` minimale (anticipo di F7.2): GET con timeout e size-cap, **whitelist di domini in config** (`security.http_allowed_domains`, default vuota = niente rete), cache su disco per task (la verifica rilegge LA copia vista dal modello), solo http(s). Niente web search (quella è F7). **FATTO** (`redgiant/tools/web.py`): + guardia sui REDIRECT (destinazione ri-verificata contro la whitelist), cache in `.rg_http_cache/` esclusa da listati/ledger (lezione batch n.5 applicata in anticipo). 4 unit.
- [x] **F3b.2** 🤖 Task sintetici multi-dominio T030-T032. **FATTO** + revisione (richiesta utente): **le tarature sono AUTOMATIZZATE nella suite** (`tests/unit/test_f3bis_tasks.py`) — giudici soddisfacibili con artefatti di riferimento (parametrizzati), servizio T031 collaudato vivo (payload + 404), parsing harness asserito. Harness esteso: `EvalTask.http_allowed_domains` (override per-task della config) e `EvalTask.service_script` (avvio/terminazione gestiti; lo script vive nella dir del task, NON nel repo: il modello non lo vede).
- [x] **F3b.3** 🤖 Plumbing di dominio: i task portano `domain` ∈ {research_local, api, docs}; card Worker invariata (le card per-dominio sono F7.4); verifica = giudici meccanici come nel coding. **FATTO** (asserito dai test).
- [x] **F3b.4** 🔎 **Verifica di fase:** i 3 task girano su severino-sim in modalità baseline con giudice esterno verde; nessuna chiamata di rete fuori whitelist (test); il report entra nell'Evaluator come le altre serie.

**ESITO F3-bis (2026-08-03, `v4.3.0`):** **3/3 VERIFICATI al primo colpo** su severino-sim
(report `bench/results/eval_severino-sim_static_20260803-165402.md`): T030 analisi documenti
68s/21.8K tok · T031 chiamata API **44.8s/18.1K tok** (http_get live: whitelist, fetch, cache)
· T032 trasformazione CSV esatta 279s/140K tok con 1 retry (il formato esatto resta il lavoro
più duro per il 2B — coerente con F18). Forbice 0, useful 100% su tutti e tre. **La tesi
"non è un coding assistant" ha i suoi primi numeri**: l'engine con giudici meccanici lavora
sui domini quotidiani alla prima uscita — ed è esattamente il regime (task stretti, catene
corte, oracoli economici) dove la letteratura colloca il valore degli SLM (README §niche).

**ADDENDUM — ATTRIBUZIONE DEL MERITO (probe "modello nudo", richiesta utente 2026-08-03,
`bench/naked_probe.py` committata e automatica):** stesso compito, materiali inline, UNA
completion, zero tool/loop/retry, stesso giudice → **9/9 VERDI anche nudo**. Attribuzione
onesta: (a) la COGNIZIONE di questi task (estrazione, formato) è **tutta del modello**;
(b) il merito del workflow qui è l'**autonomia end-to-end** (trovare i file, fare il fetch,
scrivere l'artefatto — nella probe l'ho fatto io al posto suo), l'**onestà** (giudice,
forbice 0) e la **sicurezza** (whitelist) — NON la capacità; (c) il costo dell'impacchettamento
agentico è enorme sui task stretti: T032 = 140K token in loop vs <1K nudo. **Conseguenza per
F6 (la più importante):** il percorso diretto per i task quotidiani deve essere DAVVERO
diretto — materiali raccolti deterministicamente + una chiamata + giudice — non il Worker-loop:
su questa classe di task il loop è overhead puro. La probe resta nel repo come braccio di
controllo permanente per ogni task futuro della serie.

---

## Campagna LADDER — attribuzione modello ↔ workflow → `v4.4.0` → `v4.5.x`

📎 **Metodo:** §LA MATRICE DI MISURA (regola permanente) · **Origine:** richiesta utente
2026-08-03 — *"quanto è merito del modello e quanto del workflow? Bisogna creare una batteria
di test di difficoltà crescente e farglieli svolgere nudo finché non fallisce. Poi riprovare
col loop agentico"*.
🎯 **Scope:** costruire un asse di difficoltà **deterministico e rigenerabile** che cresce in
**ampiezza** a cognizione costante per fatto, trovare il punto di rottura del modello nudo,
e sopra quel punto attribuire ogni verde a un componente identificato tramite ablazione.

- [x] **LAD.1** 🤖 Generatore del corpus a 7 gradini, seed fisso, giudici esterni non
  modificabili — `bench/ladder/generate.py`. **FATTO**, con due difetti di misura scoperti e
  corretti in corso d'opera (`data.md` §7.5): il grassetto markdown sui soli bersagli
  penalizzava **solo** il braccio workflow; il giudice stampava il valore atteso, cioè
  **regalava la risposta**. Test permanente che asserisce l'assenza di `**` nel corpus.
- [x] **LAD.2** 🤖 Braccia nude B1/B3 con troncamento dichiarato — `bench/ladder/run_naked.py`.
  **FATTO.** Soffitto del 2B nudo localizzato: **~5.8K token di materiale, 5 fatti, nessuna
  aggregazione**; sopra, zero in tutte e tre le configurazioni.
- [x] **LAD.3** 🤖 Bracci agentici B2/B4 con ablazioni da CLI — `bench/ladder/run_agentic.py`.
  **FATTO.** Attribuzione principale: **la ricerca selettiva è il componente portante**
  (`−search` = 0/5 su tutti i gradini, replicato 3× su due corpus); **la verifica compra
  onestà, non throughput** (`−verify` = 8 false dichiarazioni in 5 run, contro 1 in oltre 550
  run verificate).
- [x] **LAD.4** 🤖 **L'esperimento sull'obbedienza** (`data.md` §7.5): tre livelli di
  persuasione testuale (regola numerata → nome pieno `calculator` → descrizione MANDATORY)
  portano l'invocazione dello strumento dal 16% al 40% e **non muovono il punteggio** (L5
  fermo a 2/5). **Verdetto: un'istruzione non produce obbedienza in questo regime.**
- [x] **LAD.5** 🤖 **F4 applicato ai contenuti** — `redgiant/tools/coherence.py`
  (`arithmetic_check`), cablato in `write_file`/`edit_file`/`write_patch` via
  `fs.coherence_check`, ablabile con `RG_WORKER_ABLATE=coherence`. **FATTO** (`v4.4.0`).
  Motivazione: dove esiste un oracolo deterministico l'operazione non si *suggerisce*, si
  **toglie dalle mani del modello** — un totale non è significato, è identità derivata, e
  l'identità appartiene al control plane (PS-D11). Guardia deliberatamente conservativa
  (solo testo, totale ultimo, ≥2 addendi, un solo totale): un falso positivo blocca lavoro
  legittimo, che è peggio di un mancato aiuto. **Non è un oracolo sul task**: somma ciò che
  il modello ha scritto, non ciò che è vero.
- [x] **LAD.6** 🤖 **Lo stato del mondo nei rifiuti** — `fs.refusal_state`. **FATTO**
  (`v4.4.1`). Scoperto misurando LAD.5: la guardia mordeva in 4 run su 5 ma solo 2 si
  riprendevano — le altre chiamavano `edit_file` su un file **mai creato** o verificavano un
  artefatto mai scritto. *Un rifiuto che dice cosa era sbagliato ma non com'è rimasto il
  mondo lascia il modello a ragionare su uno stato inesistente.* Applicato anche a
  `syntax_error`, che portava la stessa trappola da F1. **Regola generale per ogni gate
  futuro che rifiuta un'azione.**
- [x] **LAD.9** 🤖 **Gate sul finish, DENTRO il loop.** ✅ **FATTO — e SPENTO: risultato nullo.**

  **ESITO (dev-fast, 20 run per braccio, `@699ed56` — `data.md` §7.7):** L5 **18/20 vs 16/20**
  (Fisher bilaterale **p = 0.66**), L7 **11/20 vs 11/20** (**p = 1.00**), con un **+15% di
  tempo** su L5. Nessun effetto su nessuno dei due gradini.

  ### ⚠️ RETTIFICA DEL 2026-08-04 — la spiegazione era sbagliata, il verdetto va riletto

  Avevo scritto: *"il loop di retry pagava già per il finish fantasma; il gate è ridondante"*, e
  ne avevo tratto il corollario *"una patologia frequente non è automaticamente costosa"*.
  **I log di LAD.13 smentiscono entrambi** (`data.md` §7.9.4): le 7 run fallite di quella
  campagna sono **7 su 7 finish fantasma, in tutti e tre i tentativi**. Il retry non paga —
  offre tre occasioni e il modello le spreca tutte allo stesso modo. E quella patologia *è*
  costosa: oggi è **l'unico modo di fallire rimasto** su L5.

  **La lettura corretta di p = 0,66:** 18/20 contro 16/20 è un effetto di **+10 punti**, e per
  separarlo dal rumore servono ~**200 run per braccio**. **L'A/B era SOTTO-POTENZIATO, non
  conclusivo.** Avevo adottato la regola delle 20 run il giorno prima senza chiedermi *20 run
  per vedere quale ampiezza d'effetto*, e ho letto il mio campione insufficiente come verdetto.

  **Il gate resta spento, ma per un motivo diverso:** non perché sia ridondante, ma perché il
  suo effetto **non è ancora dimostrato**. L'evidenza meccanicistica ora gli è **favorevole**:
  colpisce il 100% dei fallimenti residui del gradino che il sistema vince.

  **Verdetto: spento di default**, `roles/worker.py::finish_gate_enabled` dietro
  `RG_FINISH_GATE=1`. **APERTO**, con DUE condizioni di retest:
  1. **Un A/B dimensionato sull'effetto** (~200 run per braccio, o un gradino dove il fenomeno
     è più frequente): quello fatto non poteva vedere +10 punti.
  2. **Sui task coding larghi T040–T042**, dove un tentativo sprecato costa **100K+ token**
     invece di 25 secondi (T032: 140K in loop).

  **Corollario di metodo CORRETTO** (quello precedente è ritirato): **un A/B nullo su un effetto
  piccolo non è un verdetto, è un campione insufficiente.** Un numero fisso di run non è un
  calcolo di potenza: 20 run risolvono una differenza di 40 punti e sono cieche su una di 10.
  Prima di dichiarare "non paga", chiedersi *quale differenza sarei in grado di vedere*.

  Specifica originale conservata qui sotto, perché la condizione di retest la richiede.


  **Misura che lo motiva** (`data.md` §7.6.5): il Worker dichiara `done` **senza aver chiamato
  nessuno strumento di scrittura** nel **40% dei tentativi** (31 su 78), 17 dei quali al primo
  tentativo; e ripete l'errore anche quando il retry gli riporta letteralmente
  `FAIL: answer.txt missing`. La regola 8 della card lo vieta dal F1 — terza conferma
  indipendente che l'istruzione non basta.

  **Costo attuale del difetto:** un finish fantasma brucia un **tentativo intero** (90 file
  rilistati, 5 ricerche rifatte da zero) dove sarebbe bastato **un passo** con la KV calda.

  **Regola del gate — deliberatamente STRETTA, due condizioni distinte:**
  1. `spec.expected_outputs` dichiarati ma **inesistenti** → rifiuto. Costo zero, sempre
     valutata.
  2. **Firma del finish fantasma:** il tentativo non ha eseguito **nessuna mutazione**
     (`write_file`/`edit_file`/`write_patch` con `ok=True`) **E** l'oracolo di
     `spec.verification` è rosso → rifiuto.

  **Perché la congiunzione e non il solo oracolo rosso:** la regola 11 della card autorizza
  esplicitamente a chiudere `done` quando i test falliscono **fuori dal proprio perimetro**
  (li possiede una sottofase successiva). Rifiutare ogni finish con oracolo rosso
  ucciderebbe quella via d'uscita e produrrebbe thrashing sui task multi-sottofase. Con la
  congiunzione si colpisce solo il caso logicamente impossibile: *hai dichiarato fatto, non hai
  cambiato niente, e l'oracolo è rosso.*

  **Perché costa zero nel percorso buono:** se il tentativo ha mutato qualcosa, l'oracolo NON
  viene eseguito in-loop. Il comando di verifica gira solo sul sospetto di finish fantasma.

  **Non cambia chi decide:** la verifica resta il trust boundary (D10). Cambia *dove*: un
  tentativo sprecato diventa un passo di correzione.

  **Firme (file `redgiant/roles/worker.py`):**
  ```python
  _MUTATING_TOOLS: frozenset[str] = frozenset({"write_file", "edit_file", "write_patch"})
  _MAX_FINISH_REFUSALS: int = 2   # tetto: non si sostituisce un loop degenere con un altro

  class Worker(Role):
      def _finish_gate(self, ctx: RoleContext, task_id: str, mutated: bool) -> str | None:
          """Messaggio di rifiuto azionabile, o None se il finish può passare."""
  ```
  In `Worker.run`, nel ramo `isinstance(step, WorkerFinishStep)`: se
  `step.finish.status == "done"`, il gate non è ablato e i rifiuti sono sotto il tetto, si
  chiama `_finish_gate`; se ritorna un messaggio si fa
  `parts = parts.with_appended_context("\n[FINISH REFUSED] ...")` e `continue` — il finish
  diventa uno step, **non** una chiusura.

  **Il messaggio dichiara lo stato del mondo** (lezione di LAD.6): dice che nessuna scrittura è
  avvenuta in questo tentativo, riporta l'uscita reale dell'oracolo, e nomina l'azione da fare.

  **Accensione:** `RG_FINISH_GATE=1` → `roles/worker.py::finish_gate_enabled()`; bracci
  `+finishgate` e `think+finishgate` in `bench/ladder/run_agentic.py::ARMS`, B2 e B4.
  **Convenzione di polarità nei bracci:** `−x` abla un componente **attivo**, `+x` accende un
  componente **spento** (verdetto negativo ma aperto).

  **Verifica:** 8 unit test — i due rami del gate, il non-mordere dove la regola 11 autorizza,
  il check sconosciuto, il tetto, il default spento, i bracci registrati con la polarità
  giusta.
- [ ] **LAD.10** 🤖 **`bad_args` che insegna** (stessa fonte): `calculator` riceve
  `expression=None` in **27 chiamate su 67 (40%)**; il router risponde col dump grezzo di
  pydantic e il modello ci cicla 5 step prima di arrendersi. **Riscrive in parte LAD.4:** parte
  di quel "60% calcola a mente" era il modello che *provava* a usare lo strumento e veniva
  respinto da un errore che non nominava l'argomento mancante. **Intervento:** in
  `ToolRouter.dispatch`, l'errore `bad_args` nomina i campi obbligatori mancanti e mostra una
  chiamata d'esempio derivata dall'`input_model`, invece di `e.errors()`.

  ⚠️ **Attenzione all'ambito:** LAD.10 è un fix **del router**, non della calcolatrice —
  migliora *ogni* strumento del catalogo. La calcolatrice è solo il posto dove l'abbiamo
  misurato.

- [x] **LAD.13** ✅ **FATTA — NO: la calcolatrice esce dal catalogo.** (dev-fast, 20 run per
  braccio, `data.md` §7.9) `full` **16/20** contro `−calc` **17/20**, **Fisher p = 1,000** —
  l'ablazione è persino nominalmente migliore. **E non per mancato uso:** nel braccio completo
  ci sono **27 chiamate riuscite** con l'espressione giusta.
  **Causa: la guardia di coerenza (LAD.5) l'ha resa superflua** — due percorsi allo stesso
  esito, e quello deterministico non dipende da una scelta del modello.
  **Esito (b) della pre-registrazione, applicato:** spenta di default dietro `RG_CALCULATOR=1`
  (`router.calculator_enabled`), braccio `+calc` in B2 e `think+calc` in B4. Si risparmia la sua
  voce nella card, pagata a ogni step di ogni task (test permanente che lo asserisce).
  **APERTO:** la guardia copre solo i *totali in file di testo*; nei domini di F7 (matematica,
  everyday) l'aritmetica non ha quella forma → **rimisurare lì** prima di dichiararla inutile
  in generale.
  **Verifica della previsione di LAD.10 — la previsione era sbagliata, e con essa la metrica.**
  Avevo registrato *"il tasso di `bad_args` dev'essere ~0"*. Confronto **pulito** (soli task in
  cui lo strumento era nel catalogo; i primi numeri che avevo calcolato mescolavano i due bracci
  e più campagne, e nel braccio ablato l'errore è `unknown_tool`, non `bad_args`):

  | | Prima | Dopo |
  |---|---|---|
  | Chiamate malformate | 78/240 (**32%**) | 6/33 (**18%**) |
  | Sequenze consecutive, **max** | **6** | **1** |
  | Sequenze **fatali** | **7** | **0** |
  | Recupero | 85% | **100%** |

  **L'errore azionabile non impedisce lo sbaglio: elimina la spirale.** Il modello manda ancora
  argomenti vuoti una volta su cinque, ma prima costava fino a **sei passi** e uccideva il
  tentativo, ora ne costa **uno**. Stesso profilo di `refusal_state` (LAD.6).
  **Regola generale da portarsi dietro:** *i gate deterministici cambiano quanto spesso si
  riesce; gli errori azionabili cambiano quanto costa sbagliare.* Sono assi diversi — e una
  metrica di frequenza è **cieca** al secondo. È per questo che avevo pre-registrato la metrica
  sbagliata.

  Specifica originale conservata qui sotto.

- [ ] ~~**LAD.13** 🔎 **La calcolatrice merita il catalogo? — A/B a n=20, DOPO LAD.10.**~~
  Anomalia rilevata rileggendo lo stato degli interruttori: `calculator` è **acceso senza
  prove**, in mezzo a un insieme di decisioni prese tutte coi numeri. È invocato nel ~40% delle
  occasioni, e nelle run vincenti di L5 spesso **mai**; la sua ablazione (`−calc`) non ha mai
  mostrato differenze — ma a n=5, quindi non concludente. Occupa spazio nella card dei tool
  (token di prompt su ogni step) senza aver dimostrato di servire.

  **Ordine OBBLIGATO — prima LAD.10, poi questa:** misurare `−calc` adesso significherebbe
  condannare uno strumento che sappiamo **rotto sull'interfaccia** (il 40% delle chiamate non
  arriva nemmeno a eseguirsi per `expression=None`). Si ripara, poi si giudica. Invertire
  l'ordine produrrebbe un verdetto sull'implementazione, non sullo strumento.

  **Esecuzione:** `full` vs `−calc` su L5, 20 run per braccio, Fisher allegato. Esiti:
  (a) `−calc` peggiora ⇒ lo strumento resta, e LAD.4 andrà riletto (il problema era
  l'interfaccia, non l'obbedienza); (b) nessuna differenza ⇒ **si rimuove dal catalogo**, e si
  registra che la guardia di coerenza lo aveva reso superfluo — il control plane calcola, il
  modello non deve nemmeno chiedere.
- [ ] **LAD.15** 🔎 **Rimisura di B1 e B3 su TUTTA la ladder col fix dei marcatori.**
  ⚠️ **Dubbio di validità sulle FONDAMENTA, aperto dal fix di LAD.14.** I numeri B1/B3 di
  `data.md` §6.2 — cioè la base dell'affermazione più citata del progetto, *"il pavimento nudo
  è ~5,8K token, 5 fatti, nessuna aggregazione"* — sono stati misurati **prima** che
  `run_naked.strip_template_markers` esistesse, quindi con il difetto attivo: il modello emette
  a volte i marcatori del chat template come testo e il giudice li cattura dentro il valore,
  **bocciando anche una risposta esatta**.
  **Argomento per cui probabilmente non cambia nulla:** i gradini che *passavano* (L1-L4) non
  possono averne sofferto, e L6/L7 avevano il materiale troncato al 57-83% quindi sarebbero
  caduti comunque. **Perché va fatto lo stesso:** "probabilmente" non è una misura, e il
  difetto penalizzava proprio il braccio contro cui la nostra tesi si confronta — un errore che
  gonfia i *nostri* risultati va tolto di mezzo, non spiegato.
  Comandi: `python bench/ladder/run_naked.py dev-fast 20 T05` e lo stesso con `--think`.
  **Bloccante per LAD.7:** il run ufficiale non parte finché queste fondamenta non sono pulite.
- [x] **LAD.11** ✅ **FATTA — il pensiero dentro il workflow NON paga, e la previsione era
  sbagliata.** (dev-fast, 20 run per gradino per braccio, **stesso commit per i due bracci**;
  il B2 è stato rifatto apposta invece di riusare quello di LAD.9 — `data.md` §7.10)

  | Gradino | B2 workflow | B4 + pensiero | Fisher | Δ |
  |---|---|---|---|---|
  | L5 | **19/20** | 16/20 | p = 0,342 | −3 |
  | L6 | 16/20 | **19/20** | p = 0,342 | +3 |
  | L7 | 8/20 | **12/20** | p = 0,343 | +4 |
  | aggregato | **43/60** | 47/60 | **p = 0,528** | +4 |
  | tempo | **1.794 s** | 2.772 s | | **+55%** |

  Segni alternati, p identici a tre cifre: rumore attorno allo zero, a +55% di costo.

  **LA PREVISIONE REGISTRATA ERA SBAGLIATA.** Avevo scritto che su L7 il pensiero avrebbe
  **peggiorato** l'esito rubando contesto: è uscito **12/20 contro 8/20**, nominalmente il
  contrario. Il modello mentale era errato — credevo che il budget di pensiero fosse sottratto
  al **contesto durevole**. Due misure lo smentiscono: (a) il pensiero **non si comprime** al
  crescere del prompt (137 → 452 token medi) e si chiude naturalmente sotto il fusibile;
  (b) **TH-D2** fa sì che il ragionamento **non entri mai nella catena append-only** — generato
  e scartato a ogni chiamata. Il costo è **per chiamata, non cumulativo**.
  **Una decisione architetturale presa per la purezza della catena protegge da un fallimento
  identificato mesi dopo.**

  **La risposta alla domanda per cui la matrice esiste** (*il ragionamento sostituisce un
  componente mancante?*): **B3−B1 = 0/20 → 20/20** (§7.8) contro **B4−B2 = zero**. Il workflow e
  il ragionamento **risolvono lo stesso collo di bottiglia: chi arriva primo prende tutto**.
  Sono **sostituti, non complementi** — e questo dà a TH2 una spiegazione invece di un solo
  numero: il thinking non è inutile in assoluto, è inutile *sopra un'impalcatura che copre già
  il suo contributo*.

  **Riserva:** su L7 entrambi i bracci sono lontani dal soffitto (IC 95% 22-61% e 39-78%,
  ampiamente sovrapposti) ed è l'unico gradino dove il collo di bottiglia — la capienza — **non
  è coperto da nessuno dei due**. Se F5 lo rimuove, il confronto va rifatto lì: potrebbe essere
  l'unico posto dove i due smettono di essere sostituti.

- [ ] **LAD.11-bis** 🔎 **B4 con le ablazioni** (simmetria obbligatoria della matrice): finora è
  stato misurato solo il braccio `think` completo. Servono `think-search`, `think-verify`,
  `think-retry`, `think-coherence`, `think+calc`, `think+finishgate` — è la metà della matrice
  che risponde a *"il ragionamento compensa il pezzo mancante?"* per **ciascun** pezzo.
  ⚠️ **Il blocco B4 pre-fix è stato BUTTATO** (girava su codice precedente ai fix del corpus e
  del giudice, quindi non comparabile): nella matrice c'è un **buco dichiarato**, non un dato
  mancante per dimenticanza. Nessuno vada a cercarlo in `bench/results/`.
  Comando: `python bench/ladder/run_agentic.py dev-fast T056,T057 B4 20`.
- [x] ~~**LAD.12** Disambiguazione del confondimento B3/L5 col fusibile a 256.~~ **GIÀ FATTA**
  (`data.md` §6.2, nota 1): ripetuta su severino-sim con `RG_THINKING_BUDGET=256`, il
  troncamento risale a **7.280 token** contro i 7.536 del nudo — alla pari — e il risultato
  resta **0/3**. *(Era finita fra le cose da fare per un mio errore di trascrizione da una
  lista "cosa manca" non aggiornata: la sottofase esisteva già come misura eseguita.)*

- [x] **LAD.14** ✅ **FATTA — E HA RIBALTATO IL VERDETTO.** (dev-fast, 20 run per braccio,
  `@81179c3`, `data.md` §7.8)

  | Braccio su L5c | Verificati |
  |---|---|
  | B1 nudo | **0/20** |
  | B3 nudo + pensiero pieno (1536) | **20/20** |

  **Fisher esatto bilaterale p = 1,45 × 10⁻¹¹.** Condizione di validità verificata *col
  tokenizer del modello prima di leggere gli esiti*: materiale reale **3.587 token** contro
  budget 7.536 (nudo) e 6.000 (col pensiero) — **nessun troncamento in nessuno dei due bracci**,
  margine 2.413 token. I due bracci hanno visto materiale identico; l'unica differenza era il
  canale di pensiero.

  **RIBALTA** la tesi *"il ragionamento esplicito non compra l'aritmetica"*, che era scritta in
  `data.md` §6.2, nel README e nel whitepaper §6.4. Era vera **solo nel regime misurato**, e il
  regime era il confondimento stesso: due prove davano pensiero pieno e materiale troncato, la
  terza materiale alla pari e pensiero **mutilato a 256** (che TH0 aveva già misurato come "mai
  una chiusura naturale, tutte le chiamate tagliate a metà frase").

  **NON ribalta** TH2 sulla batteria ufficiale di coding (Δ = 0 su 4 batterie): altro dominio,
  altra misura, thinking resta spento lì.

  **Formulazione corretta:** *il ragionamento compra l'aritmetica, ma non entra in 8192 token
  insieme al materiale.* Verdetto sull'**hardware**, non sul modello.

  **CONSEGUENZE, tutte da propagare:**
  1. **F5 acquista un secondo obiettivo** — fare spazio al *ragionamento*, non solo al
     materiale. Da fase di prestazioni a fase di **capacità**. Vedi la nota in F5 sotto.
  2. **LAD.11 (blocco B4) sale di priorità**: se il pensiero paga da solo, cosa fa dentro il
     workflow?
  3. **Da confermare su `severino-sim`** prima di essere citato come verdetto (D6).
  4. **Regola di metodo nuova:** *un controllo che MUTILA la variabile invece di isolarla non è
     un controllo* — produce un nullo illeggibile che sembra una conferma. Prima di accettare
     un controllo, dimostrare che non disabilita il meccanismo in prova.

  Specifica originale conservata qui sotto.

- [ ] ~~**LAD.14** 🔎 **Il pensiero a budget PIENO e materiale PIENO — la cella mai misurata.**~~
  (obiezione dell'utente, 2026-08-04: *"non ha senso RIDURRE i token del pensiero, bisogna
  AUMENTARE i token di contesto se c'è il pensiero"*.)

  **Perché le due misure esistenti non bastano.** Entrambe tengono costante una variabile
  sacrificando l'altra:

  | Configurazione | Pensiero | Materiale visto | L5 |
  |---|---|---|---|
  | nudo | — | 7.536 | 0/3 |
  | nudo + thinking, fusibile 1536 | pieno | **6.000** (meno) | 0/3 |
  | nudo + thinking, fusibile 256 | **mutilato** | 7.280 (alla pari) | 0/3 |
  | **LAD.14** | **1536 (pieno)** | **7.536 (pieno)** | **?** |

  Il fusibile a 256 rende un risultato nullo **illeggibile**: non distingue *"il ragionamento
  non serve"* da *"256 token non bastano per ragionare"*. È un confondimento speculare al primo,
  non la sua soluzione.

  **DISEGNO SCELTO — rimpicciolire il materiale, non allargare il contesto.**
  Il contesto vero non è `cfg.llm.ctx_size` (che è solo il controllo lato client in
  `run_naked.py:57`, `budget = ctx_size − MAX_OUT − 400 − think_budget`): è il `-c` con cui
  `llama-server` è stato avviato, oggi **8192**. Alzarlo richiede di **riavviare il server** —
  cambio infrastrutturale, mai di iniziativa. La stessa domanda si risponde senza toccare nulla
  usando un gradino il cui materiale sta *comodo* in entrambi i bracci.

  **Gradino `L5c` = `T058_ladder_l5c`** (già in `bench/ladder/generate.py::RUNGS`): stesso
  compito di L5 — **5 fatti + la somma** — ma su **40 documenti** (~2.5K token) invece di 90.
  A ctx 8192 il braccio nudo dispone di **7.536** token di materiale e quello col pensiero
  pieno di **6.000**: con ~2.5K **nessuno dei due tronca**. Non è un gradino più duro: è la
  variante **controllata** di L5.

  **Esecuzione (da lanciare, NON ancora eseguita):**
  ```
  python bench/ladder/generate.py                              # crea T058 (seed fisso)
  python bench/ladder/run_naked.py dev-fast 20 T058            # B1: nudo
  python bench/ladder/run_naked.py dev-fast 20 T058 --think    # B3: pensiero 1536
  ```
  20 run per braccio (regola delle 20) con Fisher allegato. **GPU `dev-fast`**: serve a
  classificare, non a produrre numeri ufficiali (D6) — se emerge un effetto, si decide se vale
  una campagna su `severino-sim`.

  **Controllo obbligatorio prima di leggere gli esiti:** il runner dichiara il troncamento; su
  T058 **non deve comparire** in nessuno dei due bracci. Se compare, la misura è nulla.

  **Variante a contesto allargato — resta disponibile, richiede autorizzazione.** L5 originale
  con `RG_THINKING_BUDGET=1536` e `llama-server -c 9728`, per avere pensiero pieno **e** i
  7.536 token di materiale del braccio nudo. Ha senso solo **se** L5c mostra un effetto. Il
  risultato non descriverebbe comunque una configurazione spedibile: `ctx_size = 8192` è un
  vincolo **misurato** (F0.6 — prefill a freddo 8K = 69,6 s contro 16K = 173,6 s; a ~9,7K si
  stimano 90-100 s su Severino, oltre il tetto di D8).

  **Perché vale comunque la pena, ed è il punto dell'obiezione:** i due esiti portano a verdetti
  *di natura diversa*.
  - **Resta 0/3** ⇒ il verdetto TH3 si rafforza ed è definitivo su questo asse: il ragionamento
    esplicito non compra l'aritmetica, punto, indipendentemente da quanto contesto gli dai.
  - **Passa** ⇒ TH3 va **riqualificato**: non *"il thinking non paga"* ma **"il thinking paga e
    non ci sta in 8192"**. Diventa un verdetto sull'**hardware**, non sul modello — e cambia
    l'obiettivo di **F5**, che a quel punto dovrebbe ottimizzare il contesto anche per fare
    spazio al pensiero, non solo al materiale.

  Questa distinzione non è deducibile da nessuna delle celle già misurate.
- [ ] **LAD.7** 🔎 **Verifica di campagna:** L5/L6/L7 su `severino-sim` col codice finale,
  bracci B2 completi (`full`, `−search`, `−verify`, `−retry`, `−calc`, `−coherence`) e B4
  simmetrico, **20 run per braccio** (regola sotto) con test esatto allegato. Sono **questi** i
  numeri destinati al README e a `data.md`; gli attuali sono GPU e dichiarati tali.
  Stima: ~6 bracci × 3 gradini × 20 run su CPU — va pianificata come campagna notturna, non
  lanciata a cuor leggero.
- [x] **LAD.8** 🔎 **Diagnosi di L7. RISOLTA — e non era nessuna delle due ipotesi.**
  Non è correttezza né completamento: **è capienza.**
  ```
  llm error: prompt of 9323 tokens exceeds budget (ctx_size=8192)
  ```
  Su 92 tentativi, il Worker usa **8,5 passi di media, massimo 18** su 60 disponibili —
  **nessuno esaurisce il budget di passi**. I tentativi muoiono perché la catena append-only
  dei risultati sfonda la finestra: ogni risultato di ricerca su 400 documenti pesa fino a
  `_RESULT_MAX_CHARS = 6000` caratteri (~1500 token), e cinque o sei saturano gli 8192.
  *(Onestà: una prima classificazione automatica li aveva letti come "budget di passi esaurito"
  — il grep matchava `exceeds budget`. La diagnosi giusta è arrivata leggendo le motivazioni
  per esteso.)*
  **Conseguenza: L7 è un problema di F5, non del percorso Worker** — la ladder ha motivato
  "Dwarf Star" dal basso, con un numero invece che con un'intuizione. Leve candidate in F5.1:
  risultati di ricerca più stretti; compattazione dei risultati vecchi (**che rompe il riuso
  append-only della KV cache — F0.5: 65 token contro 7971 — è un compromesso da MISURARE, non
  da assumere**); scarico dei fatti trovati su un artefatto di appoggio.
  **Numero da non perdere:** L7 col codice attuale passa **11/20**, contro il rosso in ogni
  braccio delle misure precedenti e lo **0/3** nudo — merito dei fix precedenti (corpus
  uniforme, giudice non rivelatore, guardia di coerenza, `refusal_state`, budget di passi
  proporzionale alla taglia), **non** di LAD.9.

**ESITO (2026-08-03, GPU, `@da8df90`, **20 run per braccio** — `data.md` §7.6):**
`full` **18/20 (90%)** contro `−coherence` **9/20 (45%)** — 45 punti, **Fisher esatto
bilaterale p = 0.0057** — e il braccio con la guardia è anche **il 37% più veloce** (500s vs
797s: un rifiuto immediato costa una riscrittura, un artefatto incoerente costa un giro di
verifica fallita più il rientro nella ricerca da zero). È il primo gradino che il modello nudo
non vede in **nessuna** configurazione (B1 0/3, B3 0/3): il 90% è tutto merito
dell'impalcatura. **Nei blocchi vincenti il modello spesso non invoca mai la calcolatrice**: il
totale esce giusto perché il control plane rifiuta l'incoerenza e restituisce il numero.

**⚠️ REGOLA NUOVA E NON NEGOZIABILE — nessuna conclusione sulla ladder sotto le 20 run per
braccio, e il numero si accompagna a un test esatto, non a un'impressione.**

> **INTEGRAZIONE OBBLIGATORIA (2026-08-04), pagata subito dopo:** 20 run sono un *minimo*, non
> un calcolo di potenza. Risolvono una differenza di ~40 punti; sono **cieche** su una di 10.
> Con LAD.9 ho letto un 18/20 contro 16/20 (p = 0,66) come "non paga", quando l'unica
> conclusione lecita era "non l'ho misurato". **Prima di dichiarare un componente inutile,
> dichiarare quale differenza il campione era in grado di vedere.** Un nullo su un effetto
> piccolo non è un verdetto: è un campione insufficiente.

Pagata sul campo:
i primi blocchi erano a n=5 e hanno prodotto, **su codice funzionalmente identico**,
`−coherence` = 1/5 e poi 5/5 (`full` = 2/5, 3/5, 5/5). Su quella base avevo scritto
un'attribuzione in tre documenti e ho dovuto ritirarla. Causa: il comportamento del modello
oscilla **per blocchi interi** (calcolatrice mai usata in 5 run consecutive, poi usata di
continuo nelle 5 successive), quindi la varianza reale è molto più larga della banda di rumore
hardware di `data.md` §1.3. La regola vale per la ladder e per ogni A/B futuro di pari natura.

---

## Fase 4 — Verifica continua e supervisione → `v4.0.0`

> ### 🔀 ORDINE INVERTITO: **F5 VIENE PRIMA DI F4** (decisione utente, 2026-08-04)
>
> **Perché:** due misure indipendenti della ladder hanno indicato la **capienza di contesto**
> come il vincolo che morde davvero, non la sofisticazione del controllo.
> - **LAD.8** — L7 muore perché la catena append-only sfonda gli 8192, usando 8,5 passi di
>   media su 60 disponibili. Non è disciplina, non è completamento: è capienza.
> - **LAD.14** — il ragionamento pieno risolve l'aritmetica 20/20 contro 0/20
>   (p = 1,45×10⁻¹¹) ma **non ci sta in 8192 insieme al materiale**.
>
> **L'argomento:** F4 costruisce sofisticazione (Debugger, Supervisor, scala dei fallimenti)
> **sopra** un sistema che sbatte contro il soffitto del contesto; F5 alza il soffitto sotto cui
> tutto il resto lavora — incluse le diagnosi che F4 dovrà produrre, che a loro volta occupano
> contesto. Costruire F4 prima significherebbe tararla su un regime che F5 cambierà.
>
> **Conseguenza sulle versioni:** F5 chiude a `v5.x`, F4 la segue. La tabella delle versioni
> in testa al documento resta la fonte di verità sui numeri effettivamente usati.

📎 **Specsheet:** §6.6, §6.7, §12, §13, §14 · **Decisioni:** D10, D11
🎯 **Scope:** il sistema smette di fidarsi di sé: Debugger a due stadi, Supervisor con decisioni chiuse, scala dei fallimenti, anti-loop, checkpoint/rollback via git, BudgetManager per ruolo.
🧭 **Perché questa fase, perché ora:** con la pianificazione attiva gli errori diventano *interessanti*: distinguere "codice sbagliato" da "test sbagliato" da "piano sbagliato" (specsheet §12) è ciò che permette di correggere al livello giusto invece di ritentare alla cieca. Prima di F3 non c'era un piano da incolpare; ora c'è, e serve l'apparato che lo incolpi a ragion veduta.

#### F4.1 — Debugger a due stadi

- [ ] 🤖 **Obiettivo:** il verificatore completo: stadio 1 deterministico (esteso da F1.6), stadio 2 modello — solo sul residuo (D10).
- **Motivazione:** l'ordine dei due stadi è il punto: il modello non deve MAI poter contraddire un oracolo (se pytest dice rosso, è rosso), ma può aggiungere diagnosi dove l'oracolo è muto (perché è rosso, e di chi è la colpa). Il valore atteso del ruolo è la *classificazione* dell'errore (specsheet §12), che il Supervisor userà per decidere il livello di intervento.
- **Implementazione:** `roles/debugger.py` + card; `verify.py` esteso (stadio 1 invariato nelle firme):
  ```python
  class FailureItem(BaseModel):
      kind: Literal["code","test","plan","model"]      # la tassonomia §12
      ref: str; reason: str = Field(max_length=300)
  class DebugReport(BaseModel):
      verdict: Literal["pass","fail"]
      checks: list[CheckResult]; failures: list[FailureItem]
      severity: Literal["low","medium","high"]
      recommended_action: Literal["accept","retry","repair","replan_phase","replan_global","escalate"]
      repair_scope: list[str]                          # file/aree da toccare per riparare
  class DebuggerRole(Role):
      name = "debugger"; output_model = DebugReport
      def run(self, ctx: RoleContext, *, deterministic: Verdict) -> DebugReport
  ```
  Regole cablate nell'Orchestrator (non nella card: sono legge, non consiglio): se lo stadio 1 è tutto `pass` e la sottofase non ha criteri non-meccanici → il Debugger-modello **non viene chiamato** (costo zero, D11); se chiamato, il suo `verdict` non può ribaltare un check deterministico fallito (merge: deterministico vince). Card: distingui errori di codice/test/piano; un test generato o modificato non è vangelo (specsheet §6.6: va controllato rispetto ai requisiti).
- **Accettazione:** su T011 (v. F4.6) il Debugger identifica `kind` corretto; sul set esistente, i task con oracolo pieno non pagano nemmeno una chiamata Debugger (verificabile da `llm_calls`).

#### F4.2 — Supervisor

- [ ] 🤖 **Obiettivo:** il decisore di processo (specsheet §6.7): dove il sistema sceglie il livello d'intervento.
- **Motivazione:** finora la policy era fissa (retry → failed). Il Supervisor la sostituisce con una decisione informata (report, tentativi, budget) — ma dentro un enum chiuso, e filtrata dall'Orchestrator: il modello propone, la legge dispone.
- **Implementazione:** `roles/supervisor.py` + card:
  ```python
  class SupervisorDecision(BaseModel):
      decision: Literal["accept","retry_subtask","repair","redesign_phase",
                        "replan_global","rollback","ask_user","stop_partial","stop_failed"]
      reason: str = Field(max_length=300)
      target: str | None; retry_strategy: str | None = Field(default=None, max_length=200)
  class Supervisor(Role):
      name = "supervisor"; output_model = SupervisorDecision
      def run(self, ctx: RoleContext, *, report: DebugReport, attempts: int,
              budget_left: BudgetUsed) -> SupervisorDecision
  ```
  Filtro di legalità nell'Orchestrator (`_apply_decision`): `retry_subtask` con `attempts >= max` → declassata a `redesign_phase` (loggando la declassazione in `decisions`); `accept` con verdict deterministico `fail` → illegale, forzata a `repair` (il Supervisor non può assolvere contro l'oracolo); `rollback` senza checkpoint → declassata a `retry`. Ogni decisione (proposta e applicata) in `decisions`. Quando tutto è `pass`, il Supervisor **non viene chiamato**: accettazione automatica (stessa logica-costi di F4.1).
  `retry_strategy`, se presente, entra nel contesto S6 del retry come blocco `[STRATEGY]` — è il meccanismo con cui il retry *cambia* invece di ripetersi.
- **Accettazione:** matrice di legalità coperta da unit test (decisione proposta × stato → decisione applicata); su T012–T014 le decisioni finali sono quelle attese.

#### F4.3 — LoopGuard

- [ ] 🤖 **Obiettivo:** il rilevatore di non-progresso (specsheet §13): il sistema deve accorgersi di girare a vuoto *prima* di finire il budget.
- **Motivazione:** i loop sono il modo in cui i modelli piccoli muoiono: stessa patch, stesso errore, all'infinito. Il budget da solo li ferma tardi (dopo averlo mangiato); la firma degli errori li ferma appena si ripetono.
- **Implementazione:** `core/loopguard.py`:
  ```python
  class LoopGuard:
      def __init__(self, store: StateStore, window: int = 5) -> None
      def error_signature(self, report: DebugReport) -> str
          # hash normalizzato di (kind, ref, reason-normalizzata) dei failures:
          # depurata da numeri di riga/timestamp, perché lo STESSO errore deve dare la STESSA firma
      def register(self, task_id: str, sig: str) -> None       # persistita in decisions (actor='loopguard')
      def progress_score(self, task_id: str) -> float
          # (sottofasi completate + tool_call ok nuove) / token spesi, su finestra mobile
      def is_looping(self, task_id: str) -> bool
          # firma identica ≥2 nella finestra, O patch che si annullano (diff A+B ≈ vuoto), O score sotto soglia
  ```
  Integrazione: l'Orchestrator consulta `is_looping` prima di applicare `retry`/`repair`; se true, forza l'escalation di un livello (retry→redesign, redesign→replan, replan→stop) e lo logga. La scala §13 (1° fallimento: correzione locale; 2°: strategia nuova — `retry_strategy` obbligatoria; 3°: revisione fase; oltre: stop/escalation) vive qui + nel filtro di F4.2.
- **Accettazione:** T014 (loop-trappola) fermato entro 2 ripetizioni della firma; unit test della normalizzazione firme (stesso errore con numeri di riga diversi → stessa firma).

#### F4.4 — CheckpointManager

- [ ] 🤖 **Obiettivo:** poter tornare indietro: git come motore di checkpoint/rollback sul repo target (specsheet §16 per i punti).
- **Motivazione:** `write_patch` è reversibile solo se esiste un punto a cui tornare. Git è il motore giusto perché è già lì, è ispezionabile dall'utente con strumenti che conosce, e il branch di lavoro isola Red Giant dalla storia del target.
- **Implementazione:** `core/checkpoint.py`:
  ```python
  CheckpointKind = Literal["post_plan","post_subtask","pre_risky","pre_replan"]
  class CheckpointManager:
      def __init__(self, store: StateStore, target_repo: Path) -> None
      def ensure_work_branch(self, task_id: str) -> str    # crea/usa branch rg/task-<id> dal HEAD corrente
      def checkpoint(self, task_id: str, kind: CheckpointKind, *, subtask_id: str | None = None) -> str
          # git add -A + commit sul branch di lavoro; ritorna lo sha; riga in checkpoints
      def rollback(self, task_id: str, ref: str) -> None   # git reset --hard <ref> SOLO sul branch rg/task-*
  ```
  Punti di scatto (dall'Orchestrator): `post_plan` (dopo save_plan v1), `post_subtask` (a ogni accettazione), `pre_replan`; `pre_risky` prima di un dispatch `requires_approval` andato approvato. Onboarding del task: target non-git → `git init` + commit iniziale di servizio (dichiarato all'utente nel dettaglio task); target git → si lavora SEMPRE su `rg/task-<id>`, mai sul branch dell'utente; la consegna finale (merge o PR) resta manuale dell'utente in F4 (annotato come debito: automatizzarla è una decisione da prendere con l'uso).
- **Casi limite:** repo target con modifiche non committate dell'utente → stash? NO: rifiuto esplicito all'avvio del task ("target has uncommitted changes") — non si manipola lavoro umano non salvato.
- **Accettazione:** rollback end-to-end su un caso reale (Supervisor decide `rollback` → il file torna com'era → il retry riparte dal checkpoint); il branch dell'utente non è MAI mosso (test).

#### F4.5 — BudgetManager completo

- [ ] 🤖 **Obiettivo:** da tracker a manager: limiti per ruolo, avvisi, stop esplicativi (specsheet §15).
- **Implementazione:** `core/budget.py` esteso:
  ```python
  class BudgetVerdict(BaseModel): status: Literal["ok","warn","exceeded"]; key: str | None; detail: str
  class BudgetManager(BudgetTracker):
      def __init__(self, store: StateStore, budget: Budget, task_id: str,
                   per_role_caps: dict[str, int]) -> None    # token cap per ruolo, da F0.6
      def check(self) -> BudgetVerdict                        # warn a 80%
      def charge_llm(self, r: LlmResult) -> None              # + attribuzione per ruolo
  ```
  `warn` → una riga in `decisions` (actor `budget`) + visibile in GUI; `exceeded` → stop secondo la policy F1.7 (partial/failed spiegato). Il cap per ruolo previene il Planner-fiume e il Debugger-chiacchierone anche quando il totale reggerebbe.
- **Accettazione:** sforamento per ruolo simulato → il ruolo viene tagliato con errore esplicito e il task segue la policy; il warn compare in GUI.

#### F4.6 — 📌 Evaluator: la batteria dell'onestà

- [ ] 🤖 **Obiettivo:** i task che mettono alla prova proprio F4: **T011** bug subdolo (i test passano ma un criterio esplicito della sottofase è violato: caccia al Debugger semantico) · **T012** task impossibile (richiesta contraddittoria: DEVE finire `failed` con spiegazione onesta — specsheet §22 li prevede apposta) · **T013** informazioni mancanti (DEVE fare `ask_user`, non inventare) · **T014** loop-trappola (bug il cui fix ovvio rompe un altro test, invitando l'oscillazione).
- **Motivazione:** finora l'Evaluator premiava il successo; da F4 deve premiare anche il *fallimento giusto*. Un sistema che completa T012 sta mentendo: il report deve trattare quel "successo" come il peggiore dei fallimenti.
- **Implementazione:** `EvalTask` + `expected_outcome: Literal["verified","failed","blocked"] = "verified"`; il report confronta esito vs atteso; A/B: pipeline F3 vs F4 sull'intero set (D11 per Debugger+Supervisor come blocco).
- **Accettazione:** i 4 task nuovi si comportano come da `expected_outcome`; A/B committato con conclusione.

#### F4.7 — 🔎 Verifica di fase

- [ ] Zero successi senza evidenza su tutto il set; T012 `failed` onesto; T13 `blocked`→risposta→ripartenza; T014 fermato dal LoopGuard entro budget; rollback dimostrato; il branch utente mai toccato; A/B F4 documentato.

**Rituale di fine fase** → `v4.0.0`.

---

## Fase 5 — Contesto e KV cache (la fase "Dwarf Star") → `v5.0.0`

📎 **Specsheet:** §9 (Context Builder), §16 (KV cache) · **Decisioni:** D8, D9, D20
🎯 **Scope:** Context Builder per ruolo, strumentazione del riuso, audit e ottimizzazione dei prefissi, slot save/restore, compressione verificata dello stato.

> ### 🔀 F5 PRECEDE F4 (decisione utente, 2026-08-04) — motivazione nel riquadro in testa a F4.
>
> ### ⚠️ F5 È DIVENTATA UNA FASE DI CAPACITÀ, NON DI PRESTAZIONI (2026-08-04)
>
> Due misure indipendenti della ladder convergono qui e cambiano la natura della fase. Erano
> intuizioni, ora sono numeri:
>
> 1. **LAD.8** — il gradino più duro (L7) non muore per passi né per disciplina: muore perché
>    la catena append-only sfonda gli 8192 (8,5 passi di media su 60 disponibili). *La capienza
>    è il muro.*
> 2. **LAD.14** — il ragionamento pieno risolve l'aritmetica **20/20 contro 0/20**
>    (p = 1,45×10⁻¹¹), ma **non ci sta in 8192 insieme al materiale**: sul gradino vero il
>    materiale verrebbe troncato e il guadagno sparisce. *Il contesto è ciò che separa il
>    sistema da una capacità che il modello ha già.*
>
> **Secondo obiettivo di F5, che prima non aveva:** fare spazio **al ragionamento**, non solo al
> materiale. Il budget di contesto non è più una voce di costo, è la risorsa che decide quali
> capacità sono accessibili.
>
> **Il compromesso centrale è MISURABILE, non assumibile:** qualunque compattazione dei
> risultati vecchi compra finestra al prezzo del riuso append-only del prefisso — F0.5,
> **65 token contro 7.971**. Va misurato con la matrice come tutto il resto, non deciso a
> tavolino.
🧭 **Perché questa fase, perché ora:** è il cuore ingegneristico del progetto — l'ispirazione dichiarata a Dwarf Star: lavorare forte sul prefill per ridurne i tempi. Arriva DOPO F4 per una ragione di metodo sperimentale: solo con la pipeline completa ogni ottimizzazione ha un prima/dopo onesto sull'intero set dell'Evaluator. Ottimizzare prima significherebbe ottimizzare un sistema che non esiste ancora. Su CPU il prefill è il costo dominante: qui si decide se Red Giant è *usabile* o solo dimostrativo.

> ### 📋 CHECKLIST DI F5 — ordine di esecuzione e criterio di uscita (2026-08-04)
>
> **Le sottofasi F5.1–F5.6 qui sotto sono state scritte quando F5 era una fase di
> PRESTAZIONI. Restano valide, ma nessuna di esse tocca ciò che uccide L7.** Due sottofasi
> nuove vengono prima, e il criterio di uscita cambia.
>
> **Ordine:** **F5.0-ante** → F5.0 → F5.0-bis → F5.2 → F5.3 → F5.1 → F5.5 → F5.4 → F5.6.
> *(F5.0-ante è stata aggiunta dopo la ricerca sullo stato dell'arte: verifica se il
> compromesso che struttura tutta la fase sia reale o un artefatto della nostra config.)*
> *(F5.2 e F5.3 salgono perché sono la spina dorsale della misura: senza, tutto il resto è
> ottimizzazione a sentimento. F5.4 SlotManager scende: è prestazioni pure, non capacità.)*
>
> **Regola non negoziabile per ogni sottofase:** nasce con la sua **leva di ablazione** e si
> chiude con un A/B a **20 run per braccio minimo**, dichiarando *quale ampiezza d'effetto il
> campione era in grado di vedere* (lezione di LAD.9).

> ### 🌐 STATO DELL'ARTE — cosa hanno già risolto gli altri (ricerca del 2026-08-04)
>
> Fatta **prima** di scrivere codice, su richiesta dell'utente. Cambia due premesse della
> checklist.
>
> **1. ⚠️ `--cache-reuse` ESISTE NEL NOSTRO BINARIO E NON LO USIAMO.** Verificato su
> `bin/llama-b10217/cpu/llama-server.exe --help`:
> ```
> --cache-reuse N   min chunk size to attempt reusing from the cache via KV shifting,
>                   requires prompt caching to be enabled (default: 0)
> ```
> **Il compromesso centrale di F5.0-bis potrebbe essere in parte auto-inflitto.** Il numero
> F0.5 che lo motiva — *65 token riprocessati contro 7.971 cambiando un byte a metà* — è stato
> misurato con `--cache-reuse 0`. Con il KV shifting attivo, togliere roba dal mezzo **non
> invalida necessariamente tutto ciò che segue**. Né `start-llama.ps1` (dev-fast) né
> `docker/severino-sim/compose.yml` lo passano.
> **→ Prima sottofase concreta di F5: rimisurare F0.5 con e senza `--cache-reuse`.** Se il
> divario crolla, la leva 2 (sfratto) smette di essere proibitiva e la fase cambia forma.
> *(Nota: `--context-shift` è pure disattivato, e va lasciato così: scarterebbe i token più
> vecchi, cioè la descrizione del task. Ma la scelta va documentata come deliberata.)*
>
> **2. L'offload su filesystem è lo standard industriale, non un'idea nostra.** I framework
> agentici lo fanno già: risultato di tool oltre soglia → scritto su file, in contesto restano
> **path + anteprima**. Numeri pubblicati: soglia a 20.000 token (LangChain Deep Agents);
> un'altra implementazione riferisce soglia 8.000 caratteri e anteprime da 2 KB, con la
> lunghezza di sessione che passa da **15-20 a 30-40 turni senza compattazione**. Il nostro
> `_RESULT_MAX_CHARS = 6000` è nello stesso ordine di grandezza — ma il nostro problema non è
> *un* risultato enorme, è **l'accumulo** di cinque o sei da 6000. **La leva 3 sale a
> favorita**, non perché sia elegante ma perché è quella con più evidenza esterna.
>
> **3. Compattazione periodica > sfratto incrementale, sul piano della cache.** La letteratura
> è concorde: uno sfratto che modifica il contesto *a ogni richiesta* invalida il prefisso ogni
> volta e non ammortizza mai; una compattazione periodica produce **un solo prefisso nuovo e
> stabile** dopo ogni passata, e il riuso riparte. Se sceglieremo di comprimere, va fatto **a
> ondate**, non continuamente.
>
> **4. "Context rot": la qualità cala PRIMA del limite.** All'aumentare dei token la capacità
> di richiamare informazioni dal contesto degrada, quindi tagliare può **migliorare** la
> qualità, non solo far entrare le cose. Da tenere presente leggendo i risultati: un guadagno
> potrebbe non venire dallo spazio ma dal rumore rimosso.
>
> **5. Previsione da registrare (dalla letteratura, prima di misurare):** la compattazione
> **cambia il comportamento** dell'agente — i modelli emettono **più ricerche** per compensare
> il contesto indebolito, con ripetizione delle query in aumento. Sulla ladder lo vedremmo come
> **più passi per run**. Se compare, non è un bug: è l'effetto atteso, e va misurato invece che
> corretto d'istinto.
>
> **6. Un filone che NON si applica, e va detto per non sprecarci tempo.** Buona parte della
> ricerca 2026 su "KV cache compaction" agisce a livello di **tensori** (evict/approssima
> coppie KV per ridurre la *memoria*), con risultati forti su modelli 4B+ (riduzione KV
> dell'80%, throughput 1,7-4,2×). **Non risolve il nostro problema**, che è il *conteggio di
> token del prompt* contro `ctx_size`: la memoria non è il nostro vincolo, la finestra sì. Da
> non confondere in fase di lettura.
>
> **Fonti:** [Anthropic — context engineering: memory, compaction, tool clearing](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools) ·
> [LangChain — Context Management for Deep Agents](https://www.langchain.com/blog/context-management-for-deepagents) ·
> [Context Offloading — Encyclopedia of Agentic Coding Patterns](https://aipatternbook.com/context-offloading) ·
> [Beyond Compaction: Structured Context Eviction for Long-Horizon Agents](https://arxiv.org/pdf/2606.11213) ·
> [Practical Online KV Cache Compaction for LLM Agents](https://arxiv.org/html/2608.00902) ·
> [Addressable Recall Compaction (ARC)](https://arxiv.org/html/2607.25066v1) ·
> [Agent Context Compaction: Techniques and Tradeoffs](https://zylos.ai/research/2026-04-21-agent-context-compaction-long-running-sessions/) ·
> [llama.cpp discussion #20574 (host-memory prompt caching — ⚠️ contestata nei commenti, usata solo come pista)](https://github.com/ggml-org/llama.cpp/discussions/20574)

#### F5.0-ante — Rimisurare il costo del cambio di prefisso, con `--cache-reuse`

- [ ] 🤖 **Obiettivo:** stabilire se il compromesso che struttura tutta F5 è reale o un artefatto
  della nostra configurazione.
- **Motivazione:** F0.5 ha misurato **65 token contro 7.971** cambiando un byte a metà prompt —
  ma con `--cache-reuse 0`, cioè col KV shifting **spento**. È il numero che rende "proibitiva"
  la compattazione. Va rimisurato con il flag attivo prima di progettare intorno a esso.
- **Implementazione:** riesecuzione della sonda di riuso di `bench/run_bench.py` su
  `severino-sim`, tre configurazioni: `--cache-reuse 0` (attuale), `256` (valore comune),
  `64`. Aggiungere il flag a `scripts/start-llama.ps1` e a `docker/severino-sim/compose.yml`
  **solo dopo** aver visto i numeri.
- **Accettazione:** tabella dei token riprocessati per le tre configurazioni, su un cambio a
  metà prompt e su un troncamento in testa. **Se il divario crolla, F5.0-bis va riscritta** —
  e questo è il motivo per cui questa sottofase viene prima di tutte.

#### F5.0 — 📌 Dove vanno gli 8192 token (strumentazione, PRIMA di ogni ottimizzazione)

- [ ] 🤖 **Obiettivo:** conoscere la composizione **reale** di ogni prompt, sezione per sezione,
  su ogni chiamata — non solo quando esplode.
- **Motivazione misurata:** LAD.8 dice *che* la finestra si riempie, non *di cosa*. L'unica
  scomposizione che abbiamo è quella che il client stampa **nel messaggio d'errore**
  (`per-section: PREAMBLE=314, ROLE=1521, TOOLS=…`): esiste già il calcolo, manca la
  persistenza. Ottimizzare senza questa tabella significa scegliere la leva a caso.
- **Implementazione:** `redgiant/llm/client.py` — la scomposizione per sezione già calcolata
  viene persistita **sempre**, non solo in overflow; nuova colonna `sections` (JSON) su
  `llm_calls` con migrazione idempotente in `StateStore.init_schema`, come si è fatto per
  `thinking_tokens`.
- **Accettazione:** per una run completa di L7, la tabella della composizione media del prompt
  agli step 1 / 5 / 10 e **al punto di sfondamento**. È questa tabella che decide quale leva
  di F5.0-bis vale la pena costruire — nessuna leva si costruisce prima di averla letta.

#### F5.0-bis — La catena volatile del Worker (il vero killer di L7)

- [ ] 🤖 **Obiettivo:** tenere la catena append-only dei risultati dentro un budget dichiarato,
  senza distruggere il riuso della KV.
- **Motivazione misurata (LAD.8):** su 92 tentativi di L7 il Worker usa **8,5 passi di media,
  massimo 18 su 60 disponibili**; nessuno esaurisce i passi. Muoiono perché
  `parts.with_appended_context` accumula risultati fino a sfondare gli 8192 — un singolo
  risultato di ricerca su 400 documenti pesa fino a `_RESULT_MAX_CHARS = 6000` caratteri
  (~1500 token), e cinque o sei saturano la finestra.
  **Nessuna delle sottofasi F5.1–F5.6 esistenti agisce su questa catena:** il ContextBuilder
  lavora sull'*assemblaggio* del prompt, lo StateCompressor su S5 (stato durevole). Questa è
  S6, dentro il loop.
- **Tre leve candidate — si MISURANO, non si scelgono a tavolino:**
  1. **Risultati più stretti**: abbassare `_RESULT_MAX_CHARS` e `max_results` di
     `search_code`. Costo zero sulla KV (il prefisso resta append-only), ma il modello vede
     meno per chiamata.
  2. **Sfratto dei risultati vecchi**: tenere gli ultimi N per intero e sostituire i più
     vecchi con un digest **deterministico** (mai generato dal modello: sarebbe
     un'allucinazione dentro la catena di verità). ⚠️ **Rompe l'append-only** → il prefisso
     cambia a metà → **F0.5: 65 token riprocessati contro 7.971**. È il compromesso centrale
     della fase.
  3. **Scarico su artefatto**: il modello scrive i fatti trovati su un file di appoggio e la
     catena tiene solo il riferimento. Sposta il costo dal contesto al filesystem.
- **Leva di ablazione:** `RG_WORKER_ABLATE=compact`.
- **Accettazione — DUE condizioni, entrambe obbligatorie:**
  (a) **capacità**: L7 migliora con A/B a 20 run per braccio e test esatto allegato;
  (b) **la KV non crolla**: `avg_reuse_ratio` del Worker misurato prima e dopo (F5.2), e se
  scende il baratto va **dichiarato in numeri** — quanto contesto si compra per quanto prefill
  si ripaga. Una leva che vince sui verdi e distrugge il riuso non è accettata senza quel conto.

#### F5.1 — Context Builder

- [ ] 🤖 **Obiettivo:** la selezione del contesto minimo per ruolo (specsheet §9), al posto dell'assemblaggio semplice usato finora.
- **Motivazione:** il contesto minimo è insieme qualità (un E2B ragiona meglio su poco), costo (D8) e sicurezza (meno roba irrilevante = meno superficie di distrazione/injection). La regola d'oro della specsheet: il Worker non deve ricevere la cronologia del Planner, le fasi future, i file non correlati, i log dei test già superati.
- **Implementazione:** `core/context_builder.py`:
  ```python
  class ContextBudgets(BaseModel): s5_max_tokens: int; s6_max_tokens: int; files_max_lines: int
  class ContextBundle(BaseModel):  durable_state: str; volatile: str; sources: list[str]
  class ContextBuilder:
      def __init__(self, store: StateStore, scope: Scope, budgets: ContextBudgets) -> None
      def bundle(self, role: str, state: TaskState, subtask: SubtaskSpec | None) -> ContextBundle
  ```
  Regole di selezione per ruolo (tabella normativa nella docstring del modulo, replicata nell'atlante): Worker → spec sottofase + criteri + contenuto dei file in `inputs` (entro `files_max_lines`) + errori aperti della sottofase + decisioni con `target` pertinente + `[STRATEGY]` se retry; Planner → richiesta + esiti di fase (sintesi, non log); Debugger → spec + FinishReport + Verdict + diff della sottofase; Supervisor → DebugReport + attempts + budget (numeri, non storia). Ordine di riempimento a budget: prima gli item obbligatori, poi i file per rilevanza (citati nella spec prima, poi citati negli errori), troncando al budget con dichiarazione del troncamento. `sources` elenca cosa è entrato: è il log della selezione, per diagnosi ("perché il Worker non sapeva X?" → perché il builder non l'ha incluso, ed ecco la lista).
- **Casi limite:** file di `inputs` inesistente → voce esplicita "input not found" nel bundle (il Worker deve saperlo, non scoprirlo per assenza); budget troppo piccolo perfino per gli obbligatori → `ContextOverflow`-style errore a monte, MAI un bundle silenziosamente amputato degli obbligatori.
- **Accettazione:** unit test delle regole per ruolo (mock dello store); su un task reale, `sources` corrisponde a ciò che il prompt contiene davvero.

#### F5.2 — 📌 Strumentazione del riuso

- [ ] 🤖 **Obiettivo:** rendere misurabile D9: quanto prefisso viene riusato davvero, per ruolo, per task.
- **Motivazione:** senza questa misura F5 sarebbe ottimizzazione a sentimento. `cached_tokens` è già in ogni riga `llm_calls` (F1.2): qui si aggrega e si espone.
- **Implementazione:** `core/cache_probe.py`:
  ```python
  class ReuseStats(BaseModel):
      role: str; calls: int; avg_reuse_ratio: float      # cached/prompt
      cold_prefill_ms: float; effective_prefill_ms: float
  def reuse_stats(store: StateStore, task_id: str | None = None) -> list[ReuseStats]
  ```
  Pannello in `/metrics` (per ruolo, ultima eval e ultimo task); il report Evaluator include `avg_reuse_ratio` complessivo tra le metriche cardine (metrica 4).
- **Accettazione:** i numeri del pannello coincidono con un calcolo manuale su `llm_calls`; il loop del Worker mostra reuse crescente step dopo step (la firma dell'append-only di D20 che funziona).

#### F5.3 — Audit e ottimizzazione dei prefissi

- [ ] 🤖 **Obiettivo:** eliminare ogni violazione residua di D9 e massimizzare il prefisso condiviso tra ruoli.
- **Motivazione:** la teoria (D9) incontra la pratica: basta un separatore incoerente, un ordine di tool diverso, una data sfuggita in S4 per azzerare il riuso. L'audit è byte-level perché la cache è byte-level.
- **Implementazione:** (1) test unitario permanente: per ogni ruolo, due `build` consecutivi → prefisso S1–S4 identico (`assertEqual` sui byte); (2) test cross-ruolo: S1 identico tra tutti i ruoli (il preambolo è unico); (3) strumento di diff: al primo `reuse_ratio` anomalo in eval, dump dei prompt di due chiamate consecutive e diff — la causa va trovata e fissata, non tollerata; (4) valutazione della gerarchia di prefissi: misurare se conviene ordinare le chiamate per ruolo (tutte le verify insieme, ecc.) — probabilmente no con `--parallel 1` e slot singolo (ogni cambio di prompt lungo invalida), la risposta la danno i numeri; (5) 📌 gli esiti nell'atlante.
- **Accettazione:** `reuse_ratio` medio del Worker sopra la soglia F0.6; i test dei prefissi in `tests/unit` e verdi.

#### F5.4 — SlotManager (KV su disco)

- [ ] 🤖 **Obiettivo:** riprendere un task (o forkare una fase) **senza ripagare il prefill**: la KV cache sopravvive al riavvio del server.
- **Motivazione:** specsheet §16 (ripresa, fork, rollback). Su Severino il server si spegne a fine task (D7): senza slot persistente, ogni ripresa ripaga il prefill dell'intero stato. La soglia di convenienza è stata misurata in F0.5.4.
- **Implementazione:** `core/slots.py`:
  ```python
  class SlotManager:
      def __init__(self, base_url: str, slots_dir: Path) -> None
      def save(self, task_id: str, label: str) -> Path       # POST /slots/{id}?action=save
      def restore(self, path: Path) -> bool                  # False se incompatibile: si riparte freddi
      def gc(self, keep_last: int = 3) -> int                # gli slot pesano: pulizia per task
  ```
  Integrazione: `CheckpointManager.checkpoint` salva anche lo slot quando il prefisso corrente supera la soglia di convenienza (F0.6) e registra `slot_file`; la ripresa di un task (F1.7) tenta `restore` del più recente compatibile prima della prima chiamata.
- **Casi limite:** slot salvato con un modello/versione diversi → `restore` fallisce pulito → prefill freddo con avviso nel log (mai un crash per un'ottimizzazione); disco pieno → `save` fallisce non-fatalmente (lo slot è sempre facoltativo).
- **Accettazione:** kill del processo a metà task → ripresa con `restore` riuscito → `llm_calls` della prima chiamata post-ripresa mostra `cached_tokens` ≈ prefisso (il risparmio è visibile nei dati); gc lascia N file.

#### F5.5 — StateCompressor

- [ ] 🤖 **Obiettivo:** per task lunghi, comprimere lo storico in S5 senza perdere la verità.
- **Motivazione:** dopo 15 sottofasi lo stato duraturo cresce oltre `s5_max_tokens`. Il riassunto generato da un E2B però è un rischio di allucinazione: per questo è **verificato contro il DB** prima dell'uso — un riassunto che cita cose non successe è peggio del testo lungo.
- **Implementazione:** `core/compressor.py`:
  ```python
  class CompressedState(BaseModel):
      phase_summaries: list[str]; open_issues: list[str]; key_decisions: list[str]
  class StateCompressor:
      def __init__(self, llm: LlamaClient, store: StateStore, assembler: PromptAssembler) -> None
      def compress(self, state: TaskState) -> CompressedState
      def validate(self, c: CompressedState, state: TaskState) -> list[str]
          # ogni riferimento a fasi/sottofasi/decisioni deve esistere nelle tabelle; ritorna violazioni
  ```
  `compress` è chiamato dal ContextBuilder solo quando S5 sfora il budget; una violazione in `validate` → si scarta il riassunto e si usa la sintesi deterministica (titoli+stati, senza modello) — degradare verso il meccanico, mai verso l'inventato.
- **Accettazione:** unit test di `validate` con violazioni artificiali; su un task lungo simulato, S5 resta nel budget e il contenuto compresso passa la validazione.

#### F5.6 — 🔎 Verifica di fase

⚠️ **CRITERIO DI USCITA RIVISTO (2026-08-04): F5 è una fase di CAPACITÀ.** Il criterio
originale — solo prestazioni — è conservato ma **non basta più da solo**.

**Condizioni di capacità (nuove, bloccanti):**
- [ ] **L7 sale**, con A/B a 20 run per braccio e test esatto: è il gradino che muore per
  capienza, ed è la ragione per cui questa fase è stata anticipata. Baseline da battere:
  **B2 8/20 · B4 12/20** (`data.md` §7.10).
- [ ] **Il ragionamento entra insieme al materiale su L5.** Oggi il pensiero risolve
  l'aritmetica 20/20 solo sul gradino controllato, perché su L5 vero il materiale viene
  troncato a 6.000 token (§7.8). Se dopo F5 il braccio B3 su **L5** passa, il verdetto
  "il thinking non ci sta in 8192" è stato sciolto — ed è il risultato più significativo
  che questa fase possa produrre.
- [ ] **Il confronto B2/B4 su L7 va rifatto** (§7.10.4): è l'unico gradino dove il collo di
  bottiglia non è coperto né dall'impalcatura né dal pensiero. Se F5 lo rimuove, potrebbe
  essere l'unico posto dove i due smettono di essere sostituti — e quella è una scoperta,
  non un dettaglio.

**Condizioni di prestazione (originali, mantenute):**
- [ ] Sull'intero set Evaluator su `severino-sim`, confronto contro il "prima": **riduzione ≥40% del tempo medio di prefill per sottofase** (target fissato in F0.6 coi numeri reali; se va rivisto, la revisione è scritta con la ragione), a parità di completion rate; `reuse_ratio` medio Worker ≥ soglia; ripresa da slot dimostrata; A/B nell'atlante.

**Condizione di onestà:** se una leva compra capacità **pagando** in riuso KV, il baratto va
scritto in numeri (quanto contesto, quanto prefill) e non nascosto dietro il verde.

**Rituale di fine fase** → `v5.0.0`.

---

## Fase 6 — Routing adattivo: Classifier + Assessor → `v5.1.0`

📎 **Specsheet:** §6.1, §6.2, §5 · **Decisioni:** D11, D21
🎯 **Scope:** la pipeline si riduce da sola: segnali deterministici → (solo se ambiguo) Classifier/Assessor → pipeline `direct`/`short`/`full`; budget dinamici; calibrazione misurata.
🧭 **Perché questa fase, perché ora:** "la pipeline deve ridursi automaticamente per i task semplici" (specsheet §25.14) — ma solo ORA esistono sia le pipeline tra cui scegliere sia le metriche per giudicare le scelte. E c'è una ragione di sfiducia sana: i modelli piccoli stimano male la difficoltà, quindi il deterministico fa da prima linea e il modello decide solo i casi che i segnali non separano; la calibrazione si misura dal giorno uno perché un router mal calibrato è peggio di nessun router.

#### F6.1 — Segnali deterministici e scelta

- [ ] 🤖 **Implementazione:** `core/routing.py`:
  ```python
  class RoutingSignals(BaseModel):
      prompt_len: int; mentions_files: bool; target_file_count: int
      has_tests: bool; is_question: bool; domain_hint: str | None
  def deterministic_signals(request: str, target_dir: Path | None) -> RoutingSignals
  def choose_pipeline(sig: RoutingSignals, cls: "ClassifierOutput | None") -> Literal["direct","short","full"]
  ```
  Regole dure (esempi normativi, la lista completa vive nel modulo ed è replicata nell'atlante): domanda secca senza target (`is_question and target_file_count == 0`) → `direct`; richiesta di modifica con test presenti e ≤2 file citati → `short`; target grande (>50 file) o richiesta multi-obiettivo → `full`. Il Classifier è chiamato SOLO se nessuna regola dura scatta.
- **Accettazione:** unit test delle regole; sul set Evaluator, la % di task decisi senza modello è riportata (attesa: maggioranza).

#### F6.2 — Classifier + Assessor (chiamata combinata)

- [ ] 🤖 **Implementazione:** `roles/classifier.py`, `roles/assessor.py` + card (specsheet §23: combinati nell'MVP — una chiamata sola con due oggetti, o una card che produce entrambi: si sceglie in implementazione la variante col prompt più corto, annotando la scelta):
  ```python
  class ClassifierOutput(BaseModel):
      domain: Literal["coding","research_local","research_web","advice"]
      pipeline: Literal["direct","short","full"]
      risk: Literal["low","medium","high"]
  class AssessorOutput(BaseModel):
      difficulty: Literal["trivial","low","medium","high","critical"]
      token_budget: int; retry_budget: int
      verification_level: Literal["none","standard","strict"]
  ```
  Il `token_budget` dell'Assessor è **clampato** dai limiti di config (mai fidarsi di un numero generato: `min(assessor, config)`); `risk=high` forza `verification_level=strict` a prescindere (specsheet §6.2: il rischio decide i controlli, deterministico).
- **Accettazione:** su richieste-campione i due output sono sensati e il clamp funziona (unit test con output finti fuori scala).

#### F6.3 — Pipeline `direct` e `short`

- [ ] 🤖 **Implementazione:** nell'Orchestrator: `direct` = una chiamata (ruolo `worker` in modalità risposta, senza piano; con tool di sola lettura se il dominio li richiede) + verifica leggera (evidenze presenti se ha usato tool); `short` = PhaseDesigner direttamente sulla richiesta (una fase implicita) → sottofasi → loop normale con verifica piena. `tasks.pipeline` registra la scelta; la GUI la mostra.
- **Accettazione:** T015–T017 (v. F6.4) passano da `direct`/`short` con i token attesi (ordini di grandezza sotto `full`).

#### F6.4 — 📌 Calibrazione e task semplici

- [ ] 🤖 **Implementazione:** `routing_log` riempito a ogni task (segnali, output modello se chiamato, pipeline scelta, esito finale); report di calibrazione nell'Evaluator: per ogni pipeline scelta, % di esiti coerenti (un `direct` fallito per complessità = errore di routing; un `full` su task banale = spreco misurato in token). Nuovi task: **T015** domanda secca sulla codebase · **T016** lettura+sintesi di un file singolo · **T017** patch banale a una riga con test. A/B: F5 (tutto full) vs F6 (routing) sull'intero set.
- **Accettazione:** overhead sui task semplici ≤ soglia F0.6 (vicini alla chiamata diretta); nessun task complesso del set instradato su `direct`; report di calibrazione committato.

#### F6.5 — 🔎 Verifica di fase

- [ ] Come F6.4 + regole dure coperte da test + A/B documentato con conclusione (il routing resta se paga, D11).

**Rituale di fine fase** → `v5.1.0`.

---

## Fase 7 — Domini non-coding: ricerca e consigli → `v6.0.0`

📎 **Specsheet:** §5, §22 · **Decisioni:** D16, D17
🎯 **Scope:** ricerca locale, ricerca web e consigli sulla stessa pipeline; la verifica cambia oracolo: **fonti e triangolazione** al posto dei test; Classifier già pronto (F6) instrada.
🧭 **Perché questa fase, perché ora:** è il banco di prova della generalità — Red Giant non è un coding assistant (dichiarazione esplicita dell'utente). Arriva per ultima tra le funzionali perché sostituisce l'oracolo meccanico con la verifica documentale: farlo prima avrebbe significato progettare la verifica difficile senza aver consolidato quella facile. Il principio però non cambia: **nessuna affermazione senza evidenza** — cambia solo la natura dell'evidenza (citazione verificabile invece di exit code).

#### F7.1 — Ricerca locale + verifica citazioni

- [ ] 🤖 **Implementazione:** dominio `research_local`: il Worker usa `search_code`/`read_file`/`list_files` su uno scope documentale (il target del task può essere una cartella di documenti, non solo codice). Output strutturato e oracolo nuovo in `verify.py`:
  ```python
  class Citation(BaseModel):        kind: Literal["file","url"]; ref: str; quote: str = Field(max_length=300)
  class ResearchFinding(BaseModel): claim: str; sources: list[Citation] = Field(min_length=1)
  class ResearchReport(BaseModel):  answer: str; findings: list[ResearchFinding]; not_found: list[str]
  def verify_citations(report: ResearchReport, scope: Scope, fetch_cache: Path) -> Verdict
  ```
  `verify_citations`, per ogni citazione: `kind="file"` → il file esiste nello scope e contiene `quote` (match normalizzato: whitespace collassato, case-insensitive — abbastanza tollerante per le riformattazioni, abbastanza rigido da beccare l'inventato); `kind="url"` → la quote deve stare nella copia in `fetch_cache` (LA copia che il modello ha visto: F7.2 — niente ri-fetch, la pagina può essere cambiata). Un finding con TUTTE le citazioni fallite → check fail; `answer` che afferma cose senza finding → non verificabile meccanicamente in v1: mitigato dalla card ("every claim in answer must map to a finding") e annotato come debito con proposta (estrarre claim dall'answer e matcharli sui findings è un progetto a sé).
- **Motivazione del design:** `not_found` è un campo di prima classe perché "non l'ho trovato" è una risposta *corretta* che va premiata rispetto all'invenzione — è la versione documentale del fallire esplicito (D16, specsheet §25.13).
- **Accettazione:** T018 (fatto verificabile locale) `verified`; una citazione artificialmente falsificata nel repo di test viene respinta.

#### F7.2 — Ricerca web

- [ ] 🤖 **Implementazione:** `tools/web.py` (§A7): `web_search` + `fetch_url` con cache su disco per task. 🧑 **Decisione a inizio sottofase:** SearXNG self-hosted su Severino (coerenza D16: il motore cerca, Gemma pensa; nessun dato a terzi oltre le query) vs API di sola-ricerca esterna (meno ferro da mantenere). Il piano raccomanda SearXNG ma la scelta è dell'utente; l'interfaccia dei tool è identica nei due casi (la decisione è confinata nella config: `[web] search_backend = "searxng" | "..."` + endpoint).
  Triangolazione (regola nel verify + card): un finding fattuale con una sola fonte è marcato `single-source` nel report finale all'utente; la card chiede ≥2 fonti indipendenti (domini diversi) per le affermazioni centrali.
- **Casi limite:** rete giù → i tool falliscono puliti e il task può chiudere `partial` con ciò che ha; pagina enorme → size-cap con troncatura dichiarata; redirect verso schema non-http(s) → rifiutato.
- **Accettazione:** T019 (fatto web) `verified` con ≥2 fonti; il fetch_cache contiene esattamente le copie citate.

#### F7.3 — Consigli (advice)

- [ ] 🤖 **Implementazione:** dominio `advice`: primo step deterministico+card — la scelta **esplicita e loggata** (in `decisions`) tra web-first (freschezza necessaria o rischio alto) e knowledge-only (concetti stabili, rischio basso); knowledge-only → la risposta DICHIARA "based on model knowledge, not verified against sources" (frase nel template di output, non lasciata alla buona volontà del modello); web-first → flusso F7.2 con citazioni. `verify_citations` gira comunque: un advice knowledge-only che cita fonti inventate è respinto.
- **Motivazione:** il valore qui è l'*onestà epistemica meccanizzata*: il sistema sa dirti DA DOVE viene ciò che afferma, o ammette che viene dai pesi.
- **Accettazione:** T021 (consiglio, rubrica): la risposta contiene la dichiarazione di provenienza corretta per il ramo scelto.

#### F7.4 — Task e card per dominio

- [ ] 🤖 **Implementazione:** card del Worker estese per dominio (blocchi condizionali per S2? NO — violerebbe la stabilità del prefisso per ruolo: si creano **card separate** `worker_research.md`, `worker_advice.md`, trattate come ruoli distinti ai fini del prompt, stessa classe Python con card diversa — annotazione esplicita perché è un punto sottile: la stabilità D9 vale *per (ruolo, dominio)*); Evaluator: **T018** fatto locale · **T019** fatto web · **T020** domanda senza risposta trovabile (atteso: `not_found` onesto, `expected_outcome="verified"` con report che lo dice) · **T021** consiglio a rubrica · **T022** trappola-citazione (documento che NON contiene il fatto che sembra contenere: la quote esatta non esiste → il verify deve respingere).
- **Accettazione:** i 5 task come da atteso; 100% citazioni verificate sul set.

#### F7.5 — 🔎 Verifica di fase

- [ ] 100% delle citazioni del benchmark verificate meccanicamente; T020 chiude con `not_found` esplicito e nessuna invenzione; T022 respinta dal verificatore; il routing F6 instrada correttamente i 4 domini del set.

**Rituale di fine fase** → `v6.0.0`.

---

## Fase 8 — Benchmark reale + deploy su Severino → `v7.0.0`

📎 **Specsheet:** §19, §22 · **Decisioni:** D5, D6, D18, D19
🎯 **Scope:** il chatbot Laravel 13 come benchmark reale, i confronti della tesi, il packaging Docker, il deploy su Severino con hardening, il report finale.
🧭 **Perché questa fase, perché ultima:** è la chiusura del cerchio sperimentale: la tesi della specsheet §22 ("la pipeline migliora correttezza, verificabilità, affidabilità, task lunghi, risorse") misurata sul ferro vero (Severino) e su un progetto vero (il chatbot). Tutto ciò che viene prima esiste per rendere questi numeri credibili.

#### F8.1 — Onboarding del benchmark reale

- [ ] 🧑🤖 **Implementazione:** quando il chatbot Laravel 13 esiste su Severino (costruito nell'altro scenario, D18): suite `T100+` di task reali sulla sua codebase — bugfix veri (anche indotti ad arte con commit di sabotaggio documentati), feature piccole, refactoring, domande sulla codebase (`research_local`), ricerca nella documentazione del progetto. Ogni task col formato standard (task.toml + expected_outcome); `success_cmd` = suite test del chatbot (PHPUnit/Pest).
- **Accettazione:** ≥10 task T100+ eseguibili dall'harness contro una copia della codebase reale.

#### F8.2 — 📌 I confronti della tesi

- [ ] 🤖 **Implementazione:** sul set completo (sintetici + T100+), su `severino-sim` E su Severino reale: (1) **E2B nudo** (una chiamata, prompt diretto, nessuna pipeline — il gruppo di controllo assoluto); (2) **E2B + pipeline completa**; (3) **E4B + pipeline** (riferimento D1: quanto del gap col modello grande la pipeline recupera). Stesso commit, stessi task, report a tre colonne sulle 5 metriche + confronto §22.
- **Accettazione:** report committato; le conclusioni (comprese quelle scomode, se ci saranno) scritte senza cosmesi.

#### F8.3 — Packaging e deploy

- [ ] 🤖 **Implementazione:** `docker/deploy/`: immagine Red Giant (python slim + il pacchetto + config), compose per Severino: servizio redgiant + servizio llama-server CPU (stessa release pinnata), resource limits §6.8 della specsheet homelab (4 core, RAM concordata 🧑), rete solo tailnet, volume dati persistente, healthcheck. Ingresso via Caddy: `redgiant.home.varitest.ovh` (🧑 conferma il nome) nel blocco wildcard esistente. Nessuna porta esposta fuori dalla tailnet.
- **Accettazione:** deploy eseguito su Severino; un task di prova completa dalla GUI raggiunta via dominio; lo stack homelab non degrada oltre l'atteso durante il run (osservazione Beszel).

#### F8.4 — Hardening

- [ ] 🤖 **Implementazione:** revisione §19 con test ostili: Scope (path traversal, symlink, junction Windows→non più rilevante su Linux ma il test resta), approvazioni obbligatorie per ogni tool `requires_approval` senza scorciatoie, segreti mai nel contesto (audit: nessun env/credenziale attraversa il ContextBuilder), rete dei tool limitata (whitelist domini per fetch_url in config), log ruotati (size-cap su task.log), rate limit di cortesia sulla GUI (è in tailnet, ma un refresh impazzito non deve saturare il box).
- **Accettazione:** checklist §19 spuntata voce per voce nell'atlante, ciascuna con il test che la dimostra.

#### F8.5 — Report finale

- [ ] 🤖 **Implementazione:** `bench/results/final_report.md`: la tesi, il metodo, i numeri di F8.2, le 5 metriche nella storia del progetto (baseline F1 → F8), i limiti onesti del sistema, il confronto col principio della specsheet §27 ("il modello rimane piccolo; il sistema diventa grande") — confermato, smentito o sfumato dai dati.
- **Accettazione:** il report esiste, è committato, e l'utente lo ha letto.

#### F8.6 — 🔎 Verifica di fase

- [ ] 🧑 L'utente usa Red Giant dalla GUI **su Severino** per un task reale sul chatbot Laravel, end-to-end, con metriche raccolte lì. È il criterio finale del progetto.

**Rituale di fine fase** → `v7.0.0`.

---

## Rischi aperti e mitigazioni

| Rischio | Prob. | Mitigazione (attiva, non speranza) |
|---|---|---|
| Overhead di governance > lavoro utile | alta | D11: A/B obbligatorio per ogni ruolo; token-utili come metrica-gate; pipeline ridotte (F6); ruoli non chiamati quando l'oracolo basta (F4.1/F4.2) |
| Supporto llama.cpp per Gemma 4 E2B acerbo | media | F0.3 prima di ogni riga di pipeline; matrice di fallback esplicita; versioni pinnate |
| E2B troppo debole per output di pianificazione | media | D21 (schemi piccoli, enum, tetti su liste); validazioni deterministiche post-parse con richiamata singola; F8.2 dirà se è limite di modello o di sistema |
| Tuning su GPU nasconde i problemi CPU | alta | D6 cablato nel processo: metriche ufficiali solo CPU-only, verifiche di fase su severino-sim/Severino |
| Prefill comunque troppo lento per l'uso reale | media | D7 (prodotto batch by design) + F5 dedicata + slot persistenti; le aspettative sono job, non chat |
| `severino-sim` troppo ottimista (Zen 4 ≠ Zen 2) | media | dichiarato in F0.4; taratura periodica contro Severino reale; F8.2 gira su entrambi |
| GUI che diventa un progetto a sé | bassa | HTMX senza build; ogni feature nasce da un bisogno di testing dichiarato dall'utente |
| Verifica documentale aggirabile | media | quote-match sulla copia cachata + triangolazione + T022 (trappola) nel benchmark permanente |
| Divergenza piano↔codice | media | `check_reference.py` bloccante nel rituale; regola di direzione (piano prima) |
| Task sintetici "ammorbiditi" per far passare il sistema | bassa | D18: i task si estendono, non si ammorbidiscono; ogni modifica a un task invalida i confronti storici e va dichiarata |

## Cosa NON esiste ancora (per non cercarlo invano)

- **Nessun codice**: fino al completamento di F0.1 il repo contiene solo specsheet, questo piano e l'atlante.
- Il **chatbot Laravel 13** vive in un altro scenario e arriva solo in F8.
- **Final Reviewer** come ruolo separato (specsheet §6.8): assorbito da Supervisor + verifica finale dell'Orchestrator, finché un A/B non dimostri che serve separato (D11 vale anche per i ruoli della specsheet).
- **Multi-modalità, multi-modello simultaneo, parallelismo tra agenti**: esclusi per design (D7), non "mancanti".
- **API JSON pubblica della GUI**: non esiste e non è pianificata (D12).
- **Consegna automatica del lavoro** (merge/PR del branch `rg/task-*`): manuale per scelta (F4.4), da riconsiderare con l'uso.
