"use client";

import { useState, type FormEvent } from "react";
import { useTenant } from "@/context/TenantContext";
import MainLayout from "@/components/navigation/MainLayout";
import BroadcastBanner from "@/components/dashboard/BroadcastBanner";

interface Account {
  platform: "MT4" | "MT5";
  label: string;
  login: string;
  leverage: number;
  balance: number;
  equity: number;
  status: "Live" | "Demo";
}

type ModalKind = "deposit" | "withdraw" | "account" | null;

const accounts: Account[] = [
  { platform: "MT5", label: "Live account", login: "1002948", leverage: 500, balance: 5430.5, equity: 5430.5, status: "Live" },
  { platform: "MT4", label: "Demo account", login: "2004812", leverage: 200, balance: 25000, equity: 25142.75, status: "Demo" },
];

export default function TraderCabinet() {
  const { branding } = useTenant();
  const balance = 12500;
  const [modal, setModal] = useState<ModalKind>(null);
  const [amount, setAmount] = useState("");
  const [notice, setNotice] = useState("");
  const [requestingAccount, setRequestingAccount] = useState(false);
  const [paymentProofUrl, setPaymentProofUrl] = useState("");
  const [submittingFinance, setSubmittingFinance] = useState(false);

  async function requestAccount(platform: "MT4" | "MT5", isDemo = false) {
    setRequestingAccount(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/trader/trading-accounts/request`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`, "X-Tenant-Host": window.location.hostname },
        body: JSON.stringify({ platform, is_demo: isDemo, leverage: 100 }),
      });
      const data = await response.json().catch(() => ({})) as { detail?: string; provisioning_status?: string };
      if (!response.ok) throw new Error(data.detail ?? "Account request failed.");
      setNotice(`${platform} ${isDemo ? "demo" : "live"} account request queued (${data.provisioning_status ?? "PENDING"}).`);
      setModal(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to request trading account.");
    } finally {
      setRequestingAccount(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0 || (modal !== "deposit" && modal !== "withdraw")) return;
    setSubmittingFinance(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/trader/finance/request`, { method: "POST", headers: { "Content-Type": "application/json", Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`, "X-Tenant-Host": window.location.hostname }, body: JSON.stringify({ type: modal === "deposit" ? "DEPOSIT" : "WITHDRAWAL", amount: value, currency: "USD", payment_proof_url: paymentProofUrl.trim() || null }) });
      const data = await response.json().catch(() => ({})) as { detail?: string };
      if (!response.ok) throw new Error(data.detail ?? "Transaction request failed.");
      setNotice(`${modal === "deposit" ? "Deposit" : "Withdrawal"} request submitted for finance approval.`);
      setAmount(""); setPaymentProofUrl(""); setModal(null);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Unable to submit transaction request.");
    } finally {
      setSubmittingFinance(false);
    }
  }

  return (
    <MainLayout><main className="cabinet-shell">
      <header className="cabinet-header">
        <div className="cabinet-brand"><span className="cabinet-logo">{branding?.companyName?.slice(0, 1) ?? "B"}</span><div><strong>{branding?.companyName ?? "Broker CRM"}</strong><span>Trader Cabinet</span></div></div>
        <div className="cabinet-user"><button className="back-button" type="button" onClick={() => window.history.back()}><span className="button-arrow" aria-hidden="true">←</span> Back</button><span className="online-dot" /> Live session <span className="cabinet-avatar">TR</span></div>
      </header>
      <div className="cabinet-body">
        <aside className="cabinet-sidebar"><p className="cabinet-eyebrow">Account</p><a className="cabinet-nav active" href="/trader-cabinet">⌂ Overview</a><a className="cabinet-nav" href="/settings">⚙ Settings</a><div className="cabinet-support"><span>?</span><div><strong>Need help?</strong><small>{branding?.supportEmail ?? "Contact support"}</small></div></div></aside>
        <section className="cabinet-content"><div className="cabinet-title"><div><p className="cabinet-eyebrow">Personal workspace</p><h1>{branding?.companyName ?? "Broker CRM"} Trader Cabinet</h1><p>Welcome back. Here is your account overview.</p></div><button className="primary-action" onClick={() => setModal("account")}>＋ Create live account</button></div>
          <BroadcastBanner />{notice && <div className="cabinet-notice">{notice}<button onClick={() => setNotice("")}>×</button></div>}
          <div className="cabinet-grid"><section className="cabinet-card wallet-card"><div className="card-label">USD wallet balance <span className="verified">Verified</span></div><strong className="wallet-total">${balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}</strong><div className="wallet-meta"><span>Available balance</span><span>Updated just now</span></div><div className="wallet-actions"><button onClick={() => setModal("deposit")}>Deposit <span>↗</span></button><button onClick={() => setModal("withdraw")}>Withdraw <span>↗</span></button></div></section><section className="cabinet-card summary-card"><div className="card-label">Portfolio snapshot</div><div className="summary-row"><span>Total equity</span><strong>$18,004.25</strong></div><div className="summary-row"><span>Free margin</span><strong>$16,781.10</strong></div><div className="summary-row"><span>Month to date</span><strong className="positive">+$842.60</strong></div></section></div>
          <section className="accounts-section"><div className="section-heading"><div><p className="cabinet-eyebrow">Trading</p><h2>Trading accounts <span>2 active</span></h2></div><button className="secondary-action" onClick={() => setModal("account")}>＋ Add account</button></div><div className="account-list">{accounts.map((account) => <article className="account-card" key={account.login}><div className={`platform-badge ${account.platform.toLowerCase()}`}>{account.platform}</div><div className="account-identity"><strong>{account.label}</strong><span>#{account.login} · 1:{account.leverage} leverage</span></div><span className={`account-status ${account.status.toLowerCase()}`}><i /> {account.status}</span><div className="account-metric"><small>Balance</small><strong>${account.balance.toLocaleString("en-US", { minimumFractionDigits: 2 })}</strong></div><div className="account-metric"><small>Equity</small><strong>${account.equity.toLocaleString("en-US", { minimumFractionDigits: 2 })}</strong></div><button className="account-more" aria-label={`Open ${account.label}`}>›</button></article>)}</div></section>
          <section className="quick-section"><div className="section-heading"><div><p className="cabinet-eyebrow">Shortcuts</p><h2>Quick actions</h2></div></div><div className="quick-grid"><button onClick={() => setModal("deposit")}><span className="quick-icon deposit-icon">＋</span><span><strong>Make a deposit</strong><small>Fund your wallet securely</small></span><b>›</b></button><button onClick={() => setModal("withdraw")}><span className="quick-icon withdraw-icon">↗</span><span><strong>Request withdrawal</strong><small>Send funds to your account</small></span><b>›</b></button><button><span className="quick-icon report-icon">▤</span><span><strong>View performance</strong><small>Review your trading history</small></span><b>›</b></button></div></section>
        </section>
      </div>
      {modal && <div className="modal-backdrop" role="presentation" onClick={() => setModal(null)}><div className="cabinet-modal" role="dialog" aria-modal="true" onClick={(event) => event.stopPropagation()}><button className="modal-close" onClick={() => setModal(null)}>×</button><p className="cabinet-eyebrow">{modal === "account" ? "Account engine" : "Wallet & treasury"}</p><h2>{modal === "account" ? "Create a live account" : modal === "deposit" ? "Make a deposit" : "Request withdrawal"}</h2>{modal === "account" ? <div className="modal-options"><button disabled={requestingAccount} onClick={() => void requestAccount("MT5")}>MT5 Live <small>Standard execution account</small></button><button disabled={requestingAccount} onClick={() => void requestAccount("MT4")}>MT4 Live <small>Classic execution account</small></button><button disabled={requestingAccount} onClick={() => void requestAccount("MT5", true)}>MT5 Demo <small>Practice execution account</small></button></div> : <form onSubmit={(event) => void submit(event)}><label>Amount (USD)<input autoFocus inputMode="decimal" min="1" step="0.01" type="number" value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" required /></label>{modal === "deposit" && <label>Payment proof URL<input type="url" value={paymentProofUrl} onChange={(event) => setPaymentProofUrl(event.target.value)} placeholder="https://.../receipt.png" /></label>}<button className="primary-action modal-submit" disabled={submittingFinance} type="submit">{submittingFinance ? "Submitting..." : modal === "deposit" ? "Submit deposit request" : "Submit withdrawal request"}</button></form>}</div></div>}
    </main></MainLayout>
  );
}
