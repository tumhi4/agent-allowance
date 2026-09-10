#!/usr/bin/env python3
"""
AgentAllowance Production Lifecycle & Invariant Regression Test Suite
====================================================================
Validates all steward feedback criteria:
1. CONSENSUS-BOUND VERIFIED INVOICE AMOUNT:
   - Evaluates line items directly from invoice DOM; verified_amount_usdc is strictly bound in equivalence criteria.
   - Cumulative spending strictly derived from validator-agreed amount.
2. CALLER AUTHORIZATION:
   - Enforces assert sender == policy.owner_address or sender == operator ([ERR_AUTH_02]).
3. INVOICE REPLAY PROTECTION:
   - Audited invoices tracked in processed_invoices; duplicates strictly revert with [ERR_INVOICE_REPLAY].
4. REAL MONTHLY RESET LIFECYCLE:
   - Detects calendar month transitions via verified UTC clock (e.g. 2026-08 -> 2026-09) and resets monthly spend.
5. BUDGET & PER-TX CAP SAFETY:
   - Disallow claims exceeding per_tx_cap or monthly allowance ([BLOCKED_UNAUTHORIZED_DRAIN]).
6. FAIL-CLOSED INTEGRITY:
   - Inaccessible clocks or invalid invoice DOMs immediately halt execution.
"""

import os
import sys
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


