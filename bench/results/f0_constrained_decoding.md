# F0.3 — Constrained decoding su Gemma 4 E2B (QAT UD-Q4_K_XL)

Data: 2026-08-01T12:50:01+00:00 · endpoint: `http://127.0.0.1:8080` · n per schema: 20 · temperature 0.2, seed variabile

Server: `"b10217-ddd4ec142"`

| Schema | JSON validi | Schema validi (Pydantic) | contenuto pieno (no placeholder) | troncati | gen tok/s con grammatica | gen tok/s senza | costo grammatica |
|---|---|---|---|---|---|---|---|
| ProbeDecision | 20/20 | 20/20 | 20/20 | 0 | 34.0 | 37.7 | +9.8% |

<details><summary>campioni ProbeDecision</summary>

- `[ProbeDecision run 0] deg=0 {"decision": "repair", "reason": "The regression test failure points to a specific calculation logic error (rounding). I will immediately inspect the new TaxCalculator implementation to correct the rounding mechanism to ensure total/t"}`
- `[ProbeDecision run 1] deg=0 {"decision": "repair", "reason": "The regression test failure points to a specific calculation logic error (rounding). I will immediately inspect the TaxCalculator class and the InvoiceController integration to fix the rounding issue,"}`

</details>

| ProbePlan | 20/20 | 20/20 | 20/20 | 0 | 34.4 | 34.6 | +0.4% |

<details><summary>campioni ProbePlan</summary>

- `[ProbePlan run 0] deg=0 {"goal": "Extract tax computation logic from InvoiceController into a dedicated TaxCalculator class while maintaining the existing public API and ensuring the existing PHPUnit tests remain green.", "success_criteria": ["Tax computation logic is successfully moved to a new TaxCalculator class.", "The InvoiceController's public API remains unchanged.", "All existing PHPUnit tests pass without modifi`
- `[ProbePlan run 1] deg=0 {"goal": "Extract tax computation logic from InvoiceController into a dedicated TaxCalculator class while maintaining the existing public API and ensuring all existing PHPUnit tests pass.", "success_criteria": ["Tax computation logic is successfully moved to TaxCalculator class.", "The public API of InvoiceController remains unchanged.", "All existing PHPUnit tests for InvoiceController and relate`

</details>

| ProbeSubtasks | 20/20 | 20/20 | 20/20 | 0 | 34.4 | 34.9 | +1.3% |

<details><summary>campioni ProbeSubtasks</summary>

- `[ProbeSubtasks run 0] deg=0 {"phase_id": "P3", "subtasks": [{"id": "P3-1", "title": "Analyze existing tax logic and define TaxCalculator interface", "objective": "Analyze the current tax computation logic within InvoiceController to identify all tax-related methods and define a clean, decoupled TaxCalculator interface that adheres to the existing public API contract.", "inputs": ["InvoiceController source code", "Existing ta`
- `[ProbeSubtasks run 1] deg=0 {"phase_id": "P3", "subtasks": [{"id": "P3.1", "title": "Analyze existing tax logic and define TaxCalculator interface", "objective": "Analyze the current tax computation logic within InvoiceController to identify all tax-related calculations, and define a clean, decoupled TaxCalculator interface that adheres to the existing public API contract.", "inputs": ["InvoiceController.php", "TaxComputatio`

</details>


**Esito: 100% valido — D3 confermata su questo stack**
