# CentrAlign AI — System Architecture & Design Rationale
> **Engineering Deep-Dive into the Autonomous AI Task Worker**  
> *Technical specifications, component interactions, failure recovery semantics, and design defense for CentrAlign AI.*

---

## 1. Architectural Philosophy

The CentrAlign Autonomous AI Task Worker is architected from first principles to satisfy four enterprise invariants:

1. **Execution Grounding:** Actions must perform real state mutations (file I/O, SQL commits, API calls) rather than conversational simulation.
2. **Independent Verification:** The entity confirming success must be distinct from the entity taking the action. "The agent believes it succeeded" is not proof of success.
3. **Deterministic Safety Boundaries:** High-risk financial or operational thresholds must be enforced by deterministic code policies, never left solely to the probabilistic behavior of LLM prompt following.
4. **Resilient Adaptation:** Real enterprise environments are imperfect. Corrupted documents, duplicate requests, and transient network glitches must be handled by structured recovery paths.

---

## 2. Component Architecture

```
+-----------------------------------------------------------------------------------+
|                                  USER INTERFACES                                  |
|            Streamlit Web Dashboard (app/ui)  |  Rich CLI Interface (app/cli)      |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                             AUTONOMOUS WORKER RUNTIME                             |
|                               (app/agent/runtime.py)                              |
|                                                                                   |
|  +--------------------+     +---------------------+     +----------------------+  |
|  |   Dynamic Planner  |     |   Working Memory    |     | Safety Policy Engine |  |
|  | (app/agent/planner)|     |  (app/agent/memory) |     |  (app/agent/safety)  |  |
|  +--------------------+     +---------------------+     +----------------------+  |
|            |                           |                           |              |
|            v                           v                           v              |
|  +--------------------+     +---------------------+     +----------------------+  |
|  |  Recovery Engine   |     |    LLM Provider     |     | Independent Verifier |  |
|  | (app/agent/recovery)     |  (app/llm/providers)|     | (app/agent/verifier) |  |
|  +--------------------+     +---------------------+     +----------------------+  |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                            TOOL REGISTRY & HARNESS                                |
|                             (app/tools/registry.py)                               |
|                                                                                   |
|  - search_company_documents    - read_document          - extract_invoice_data    |
|  - query_accounts_payable      - create_payable_record  - inspect_database_record |
|  - query_vendor_portal         - download_attachment    - fetch_audit_trail       |
|  - record_ledger_disbursement                                                     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                         ENTERPRISE SANDBOX ENVIRONMENT                            |
|                          (app/environment/company_sandbox)                         |
|                                                                                   |
|  +----------------------------+   +-----------------------+   +----------------+  |
|  |  SQLite ERP Database       |   | File Repository       |   | Vendor Portal  |  |
|  |  - invoices_payable        |   | - invoices/*.pdf      |   | - Clearinghouse|  |
|  |  - financial_ledger        |   | - invoices/*.txt      |   |   API records  |  |
|  |  - audit_log               |   | - contracts/*.txt     |   |   & checksums  |  |
|  +----------------------------+   +-----------------------+   +----------------+  |
+-----------------------------------------------------------------------------------+
```

---

## 3. Subsystem Breakdown & Design Rationale

### 3.1 Autonomous Worker Runtime (`app/agent/runtime.py`)
- **Role:** Central orchestrator executing the `Goal -> Understand -> Plan -> Execute -> Observe -> Adapt -> Verify -> Complete` loop.
- **Loop Guards:** Implements strict step-limit bounds (`AGENT_MAX_STEPS`, default 12) to prevent infinite execution loops in ambiguous states.
- **Pause & Resume Protocol:** When a policy trigger requires human approval, the runtime snapshots current memory, traces, and pending parameters, transitioning to `AWAITING_APPROVAL`. The `resume()` method accepts an `ApprovalDecision` and restarts execution without re-running earlier steps.

### 3.2 Model Provider Abstraction (`app/llm/`)
- **Interface:** `BaseLLMProvider` with two contracts: `generate_plan(goal, tools)` and `decide_next_action(goal, plan, tools, memory, traces)`.
- **Implementations:**
  - `DeterministicReActEngine`: High-performance semantic engine that evaluates working memory and recent observations to select next actions, parse latest files, recover corrupted fields, and verify database state. Used for zero-dependency local testing, CI/CD, and fast evaluation.
  - `GeminiProvider`: Live provider for Google's `gemini-1.5-flash` with structured JSON schema mode.
  - `OpenAIProvider`: Live provider for OpenAI's `gpt-4o-mini` with JSON function calling.
- **Factory:** `get_llm_provider()` automatically initializes based on environment variables.

### 3.3 Tool Registry & Execution Harness (`app/tools/registry.py`)
- **Schema Reflection:** Dynamically inspects Python function signatures and type annotations to generate OpenAI/Gemini compatible JSON schemas.
- **Safety Classification:** Each tool definition declares whether the operation is reversible, its risk category (`filesystem`, `database`, `external_api`, `audit`), and approval defaults.
- **Error Isolation:** Tool executions are wrapped in try-catch boundaries with wall-clock millisecond timing, returning structured `ToolResult` models rather than propagating unhandled exceptions into the LLM loop.