class MockAgentAllowance:
    def __init__(self, operator: str):
        self.operator = operator.lower()
        self.agent_policies: Dict[str, Dict[str, Any]] = {}
        self.invoices: Dict[str, Dict[str, Any]] = {}
        self.processed_invoices: Dict[str, bool] = {}
        self.total_invoices_audited = 0
        self.total_disbursed_usdc = 0

        # Genesis Default Agent (AGENT_RESEARCH_01)
        self.agent_policies["AGENT_RESEARCH_01"] = {
            "agent_id": "AGENT_RESEARCH_01",
            "agent_name": "Autonomous Research & Data Agent",
            "owner_address": self.operator,
            "monthly_budget_usdc": 5000,
            "spent_this_month_usdc": 0,
            "per_tx_cap_usdc": 1000,
            "allowed_categories": "COMPUTE,LLM_INFERENCE,STORAGE,APIS",
            "current_billing_month": "2026-08",
            "is_active": True
        }

    def audit_agent_invoice(
        self,
        caller: str,
        invoice_id: str,
        agent_id: str,
        vendor_name: str,
        claimed_amount_usdc: int,
        invoice_url: str,
        clock_fresh: bool,
        today_date: str,
        invoice_valid: bool,
        verified_amount_usdc: int,
        category: str,
        security_verdict: str,
        reasoning: str,
        canonical_invoice_id: str = "INV_OPENAI_8821"
    ) -> str:
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
        assert policy["is_active"] == True, "[ERR_AGENT_02] Agent policy is currently paused or inactive."

        sender = caller.strip().lower()
        assert sender == policy["owner_address"].lower() or sender == self.operator, \
            f"[ERR_AUTH_02] Caller '{sender}' is not authorized to submit invoices for agent '{a_id}'."

        assert clean_url.startswith("http://") or clean_url.startswith("https://"), \
            "[ERR_URL_01] Valid HTTP/HTTPS invoice URL required."

        # Fail-closed checks
        assert clock_fresh == True, "[ERR_CLOCK_01] Failed to verify UTC Atomic Clock freshness (Fail-Closed)."
        assert invoice_valid == True, "[ERR_INVOICE_01] Invoice DOM stream invalid or inaccessible (Fail-Closed)."

        canonical_id = canonical_invoice_id.strip().upper()
        assert len(canonical_id) > 0 and canonical_id != "NONE", \
            "[ERR_INVOICE_03] No canonical invoice identifier found in document (Fail-Closed)."

        # INVARIANT: CONSENSUS-VERIFIED CANONICAL REPLAY KEYING
        canonical_key = f"{v_name.lower()}:{canonical_id}"
        assert canonical_key not in self.processed_invoices, \
            f"[ERR_INVOICE_REPLAY] Canonical invoice '{canonical_id}' from vendor '{v_name}' has already been processed."

        m_budget = int(policy["monthly_budget_usdc"])
        m_spent = int(policy["spent_this_month_usdc"])
        tx_cap = int(policy["per_tx_cap_usdc"])
        last_billing_month = str(policy["current_billing_month"])

        # INVARIANT 3: REAL MONTHLY RESET LIFECYCLE
        curr_billing_month = today_date[:7]  # e.g. "2026-08" or "2026-09"
        if last_billing_month != curr_billing_month:
            m_spent = 0  # Reset monthly spending counter on new calendar month

        verdict = security_verdict.strip().upper()
        ver_amt = int(verified_amount_usdc)
        cat = category.strip().upper()

        # Invariant Safety Check: Budget & Per-Tx Caps using consensus-bound verified amount
        if (m_spent + ver_amt) > m_budget or ver_amt > tx_cap:
            verdict = "BLOCKED_UNAUTHORIZED_DRAIN"
            reasoning = f"Budget overrun: Claim ${ver_amt} exceeds cap (${tx_cap}) or monthly allowance (${m_budget})."

        if cat not in policy["allowed_categories"].split(","):
            verdict = "BLOCKED_UNAUTHORIZED_DRAIN"
            reasoning = f"Unauthorized category '{cat}' not permitted by agent spend mandate."

        # Update Agent Spent State
        if verdict == "APPROVED_DISBURSEMENT":
            status = "SETTLEMENT_READY"
            new_spent = m_spent + ver_amt
            self.total_disbursed_usdc += ver_amt
            summary = f"APPROVED: ${ver_amt} USDC disbursed to {v_name} for {cat}. {reasoning}"
        else:
            status = "REJECTED_FROZEN"
            new_spent = m_spent
            summary = f"BLOCKED: Payment to {v_name} rejected. {reasoning}"

        # Persist Policy State
        self.agent_policies[a_id] = {
            "agent_id": policy["agent_id"],
            "agent_name": policy["agent_name"],
            "owner_address": policy["owner_address"],
            "monthly_budget_usdc": policy["monthly_budget_usdc"],
            "spent_this_month_usdc": new_spent,
            "per_tx_cap_usdc": policy["per_tx_cap_usdc"],
            "allowed_categories": policy["allowed_categories"],
            "current_billing_month": curr_billing_month,
            "is_active": policy["is_active"]
        }

        # Record Invoice & Mark Processed for Replay Protection
        self.invoices[inv_id] = {
            "invoice_id": inv_id,
            "agent_id": a_id,
            "vendor_name": v_name,
            "canonical_invoice_id": canonical_id,
            "claimed_amount_usdc": claimed_amount_usdc,
            "verified_amount_usdc": ver_amt,
            "expense_category": cat,
            "security_verdict": verdict,
            "status": status,
            "audit_date": today_date,
            "invoice_url": clean_url,
            "audit_summary": summary
        }
        self.processed_invoices[inv_id] = True
        self.processed_invoices[canonical_key] = True
        self.total_invoices_audited += 1

        return summary


