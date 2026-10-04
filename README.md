# AI-autonomous-task-worker-
> **Enterprise Autonomous Operator for Repetitive Business Workflows**  
> *Understands goals, plans actions, operates tools, adapts to failures, verifies ground-truth outcomes, and involves humans only when necessary.*

---

## Table of Contents
- [1. Executive Summary](#1-executive-summary)
- [2. Problem Statement](#2-problem-statement)
- [3. Architecture Overview](#3-architecture-overview)
- [4. Core Cognitive Loop](#4-core-cognitive-loop)
- [5. Key Engineering Capabilities](#5-key-engineering-capabilities)
  - [Autonomy & Execution](#a-autonomy--execution)
  - [Failure Recovery & Adaptation](#b-failure-recovery--adaptation)
  - [Human-in-the-Loop Policy Controls](#c-human-in-the-loop-policy-controls)
  - [Independent Ground-Truth Verification](#d-independent-ground-truth-verification)
- [6. Architecture Decisions & Trade-Offs](#6-architecture-decisions--trade-offs)
- [7. Quickstart & Setup](#7-quickstart--setup)
- [8. Running the Worker](#8-running-the-worker)
  - [Interactive Web UI](#interactive-executive-web-ui)
  - [Rich CLI](#rich-command-line-interface)
  - [Automated Demo Mode](#automated-demo-mode)
- [9. Copy-Paste Demo Tasks](#9-copy-paste-demo-tasks)
- [10. Test Suite](#10-test-suite)
- [11. Known Limitations & Roadmap](#11-known-limitations--roadmap)
- [12. Technology Stack & AI Disclosure](#12-technology-stack--ai-disclosure)

---

## 1. Executive Summary

This repository is a production-grade prototype of an **Autonomous AI Task Worker** built for the CentrAlign AI **AI Engineering Intern / Founding Engineer** assignment. 

Rather than building a conversational chatbot that only explains what *should* be done, or a brittle hard-coded script that simulates autonomy, this system implements a genuine **autonomous agent loop** that operates across enterprise documents, file systems, internal company ERP databases, and external clearinghouse APIs.

### Key Highlights
- **100% Real Execution:** Operates on real PDF/text invoices, executes atomic SQLite transactions in internal ERP tables (`invoices_payable`, `financial_ledger`, `audit_log`), and queries external vendor APIs.
- **Dynamic ReAct Reasoning:** Accepts vague natural language requests (e.g., *"Find the latest invoice from Acme Corp and enter it into our internal system"*), infers all intermediate steps, selects the latest file among archives, extracts fields, prevents duplicates, and commits records.
- **Autonomous Anomaly Recovery:** Dynamically detects corrupted OCR scans or missing invoice attributes, catches the error, pivots to query external clearinghouse APIs, and completes the transaction without crashing.
- **Human-in-the-Loop Safety:** Evaluates financial control policies (e.g. invoice > $5,000 threshold); halts high-value actions for managerial review; supports clean pause and resumption.
- **Independent Verification:** Verifies the destination database state directly using out-of-band queries, comparing expected attributes against durable persisted rows.
- **Zero-Dependency Reproducibility:** Features a built-in semantic deterministic reasoning engine that allows the evaluator to run the full CLI, Web UI, and 21 unit tests immediately without needing API keys, while also supporting live Google Gemini and OpenAI frontier models via `.env`.

---

## 2. Problem Statement

Enterprises are burdened by repetitive operational workflows spread across local files, desktop apps, portals, and ERP systems. A human operator typically must:
1. Locate documents across shared drives.
2. Discern between historical drafts and the latest version.
3. Extract billing numbers, tax identifiers, dates, and amounts.
4. Manually resolve unreadable or damaged fields via vendor portals.
5. Check internal systems for duplicates.
6. Check corporate approval thresholds before entering payments.
7. Double-check that records were committed correctly.

CentrAlign's mission is to replace this manual friction with autonomous AI workers that can execute and independently verify these workflows end-to-end.

---

## 3. Architecture Overview

```
                      +-----------------------------------+
                      |       Natural Language Goal       |
                      +-----------------+-----------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      |    Dynamic Planner / ReAct LLM    |
                      |   (Gemini / OpenAI / Deterministic)|
                      +-----------------+-----------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      |         Working Memory            |
                      | (Entities, History, Step Counter) |
                      +-----------------+-----------------+
                                        |
                 +----------------------+----------------------+
                 |                                             |
                 v                                             v
+----------------+----------------+          +-----------------+---------------+
|      Safety Policy Engine       |          |         Tool Registry           |
| (Thresholds, Risk Levels, HITL) |          | (Schemas, Isolation, Execution) |
+----------------+----------------+          +-----------------+---------------+
                 |                                             |
                 v                                             v
     [Managerial Approval]                   +-----------------+---------------+
                 |                           |        Sandbox Environment      |
                 +-------------------------->| - Document Repo (PDF/TXT/JSON)  |
                                             | - Company ERP (SQLite DB)       |
                                             | - External Clearinghouse API    |
                                             +-----------------+---------------+
                                                               |
                                        +----------------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      |          Observation              |
                      +-----------------+-----------------+
                                        |
                     +------------------+------------------+
                     | Success                             | Failure
                     v                                     v
       +-------------+-------------+         +-------------+-------------+
       |   State & Memory Update   |         |      Recovery Engine      |
       +-------------+-------------+         | (Portal Fallback, Retries)|
                     |                       +-------------+-------------+
                     |                                     |
                     +------------------+------------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      |   Independent Outcome Verifier    |
                      | (Ground-truth DB checks & evidence)
                      +-----------------+-----------------+
                                        |
                                        v
                      +-----------------+-----------------+
                      | Verified Final Completion Report  |
                      +-----------------------------------+
```

---

## 4. Core Cognitive Loop

The worker strictly follows the CentrAlign loop:

$$\text{Goal} \longrightarrow \text{Understand} \longrightarrow \text{Plan} \longrightarrow \text{Execute} \longrightarrow \text{Observe} \longrightarrow \text{Adapt} \longrightarrow \text{Verify} \longrightarrow \text{Complete}$$

1. **Understand:** Inters the business intent and target entity (e.g. Acme Corp invoice processing).
2. **Plan:** Generates an initial multi-step execution plan with milestones.
3. **Execute:** Calls structured tools with schema-validated parameters.
4. **Observe:** Receives structured output, raw payloads, error tags, and latency.
5. **Adapt:** If an action fails (e.g. corrupted OCR due date), the recovery engine triggers alternative strategies (e.g. clearinghouse portal query) without aborting.
6. **Verify:** Directly inspects the destination SQLite database table, verifying record existence, field equality, numerical tolerance, and audit logging.
7. **Complete:** Returns a structured summary with verifiable cryptographic and transactional evidence.

---

## 5. Key Engineering Capabilities

### A. Autonomy & Execution
The user does not specify low-level instructions. Given:
> *"Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."*

The agent autonomously:
1. Searches `data/company_files/invoices/`.
2. Compares `INV-2024-001_AcmeCorp_Jan.txt` vs `INV-2024-089_AcmeCorp_Latest.pdf`.
3. Selects `INV-2024-089` based on filename versioning and modification timestamp.
4. Extracts `$3,450.00`, due date `2024-10-25`, and vendor `Acme Corp`.
5. Queries `invoices_payable` to ensure no duplicate exists.
6. Inserts the record into the SQLite ERP database.
7. Queries the database directly to confirm persistence.

### B. Failure Recovery & Adaptation
In reality, scans are blurry, networks flake, and data is corrupted.
- When processing `INV-2024-301_Initech_CorruptScan.txt`, the due date field contains `[SCAN_BLUR_CORRUPTED_VALUE - REQUERY_PORTAL]`.
- The tool returns `DataExtractionIncompleteError`.
- The recovery engine diagnoses the missing attribute and invokes `query_vendor_portal(invoice_number='INV-2024-301')`.
- The official due date `2024-12-01` is recovered and merged into working memory.
- The task completes with 100% verified accuracy.

### C. Human-in-the-Loop Policy Controls
Autonomous workers must operate within company risk boundaries.
- When an invoice exceeds the `$5,000.00` organizational policy threshold (e.g. Stark Industries at `$14,200.00`), the safety engine flags a `HIGH` risk action.
- Execution safely pauses in `AWAITING_APPROVAL` status.
- In the Web UI, an approval card prompts the manager with risk justification, context, and amount comparisons.
- When authorized, the worker resumes, injects `approved_by='Corporate_Manager'`, enters the record, and completes independent verification.

### D. Independent Ground-Truth Verification
Never trust that "the tool call didn't crash, therefore the task succeeded."
The verification engine executes out-of-band checks against the SQLite database:
1. **Record Persistence:** Confirms row ID exists in `invoices_payable`.
2. **Vendor Name Match:** Confirms stored string matches expected entity.
3. **Amount Numerical Tolerance:** Evaluates $|actual - expected| < 0.01$.
4. **Due Date Accuracy:** Confirms exact ISO date match.
5. **General Ledger Balance:** Verifies balanced debits and credits in `financial_ledger`.
6. **Audit Trail Compliance:** Verifies tamper-evident record in `audit_log`.

---

## 6. Architecture Decisions & Trade-Offs

| Decision | Why Chosen | Alternative Considered | Trade-Off Rationale |
| :--- | :--- | :--- | :--- |
| **Controlled Sandbox ERP (SQLite)** | Provides authentic database transactions, foreign keys, SQL integrity constraints, and query verification without external cloud costs. | Full cloud ERP (SAP/NetSuite) or Mock dictionary. | Real SQLite provides true durable persistence while remaining 100% locally runnable and testable in under 5 seconds. |
| **Deterministic Engine + Live LLM Bridge** | Guarantees instant evaluator reproducibility without requiring API keys, while fully supporting live Gemini and OpenAI models. | LLM-only dependency. | Evaluators and CI/CD pipelines often test offline or lack immediate API credits; providing both ensures zero friction. |
| **Independent Verifier Module** | Decouples verification from tool execution to prevent hallucinated completion. | Asking the LLM if it completed the task. | Self-evaluation by the acting model is prone to confirmation bias; direct database inspection is deterministic truth. |
| **Explicit Risk Policy Engine** | Hard guardrails in code rather than relying solely on LLM prompt obedience. | System prompt instruction "please ask before high amounts". | Enterprise security requires non-bypassable policy guardrails outside the model's token prediction path. |

---

## 7. Quickstart & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.12)
- Git

### Installation
```bash
# 1. Clone or navigate to the repository
cd "ai task project"

# 2. (Optional) Create virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Configuration
The application comes pre-configured to run out of the box in `deterministic` mode. To enable live frontier models, configure `.env`:
```env
# Choose provider: deterministic | gemini | openai
LLM_PROVIDER=deterministic

# Optional: Add keys to enable live models
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

---

## 8. Running the Worker

### Interactive Executive Web UI
Launch the visual dashboard:
```bash
streamlit run app/ui/streamlit_app.py
```
*Opens in browser at `http://localhost:8501`. Includes one-click task presets, live execution traces, human approval modal, and live ERP database viewer.*

### Rich Command Line Interface
Execute any task directly from terminal:
```bash
python -m app.cli run --task "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."
```

### Automated Demo Mode
Run the complete 3-phase demonstration (Happy Path, Failure Recovery, Human Approval):
```bash
python -m app.cli demo
```

### Inspect Database State
View the current enterprise database records:
```bash
python -m app.cli inspect-db
```

### Re-seed Clean Sandbox
Reset all databases and file repositories to pristine state:
```bash
python -m app.cli seed
```

---

## 9. Copy-Paste Demo Tasks

### Task 1: Standard Autonomous Processing (Acme Corp)
```bash
python -m app.cli run --task "Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved."
```
*Expected Result:* Selects latest invoice `INV-2024-089.pdf`, extracts `$3,450.00` due `2024-10-25`, commits payable row, verifies 5/5 database checks.

### Task 2: Failure Recovery on Corrupted Document (Initech LLC)
```bash
python -m app.cli run --task "Process the invoice for Initech, extract the details, enter it into our internal system, and confirm it was saved."
```
*Expected Result:* Detects corrupted due date in `INV-2024-301_Initech_CorruptScan.txt`, catches error, queries vendor portal API to recover `2024-12-01`, commits, verifies 5/5 database checks.

### Task 3: High-Value Financial Policy Approval (Stark Industries)
```bash
python -m app.cli run --task "Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved." --auto-approve
```
*Expected Result:* Detects `$14,200.00` exceeds `$5,000.00` policy limit, triggers human approval requirement, processes authorization, verifies record.

### Task 4: General Ledger Disbursement Reconciliation (Cyberdyne Systems)
```bash
python -m app.cli run --task "Process payment reconciliation for Cyberdyne Systems contract, record disbursement into the financial ledger, and verify the updated balance."
```
*Expected Result:* Enters payable record, posts balanced double-entry transaction to `financial_ledger`, verifies 6/6 checks including General Ledger posting.

---

## 10. Test Suite

The test suite covers happy paths, recovery, policy guardrails, loop prevention, and tool validation.

```bash
pytest
```

**Test Coverage Highlights (21 Passed Tests):**
- `test_happy_path_acme_invoice_processing`: End-to-end autonomous flow.
- `test_autonomy_infers_steps_without_explicit_commands`: Inferred sub-steps.
- `test_recovery_from_corrupted_due_date`: Authoritative portal recovery.
- `test_recovery_from_duplicate_entry`: Idempotency handling.
- `test_high_value_transaction_triggers_approval`: Policy trigger > $5k.
- `test_approval_resumption_workflow`: State resumption post-approval.
- `test_rejection_halts_execution_without_database_write`: Clean abort on rejection.
- `test_independent_verification_detects_amount_tampering_or_discrepancy`: Catching data corruption.
- `test_task_variation_cyberdyne_general_ledger`: Multi-system accounting generalization.
- `test_max_step_guardrail_prevents_infinite_loop`: Loop prevention boundaries.

---

## 11. Known Limitations & Roadmap

### Current Limitations
1. **Simulated Browser/Desktop UI:** The prototype operates through real file system parsers and database drivers rather than mouse/keyboard screen-pixel clicks. While permitted by the assignment, production systems require Playwright or OS-level accessibility trees for non-API applications.
2. **Synchronous Execution Loop:** The current orchestrator executes steps in a serial loop. Production enterprise tasks often benefit from parallel subagent delegation (e.g. parallel vendor batch queries).
3. **Single Tenant Sandbox:** The local SQLite database models one enterprise environment.

### Roadmap for Production
- **Playwright & Computer-Use Integration:** Add DOM accessibility tree navigation and vision-based GUI interaction for legacy desktop applications.
- **Persistent Vector Memory:** Index historical invoices and company standard operating procedures (SOPs) into pgvector / Chroma for semantic guideline retrieval.
- **Distributed Task Queue:** Transition execution engine to Celery / Temporal for durable state persistence across machine reboots.
- **Enterprise RBAC:** Integrate SSO and role-based access control for managerial approvals.

---

## 12. Technology Stack & AI Disclosure

- **Language:** Python 3.12
- **Data Validation:** Pydantic v2
- **Durable Storage:** SQLite 3 (WAL mode)
- **Document Processing:** PyPDF, ReportLab
- **CLI Framework:** Rich
- **Web UI:** Streamlit
- **Test Framework:** Pytest
- **Supported LLM Providers:** Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), and Deterministic ReAct Semantic Engine

### AI-Assisted Development Disclosure
In accordance with CentrAlign's submission guidelines, AI coding assistants (including Antigravity IDE and LLM models) were used during development. All architectural decisions, state models, failure recovery flows, verification checks, and tests were designed from first principles and verified for correctness.

