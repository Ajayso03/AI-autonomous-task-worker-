"""Rich interactive Command Line Interface for CentrAlign Autonomous AI Worker."""

import sys
import argparse
from typing import Optional

# Ensure UTF-8 output on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from app.config import settings
from app.environment.seed_data import seed_sandbox
from app.environment.company_sandbox import CompanySandbox
from app.agent.runtime import AutonomousWorker
from app.models.task import TaskStatus
from app.models.approval import ApprovalDecision, ApprovalStatus
from app.models.verification import CheckStatus

console = Console(force_terminal=True, legacy_windows=False)


def render_banner():
    banner = Text("CentrAlign AI - Autonomous AI Task Worker", style="bold cyan")
    subtext = Text("Enterprise Operator Runtime | Goal -> Understand -> Plan -> Execute -> Observe -> Adapt -> Verify", style="dim white")
    console.print(Panel(Text.assemble(banner, "\n", subtext), box=box.ROUNDED, border_style="cyan"))


def format_step_trace(trace):
    """Renders a single step trace panel with action, observation, and decision."""
    content = Text()
    content.append(f"THOUGHT: {trace.action.thought}\n", style="italic yellow")
    content.append(f"ACTION:  {trace.action.tool_name}({trace.action.arguments})\n", style="bold green")
    obs_style = "white" if trace.observation.success else "bold red"
    content.append(f"OBSERVE: {trace.observation.summary}\n", style=obs_style)
    content.append(f"DECIDE:  {trace.decision.next_step}", style="cyan")

    panel_title = f"Step {trace.step_number} [{trace.action.tool_name}]"
    border = "green" if trace.observation.success else "red"
    console.print(Panel(content, title=panel_title, border_style=border, box=box.ROUNDED))


def render_verification_report(report):
    """Renders the independent verification results table."""
    if not report:
        console.print("[yellow]No verification report generated.[/yellow]")
        return

    table = Table(title="Independent Ground-Truth Verification", box=box.ROUNDED, border_style="cyan")
    table.add_column("Status", style="bold", width=10)
    table.add_column("Check Name", style="bold cyan")
    table.add_column("Target Entity", style="dim")
    table.add_column("Expected Value", style="white")
    table.add_column("Actual DB Value", style="white")
    table.add_column("Evidence Source", style="dim")

    for c in report.checks:
        status_text = "[bold green]PASS[/bold green]" if c.status == CheckStatus.PASSED else "[bold red]FAIL[/bold red]"
        if c.status == CheckStatus.WARNING:
            status_text = "[bold yellow]WARN[/bold yellow]"
        table.add_row(
            status_text,
            c.check_name,
            c.target_entity,
            str(c.expected_value),
            str(c.actual_value),
            c.evidence_source,
        )

    console.print(table)
    summary_style = "bold green" if report.verified else "bold red"
    console.print(f"[{summary_style}]{report.summary}[/{summary_style}]")


def run_task(task_prompt: str, auto_approve: bool = False):
    """Executes a natural language task and renders live updates."""
    render_banner()
    console.print(f"\n[bold yellow]User Goal:[/bold yellow] [bold white]\"{task_prompt}\"[/bold white]\n")

    worker = AutonomousWorker()

    def approval_callback(req):
        console.print(Panel(
            f"[bold red]POLICY CONTROL TRIGGERED[/bold red]\n"
            f"Action: [bold white]{req.action_name}[/bold white]\n"
            f"Risk Level: [bold yellow]{req.risk_level}[/bold yellow]\n"
            f"Reason: {req.reason}\n"
            f"Context: {req.context_summary}\n"
            f"Threshold: ${req.threshold_value:,.2f} | Value: ${req.actual_value:,.2f}",
            title="Human Approval Required",
            border_style="red",
            box=box.DOUBLE
        ))
        if auto_approve:
            console.print("[green]Auto-approve flag set. Approving transaction...[/green]")
            return True

        if not sys.stdin.isatty():
            console.print("[yellow]Non-interactive terminal; approving for demo.[/yellow]")
            return True

        resp = console.input("[bold yellow]Authorize this transaction? (y/N): [/bold yellow]").strip().lower()
        return resp in ("y", "yes")

    summary = worker.run(
        goal=task_prompt,
        approval_handler=approval_callback,
    )

    console.print(f"[bold cyan]Plan:[/bold cyan] {summary.plan.interpreted_objective if summary.plan else 'N/A'}")
    if summary.plan:
        for s in summary.plan.steps:
            console.print(f"  [dim]{s.index}. {s.description}[/dim]")

    console.print("\n[bold]Execution Trace:[/bold]")
    for trace in summary.traces:
        format_step_trace(trace)

    console.print("\n")
    render_verification_report(summary.verification_report)

    status_color = "bold green" if summary.status == TaskStatus.COMPLETED_VERIFIED else "bold red"
    console.print(Panel(
        f"Status: [{status_color}]{summary.status}[/{status_color}]\n"
        f"Execution Time: [bold white]{summary.execution_time_seconds}s[/bold white]\n"
        f"Total Steps: [bold white]{summary.total_steps}[/bold white]\n"
        f"Summary: {summary.completion_message}",
        title="Execution Summary",
        border_style="cyan",
        box=box.ROUNDED,
    ))


