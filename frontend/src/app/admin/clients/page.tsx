"use client";

import {
  useEffect,
  useMemo,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  ArrowDownToLine,
  ArrowUpToLine,
  Ban,
  Check,
  ChevronDown,
  CircleDollarSign,
  Edit3,
  Filter,
  Search,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";

type Kyc = "Verified" | "Pending";
type Kind = "Live" | "Demo";
type State = "Active" | "Suspended";
type Client = {
  id: string;
  name: string;
  email: string;
  accountId: string;
  kind: Kind;
  leverage: string;
  equity: number;
  balance: number;
  kyc: Kyc;
  state: State;
  initials: string;
};
type Mode = "credit" | "debit";
const clientsSeed: Client[] = [
  {
    id: "client-10482",
    name: "Amelia Thompson",
    email: "amelia.thompson@example.com",
    accountId: "MT5-1048291",
    kind: "Live",
    leverage: "1:500",
    equity: 184250.4,
    balance: 181900,
    kyc: "Verified",
    state: "Active",
    initials: "AT",
  },
  {
    id: "client-09831",
    name: "Nikolai Petrov",
    email: "n.petrov@example.com",
    accountId: "MT4-0983144",
    kind: "Live",
    leverage: "1:200",
    equity: 72840.1,
    balance: 75200,
    kyc: "Pending",
    state: "Active",
    initials: "NP",
  },
  {
    id: "client-11720",
    name: "Sofia Mendes",
    email: "sofia.mendes@example.com",
    accountId: "MT5-1172040",
    kind: "Demo",
    leverage: "1:100",
    equity: 42000,
    balance: 42000,
    kyc: "Verified",
    state: "Active",
    initials: "SM",
  },
  {
    id: "client-08317",
    name: "Daniel Okafor",
    email: "daniel.okafor@example.com",
    accountId: "MT4-0831728",
    kind: "Live",
    leverage: "1:100",
    equity: 38000,
    balance: 40250,
    kyc: "Verified",
    state: "Suspended",
    initials: "DO",
  },
  {
    id: "client-12108",
    name: "Elena Rossi",
    email: "elena.rossi@example.com",
    accountId: "MT5-1210881",
    kind: "Demo",
    leverage: "1:50",
    equity: 12500,
    balance: 12500,
    kyc: "Pending",
    state: "Active",
    initials: "ER",
  },
];
const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});
const leverageOptions = [
  "1:25",
  "1:50",
  "1:100",
  "1:200",
  "1:300",
  "1:500",
  "1:1000",
];

