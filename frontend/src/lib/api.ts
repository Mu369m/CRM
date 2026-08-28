export interface DashboardSummary {
  assetsUnderManagement: number;
  netDeposits24h: number;
  activeTraders: number;
  volume24h: number;
}

export interface ApiError {
  detail: string;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init.headers },
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
};
