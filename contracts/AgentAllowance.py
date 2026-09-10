# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""
AgentAllowance — Zero-Trust AI Agent Invoice & Spend Controller
=============================================================
An Intelligent Contract on GenLayer that serves as an autonomous spending
allowance controller for AI agents, auditing natural-language invoices and
authorizing capped treasury disbursements via decentralized AI consensus.

Key Architectural Invariants:
1. Multi-Agent Policy Isolation: Enforces monthly spending ceilings and per-transaction caps per agent.
2. Semantic Invoice Audit: AI validators verify invoice legitimacy, vendor domain, and service deliverable.
3. Unified Single-Round Consensus: Clock freshness and invoice inspection execute in 1 parallel round.
4. 100% Fail-Closed Safety: Any discrepancy or inaccessible invoice halts payment execution.
5. Evidence-Bound Replay Protection: Keyed to consensus-extracted canonical invoice identifier in the DOM (vendor:canonical_id).
"""

import json
import re
import hashlib
from dataclasses import dataclass
from genlayer import *


@allow_storage
@dataclass
class AgentSpendPolicy:
    agent_id: str
    agent_name: str
    owner_address: str
    monthly_budget_usdc: u256
    spent_this_month_usdc: u256
    per_tx_cap_usdc: u256
    allowed_categories: str  # "COMPUTE,LLM_INFERENCE,STORAGE,APIS"
    current_billing_month: str # "YYYY-MM" (e.g. "2026-08")
    is_active: bool


@allow_storage
@dataclass
class InvoiceSpendRecord:
    invoice_id: str
    agent_id: str
    vendor_name: str
    canonical_invoice_id: str
    claimed_amount_usdc: u256
    verified_amount_usdc: u256
    expense_category: str
    security_verdict: str  # "APPROVED_DISBURSEMENT" | "BLOCKED_UNAUTHORIZED_DRAIN" | "FLAGGED_PARTIAL_REVIEW"
    status: str            # "SETTLEMENT_READY" | "REJECTED_FROZEN" | "PENDING"
    audit_date: str
    invoice_url: str
    audit_summary: str


class AgentAllowance(gl.Contract):
    operator: str
    agent_policies: TreeMap[str, AgentSpendPolicy]
    invoices: TreeMap[str, InvoiceSpendRecord]
    processed_invoices: TreeMap[str, bool]
    total_invoices_audited: u256
    total_disbursed_usdc: u256

    def __init__(self, operator: str):
        self.operator = operator.strip().strip('"').strip("'").lower()
        self.total_invoices_audited = u256(0)
        self.total_disbursed_usdc = u256(0)

        # Register Genesis Default AI Agent Policy (Agent 001) with Initial Billing Month (2026-08)
        self.agent_policies["AGENT_RESEARCH_01"] = AgentSpendPolicy(
            agent_id="AGENT_RESEARCH_01",
            agent_name="Autonomous Research & Data Agent",
            owner_address=self.operator,
            monthly_budget_usdc=u256(5000),      # $5,000 / month
            spent_this_month_usdc=u256(0),
            per_tx_cap_usdc=u256(1000),          # $1,000 max single payment
            allowed_categories="COMPUTE,LLM_INFERENCE,STORAGE,APIS",
            current_billing_month="2026-08",
            is_active=True
        )

    @gl.public.write
    def register_agent_policy(
        self,
        agent_id: str,
        agent_name: str,
        monthly_budget_usdc: int,
        per_tx_cap_usdc: int,
        allowed_categories: str
    ) -> str:
        """Allows contract owner to provision a new isolated agent spending mandate."""
        sender = str(gl.message.sender_address).lower()
        assert sender == self.operator, "[ERR_AUTH_01] Only contract operator can provision agent policies."

        a_id = agent_id.strip()
        assert a_id not in self.agent_policies, "[ERR_DUP_01] Agent policy already registered."
        assert monthly_budget_usdc > 0 and per_tx_cap_usdc > 0, "[ERR_PARAM_01] Budgets must be positive."

        self.agent_policies[a_id] = AgentSpendPolicy(
            agent_id=a_id,
            agent_name=agent_name.strip(),
            owner_address=sender,
            monthly_budget_usdc=u256(monthly_budget_usdc),
            spent_this_month_usdc=u256(0),
            per_tx_cap_usdc=u256(per_tx_cap_usdc),
            allowed_categories=allowed_categories.strip(),
            current_billing_month="2026-08",
            is_active=True
        )
        return f"Policy provisioned for {a_id} (Budget: ${monthly_budget_usdc} USDC)"

    @gl.public.write
    def audit_agent_invoice(
        self,
        invoice_id: str,
        agent_id: str,
        vendor_name: str,
        claimed_amount_usdc: int,
        invoice_url: str
    ) -> str:
        """
        Audits an AI agent purchase invoice via decentralized AI consensus.
        Enforces caller authorization, invoice replay protection, consensus-bound verified amounts,
        and automatic monthly reset lifecycles.
        """
        inv_id = invoice_id.strip()
        a_id = agent_id.strip()
        v_name = vendor_name.strip()
        clean_url = invoice_url.strip().strip('"').strip("'")

        # INVARIANT 1: INVOICE REPLAY PROTECTION
        assert inv_id not in self.processed_invoices and inv_id not in self.invoices, \
            f"[ERR_INVOICE_REPLAY] Invoice '{inv_id}' has already been audited and processed."

        # INVARIANT 2: CALLER AUTHORIZATION
        assert a_id in self.agent_policies, "[ERR_AGENT_01] Agent ID not registered in policy registry."
        policy = self.agent_policies[a_id]
        assert policy.is_active == True, "[ERR_AGENT_02] Agent policy is currently paused or inactive."

        sender = str(gl.message.sender_address).lower()
        assert sender == policy.owner_address.lower() or sender == self.operator, \
            f"[ERR_AUTH_02] Caller '{sender}' is not authorized to submit invoices for agent '{a_id}'."

        assert clean_url.startswith("http://") or clean_url.startswith("https://"), \
            "[ERR_URL_01] Valid HTTP/HTTPS invoice URL required."

        # Extract policy limits
        m_budget = int(policy.monthly_budget_usdc)
        m_spent = int(policy.spent_this_month_usdc)
        tx_cap = int(policy.per_tx_cap_usdc)
        categories = str(policy.allowed_categories)
        last_billing_month = str(policy.current_billing_month)

        time_url = "https://timeapi.io/api/time/current/zone?timeZone=UTC"

        # UNIFIED NON-DETERMINISTIC INGESTION (Clock + Invoice DOM in 1 Consensus Pass)
        def get_unified_input() -> str:
            try:
                time_resp = gl.nondet.web.render(time_url, mode="text")
            except Exception as e:
                time_resp = f"TIME_FETCH_ERROR: {str(e)}"

            try:
                inv_data = gl.nondet.web.render(clean_url, mode="text")
            except Exception as e:
                inv_data = f"INVOICE_FETCH_ERROR: {str(e)}"

            return (
                f"=== AUTHORITATIVE UTC ATOMIC CLOCK FEED ===\n"
                f"{time_resp}\n\n"
                f"=== AGENT SPENDING MANDATE ===\n"
                f"Agent ID: {a_id}\n"
                f"Vendor: {v_name}\n"
                f"Claimed Amount: ${claimed_amount_usdc} USDC\n"
                f"Monthly Budget: ${m_budget} (Spent so far this cycle: ${m_spent})\n"
                f"Per-Tx Limit: ${tx_cap}\n"
                f"Allowed Categories: {categories}\n"
                f"Current Billing Month: {last_billing_month}\n\n"
                f"=== VENDOR INVOICE EVIDENCE STREAM ===\n"
                f"{inv_data}"
            )

        task = (
            "You are the AgentAllowance Autonomous Spending Controller.\n"
            "Audit the vendor invoice and compare with the agent's spending mandate.\n\n"
            "Evaluate:\n"
            "1. clock_fresh: boolean (true if UTC Clock is fresh and valid)\n"
            "2. today_date: UTC date (YYYY-MM-DD format)\n"
            "3. invoice_valid: boolean (true if invoice DOM is accessible and parseable)\n"
            "4. canonical_invoice_id: string (exact official invoice number or identifier printed on the invoice document itself in the DOM, e.g. 'INV_OPENAI_8821'. If no invoice identifier exists anywhere in the document, output 'NONE' and set invoice_valid to false)\n"
            "5. verified_amount_usdc: integer (exact recomputed dollar amount on the invoice deliverable line items)\n"
            "6. category: string ('COMPUTE', 'LLM_INFERENCE', 'STORAGE', 'APIS', 'UNAUTHORIZED')\n"
            "7. security_verdict: Strict enum ('APPROVED_DISBURSEMENT', 'BLOCKED_UNAUTHORIZED_DRAIN', 'FLAGGED_PARTIAL_REVIEW')\n"
            "   - APPROVED_DISBURSEMENT: Invoice is authentic, within spending cap, and matches allowed category.\n"
            "   - BLOCKED_UNAUTHORIZED_DRAIN: Invoice is fake, exceeds monthly budget/tx cap, or claims unauthorized personal expenses.\n"
            "   - FLAGGED_PARTIAL_REVIEW: Invoice contains ambiguous or unitemized surcharges.\n"
            "8. reasoning: Concise 1-2 sentence explanation of audit verdict.\n\n"
            "Output JSON format:\n"
            "{\n"
            '  "clock_fresh": true/false,\n'
            '  "today_date": "<YYYY-MM-DD>",\n'
            '  "invoice_valid": true/false,\n'
            '  "canonical_invoice_id": "<exact printed invoice ID or NONE>",\n'
            '  "verified_amount_usdc": <integer>,\n'
            '  "category": "<string>",\n'
            '  "security_verdict": "<APPROVED_DISBURSEMENT|BLOCKED_UNAUTHORIZED_DRAIN|FLAGGED_PARTIAL_REVIEW>",\n'
            '  "reasoning": "<sentence>"\n'
            "}\n"
            "Respond ONLY with raw JSON."
        )

        criteria = (
            "AgentAllowance Invoice Equivalence Rule:\n"
            "1. Strict Consensus Fields (100% exact match required across all validator nodes):\n"
            "   - clock_fresh (boolean: true)\n"
            "   - today_date (YYYY-MM-DD)\n"
            "   - invoice_valid (boolean: true)\n"
            "   - canonical_invoice_id (string exactly matching the invoice identifier printed in the DOM)\n"
            "   - verified_amount_usdc (integer matching exact itemized invoice total)\n"
            "   - category (enum 'COMPUTE', 'LLM_INFERENCE', 'STORAGE', 'APIS', 'UNAUTHORIZED')\n"
            "   - security_verdict (enum 'APPROVED_DISBURSEMENT', 'BLOCKED_UNAUTHORIZED_DRAIN', 'FLAGGED_PARTIAL_REVIEW')\n"
            "Independently parse invoice DOM, recompute deliverables, extract canonical invoice identifier, and check policy limits.\n"
            "REJECT the leader proposal if:\n"
            "(1) canonical_invoice_id does not match the identifier printed in the invoice document DOM — "
            "REJECT if the leader fabricates an ID not in the DOM, alters the printed ID, or claims NONE when an identifier is present,\n"
            "(2) verified_amount_usdc does not match the exact itemized invoice deliverable sum in the DOM,\n"
            "(3) security_verdict is marked APPROVED when verified_amount_usdc exceeds per_tx_cap or monthly budget,\n"
            "(4) security_verdict is marked APPROVED when category is not in allowed_categories,\n"
            "(5) invoice_valid is marked false or clock_fresh is marked false.\n"
            "Output must be valid JSON matching the schema."
        )

        consensus_result = gl.eq_principle.prompt_non_comparative(
            get_unified_input,
            task=task,
            criteria=criteria
        )

        raw_res = consensus_result.strip()
        if "</think>" in raw_res:
            raw_res = raw_res.split("</think>")[-1].strip()
        if raw_res.startswith("```"):
            r_lines = raw_res.split("\n")
            if len(r_lines) >= 3 and r_lines[0].startswith("```") and r_lines[-1].startswith("```"):
                raw_res = "\n".join(r_lines[1:-1]).strip()
            else:
                raw_res = raw_res.replace("```json", "").replace("```", "").strip()

        res_parsed = json.loads(raw_res)
        clock_fresh = bool(res_parsed.get("clock_fresh", False))
        assert clock_fresh == True, "[ERR_CLOCK_01] Failed to verify UTC Atomic Clock freshness (Fail-Closed)."

        invoice_valid = bool(res_parsed.get("invoice_valid", False))
        assert invoice_valid == True, "[ERR_INVOICE_01] Invoice DOM stream invalid or inaccessible (Fail-Closed)."

        canonical_id = str(res_parsed.get("canonical_invoice_id", "")).strip().upper()
        assert len(canonical_id) > 0 and canonical_id != "NONE", \
            "[ERR_INVOICE_03] No canonical invoice identifier found in document (Fail-Closed)."

        # INVARIANT: CONSENSUS-VERIFIED CANONICAL REPLAY KEYING
        # Keyed directly by consensus-verified document evidence (vendor + canonical ID)
        canonical_key = f"{v_name.lower()}:{canonical_id}"
        assert canonical_key not in self.processed_invoices, \
            f"[ERR_INVOICE_REPLAY] Canonical invoice '{canonical_id}' from vendor '{v_name}' has already been processed."

        today_str = str(res_parsed.get("today_date", "2026-08-21"))
        verdict = str(res_parsed.get("security_verdict", "BLOCKED_UNAUTHORIZED_DRAIN")).strip().upper()
        ver_amt = int(res_parsed.get("verified_amount_usdc", claimed_amount_usdc))
        cat = str(res_parsed.get("category", "APIS")).strip().upper()
        reasoning = str(res_parsed.get("reasoning", "Invoice audit complete."))

        # INVARIANT 3: REAL MONTHLY RESET LIFECYCLE
        # Automatically resets monthly spend counter when calendar month advances
        curr_billing_month = today_str[:7]  # "YYYY-MM"
        if last_billing_month != curr_billing_month:
            m_spent = 0  # Reset monthly spending counter

        # Invariant Safety Check: Budget Constraints with Consensus-Bound Amount
        if (m_spent + ver_amt) > m_budget or ver_amt > tx_cap:
            verdict = "BLOCKED_UNAUTHORIZED_DRAIN"
            reasoning = f"Budget overrun: Claim ${ver_amt} exceeds cap (${tx_cap}) or monthly allowance (${m_budget})."

        if cat not in [c.strip() for c in categories.split(",")]:
            verdict = "BLOCKED_UNAUTHORIZED_DRAIN"
            reasoning = f"Unauthorized category '{cat}' not permitted by agent spend mandate ({categories})."

        # Update Agent Spent State if Approved
        if verdict == "APPROVED_DISBURSEMENT":
            status = "SETTLEMENT_READY"
            new_spent = m_spent + ver_amt
            self.total_disbursed_usdc = u256(int(self.total_disbursed_usdc) + ver_amt)
            summary = f"APPROVED: ${ver_amt} USDC disbursed to {v_name} for {cat}. {reasoning}"
        else:
            status = "REJECTED_FROZEN"
            new_spent = m_spent
            summary = f"BLOCKED: Payment to {v_name} rejected. {reasoning}"

        # Persist Agent Spent State & Updated Billing Month
        self.agent_policies[a_id] = AgentSpendPolicy(
            agent_id=policy.agent_id,
            agent_name=policy.agent_name,
            owner_address=policy.owner_address,
            monthly_budget_usdc=policy.monthly_budget_usdc,
            spent_this_month_usdc=u256(new_spent),
            per_tx_cap_usdc=policy.per_tx_cap_usdc,
            allowed_categories=policy.allowed_categories,
            current_billing_month=curr_billing_month,
            is_active=policy.is_active
        )

        # Record Invoice & Mark Invoice as Processed for Replay Protection
        new_inv = InvoiceSpendRecord(
            invoice_id=inv_id,
            agent_id=a_id,
            vendor_name=v_name,
            canonical_invoice_id=canonical_id,
            claimed_amount_usdc=u256(claimed_amount_usdc),
            verified_amount_usdc=u256(ver_amt),
            expense_category=cat,
            security_verdict=verdict,
            status=status,
            audit_date=today_str,
            invoice_url=clean_url,
            audit_summary=summary
        )

        self.invoices[inv_id] = new_inv
        self.processed_invoices[inv_id] = True
        self.processed_invoices[canonical_key] = True
        self.total_invoices_audited = u256(int(self.total_invoices_audited) + 1)

        return summary

    @gl.public.view
    def get_invoice_audit(self, invoice_id: str) -> InvoiceSpendRecord:
        """Queries the security audit record for a given invoice."""
        i_key = invoice_id.strip()
        assert i_key in self.invoices, "[ERR_STATE_01] Invoice ID does not exist."
        return self.invoices[i_key]

    @gl.public.view
    def get_agent_policy(self, agent_id: str) -> AgentSpendPolicy:
        """Queries the current budget and spending state for an agent."""
        a_key = agent_id.strip()
        assert a_key in self.agent_policies, "[ERR_STATE_02] Agent policy not found."
        return self.agent_policies[a_key]

    @gl.public.view
    def get_total_audited(self) -> u256:
        return self.total_invoices_audited
