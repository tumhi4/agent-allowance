# AgentAllowance — Zero-Trust AI Agent Invoice & Spend Controller
**Contribution Type**: Builder · Intelligent Contracts  
**Deployed Contract**: [`0xEFF74aBcfa4006C2601aDaEcb259700ef1870e89`](https://explorer-studio.genlayer.com/address/0xEFF74aBcfa4006C2601aDaEcb259700ef1870e89)  
**Tx Hash**: `0xfad146f6c5490d40cb3d20f32348dd3c070ce49a3f1eb8098a1cffdcb96509b5`  
**GitHub Repository**: [https://github.com/tumhi4/agent-allowance](https://github.com/tumhi4/agent-allowance)  
**Live Telemetry / Evidence**: [https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html](https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html)

---

## 🎯 Steward Feedback Resolution (Joaquin / Pavel Kolosov)

### Steward Rejection Reason:
> *"The Explorer deployment contains the requested evidence-bound replay protection, but the frozen GitHub contract does not: it still keys replay checks only by the caller-chosen invoice ID and omits the canonical invoice identity. The submitted and deployed sources therefore do not match, leaving the prior correction unresolved."*

### Resolution & Proof of Source Alignment:
1. **Consensus-Verified Canonical Invoice Extraction**:
   - The contract prompt explicitly commands validators to parse the invoice document DOM and extract `canonical_invoice_id`: the official printed invoice identifier (e.g. `INV_OPENAI_8821`).
   - If missing from the document, validators must output `NONE` and fail-closed with `[ERR_INVOICE_03]`.
2. **Strict Consensus Equivalence Criterion**:
   - `canonical_invoice_id` is registered in the Equivalence Principle criteria as a strict 100% agreement field across all validator nodes.
   - Any leader proposal that fabricates an ID, alters the printed ID, or claims `NONE` when an identifier exists in the DOM is strictly rejected by validators.
3. **Evidence-Bound Replay Protection Key**:
   - Replay protection is no longer keyed solely to the caller-chosen `invoice_id`.
   - The contract constructs an evidence-derived key: `canonical_key = f"{vendor_name.lower()}:{canonical_id}"` and checks/persists it in `self.processed_invoices`.
   - Re-submitting the exact same invoice document under an alternating caller-chosen `invoice_id` (e.g., `CALLER_ATTACK_9999`) strictly reverts with `[ERR_INVOICE_REPLAY]`.
4. **Permanent Audit Record (`InvoiceSpendRecord`)**:
   - Stores `canonical_invoice_id` in storage alongside `claimed_amount_usdc`, `verified_amount_usdc`, `security_verdict`, and `audit_summary`.
5. **100% GitHub & Explorer Source Synchronization**:
   - The GitHub repository (`main` branch) is now fully synchronized and identical to the deployed Explorer contract at `0xEFF74aBcfa4006C2601aDaEcb259700ef1870e89`.

---

## 🛡️ Core Architectural Invariants

1. **Isolated Multi-Agent Policies**: Enforces monthly spending ceilings and per-transaction caps per agent (`AgentSpendPolicy`).
2. **Consensus-Bound Verified Amount**: Validators parse the invoice DOM and bind `verified_amount_usdc` (100% exact match) in strict criteria. Cumulative spending is derived solely from the consensus-verified amount.
3. **Caller Authorization**: `audit_agent_invoice` asserts caller is the policy owner or operator (`[ERR_AUTH_02]`).
4. **Real Monthly Reset Lifecycle**: Evaluates verified UTC clock and resets `spent_this_month_usdc` upon calendar month rollover (e.g., `2026-08` -> `2026-09`).
5. **Fail-Closed Safety**: Inaccessible clock (`[ERR_CLOCK_01]`), unreachable invoice DOM (`[ERR_INVOICE_01]`), missing canonical ID (`[ERR_INVOICE_03]`), or budget overruns immediately halt execution.

---

## 🧪 Comprehensive Test Suite
- Location: `test/test_agent_allowance.py`
- Result: **12/12 Invariant Tests Passing (100%)**
  - Test 1: Genesis Policy Initialized
  - Test 2: Caller Authorization Verified (`[ERR_AUTH_02]`)
  - Test 3: Consensus-Bound Invoice Approved ($450 USDC disbursed)
  - Test 4: Caller Invoice ID Replay Protection Verified (`[ERR_INVOICE_REPLAY]`)
  - Test 5: Per-Tx Cap Protection Verified ($4,800 over $1,000 cap blocked)
  - Test 6: Category Whitelist Verified (blocked `PERSONAL_TRAVEL`)
  - Test 7: Cumulative Spending Tracked ($1,340/$5,000)
  - Test 8: Real Monthly Reset Lifecycle Verified (reset to $500/$5,000 in September)
  - Test 9: Fail-Closed Clock Guard Verified (`[ERR_CLOCK_01]`)
  - Test 10: Fail-Closed Invoice Guard Verified (`[ERR_INVOICE_01]`)
  - **Test 11: Consensus Canonical Replay Key Guard Verified (alternating caller ID on same document blocked with `[ERR_INVOICE_REPLAY]`)**
  - **Test 12: Fail-Closed Missing Canonical ID Guard Verified (`[ERR_INVOICE_03]`)**
