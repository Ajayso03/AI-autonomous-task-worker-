# CentrAlign AI — Video Demonstration Script
> **Live Presentation Walkthrough for CentrAlign Evaluators (Target Duration: ~3.5 Minutes)**

---

## Video Outline & Timings

| Segment | Timing | Key Screen Action | Voiceover / Talking Points |
| :--- | :--- | :--- | :--- |
| **1. Opening** | 0:00 – 0:20 (20s) | Display CentrAlign Web Dashboard header & control panel. | *"Hi everyone. Today I'm demonstrating an autonomous AI task worker built for enterprise operations. Instead of a chatbot that merely tells you what to do, this system accepts natural language goals, plans actions, operates files and internal ERP databases, recovers from corrupted documents, and independently verifies that work was committed."* |
| **2. Task 1: Happy Path** | 0:20 – 1:20 (60s) | Click Preset 1 (Acme Corp). Hit **Deploy Worker**. Expand step traces. | *"Let's give the worker a high-level task: 'Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved.' Notice the user didn't specify where the invoice is or how to check duplicates. The agent understands the goal, generates a 6-step plan, searches the document repository, compares historical drafts to pick the latest invoice (INV-2024-089), extracts $3,450.00 due October 25th, queries the internal ERP to prevent duplicate entries, and commits the payable record."* |
| **3. Independent Verification** | 1:20 – 1:40 (20s) | Switch to **Independent Verification** tab. | *"Crucially, notice how the agent confirms completion. It doesn't ask itself if it succeeded. Our independent verification engine queries the SQLite ERP database directly, checking 5 separate invariants: record persistence, vendor name, exact numerical amount, due date match, and compliance audit logging. All 5 checks passed with ground-truth database evidence."* |
| **4. Task 2: Failure Recovery** | 1:40 – 2:25 (45s) | Click Preset 2 (Initech). Hit **Deploy Worker**. Show Step 2 failure & adaptation. | *"Now let's test real-world messy conditions. In Task 2, we process Initech's invoice. In Step 2, the document extraction tool detects that the local scan is corrupted with blurred text in the due date field. Instead of crashing or halting, the worker's failure recovery engine diagnoses the missing field and adapts. It queries the official external vendor portal clearinghouse API, recovers the authentic due date of 2024-12-01, and completes the entry. The database verification once again confirms 5 out of 5 checks passed."* |
| **5. Task 3: Human Approval** | 2:25 – 3:10 (45s) | Click Preset 3 (Stark Industries). Hit **Deploy Worker**. Show approval banner. Click **Authorize Action**. | *"Next is safety. Autonomous employees cannot execute high-risk actions unchecked. When we process Stark Industries' invoice of $14,200, the safety policy engine flags that it exceeds the $5,000 corporate threshold. The worker halts in AWAITING_APPROVAL status. No record is entered into the database. The manager reviews the risk summary, context, and amount right here in the UI. When I click 'Authorize Action', execution cleanly resumes, records the transaction with managerial sign-off, and independently verifies it."* |
| **6. Live Database & Architecture** | 3:10 – 3:40 (30s) | Switch to **Company ERP Database** tab. Show `invoices_payable` and `audit_log` rows. | *"Finally, switching to the ERP Database tab, you can see all persisted rows in the SQLite subledger and tamper-evident audit logs. The entire codebase is modularly separated into agent runtime, tool registry, recovery engine, and independent verifiers, and passes all 21 automated tests. Thank you!"* |

---

## Demo Preparation Checklist Before Recording

1. Ensure dependencies are installed: `pip install -r requirements.txt`
2. Run database reset: `python -m app.cli seed`
3. Launch Streamlit dashboard: `streamlit run app/ui/streamlit_app.py`
4. Confirm resolution is set to 1920x1080 with clean browser zoom (100%).
5. Have terminal open in split screen or ready for quick CLI demo verification: `pytest`