### 3.4 Working Memory & Context Manager (`app/agent/memory.py`)
- **Working Memory:** Key-value state capturing discovered entities (e.g. `selected_document`, `invoice_data`, `payable_created`, `verified_in_db`).
- **Entity Cache:** Prevents duplicate disk or database reads by persisting normalized entity structures.
- **Observation History:** Chronological log of step traces (Action, Observation, Decision, Timestamp, Latency) injected into future decision prompts.

### 3.5 Failure Recovery Engine (`app/agent/recovery.py`)
- **Fault Diagnosis:** Classifies tool failures into categories:
  - `DataExtractionIncompleteError`: Local file corrupted or OCR unreadable.
  - `DuplicateRecordError`: Target invoice already committed in ERP.
  - `FileNotFoundError`: Search pattern too narrow.
  - `TransientError`: Temporary lock or network timeout.
- **Recovery Strategies:**
  - *Data Corruption:* Pointers to authoritative external clearinghouse (`query_vendor_portal`).
  - *Duplicate Record:* Idempotency branch to read existing ERP record and verify state.
  - *Bounded Retries:* Exponential backoff capped at `MAX_TOOL_RETRIES` (default 3).

### 3.6 Independent Ground-Truth Verifier (`app/agent/verifier.py`)
- **Out-of-Band Verification:** Connects directly to SQLite `company_erp.db` with isolated database cursors.
- **Multi-Point Invariant Suite:**
  1. Record existence in `invoices_payable`.
  2. Vendor string matching.
  3. Amount float equality ($|actual - expected| < 0.01$).
  4. Due date ISO string equality.
  5. General Ledger balanced postings (when ledger update requested).
  6. Audit log compliance row.
- **Evidence Reporting:** Emits structured `VerificationReport` with individual check statuses (`PASSED`, `FAILED`, `WARNING`) and database row snapshots.

---

## 4. Key Architectural Decisions (Why / Alternative / Rationale)

### Decision 1: SQLite Enterprise Sandbox vs Cloud SaaS Mocking
- **Why this approach?** SQLite is a zero-latency, ACID-compliant relational engine built into Python. It enforces unique constraints, transaction rollbacks, SQL queries, and file persistence.
- **What alternative was considered?** An in-memory Python dictionary or mocking external cloud SaaS APIs (e.g. mock QuickBooks / NetSuite).
- **Why was this approach preferred?** In-memory dicts fake durability and mask concurrency/schema bugs. Remote cloud sandboxes introduce network latency, rate limits, and fragile external dependencies for the evaluator. SQLite provides 100% genuine database execution that runs anywhere in milliseconds.

### Decision 2: Independent Verifier vs Model Self-Assessment
- **Why this approach?** The agent's action loop and the verification engine are strictly decoupled. Verification queries the raw SQLite database directly.
- **What alternative was considered?** Prompting the LLM: *"Did you successfully complete the user's task?"*
- **Why was this approach preferred?** LLM self-evaluation suffers from severe sycophancy and confirmation bias. If an agent hallucinated an entry or swallowed a database write error, asking the same agent will almost always return a false positive. Direct SQL inspection provides mathematical certainty.

### Decision 3: Code-Enforced Safety Policies vs Prompt-Based Safety
- **Why this approach?** Financial thresholds (e.g. invoice > $5,000 requiring approval) are hard-coded in the `SafetyPolicyEngine` before tool execution.
- **What alternative was considered?** Instructing the LLM in the system prompt: *"If an invoice is over $5,000, please ask the user for permission."*
- **Why was this approach preferred?** Probabilistic models can bypass prompt-based guardrails under adversarial prompts, long contexts, or formatting quirks. In enterprise AI, financial authorization must be non-bypassable and deterministic.

### Decision 4: Deterministic Engine with Live LLM Fallback
- **Why this approach?** Built-in deterministic ReAct engine + live Gemini/OpenAI providers.
- **What alternative was considered?** Requiring an active OpenAI/Gemini API key for all test runs.
- **Why was this approach preferred?** When an evaluator or automated CI/CD runs the repository, missing API keys or depleted credits cause immediate failure. A deterministic semantic engine guarantees 100% test passing and instant evaluation out of the box, with live models available via a simple `.env` toggle.

---

## 5. Scaling to 100+ Tools and Multiple Companies

### Tool Retrieval & Routing
In this prototype, all 10 tools fit comfortably in context. At 100+ tools:
1. **Dynamic Tool Retrieval (Tool-RAG):** Cluster tools by functional domain (`accounting`, `hr`, `procurement`, `it_admin`). Use semantic vector search against tool descriptions to retrieve the top 5–8 relevant tools for the current step.
2. **Hierarchical Subagents:** A root Planner delegating to specialized domain workers (e.g. `InvoiceProcessingAgent`, `TaxReconciliationAgent`).

### Multi-Company Tenancy
1. **Isolated Sandbox Namespaces:** Parameterize the environment with `company_id`. File repositories are partitioned into `data/{company_id}/files/` and database rows contain `tenant_id` with Row-Level Security (RLS).
2. **Company Operating Memory:** Store company-specific rules (e.g. *"Acme Corp requires Net 30 terms; payments over $2,500 require VP sign-off"*) in persistent vector databases linked to the tenant context.
