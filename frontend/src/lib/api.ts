export interface DashboardSummary {
  assetsUnderManagement: number;
  netDeposits24h: number;
  activeTraders: number;
  volume24h: number;
}

export interface PaymentMethod {
  id?: string;
  method: string;
  network: string;
  asset: string;
  chain_id?: string | null;
  contract_address?: string | null;
  deposit_address?: string | null;
  qr_code_url?: string | null;
  account_details?: Record<string, string>;
  min_deposit: number | string;
  max_deposit?: number | string | null;
  min_withdrawal: number | string;
  processing_fee: number | string;
  is_active_broker: boolean;
}

export interface MasterPaymentControl {
  id?: string;
  tenant_id?: string | null;
  method: string;
  network: string;
  asset: string;
  is_active_master: boolean;
}

export interface ApiError {
  detail: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = typeof window === "undefined" ? "" : localStorage.getItem("access_token") ?? "";
  const tenantHost = typeof window === "undefined" ? "" : window.location.hostname;
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(tenantHost ? { "X-Tenant-Host": tenantHost } : {}), ...init.headers },
  });
  if (!response.ok) {
    const error = (await response.json().catch(() => ({ detail: response.statusText }))) as ApiError;
    throw new Error(error.detail);
  }
  return response.json() as Promise<T>;
}

export const crmApi = {
  health: () => request<{ status: string }>("/health"),
  login: (email: string, password: string, twoFactorCode?: string) => request<{ access_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password, two_factor_code: twoFactorCode }) }),
  wallet: (token: string) => request<{ balance: string; currency: string }>("/api/wallet", { headers: { Authorization: `Bearer ${token}` } }),
  portfolio: () => request<Portfolio>("/api/v1/trader/portfolio"),
  positions: () => request<Position[]>("/api/v1/trader/positions"),
  ledger: () => request<LedgerPage>("/api/v1/trader/wallet/transactions"),
  profile: () => request<Profile>("/api/v1/trader/profile"),
  updateProfile: (body: Partial<Profile>) => request<Profile>("/api/v1/trader/profile", { method: "PUT", body: JSON.stringify(body) }),
  setup2fa: () => request<{ secret: string; provisioning_uri: string }>("/api/auth/2fa/setup", { method: "POST" }),
  verify2fa: (code: string) => request<{ enabled: boolean }>("/api/auth/2fa/verify", { method: "POST", body: JSON.stringify({ code }) }),
  kycDocuments: () => request<KycDocument[]>("/api/v1/trader/kyc/documents"),
  kycUploadUrl: (body: { document_type: string; content_type: string }) => request<{ upload_url: string; storage_key: string }>("/api/v1/trader/kyc/upload-url", { method: "POST", body: JSON.stringify(body) }),
  submitKyc: (body: { document_type: string; storage_key: string; fields: Record<string, string> }) => request<unknown>("/api/v1/trader/kyc/submit", { method: "POST", body: JSON.stringify(body) }),
  ibOverview: () => request<IbOverview>("/api/v1/trader/ib/overview"),
  ibNetwork: () => request<NetworkNode[]>("/api/v1/trader/ib/network"),
  ibCommissions: () => request<LedgerPage>("/api/v1/trader/ib/commissions"),
  ibWithdraw: (body: { amount: string; destination: string }) => request<unknown>("/api/v1/trader/ib/withdraw", { method: "POST", body: JSON.stringify(body) }),
  tradeHistory: () => request<HistoryPage>("/api/v1/trader/history"),
  cryptoDeposit: (body: { amount: string }, idempotencyKey: string) => request<{ id: string; status: string; address: string; network: string; qr_code: string }>("/api/v1/trader/finance/deposit/crypto", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) }),
  paymentWithdraw: (body: { amount: string; destination: string }, idempotencyKey: string) => request<unknown>("/api/v1/trader/finance/withdraw", { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body) }),  brokerPaymentMethods: () => request<PaymentMethod[]>('/api/v1/broker/payments/methods'),
  saveBrokerPaymentMethod: (body: PaymentMethod) => request<PaymentMethod>('/api/v1/broker/payments/methods', { method: 'PUT', body: JSON.stringify(body) }),
  masterPaymentControls: () => request<MasterPaymentControl[]>('/api/v1/owner/payments/controls'),
  saveMasterPaymentControl: (body: MasterPaymentControl) => request<MasterPaymentControl>('/api/v1/owner/payments/controls', { method: 'PUT', body: JSON.stringify(body) }),};

export interface Portfolio { balance: string; equity: string; used_margin: string; free_margin: string; floating_pnl: string; accounts: Array<{ id: string; platform: string; login: string; server: string; leverage: number; is_demo: boolean; is_locked: boolean; status: string }> }
export interface Position { id: string; account_id: string; symbol: string; side: string; volume: string; open_price: string; current_price: string; floating_pnl: string; opened_at: string }
export interface LedgerPage { items: Array<{ id: string; entry_type: string; amount: string; reference: string; created_at: string }>; total: number; offset: number; limit: number }
export interface Profile { id: string; email: string; full_name: string | null; phone: string | null; country: string | null; address: string | null; role: string; kyc_status: string; is_kyc_verified: boolean; totp_enabled: boolean }
export interface KycDocument { id: string; document_type: string; status: string; review_note?: string | null; created_at: string }
export interface IbOverview { referral_code: string; referral_link: string; referred_traders: number; direct_active_volume: string; total_earned_commissions: string; wallet_balance: string }
export interface NetworkNode { id: string; email: string; full_name: string | null; role: string; level: number; children: NetworkNode[] }
export interface HistoryPage { items: Array<{ id: string; symbol: string; realized_pnl: string; closed_at: string }>; total: number; offset: number; limit: number }