export default function ClientsPage() {
  const [clients, setClients] = useState(clientsSeed);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [kyc, setKyc] = useState("All");
  const [kind, setKind] = useState("All");
  const [balanceClient, setBalanceClient] = useState<Client | null>(null);
  const [leverageClient, setLeverageClient] = useState<Client | null>(null);
  const [mode, setMode] = useState<Mode>("credit");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [leverage, setLeverage] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    async function loadClients() {
      try {
        const response = await fetch(
          "/api/v1/broker/clients/?page=1&limit=100",
          {
            headers: {
              Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
            },
          },
        );
        if (!response.ok) throw new Error("Unable to load clients.");
        const data = (await response.json()) as {
          items: Array<{
            id: string;
            first_name: string;
            last_name: string;
            email: string;
            status: string;
          }>;
        };
        setClients(
          data.items.map((client) => ({
            id: client.id,
            name: `${client.first_name} ${client.last_name}`,
            email: client.email,
            accountId: "—",
            kind: "Live",
            leverage: "—",
            equity: 0,
            balance: 0,
            kyc: "Pending",
            state: client.status === "SUSPENDED" ? "Suspended" : "Active",
            initials: `${client.first_name[0] ?? ""}${client.last_name[0] ?? ""}`,
          })),
        );
      } catch (error) {
        setNotice(
          error instanceof Error ? error.message : "Unable to load clients.",
        );
      } finally {
        setLoading(false);
      }
    }
    void loadClients();
  }, []);
  const filtered = useMemo(
    () =>
      clients.filter((client) => {
        const term = query.toLowerCase();
        return (
          (!term ||
            client.name.toLowerCase().includes(term) ||
            client.accountId.toLowerCase().includes(term)) &&
          (kyc === "All" || client.kyc === kyc) &&
          (kind === "All" || client.kind === kind)
        );
      }),
    [clients, kind, kyc, query],
  );
  const toggleState = async (id: string) => {
    const client = clients.find((item) => item.id === id);
    if (!client) return;
    const nextStatus = client.state === "Active" ? "SUSPENDED" : "ACTIVE";
    try {
      const response = await fetch(`/api/v1/broker/clients/${id}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
        },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!response.ok) throw new Error("Client status update was rejected.");
      setClients((current) =>
        current.map((item) =>
          item.id === id
            ? {
                ...item,
                state: nextStatus === "SUSPENDED" ? "Suspended" : "Active",
              }
            : item,
        ),
      );
      setNotice("Client status updated.");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Unable to update client status.",
      );
    }
  };
  const submitBalance = async (event: FormEvent) => {
    event.preventDefault();
    if (!balanceClient || !reason.trim() || Number(amount) <= 0) return;
    const value = Number(amount);
    try {
      const response = await fetch(
        `/api/v1/broker/clients/${balanceClient.id}/adjust-balance`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${localStorage.getItem("access_token") ?? ""}`,
          },
          body: JSON.stringify({
            amount: value,
            operation: mode,
            reason: reason.trim(),
          }),
        },
      );
      if (!response.ok) throw new Error("Balance adjustment was rejected.");
      const delta = mode === "credit" ? value : -value;
      setClients((current) =>
        current.map((client) =>
          client.id === balanceClient.id
            ? {
                ...client,
                balance: client.balance + delta,
                equity: client.equity + delta,
              }
            : client,
        ),
      );
      setBalanceClient(null);
      setNotice("Balance adjustment submitted and audit logged.");
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Unable to adjust balance.",
      );
    }
  };
  const submitLeverage = (event: FormEvent) => {
    event.preventDefault();
    if (!leverageClient || !leverage) return;
    setClients((current) =>
      current.map((client) =>
        client.id === leverageClient.id ? { ...client, leverage } : client,
      ),
    );
    setLeverageClient(null);
    setNotice("Leverage updated for the trading account.");
  };
  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--bg-primary)] px-4 py-10 text-[var(--text-secondary)] sm:px-6 lg:px-8">
        Loading clients...
      </main>
    );
  }
  return (
    <main className="min-h-screen bg-[#070A11] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-[1480px]">
        <header className="mb-7 flex flex-col gap-5 border-b border-slate-800/80 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[.2em] text-cyan-400">
              Broker administration / accounts
            </p>
            <h1 className="mt-2 text-3xl font-semibold text-white">
              Client management
            </h1>
            <p className="mt-2 text-sm text-slate-500">
              Monitor account health, KYC readiness, and wallet controls.
            </p>
          </div>
          <span className="flex items-center gap-2 rounded-md border border-slate-800 bg-[#0D121F] px-3 py-2 text-xs text-emerald-300">
            <span className="size-2 rounded-full bg-emerald-400" /> Live
            registry
          </span>
        </header>
        <div className="mb-5 grid gap-3 sm:grid-cols-3">
          <Stat
            icon={UserRound}
            label="Total clients"
            value={clients.length.toLocaleString()}
          />
          <Stat
            icon={ShieldCheck}
            label="Verified KYC"
            value={`${clients.filter((client) => client.kyc === "Verified").length}/${clients.length}`}
          />
          <Stat
            icon={CircleDollarSign}
            label="Total equity"
            value={money.format(
              clients.reduce((sum, client) => sum + client.equity, 0),
            )}
          />
        </div>
        <section className="overflow-hidden rounded-lg border border-slate-800/80 bg-[#0D121F]">
          <div className="flex flex-col gap-3 border-b border-slate-800/80 p-4 lg:flex-row lg:items-center">
            <div className="flex flex-1 flex-col gap-3 sm:flex-row">
              <label className="relative block flex-1 sm:max-w-sm">
                <Search
                  className="absolute left-3 top-2.5 text-slate-500"
                  size={16}
                />
                <input
                  className="w-full rounded-md border border-slate-700 bg-[#070A11] py-2 pl-9 pr-3 text-xs text-white outline-none placeholder:text-slate-600 focus:border-cyan-400/60"
                  placeholder="Search name or account ID"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </label>
              <Filter
                size={16}
                className="hidden self-center text-slate-600 sm:block"
              />
              <Select
                label="KYC status"
                value={kyc}
                options={["All", "Verified", "Pending"]}
                onChange={setKyc}
              />
              <Select
                label="Account type"
                value={kind}
                options={["All", "Live", "Demo"]}
                onChange={setKind}
              />
            </div>
            <span className="text-[11px] text-slate-500">
              Showing {filtered.length} of {clients.length}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-left">
              <thead className="bg-[#0A0E18] text-[10px] uppercase tracking-wider text-slate-500">
                <tr>
                  {[
                    "Client",
                    "Account",
                    "Leverage",
                    "Equity",
                    "Balance",
                    "KYC",
                    "Status",
                    "Actions",
                  ].map((heading) => (
                    <th
                      className="px-4 py-3 font-medium first:pl-6 last:pr-6"
                      key={heading}
                    >
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {filtered.map((client) => (
                  <tr
                    className="group hover:bg-cyan-500/[.025]"
                    key={client.id}
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <span className="grid size-9 place-items-center rounded-full border border-cyan-400/20 bg-cyan-400/10 text-[10px] font-bold text-cyan-200">
                          {client.initials}
                        </span>
                        <span>
                          <strong className="block text-xs text-slate-200">
                            {client.name}
                          </strong>
                          <small className="text-[10px] text-slate-500">
                            {client.email}
                          </small>
                        </span>
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <strong className="block font-mono text-xs text-slate-200">
                        {client.accountId}
                      </strong>
                      <small className="text-[10px] text-slate-500">
                        {client.kind}
                      </small>
                    </td>
                    <td className="px-4 py-4 font-mono text-xs text-slate-300">
                      {client.leverage}
                    </td>
                    <td className="px-4 py-4 text-xs font-semibold text-slate-200">
                      {money.format(client.equity)}
                    </td>
                    <td className="px-4 py-4 text-xs text-slate-400">
                      {money.format(client.balance)}
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`text-[10px] font-semibold ${client.kyc === "Verified" ? "text-emerald-300" : "text-amber-300"}`}
                      >
                        {client.kyc}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`rounded px-2 py-1 text-[10px] font-semibold ${client.state === "Active" ? "bg-emerald-400/10 text-emerald-300" : "bg-rose-400/10 text-rose-300"}`}
                      >
                        {client.state}
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex gap-1">
                        <ActionButton
                          icon={client.state === "Active" ? Ban : Check}
                          label={
                            client.state === "Active"
                              ? "Suspend account"
                              : "Activate account"
                          }
                          onClick={() => toggleState(client.id)}
                        />
                        <ActionButton
                          icon={CircleDollarSign}
                          label="Adjust balance"
                          onClick={() => {
                            setBalanceClient(client);
                            setMode("credit");
                            setAmount("");
                            setReason("");
                          }}
                        />
                        <ActionButton
                          icon={Edit3}
                          label="Change leverage"
                          onClick={() => {
                            setLeverageClient(client);
                            setLeverage(client.leverage);
                          }}
                        />
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {notice && (
          <div className="mt-4 flex items-center justify-between rounded-md border border-cyan-500/20 bg-cyan-500/5 px-4 py-3 text-xs text-cyan-200">
            {notice}
            <button onClick={() => setNotice("")} aria-label="Dismiss message">
              <X size={15} />
            </button>
          </div>
        )}
      </div>
      {balanceClient && (
        <Modal
          title={`Adjust balance · ${balanceClient.name}`}
          onClose={() => setBalanceClient(null)}
        >
          <form className="space-y-4" onSubmit={submitBalance}>
            <div className="flex gap-2">
              <button
                className={`flex-1 rounded-md border px-3 py-2 text-xs ${mode === "credit" ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-200" : "border-slate-700 text-slate-500"}`}
                type="button"
                onClick={() => setMode("credit")}
              >
                <ArrowDownToLine size={14} className="mr-2 inline" />
                Credit
              </button>
              <button
                className={`flex-1 rounded-md border px-3 py-2 text-xs ${mode === "debit" ? "border-rose-400/50 bg-rose-400/10 text-rose-200" : "border-slate-700 text-slate-500"}`}
                type="button"
                onClick={() => setMode("debit")}
              >
                <ArrowUpToLine size={14} className="mr-2 inline" />
                Debit
              </button>
            </div>
            <label className="block text-xs text-slate-400">
              Amount
              <input
                className="modal-input"
                type="number"
                min="0.01"
                step="0.01"
                required
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
            </label>
            <label className="block text-xs text-slate-400">
              Mandatory reason
              <input
                className="modal-input"
                minLength={5}
                required
                value={reason}
                onChange={(event) => setReason(event.target.value)}
              />
            </label>
            <button
              className="w-full rounded-md bg-cyan-400 px-4 py-2.5 text-xs font-bold text-slate-950"
              type="submit"
            >
              Submit {mode}
            </button>
          </form>
        </Modal>
      )}
      {leverageClient && (
        <Modal
          title={`Change leverage · ${leverageClient.accountId}`}
          onClose={() => setLeverageClient(null)}
        >
          <form className="space-y-4" onSubmit={submitLeverage}>
            <label className="block text-xs text-slate-400">
              New leverage
              <select
                className="modal-input"
                value={leverage}
                onChange={(event) => setLeverage(event.target.value)}
              >
                {leverageOptions.map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </label>
            <button
              className="w-full rounded-md bg-cyan-400 px-4 py-2.5 text-xs font-bold text-slate-950"
              type="submit"
            >
              Save leverage
            </button>
          </form>
        </Modal>
      )}
    </main>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof UserRound;
  label: string;
  value: string;
}) {
  return (
    <article className="rounded-lg border border-slate-800/80 bg-[#0D121F] p-4">
      <Icon size={17} className="mb-4 text-cyan-300" />
      <p className="text-[10px] uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <strong className="mt-1 block text-xl text-white">{value}</strong>
    </article>
  );
}
function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="relative">
      <span className="sr-only">{label}</span>
      <select
        className="appearance-none rounded-md border border-slate-700 bg-[#070A11] py-2 pl-3 pr-8 text-xs text-slate-300 outline-none focus:border-cyan-400/60"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option}>{option}</option>
        ))}
      </select>
      <ChevronDown
        className="pointer-events-none absolute right-2 top-2.5 text-slate-500"
        size={14}
      />
    </label>
  );
}
function ActionButton({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof Ban;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      className="grid size-7 place-items-center rounded border border-slate-700 text-slate-400 hover:border-cyan-400/50 hover:text-cyan-200"
      type="button"
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      <Icon size={14} />
    </button>
  );
}
function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/80 p-4 backdrop-blur-sm">
      <section className="w-full max-w-md rounded-lg border border-slate-700 bg-[#0D121F] p-5 shadow-2xl">
        <header className="mb-5 flex items-center justify-between">
          <h2 className="text-base font-semibold text-white">{title}</h2>
          <button
            className="text-slate-500 hover:text-white"
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </header>
        {children}
      </section>
    </div>
  );
}
