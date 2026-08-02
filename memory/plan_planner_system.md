# plan_planner_system.md — il Planner come autore, i Gate come giudici

> **SEED (v0)** — 2026-08-02. Venti righe di criteri fondanti, da estendere e rendere
> ossessivi (firme vere, percorsi, prompt, DDL) nella prossima sessione. Sistema a sé
> stante: NON è una fase del piano generale (`plan_red_giant.md`), che resta in pausa
> (F3 aperta, Planner default OFF da verdetto D11: 2/10 vs baseline 9/10).

**Obiettivo.** Il motore riproduce la working pipeline dell'utente — `plan_*.md` →
implementazione → gate di fine fase → `codebase_reference.md` — con **gate più pesanti
e contesti più piccoli**: nell'umano la qualità vive nel plan e i gate sono leggeri;
con un 2B il plan è il pezzo debole, quindi la qualità deve vivere nei gate.

**Criteri fondanti:**

1. **Il Planner è un autore, non un collega.** Scrive il piano UNA volta e esce di
   scena. Nessuna partecipazione al loop di esecuzione.
2. **Plan-as-artifact.** Il Planner emette JSON vincolato (grammatica + validazione +
   `normalize_plan`, invariati); un **renderer deterministico** lo trasforma in un
   file greppabile (intestazioni fisse, ID stabili `P1…`, criteri checkbox). Il DB
   resta fonte di verità; il file è la vista ricercabile dal modello piccolo.
3. **I ruoli consultano, non ricevono.** In contesto solo goal + fase corrente; il
   resto si cerca nel file coi tool (`read_file`/`search_code`). Contesto ≠ memoria:
   la memoria sta negli artefatti (stessa fisica di D18: pagare una volta).
4. **Gate deterministici prima, modello poi.** Zero token dove possibile:
   - **gate d'ingresso fase**: criteri già soddisfatti → fase chiusa senza LLM;
   - **gate di retry**: un retry DEVE differire (stessa spec + stesso fallimento =
     vietato riprovare fotocopia; si riparte solo con istruzioni emendate);
   - **gate di replan**: piano nuovo ≡ piano fallito → stop onesto, niente giri.
5. **Il ledger di task** (mini-`codebase_reference`): a ogni gate il SISTEMA — mai il
   modello — rigenera da DB e log dei tool l'atlante del task (cosa esiste, cosa è
   verificato, cosa si è scoperto). I ruoli a valle consultano, non ri-esplorano.
6. **Il modello entra solo nella diagnosi residua** (Supervisor, enum chiuso di
   decisioni), e solo a valle di un fallimento: è l'unico pezzo di gate che costa.
7. **Replanning = nuova versione del documento.** Evento eccezionale, versionato,
   diffato contro la versione fallita. Mai un dialogo in-loop.
8. **Ancoraggio al contratto.** Il plan debole riceve le "firme vere" (estratti
   verbatim dei test, identificatori esistenti) come l'utente le mette nei suoi plan.
9. **Tutto si guadagna il posto (D11).** Ogni pezzo del sistema viene A/B-ato contro
   il baseline senza pianificazione (9/10 · 710K token sulla batteria). Se non paga,
   resta spento — e se non funziona lo stesso, abbiamo imparato qualcosa di nuovo.
10. **Metrica guida:** token utili / token totali, con i gate quasi gratis per
    costruzione (l'esatto opposto del 10× misurato sul Planner in-loop).