def show_database():
    """Inspects the current ERP database rows."""
    sb = CompanySandbox()
    conn = sb.get_connection()

    table = Table(title="ERP Database: invoices_payable", box=box.ROUNDED)
    table.add_column("ID", justify="right")
    table.add_column("Invoice #", style="cyan")
    table.add_column("Vendor", style="bold")
    table.add_column("Amount", justify="right")
    table.add_column("Due Date")
    table.add_column("Status")
    table.add_column("Approved By")

    for r in sb.fetch_all_invoices():
        table.add_row(
            str(r["id"]),
            r["invoice_number"],
            r["vendor_name"],
            f"${r['amount']:,.2f}",
            r["due_date"],
            r["status"],
            r["approved_by"] or "N/A"
        )
    console.print(table)


def run_demo():
    """Runs a 3-part demo exhibiting all evaluation criteria."""
    render_banner()
    console.print("[bold yellow]Initializing Clean Enterprise Sandbox...[/bold yellow]")
    seed_sandbox()

    console.print("\n" + "="*80)
    console.print("[bold cyan]DEMO 1: Standard Autonomous Invoice Processing (Acme Corp)[/bold cyan]")
    console.print("="*80)
    run_task("Find the latest invoice from Acme Corp, extract the amount and due date, enter it into our internal system, and confirm it was saved.")

    console.print("\n" + "="*80)
    console.print("[bold cyan]DEMO 2: Autonomous Failure Recovery on Corrupted Document (Initech LLC)[/bold cyan]")
    console.print("="*80)
    run_task("Process the invoice for Initech, extract the details, enter it into our internal system, and confirm it was saved.")

    console.print("\n" + "="*80)
    console.print("[bold cyan]DEMO 3: Human-in-the-Loop High-Value Policy Guardrail (Stark Industries)[/bold cyan]")
    console.print("="*80)
    run_task("Find invoice for Stark Industries, extract amount and due date, enter it into our internal system, and confirm it was saved.", auto_approve=True)


def main():
    parser = argparse.ArgumentParser(description="CentrAlign AI Autonomous Task Worker CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_p = subparsers.add_parser("run", help="Execute an autonomous task")
    run_p.add_argument("--task", type=str, required=True, help="Natural language goal")
    run_p.add_argument("--auto-approve", action="store_true", help="Auto-approve policy triggers")

    # Demo command
    subparsers.add_parser("demo", help="Run full 3-phase demonstration")

    # Seed command
    subparsers.add_parser("seed", help="Reset and seed enterprise sandbox")

    # Inspect command
    subparsers.add_parser("inspect-db", help="Inspect company ERP database tables")

    args = parser.parse_args()

    if args.command == "run":
        run_task(args.task, auto_approve=args.auto_approve)
    elif args.command == "demo":
        run_demo()
    elif args.command == "seed":
        seed_sandbox()
        console.print("[bold green]Successfully re-seeded enterprise sandbox.[/bold green]")
    elif args.command == "inspect-db":
        show_database()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