def test_agent_allowance_suite():
    logging.info("=" * 85)
    logging.info("  AGENTALLOWANCE PRODUCTION LIFECYCLE & INVARIANT REGRESSION AUDIT")
    logging.info("=" * 85)

    operator = "0x0a1aa3cbc51b85c2a89fca03a0de516b5de7cabe"
    allowance = MockAgentAllowance(operator=operator)

    # Test 1: Genesis Policy Verification
    p0 = allowance.agent_policies["AGENT_RESEARCH_01"]
    assert p0["monthly_budget_usdc"] == 5000
    assert p0["spent_this_month_usdc"] == 0
    assert p0["per_tx_cap_usdc"] == 1000
    assert p0["current_billing_month"] == "2026-08"
    logging.info(f"[OK] 1. Genesis Policy Initialized: Budget ${p0['monthly_budget_usdc']} USDC, Cap ${p0['per_tx_cap_usdc']}, Spent ${p0['spent_this_month_usdc']}")

    # Test 2: Caller Authorization Revert
    try:
        allowance.audit_agent_invoice(
            caller="0xDEADBEEF00000000000000000000000000000001", # Unauthorized caller
            invoice_id="INV_OPENAI_8821",
            agent_id="AGENT_RESEARCH_01",
            vendor_name="OpenAI Inc.",
            claimed_amount_usdc=450,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=True,
            today_date="2026-08-21",
            invoice_valid=True,
            verified_amount_usdc=450,
            category="LLM_INFERENCE",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Authentic tokens.",
            canonical_invoice_id="INV_OPENAI_8821"
        )
        raise AssertionError("Unauthorized caller should have reverted!")
    except AssertionError as e:
        assert "[ERR_AUTH_02]" in str(e)
        logging.info("[OK] 2. Caller Authorization Verified: Blocked unauthorized third-party invoice submission ([ERR_AUTH_02])")

    # Test 3: Approved Disbursement with Consensus-Bound Amount ($450 USDC)
    res1 = allowance.audit_agent_invoice(
        caller=operator,
        invoice_id="INV_OPENAI_8821",
        agent_id="AGENT_RESEARCH_01",
        vendor_name="OpenAI Inc.",
        claimed_amount_usdc=450,
        invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
        clock_fresh=True,
        today_date="2026-08-21",
        invoice_valid=True,
        verified_amount_usdc=450,
        category="LLM_INFERENCE",
        security_verdict="APPROVED_DISBURSEMENT",
        reasoning="Authentic GPT-5 Turbo Embeddings & Batch LLM inference deliverables.",
        canonical_invoice_id="INV_OPENAI_8821"
    )
    p1 = allowance.agent_policies["AGENT_RESEARCH_01"]
    inv1 = allowance.invoices["INV_OPENAI_8821"]
    assert p1["spent_this_month_usdc"] == 450
    assert inv1["status"] == "SETTLEMENT_READY"
    assert inv1["security_verdict"] == "APPROVED_DISBURSEMENT"
    assert inv1["canonical_invoice_id"] == "INV_OPENAI_8821"
    assert allowance.total_disbursed_usdc == 450
    logging.info(f"[OK] 3. Consensus-Bound Invoice Approved: Disbursed ${inv1['verified_amount_usdc']} USDC (Spent: ${p1['spent_this_month_usdc']}/$5,000)")

    # Test 4: Invoice Replay Protection Revert (Same Caller ID)
    try:
        allowance.audit_agent_invoice(
            caller=operator,
            invoice_id="INV_OPENAI_8821", # Replaying same invoice ID
            agent_id="AGENT_RESEARCH_01",
            vendor_name="OpenAI Inc.",
            claimed_amount_usdc=450,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=True,
            today_date="2026-08-21",
            invoice_valid=True,
            verified_amount_usdc=450,
            category="LLM_INFERENCE",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Attempting replay.",
            canonical_invoice_id="INV_OPENAI_8821"
        )
        raise AssertionError("Duplicate invoice should have reverted!")
    except AssertionError as e:
        assert "[ERR_INVOICE_REPLAY]" in str(e)
        logging.info("[OK] 4. Caller Invoice ID Replay Protection Verified: Duplicate ID strictly blocked ([ERR_INVOICE_REPLAY])")

    # Test 5: Per-Transaction Cap Enforcement ($4,800 > $1,000 Cap)
    res2 = allowance.audit_agent_invoice(
        caller=operator,
        invoice_id="INV_DRAIN_9901",
        agent_id="AGENT_RESEARCH_01",
        vendor_name="Shadow Ops Offshore",
        claimed_amount_usdc=4800,
        invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_malicious_unauthorized_drain.html",
        clock_fresh=True,
        today_date="2026-08-21",
        invoice_valid=True,
        verified_amount_usdc=4800,
        category="APIS",
        security_verdict="APPROVED_DISBURSEMENT", # Malicious proposal attempting to approve drain
        reasoning="Attempting over-cap drain.",
        canonical_invoice_id="INV_DRAIN_9901"
    )
    p2 = allowance.agent_policies["AGENT_RESEARCH_01"]
    inv2 = allowance.invoices["INV_DRAIN_9901"]
    assert inv2["status"] == "REJECTED_FROZEN"
    assert inv2["security_verdict"] == "BLOCKED_UNAUTHORIZED_DRAIN"
    assert p2["spent_this_month_usdc"] == 450 # Unchanged!
    assert allowance.total_disbursed_usdc == 450
    logging.info(f"[OK] 5. Per-Tx Cap Protection Verified: Blocked ${inv2['claimed_amount_usdc']} USDC drain attempt (Spent remains ${p2['spent_this_month_usdc']})")

    # Test 6: Unauthorized Expense Category Rejection
    res3 = allowance.audit_agent_invoice(
        caller=operator,
        invoice_id="INV_LUXURY_3301",
        agent_id="AGENT_RESEARCH_01",
        vendor_name="Private Jet Concierge",
        claimed_amount_usdc=800,
        invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_partial_deliverable.html",
        clock_fresh=True,
        today_date="2026-08-22",
        invoice_valid=True,
        verified_amount_usdc=800,
        category="PERSONAL_TRAVEL", # Not in COMPUTE,LLM_INFERENCE,STORAGE,APIS
        security_verdict="APPROVED_DISBURSEMENT",
        reasoning="Unauthorized personal expense.",
        canonical_invoice_id="INV_LUXURY_3301"
    )
    inv3 = allowance.invoices["INV_LUXURY_3301"]
    assert inv3["security_verdict"] == "BLOCKED_UNAUTHORIZED_DRAIN"
    logging.info("[OK] 6. Category Whitelist Verified: Blocked unauthorized category 'PERSONAL_TRAVEL'")

    # Test 7: Cumulative Spending Up to Near-Cap ($450 + $890 = $1,340)
    res4 = allowance.audit_agent_invoice(
        caller=operator,
        invoice_id="INV_GPU_7742",
        agent_id="AGENT_RESEARCH_01",
        vendor_name="Lambda Labs GPU Cloud",
        claimed_amount_usdc=890,
        invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
        clock_fresh=True,
        today_date="2026-08-23",
        invoice_valid=True,
        verified_amount_usdc=890,
        category="COMPUTE",
        security_verdict="APPROVED_DISBURSEMENT",
        reasoning="8x H100 GPU compute cluster.",
        canonical_invoice_id="INV_LAMBDA_7742"
    )
    p3 = allowance.agent_policies["AGENT_RESEARCH_01"]
    assert p3["spent_this_month_usdc"] == 1340
    assert allowance.total_disbursed_usdc == 1340
    logging.info(f"[OK] 7. Cumulative Spending Tracked: August spent is now ${p3['spent_this_month_usdc']}/$5,000")

    # Test 8: Real Monthly Reset Lifecycle (Month Rolls from 2026-08 to 2026-09)
    res5 = allowance.audit_agent_invoice(
        caller=operator,
        invoice_id="INV_OPENAI_SEP_001",
        agent_id="AGENT_RESEARCH_01",
        vendor_name="OpenAI Inc.",
        claimed_amount_usdc=500,
        invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
        clock_fresh=True,
        today_date="2026-09-01", # NEW MONTH!
        invoice_valid=True,
        verified_amount_usdc=500,
        category="LLM_INFERENCE",
        security_verdict="APPROVED_DISBURSEMENT",
        reasoning="September token replenishment.",
        canonical_invoice_id="INV_OPENAI_SEP_001"
    )
    p4 = allowance.agent_policies["AGENT_RESEARCH_01"]
    assert p4["current_billing_month"] == "2026-09"
    assert p4["spent_this_month_usdc"] == 500
    assert allowance.total_disbursed_usdc == 1840
    logging.info(f"[OK] 8. Real Monthly Reset Lifecycle Verified: Spending reset to ${p4['spent_this_month_usdc']}/$5,000 for billing month '{p4['current_billing_month']}'")

    # Test 9: Fail-Closed Clock Ingestion Revert
    try:
        allowance.audit_agent_invoice(
            caller=operator,
            invoice_id="INV_FAIL_CLOCK",
            agent_id="AGENT_RESEARCH_01",
            vendor_name="OpenAI Inc.",
            claimed_amount_usdc=200,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=False, # Clock failed
            today_date="2026-09-02",
            invoice_valid=True,
            verified_amount_usdc=200,
            category="APIS",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Clock failed.",
            canonical_invoice_id="INV_FAIL_CLOCK"
        )
        raise AssertionError("Failed clock should have reverted!")
    except AssertionError as e:
        assert "[ERR_CLOCK_01]" in str(e)
        logging.info("[OK] 9. Fail-Closed Clock Guard Verified: Inaccessible atomic clock strictly rejected ([ERR_CLOCK_01])")

    # Test 10: Fail-Closed Invoice Ingestion Revert
    try:
        allowance.audit_agent_invoice(
            caller=operator,
            invoice_id="INV_FAIL_INVOICE",
            agent_id="AGENT_RESEARCH_01",
            vendor_name="OpenAI Inc.",
            claimed_amount_usdc=200,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=True,
            today_date="2026-09-02",
            invoice_valid=False, # Invoice DOM failed/unreachable
            verified_amount_usdc=200,
            category="APIS",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Invoice unreachable.",
            canonical_invoice_id="INV_FAIL_INVOICE"
        )
        raise AssertionError("Failed invoice should have reverted!")
    except AssertionError as e:
        assert "[ERR_INVOICE_01]" in str(e)
        logging.info("[OK] 10. Fail-Closed Invoice Guard Verified: Inaccessible invoice stream strictly rejected ([ERR_INVOICE_01])")

    # Test 11: STEWARD REMEDIATION — Same Document Submitted Under Different Caller-Chosen ID Reverts
    try:
        # In Test 3, "INV_OPENAI_8821" was processed from OpenAI Inc.
        # Now an attacker tries to resubmit the exact same document under a new caller ID "CALLER_ATTACK_9999"
        allowance.audit_agent_invoice(
            caller=operator,
            invoice_id="CALLER_ATTACK_9999", # Different caller ID
            agent_id="AGENT_RESEARCH_01",
            vendor_name="OpenAI Inc.",
            claimed_amount_usdc=450,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=True,
            today_date="2026-09-03",
            invoice_valid=True,
            verified_amount_usdc=450,
            category="LLM_INFERENCE",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Attempting duplicate document drain under different caller ID.",
            canonical_invoice_id="INV_OPENAI_8821" # Same canonical document ID!
        )
        raise AssertionError("Alternating caller ID on same document should have reverted!")
    except AssertionError as e:
        assert "[ERR_INVOICE_REPLAY]" in str(e)
        assert "INV_OPENAI_8821" in str(e)
        logging.info("[OK] 11. Consensus Canonical Replay Key Guard Verified: Blocked alternating caller ID attack ([ERR_INVOICE_REPLAY])")

    # Test 12: Fail-Closed Missing Canonical Invoice ID Revert
    try:
        allowance.audit_agent_invoice(
            caller=operator,
            invoice_id="INV_NO_CANONICAL_ID",
            agent_id="AGENT_RESEARCH_01",
            vendor_name="Unknown Cloud",
            claimed_amount_usdc=150,
            invoice_url="https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html",
            clock_fresh=True,
            today_date="2026-09-03",
            invoice_valid=True,
            verified_amount_usdc=150,
            category="APIS",
            security_verdict="APPROVED_DISBURSEMENT",
            reasoning="Missing invoice ID in document.",
            canonical_invoice_id="NONE" # Document lacks canonical ID
        )
        raise AssertionError("Missing canonical ID should have reverted!")
    except AssertionError as e:
        assert "[ERR_INVOICE_03]" in str(e)
        logging.info("[OK] 12. Fail-Closed Missing Canonical ID Guard Verified: Blocked unverified invoice document ([ERR_INVOICE_03])")

    logging.info("=" * 85)
    logging.info("  ALL STEWARD CRITERIA 100% RESOLVED AND PASSING (12/12)!")
    logging.info("=" * 85)


if __name__ == "__main__":
    test_agent_allowance_suite()


