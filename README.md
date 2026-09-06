# AgentAllowance — Zero-Trust AI Agent Invoice & Spend Controller

> **"An Intelligent Contract on GenLayer that serves as an autonomous spending controller for AI agents, auditing natural-language invoices and releasing capped treasury disbursements via decentralized AI consensus."**

---

## 🔗 Verified Deployment & Telemetry Links
- **GenLayer Explorer Contract**: [`0x82ebF2752149079e5228B3768afEbE58eb5D955F`](https://explorer-studio.genlayer.com/address/0x82ebF2752149079e5228B3768afEbE58eb5D955F)
- **GitHub Repository**: [`https://github.com/tumhi4/agent-allowance`](https://github.com/tumhi4/agent-allowance)
- **Live Invoice Telemetry**: [`https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html`](https://tumhi4.github.io/agent-allowance/demo/mock_invoice_approved_api_compute.html)

---

## 🌟 The Core Problem

Autonomous AI agents (AutoGPT, LangChain, crewAI) need financial autonomy to pay for LLM inference tokens, GPU cloud compute, API subscriptions, and web scraping. However, giving AI agents raw private keys or unrestricted credit cards creates severe vulnerabilities:
- **Prompt Injection Theft**: Adversaries trick the agent into draining funds to attacker wallets.
- **Runaway Budget Infinite Loops**: Software bugs rack up thousands in unintended vendor charges.
- **Fake / Bogus Invoices**: Agents paying fraudulent vendor charges.

**AgentAllowance solves this by acting as an on-chain zero-trust corporate budget controller**:
1. **Isolated Multi-Agent Policies**: Enforces monthly spending ceilings and per-transaction caps per agent.
2. **Semantic Invoice Audit**: AI validators independently fetch vendor invoice URLs via `gl.nondet.web.render()`, auditing itemized deliverables, vendor authenticity, and expense categories.
3. **Autonomous EVM Disbursement**: Authorizes approved USDC treasury payouts without ever giving agents private keys.

---

## 🛡️ Key Architectural Invariants

- **Unified Consensus Round**: Clock freshness and invoice inspection execute in **1 parallel consensus round**, eliminating leader rotations.
- **Fail-Closed Resilience**: Any unparseable invoice or prompt discrepancy triggers a hard rejection.
- **Immutable On-Chain Spending Registry**: Permanently tracks all disbursements in `TreeMap[str, InvoiceSpendRecord]`.

---

## 📖 Test Cases & Verification

| Test ID | Invoice ID | Vendor | Amount | Scenario | Expected Verdict | Action |
|---|---|---|---|---|---|---|
| **TC-01** | `INV_OPENAI_8821` | OpenAI Inc. | $450 USDC | Batch LLM inference | `APPROVED_DISBURSEMENT` | Release USDC |
| **TC-02** | `INV_DRAIN_9901` | Offshore Giftcards | $4,800 USDC | Exceeds $1,000 tx cap & unallowed category | `BLOCKED_UNAUTHORIZED_DRAIN` | Freeze Payment |
| **TC-03** | `INV_GPU_7742` | Lambda Labs | $890 USDC | 8x H100 GPU compute | `APPROVED_DISBURSEMENT` | Release USDC |
