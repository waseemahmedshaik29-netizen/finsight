"use client";
import { useCallback, useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  Line,
  ComposedChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";
import {
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  BriefcaseBusiness,
  ChartNoAxesCombined,
  ShieldCheck,
  ScanSearch,
  SlidersHorizontal,
  Sparkles,
  History,
  Plus,
  RefreshCw,
  Download,
  ChevronRight,
  Trash2,
  X,
  Pencil,
  Command,
} from "lucide-react";
import type {
  Portfolio,
  Analytics,
  Macro,
  Fundamentals,
  Filing,
  Citation,
  Snapshot,
  Changes,
  DCFInputs,
  DCF,
  Stress,
  Answer,
  Position,
} from "./types";
const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const colors = [
  "#b7f06b",
  "#7195fb",
  "#bba6ef",
  "#efbc77",
  "#4fbca7",
  "#607086",
];
const money = (n: number | null, d = 0) =>
  n === null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: Math.abs(n) >= 1e7 ? 2 : d,
        notation: Math.abs(n) >= 1e7 ? "compact" : "standard",
      }).format(n);
const pct = (n: number | null) =>
  n === null ? "—" : `${(n * 100).toFixed(2)}%`;
const num = (n: number | null) => (n === null ? "—" : n.toFixed(2));
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const r = await fetch(API + path, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : JSON.stringify(body.detail),
    );
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}
const initialDCF: DCFInputs = {
  revenue: 100e9,
  growth: 0.08,
  margin: 0.25,
  tax_rate: 0.21,
  da_ratio: 0.03,
  capex_ratio: 0.06,
  working_capital_ratio: 0.1,
  wacc: 0.09,
  terminal_growth: 0.025,
  net_debt: 10e9,
  shares: 3e9,
};
const tabs = [
  { name: "Overview", icon: ChartNoAxesCombined },
  { name: "Risk", icon: ShieldCheck },
  { name: "Research", icon: ScanSearch },
  { name: "Scenarios", icon: SlidersHorizontal },
  { name: "AI Analyst", icon: Sparkles },
  { name: "What Changed?", icon: History },
];
export default function Terminal() {
  const [tab, setTab] = useState("Overview"),
    [mode, setMode] = useState("demo"),
    [portfolios, setPortfolios] = useState<Portfolio[]>([]),
    [id, setId] = useState(0),
    [a, setA] = useState<Analytics | null>(null),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true),
    [modal, setModal] = useState<
      "portfolio" | "position" | "editPortfolio" | null
    >(null),
    [editing, setEditing] = useState<Position | null>(null),
    [ticker, setTicker] = useState("MSFT"),
    [tickerInput, setTickerInput] = useState("MSFT"),
    [f, setF] = useState<Fundamentals | null>(null),
    [docs, setDocs] = useState<Filing[]>([]),
    [hits, setHits] = useState<Citation[]>([]),
    [search, setSearch] = useState("risk factors"),
    [m, setM] = useState<Macro | null>(null),
    [dcfInputs, setDCFInputs] = useState(initialDCF),
    [valuation, setValuation] = useState<DCF | null>(null),
    [shock, setShock] = useState(-0.2),
    [rate, setRate] = useState(100),
    [oil, setOil] = useState(-0.25),
    [stress, setStress] = useState<Stress | null>(null),
    [useModel, setUseModel] = useState(false),
    [question, setQuestion] = useState(
      "What are the largest risks in my portfolio?",
    ),
    [answer, setAnswer] = useState<Answer | null>(null),
    [snaps, setSnaps] = useState<Snapshot[]>([]),
    [before, setBefore] = useState(0),
    [after, setAfter] = useState(0),
    [changes, setChanges] = useState<Changes | null>(null);
  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };
  const reload = useCallback(
    async (selected: number) => {
      const p = await api<Portfolio[]>("/portfolios");
      setPortfolios(p);
      if (selected) {
        setA(
          await api<Analytics>(
            `/portfolios/${selected}/analytics?mode=${mode}`,
          ),
        );
      } else setA(null);
    },
    [mode],
  );
  useEffect(() => {
    let active = true;
    api<Portfolio[]>("/portfolios")
      .then((p) => {
        if (active) {
          setPortfolios(p);
          setId(p[0]?.id || 0);
          setLoading(false);
        }
      })
      .catch((e) => {
        setError(
          "Backend unavailable. Start the API on port 8000. " + e.message,
        );
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!id) {
      setA(null);
      return;
    }
    let active = true;
    setLoading(true);
    setA(null);
    setError("");
    api<Analytics>(`/portfolios/${id}/analytics?mode=${mode}`)
      .then((data) => {
        if (active) setA(data);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, mode]);
  useEffect(() => {
    setF(null);
    setDocs([]);
    setHits([]);
    setM(null);
    setStress(null);
    setAnswer(null);
    setChanges(null);
    setValuation(null);
    setSnaps([]);
  }, [id, mode]);
  useEffect(() => {
    if (tab !== "Research") return;
    let active = true;
    setF(null);
    setDocs([]);
    setHits([]);
    setError("");
    Promise.all([
      api<Fundamentals>(`/companies/${ticker}/fundamentals?mode=${mode}`),
      api<{ documents: Filing[] }>(`/companies/${ticker}/filings?mode=${mode}`),
    ])
      .then(([facts, filings]) => {
        if (active) {
          setF(facts);
          setDocs(filings.documents);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [tab, ticker, mode]);
  useEffect(() => {
    if (tab !== "Scenarios") return;
    let active = true;
    api<Macro>(`/macro?mode=${mode}`)
      .then((x) => {
        if (active) setM(x);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [tab, mode]);
  const loadSnaps = useCallback(async () => {
    const data = await api<Snapshot[]>(`/portfolios/${id}/snapshots`);
    setSnaps(data);
    const eligible = data.filter((s) => s.mode === mode);
    setAfter(eligible[0]?.id || 0);
    setBefore(eligible[1]?.id || 0);
  }, [id, mode]);
  useEffect(() => {
    if (tab === "What Changed?" && id)
      loadSnaps().catch((e) => setError(e.message));
  }, [tab, id, loadSnaps]);
  const selected = portfolios.find((p) => p.id === id);
  const allocation = a
    ? [
        ...a.holdings.map((h) => ({ name: h.ticker, value: h.value })),
        { name: "Cash", value: a.portfolio.cash },
      ].filter((x) => x.value > 0)
    : [];
  const exportReport = () =>
    run(async () => {
      const r = await fetch(`${API}/portfolios/${id}/report?mode=${mode}`);
      if (!r.ok) throw new Error("Report unavailable");
      const text = await r.text();
      const url = URL.createObjectURL(
        new Blob([text], { type: "text/markdown" }),
      );
      const el = document.createElement("a");
      el.href = url;
      el.download = "finsight-committee-report.md";
      el.click();
      URL.revokeObjectURL(url);
      setNotice("Investment committee report downloaded.");
    });
  const saveForm = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void run(async () => {
      if (modal === "portfolio" || modal === "editPortfolio") {
        const body = {
          name: data.get("name"),
          benchmark: String(data.get("benchmark")).toUpperCase(),
          cash: Number(data.get("cash")),
        };
        const p = await api<Portfolio>(
          modal === "portfolio" ? "/portfolios" : `/portfolios/${id}`,
          {
            method: modal === "portfolio" ? "POST" : "PUT",
            body: JSON.stringify(body),
          },
        );
        await reload(p.id);
        setId(p.id);
      } else {
        await api(
          `/portfolios/${id}/positions${editing ? "/" + editing.id : ""}`,
          {
            method: editing ? "PUT" : "POST",
            body: JSON.stringify({
              ticker: String(data.get("ticker")).toUpperCase(),
              quantity: Number(data.get("quantity")),
              cost_basis: Number(data.get("cost_basis")),
            }),
          },
        );
        await reload(id);
      }
      setModal(null);
      setEditing(null);
      setNotice("Portfolio saved.");
    });
  };
  return (
    <div className="shell">
      <aside>
        <a className="brand" href="/" aria-label="FinSight home">
          <span className="brand-icon">
            <Activity size={22} />
          </span>
          FinSight<span className="brand-dot">.</span>
        </a>
        <div className="workspace-label">INTELLIGENCE WORKSPACE</div>
        <nav>
          {tabs.map((t) => (
            <button
              key={t.name}
              className={tab === t.name ? "nav active" : "nav"}
              onClick={() => {
                setTab(t.name);
                setError("");
              }}
            >
              <t.icon size={18} />
              {t.name}
              {t.name === "What Changed?" && <span className="new">NEW</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="system-dot" />
          Local research terminal
          <p>
            Deterministic analytics
            <br />
            Evidence you can inspect
          </p>
          <div className="avatar">W</div>
          <span>
            Analyst workspace<small>FinSight / v1.0</small>
          </span>
        </div>
      </aside>
      <div className="main-wrap">
        <header className="topbar">
          <span>
            <BriefcaseBusiness size={15} /> Workspace <ChevronRight size={14} />
            <b>{selected?.name || "Portfolio"}</b>
          </span>
          <div>
            <span className="key">
              <Command size={12} /> Research terminal
            </span>
            <span className="status-dot" />
            Local workspace
          </div>
        </header>
        <main>
          <div className="page-head">
            <div className="eyebrow">PORTFOLIO INTELLIGENCE</div>
            <div className="heading-row">
              <div>
                <h1>
                  {tab === "Overview" ? "Your portfolio, in focus." : tab}
                </h1>
                <p>
                  {
                    (
                      {
                        Overview:
                          "A clear view of performance, concentration and downside risk.",
                        Risk: "Inspect the risk behind your returns.",
                        Research:
                          "Company financials and source-linked filing evidence.",
                        Scenarios:
                          "Explore portfolio exposure under explicit assumptions.",
                        "AI Analyst":
                          "Ask questions. Inspect the calculations behind every answer.",
                        "What Changed?":
                          "Compare stored snapshots and follow the evidence.",
                      } as Record<string, string>
                    )[tab]
                  }
                </p>
              </div>
              <div className="actions">
                <button
                  className="secondary"
                  onClick={exportReport}
                  disabled={!a || busy}
                >
                  <Download size={15} />
                  Export report
                </button>
                <button
                  className="primary"
                  onClick={() => {
                    setEditing(null);
                    setModal("position");
                  }}
                  disabled={!id}
                >
                  <Plus size={16} />
                  Add position
                </button>
              </div>
            </div>
          </div>
          <div className="toolbar">
            <div>
              <select
                aria-label="Portfolio"
                value={id}
                onChange={(e) => setId(Number(e.target.value))}
              >
                <option value={0}>Select portfolio</option>
                {portfolios.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
              <button
                className="icon-button"
                title="Create portfolio"
                onClick={() => setModal("portfolio")}
              >
                <Plus size={16} />
              </button>
              <button
                className="icon-button"
                title="Edit portfolio"
                disabled={!id}
                onClick={() => setModal("editPortfolio")}
              >
                <Pencil size={14} />
              </button>
            </div>
            <div>
              <span className={"mode " + mode}>
                {mode === "demo" ? "SYNTHETIC DEMO" : "PUBLIC DATA"}
              </span>
              <select
                aria-label="Data mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="demo">Demo data</option>
                <option value="live">Live sources</option>
              </select>
              <button
                className="icon-button"
                title="Refresh analytics"
                disabled={busy || !id}
                onClick={() =>
                  run(async () => {
                    await reload(id);
                    setNotice(
                      "Analytics refreshed. Public sources use a 12-hour cache.",
                    );
                  })
                }
              >
                <RefreshCw size={15} className={busy ? "spin" : ""} />
              </button>
            </div>
          </div>
          {error && (
            <div role="alert" className="alert">
              {error}
            </div>
          )}
          {notice && (
            <div role="status" className="notice">
              {notice}
            </div>
          )}
          {loading && (
            <div className="loading">Loading portfolio intelligence…</div>
          )}
          {!loading && !a && !error && (
            <div className="empty">
              <BriefcaseBusiness />
              <h2>Start your portfolio</h2>
              <p>
                Create a portfolio, then add a position or a positive cash
                balance.
              </p>
              <button className="primary" onClick={() => setModal("portfolio")}>
                Create portfolio
              </button>
            </div>
          )}
          {a && (
            <>
              {tab === "Overview" && (
                <>
                  <div className="metrics">
                    <Metric
                      label="PORTFOLIO VALUE"
                      value={money(a.value)}
                      detail={`${a.holdings.length} holdings · ${a.portfolio.benchmark} benchmark`}
                      icon="value"
                    />
                    <Metric
                      label="SAMPLE RETURN"
                      value={pct(a.total_return)}
                      detail={`${a.start} → ${a.end}`}
                      positive={a.total_return >= 0}
                    />
                    <Metric
                      label="ANNUALIZED VOLATILITY"
                      value={pct(a.volatility)}
                      detail={`${a.observations} daily return observations`}
                    />
                    <Metric
                      label="SHARPE RATIO"
                      value={num(a.sharpe)}
                      detail="4% assumed risk-free rate"
                    />
                  </div>
                  <div className="overview-grid">
                    <section className="panel performance">
                      <PanelTitle
                        title="Portfolio performance"
                        sub="Growth of $100 · constant current holdings"
                      />
                      <div className="chart-meta">
                        <span>
                          <i style={{ background: colors[0] }} />
                          Portfolio
                        </span>
                        <span>
                          <i style={{ background: colors[1] }} />
                          {a.portfolio.benchmark}
                        </span>
                        <b>FULL SAMPLE</b>
                      </div>
                      <div className="chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart data={a.curve}>
                            <defs>
                              <linearGradient
                                id="green"
                                x1="0"
                                y1="0"
                                x2="0"
                                y2="1"
                              >
                                <stop
                                  offset="0%"
                                  stopColor="#b7f06b"
                                  stopOpacity={0.18}
                                />
                                <stop
                                  offset="100%"
                                  stopColor="#b7f06b"
                                  stopOpacity={0}
                                />
                              </linearGradient>
                            </defs>
                            <CartesianGrid
                              vertical={false}
                              stroke="#263039"
                              strokeDasharray="3 4"
                            />
                            <XAxis
                              dataKey="date"
                              tickFormatter={(d) =>
                                new Date(d).toLocaleDateString("en-US", {
                                  month: "short",
                                  timeZone: "UTC",
                                })
                              }
                              minTickGap={55}
                              stroke="#68767d"
                              tickLine={false}
                              axisLine={false}
                            />
                            <YAxis
                              domain={["auto", "auto"]}
                              stroke="#68767d"
                              tickLine={false}
                              axisLine={false}
                              width={35}
                            />
                            <Tooltip
                              contentStyle={tooltipStyle}
                              formatter={(v) => num(Number(v))}
                            />
                            <Area
                              type="monotone"
                              dataKey="portfolio"
                              stroke={colors[0]}
                              fill="url(#green)"
                              strokeWidth={2}
                            />
                            <Line
                              dataKey="benchmark"
                              dot={false}
                              stroke={colors[1]}
                              strokeWidth={1.5}
                            />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </div>
                      <div className="chart-footer">
                        <span>As of {a.end}</span>
                        <span>
                          Annualized return{" "}
                          <b className="green">{pct(a.annual_return)}</b>
                        </span>
                      </div>
                    </section>
                    <section className="panel">
                      <PanelTitle
                        title="Capital allocation"
                        sub="Current position weights"
                      />
                      <div className="donut">
                        <ResponsiveContainer width="100%" height={190}>
                          <PieChart>
                            <Pie
                              data={allocation}
                              dataKey="value"
                              innerRadius={64}
                              outerRadius={82}
                              paddingAngle={3}
                              stroke="none"
                            >
                              {allocation.map((x, i) => (
                                <Cell
                                  key={x.name}
                                  fill={colors[i % colors.length]}
                                />
                              ))}
                            </Pie>
                            <Tooltip
                              contentStyle={tooltipStyle}
                              formatter={(v) => money(Number(v))}
                            />
                          </PieChart>
                        </ResponsiveContainer>
                        <div className="donut-center">
                          <strong>{a.holdings.length}</strong>
                          <span>HOLDINGS</span>
                        </div>
                      </div>
                      <div className="allocation-list">
                        {allocation.map((x, i) => (
                          <div key={x.name}>
                            <span>
                              <i
                                style={{
                                  background: colors[i % colors.length],
                                }}
                              />
                              {x.name}
                            </span>
                            <b>{pct(x.value / a.value)}</b>
                          </div>
                        ))}
                      </div>
                    </section>
                  </div>
                  <div className="lower-grid">
                    <section className="panel">
                      <PanelTitle
                        title="Your holdings"
                        sub="Current quantities · USD"
                        extra={
                          <span className="badge">
                            {a.holdings.length} assets
                          </span>
                        }
                      />
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>ASSET</th>
                              <th>PRICE</th>
                              <th>VALUE</th>
                              <th>WEIGHT</th>
                              <th>UNREALIZED P/L</th>
                              <th />
                            </tr>
                          </thead>
                          <tbody>
                            {a.holdings.map((h, i) => (
                              <tr key={h.id}>
                                <td>
                                  <div className="asset">
                                    <span
                                      style={{
                                        color: colors[i % colors.length],
                                        background:
                                          colors[i % colors.length] + "15",
                                      }}
                                    >
                                      {h.ticker.slice(0, 2)}
                                    </span>
                                    <div>
                                      <b>{h.ticker}</b>
                                      <small>{h.name}</small>
                                    </div>
                                  </div>
                                </td>
                                <td>{money(h.price, 2)}</td>
                                <td>{money(h.value)}</td>
                                <td>{pct(h.weight)}</td>
                                <td className={h.pnl >= 0 ? "green" : "red"}>
                                  {money(h.pnl)}
                                </td>
                                <td>
                                  <button
                                    className="icon-button"
                                    title={"Edit " + h.ticker}
                                    onClick={() => {
                                      setEditing(h);
                                      setModal("position");
                                    }}
                                  >
                                    <Pencil size={13} />
                                  </button>
                                  <button
                                    className="icon-button"
                                    title={"Remove " + h.ticker}
                                    onClick={() =>
                                      run(async () => {
                                        await api(
                                          `/portfolios/${id}/positions/${h.id}`,
                                          { method: "DELETE" },
                                        );
                                        await reload(id);
                                      })
                                    }
                                  >
                                    <X size={14} />
                                  </button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      {!a.holdings.length && (
                        <p className="empty-text">
                          No positions. Add your first holding.
                        </p>
                      )}
                    </section>
                    <section className="panel insight">
                      <div className="insight-icon">
                        <History size={21} />
                      </div>
                      <span className="eyebrow">THE CHANGE ENGINE</span>
                      <h2>
                        What moved.
                        <br />
                        What matters.
                      </h2>
                      <p>
                        Capture today’s portfolio. Compare value, risk,
                        allocation, macro observations and new filings with an
                        earlier snapshot.
                      </p>
                      <button onClick={() => setTab("What Changed?")}>
                        Open What Changed? <ArrowUpRight size={16} />
                      </button>
                      <div className="insight-foot">
                        Stored evidence. Observable differences.
                      </div>
                    </section>
                  </div>
                </>
              )}
              {tab === "Risk" && (
                <>
                  <div className="metrics">
                    <Metric
                      label="1-DAY 95% VaR"
                      value={money(a.var_dollars)}
                      detail="Historical loss quantile"
                    />
                    <Metric
                      label="CONDITIONAL VaR"
                      value={pct(a.cvar95)}
                      detail="Mean loss in the worst 5% tail"
                    />
                    <Metric
                      label="MAX DRAWDOWN"
                      value={pct(a.max_drawdown)}
                      detail="Peak to trough · sample window"
                    />
                    <Metric
                      label="BETA / ALPHA"
                      value={`${num(a.beta)} / ${pct(a.alpha)}`}
                      detail="CAPM · annual arithmetic alpha"
                    />
                  </div>
                  <div className="two-columns">
                    <section className="panel">
                      <PanelTitle
                        title="Risk contribution"
                        sub="Current-weight covariance decomposition"
                      />
                      <div className="chart">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={Object.entries(a.risk_contribution).map(
                              ([ticker, value]) => ({
                                ticker,
                                value: value * 100,
                              }),
                            )}
                          >
                            <CartesianGrid vertical={false} stroke="#263039" />
                            <XAxis dataKey="ticker" stroke="#68767d" />
                            <YAxis stroke="#68767d" unit="%" />
                            <Tooltip contentStyle={tooltipStyle} />
                            <Bar
                              dataKey="value"
                              fill={colors[0]}
                              radius={[4, 4, 0, 0]}
                            />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </section>
                    <section className="panel">
                      <PanelTitle
                        title="Return correlations"
                        sub="Pearson · aligned daily observations"
                      />
                      <div className="table-scroll">
                        <table className="heatmap">
                          <thead>
                            <tr>
                              <th />
                              {a.holdings.map((h) => (
                                <th key={h.ticker}>{h.ticker}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {a.holdings.map((h) => (
                              <tr key={h.ticker}>
                                <th>{h.ticker}</th>
                                {a.holdings.map((j) => {
                                  const value =
                                    a.correlations[h.ticker]?.[j.ticker] || 0;
                                  return (
                                    <td
                                      key={j.ticker}
                                      style={{
                                        background: `rgba(183,240,107,${Math.max(0.02, value * 0.28)})`,
                                      }}
                                    >
                                      {num(value)}
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="footnote">
                        Negative contributions can occur with hedging assets.
                        Correlations do not measure diversification under every
                        scenario.
                      </p>
                    </section>
                  </div>
                  <section className="panel">
                    <PanelTitle
                      title="Rolling volatility"
                      sub="21-observation window · annualized"
                    />
                    <div className="chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={a.rolling_volatility}>
                          <CartesianGrid vertical={false} stroke="#263039" />
                          <XAxis
                            dataKey="date"
                            minTickGap={70}
                            stroke="#68767d"
                          />
                          <YAxis
                            tickFormatter={(v) => pct(v)}
                            stroke="#68767d"
                          />
                          <Tooltip
                            contentStyle={tooltipStyle}
                            formatter={(v) => pct(Number(v))}
                          />
                          <Area
                            dataKey="value"
                            fill="#7195fb22"
                            stroke={colors[1]}
                          />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </section>
                  <div className="metrics compact">
                    <Metric
                      label="SORTINO"
                      value={num(a.sortino)}
                      detail="Downside semideviation"
                    />
                    <Metric
                      label="HISTORICAL VaR"
                      value={pct(a.var95)}
                      detail="1 day · 95% confidence"
                    />
                  </div>
                </>
              )}
              {tab === "Research" && (
                <>
                  <form
                    className="research-controls"
                    onSubmit={(e) => {
                      e.preventDefault();
                      setTicker(tickerInput);
                    }}
                  >
                    <label>
                      Company ticker
                      <input
                        value={tickerInput}
                        onChange={(e) =>
                          setTickerInput(
                            e.target.value
                              .toUpperCase()
                              .replace(/[^A-Z0-9.\-]/g, "")
                              .slice(0, 12),
                          )
                        }
                      />
                    </label>
                    <button className="secondary" disabled={!tickerInput}>
                      Load company
                    </button>
                    <span className="muted">
                      Select a held company or enter a US issuer ticker.
                    </span>
                  </form>
                  {f && (
                    <>
                      <div className="metrics">
                        <Metric
                          label="REVENUE"
                          value={money(f.revenue)}
                          detail={f.period || "Unavailable period"}
                        />
                        <Metric
                          label="OPERATING MARGIN"
                          value={pct(f.operating_margin)}
                          detail="Operating income / revenue"
                        />
                        <Metric
                          label="FREE CASH FLOW"
                          value={money(f.free_cash_flow)}
                          detail="Operating cash flow − CapEx"
                        />
                        <Metric
                          label="RETURN ON EQUITY"
                          value={pct(f.roe)}
                          detail="Annual income / period-end equity"
                        />
                      </div>
                      <section className="panel">
                        <PanelTitle
                          title={f.name + " · financial statements"}
                          sub={f.source}
                        />
                        <div className="statement-grid">
                          {[
                            ["Net income", f.net_income],
                            ["Operating income", f.operating_income],
                            ["Cash", f.cash],
                            ["Long-term debt*", f.debt],
                            ["Assets", f.assets],
                            ["Equity", f.equity],
                            ["Operating cash flow", f.operating_cash_flow],
                            ["Capital expenditure", f.capex],
                          ].map(([key, value]) => (
                            <div key={String(key)}>
                              <span>{key}</span>
                              <b>{money(value as number | null)}</b>
                            </div>
                          ))}
                        </div>
                        {f.debt_note && (
                          <p className="footnote">{f.debt_note}</p>
                        )}
                        <button
                          className="secondary"
                          onClick={() => {
                            setValuation(null);
                            setDCFInputs({
                              ...initialDCF,
                              revenue: f.revenue || initialDCF.revenue,
                              shares: f.shares || initialDCF.shares,
                              margin: f.operating_margin || initialDCF.margin,
                              net_debt: (f.debt || 0) - (f.cash || 0),
                            });
                            setNotice(
                              "Available facts loaded into the DCF. Review all assumptions and debt definitions.",
                            );
                          }}
                        >
                          Use available facts in DCF
                        </button>
                      </section>
                    </>
                  )}
                  <div className="two-columns">
                    <section className="panel">
                      <PanelTitle
                        title="Filing library"
                        sub="Latest three 10-K / 10-Q / 8-K documents"
                      />
                      {docs.map((d) => (
                        <a
                          className="filing"
                          key={d.id}
                          href={d.url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <span className="form-tag">{d.form}</span>
                          <div>
                            <b>{d.title}</b>
                            <small>
                              {d.date} · {d.id}
                            </small>
                          </div>
                          <ArrowUpRight size={16} />
                        </a>
                      ))}
                      {!docs.length && (
                        <p className="empty-text">No documents loaded.</p>
                      )}
                    </section>
                    <section className="panel">
                      <PanelTitle
                        title="Search the evidence"
                        sub="Lexical retrieval · source links and text offsets"
                      />
                      <form
                        onSubmit={(e) => {
                          e.preventDefault();
                          run(async () => {
                            const r = await api<{ results: Citation[] }>(
                              `/companies/${ticker}/filings/search?q=${encodeURIComponent(search)}&mode=${mode}`,
                            );
                            setHits(r.results);
                            if (!r.results.length)
                              setNotice("No matching passages found.");
                          });
                        }}
                        className="search-form"
                      >
                        <input
                          aria-label="Search filings"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          minLength={3}
                          required
                        />
                        <button className="primary" disabled={busy}>
                          Search
                        </button>
                      </form>
                      {hits.map((h, i) => (
                        <div className="citation" key={i}>
                          <a href={h.url} target="_blank" rel="noreferrer">
                            {h.form} · {h.citation} <ArrowUpRight size={12} />
                          </a>
                          <p>{h.text}</p>
                        </div>
                      ))}
                    </section>
                  </div>
                  <section className="panel">
                    <PanelTitle
                      title="Discounted cash flow"
                      sub="Five-year unlevered free cash flow + Gordon terminal value"
                    />
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        run(async () => {
                          setValuation(
                            await api<DCF>("/valuation/dcf", {
                              method: "POST",
                              body: JSON.stringify(dcfInputs),
                            }),
                          );
                        });
                      }}
                    >
                      <div className="dcf-inputs">
                        {(Object.keys(initialDCF) as (keyof DCFInputs)[]).map(
                          (k) => (
                            <label key={k}>
                              {k.replaceAll("_", " ")}
                              <input
                                type="number"
                                step="any"
                                required
                                value={dcfInputs[k]}
                                onChange={(e) => {
                                  setValuation(null);
                                  setDCFInputs({
                                    ...dcfInputs,
                                    [k]: Number(e.target.value),
                                  });
                                }}
                              />
                            </label>
                          ),
                        )}
                      </div>
                      <div className="form-footer">
                        <span>
                          Rates are decimals: 0.09 = 9%. Currency and shares use
                          full units.
                        </span>
                        <button className="primary" disabled={busy}>
                          Calculate valuation
                        </button>
                      </div>
                    </form>
                    {valuation && (
                      <>
                        <div className="metrics compact">
                          <Metric
                            label="IMPLIED SHARE PRICE"
                            value={money(valuation.price, 2)}
                            detail="Analyst assumptions"
                          />
                          <Metric
                            label="ENTERPRISE VALUE"
                            value={money(valuation.enterprise_value)}
                            detail="Discounted cash flows + terminal"
                          />
                          <Metric
                            label="EQUITY VALUE"
                            value={money(valuation.equity_value)}
                            detail="Enterprise value − net debt"
                          />
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>WACC / TERMINAL GROWTH</th>
                                {valuation.growth_columns.map((g) => (
                                  <th key={g}>{pct(g)}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {valuation.sensitivity.map((row) => (
                                <tr key={row.wacc}>
                                  <th>{pct(row.wacc)}</th>
                                  {row.values.map((v, i) => (
                                    <td key={i}>{money(v, 2)}</td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <div className="table-scroll">
                          <table>
                            <thead>
                              <tr>
                                <th>FORECAST YEAR</th>
                                <th>REVENUE</th>
                                <th>FREE CASH FLOW</th>
                                <th>PRESENT VALUE</th>
                              </tr>
                            </thead>
                            <tbody>
                              {valuation.forecast.map((row) => (
                                <tr key={row.year}>
                                  <td>{row.year}</td>
                                  <td>{money(row.revenue)}</td>
                                  <td>{money(row.fcf)}</td>
                                  <td>{money(row.present_value)}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </>
                    )}
                  </section>
                </>
              )}
              {tab === "Scenarios" && (
                <>
                  {m && (
                    <div className="metrics">
                      {m.series.map((s) => (
                        <Metric
                          key={s.id}
                          label={s.name.toUpperCase()}
                          value={`${s.value.toFixed(2)}${s.unit === "%" ? "%" : ""}`}
                          detail={`${s.date} · ${s.unit}`}
                        />
                      ))}
                    </div>
                  )}
                  <section className="panel">
                    <PanelTitle
                      title="Scenario lab"
                      sub="Explicit shocks · inspect the assumptions"
                    />
                    <div className="scenario-presets">
                      {[
                        ["Equity selloff", -0.2, 0, 0],
                        ["Rates +100 bps", 0, 100, 0],
                        ["Oil −25%", 0, 0, -0.25],
                        ["Recession mix", -0.25, -100, -0.3],
                      ].map(([name, e, r, o]) => (
                        <button
                          className="secondary"
                          key={name}
                          onClick={() => {
                            setStress(null);
                            setShock(Number(e));
                            setRate(Number(r));
                            setOil(Number(o));
                          }}
                        >
                          {name}
                        </button>
                      ))}
                    </div>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        run(async () =>
                          setStress(
                            await api<Stress>(
                              `/portfolios/${id}/stress?mode=${mode}`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  market_shock: shock,
                                  rate_bps: rate,
                                  oil_shock: oil,
                                }),
                              },
                            ),
                          ),
                        );
                      }}
                    >
                      <div className="sliders">
                        <label>
                          Market shock <b>{pct(shock)}</b>
                          <input
                            type="range"
                            min={-1}
                            max={1}
                            step={0.01}
                            value={shock}
                            onChange={(e) => {
                              setStress(null);
                              setShock(Number(e.target.value));
                            }}
                          />
                        </label>
                        <label>
                          Rate change <b>{rate} bps</b>
                          <input
                            type="range"
                            min={-500}
                            max={500}
                            step={25}
                            value={rate}
                            onChange={(e) => {
                              setStress(null);
                              setRate(Number(e.target.value));
                            }}
                          />
                        </label>
                        <label>
                          Oil shock <b>{pct(oil)}</b>
                          <input
                            type="range"
                            min={-1}
                            max={1}
                            step={0.01}
                            value={oil}
                            onChange={(e) => {
                              setStress(null);
                              setOil(Number(e.target.value));
                            }}
                          />
                        </label>
                      </div>
                      <button className="primary" disabled={busy}>
                        Run stress test <ArrowUpRight size={16} />
                      </button>
                    </form>
                    {stress && (
                      <>
                        <div className="stress-result">
                          <span>ESTIMATED SCENARIO IMPACT</span>
                          <strong
                            className={stress.impact < 0 ? "red" : "green"}
                          >
                            {money(stress.impact)}{" "}
                            <small>{pct(stress.return)}</small>
                          </strong>
                          <p>{stress.method}</p>
                        </div>
                        <table>
                          <thead>
                            <tr>
                              <th>POSITION</th>
                              <th>ASSUMED SHOCK</th>
                              <th>DOLLAR IMPACT</th>
                            </tr>
                          </thead>
                          <tbody>
                            {stress.positions.map((x) => (
                              <tr key={x.ticker}>
                                <td>{x.ticker}</td>
                                <td>{pct(x.shock)}</td>
                                <td>{money(x.impact)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </>
                    )}
                  </section>
                  <p className="footnote">
                    {m?.source}. Scenario rate sensitivities are documented
                    sector assumptions, not estimated causal exposures.
                  </p>
                </>
              )}
              {tab === "AI Analyst" && (
                <div className="analyst-grid">
                  <section className="panel">
                    <div className="analyst-heading">
                      <Sparkles size={26} />
                      <h2>Your evidence desk.</h2>
                      <p>Portfolio calculations first. Explanations follow.</p>
                    </div>
                    <div className="prompts">
                      {[
                        "What are the largest risks in my portfolio?",
                        "Show macro rates and inflation observations",
                        "Search MSFT filing risk factors",
                      ].map((q) => (
                        <button key={q} onClick={() => setQuestion(q)}>
                          {q}
                          <ArrowUpRight size={14} />
                        </button>
                      ))}
                    </div>
                    <form
                      onSubmit={(e) => {
                        e.preventDefault();
                        run(async () =>
                          setAnswer(
                            await api<Answer>(
                              `/portfolios/${id}/analyst?mode=${mode}`,
                              {
                                method: "POST",
                                body: JSON.stringify({
                                  question,
                                  use_model: useModel,
                                }),
                              },
                            ),
                          ),
                        );
                      }}
                    >
                      <textarea
                        aria-label="Analyst question"
                        value={question}
                        onChange={(e) => setQuestion(e.target.value)}
                        minLength={3}
                        maxLength={2000}
                        required
                      />
                      <div className="form-footer">
                        <label className="model-toggle">
                          <input
                            type="checkbox"
                            checked={useModel}
                            onChange={(e) => setUseModel(e.target.checked)}
                          />
                          Optional model planner
                        </label>
                        <button className="primary" disabled={busy}>
                          Ask analyst <ArrowUpRight size={16} />
                        </button>
                      </div>
                    </form>
                    {answer && (
                      <div className="answer">
                        <span className="eyebrow">{answer.engine}</span>
                        {answer.warning && (
                          <div className="notice">{answer.warning}</div>
                        )}
                        <p>{answer.answer}</p>
                        {answer.citations.map((c, i) => (
                          <div className="citation" key={i}>
                            <a href={c.url} target="_blank" rel="noreferrer">
                              {c.citation}
                            </a>
                            <p>{c.text}</p>
                          </div>
                        ))}
                        <small>{answer.limitation}</small>
                      </div>
                    )}
                  </section>
                  <section className="panel">
                    <PanelTitle
                      title="Tool trace"
                      sub="Inspect the evidence path"
                    />
                    {answer ? (
                      answer.tools.map((t, i) => (
                        <div className="tool" key={i}>
                          <span>{String(i + 1).padStart(2, "0")}</span>
                          <div>
                            <b>{t.name.replaceAll("_", " ")}</b>
                            <small>
                              {t.endpoint ||
                                t.ticker ||
                                "Public-source adapter"}
                            </small>
                          </div>
                          <ShieldCheck size={16} />
                        </div>
                      ))
                    ) : (
                      <p className="empty-text">
                        Ask a question to see which backend tools were used.
                      </p>
                    )}
                    <div className="trace-note">
                      <ShieldCheck size={20} />
                      <p>
                        All displayed numbers come from backend calculations or
                        labeled source observations. The local analyst uses
                        rule-based routing and templates.
                      </p>
                    </div>
                    <button
                      className="secondary"
                      onClick={exportReport}
                      disabled={busy}
                    >
                      <Download size={14} />
                      Committee memo
                    </button>
                  </section>
                </div>
              )}
              {tab === "What Changed?" && (
                <>
                  <section className="panel">
                    <PanelTitle
                      title="Snapshot comparison"
                      sub="Immutable intelligence captures, scoped to this portfolio"
                      extra={
                        <button
                          className="primary"
                          disabled={busy}
                          onClick={() =>
                            run(async () => {
                              await api(
                                `/portfolios/${id}/snapshots?mode=${mode}`,
                                { method: "POST" },
                              );
                              await loadSnaps();
                              setNotice(
                                "Snapshot captured. Edit a holding or refresh live data, then capture another to compare.",
                              );
                            })
                          }
                        >
                          <Plus size={15} />
                          Capture snapshot
                        </button>
                      }
                    />
                    <div className="snapshot-controls">
                      <label>
                        Baseline
                        <select
                          value={before}
                          onChange={(e) => setBefore(Number(e.target.value))}
                        >
                          <option value={0}>Choose earlier capture</option>
                          {snaps
                            .filter((s) => s.mode === mode)
                            .map((s) => (
                              <option value={s.id} key={s.id}>
                                #{s.id} ·{" "}
                                {new Date(s.created_at).toLocaleString()} ·{" "}
                                {money(s.value)}
                              </option>
                            ))}
                        </select>
                      </label>
                      <ChevronRight />
                      <label>
                        Compare with
                        <select
                          value={after}
                          onChange={(e) => setAfter(Number(e.target.value))}
                        >
                          <option value={0}>Choose later capture</option>
                          {snaps
                            .filter((s) => s.mode === mode)
                            .map((s) => (
                              <option value={s.id} key={s.id}>
                                #{s.id} ·{" "}
                                {new Date(s.created_at).toLocaleString()} ·{" "}
                                {money(s.value)}
                              </option>
                            ))}
                        </select>
                      </label>
                      <button
                        className="secondary"
                        disabled={!before || !after || busy}
                        onClick={() =>
                          run(async () =>
                            setChanges(
                              await api<Changes>(
                                `/portfolios/${id}/changes?before=${before}&after=${after}`,
                              ),
                            ),
                          )
                        }
                      >
                        Compare
                      </button>
                    </div>
                    {snaps.length < 2 && (
                      <div className="empty">
                        <History size={32} />
                        <h2>Build an evidence trail.</h2>
                        <p>
                          Capture a baseline, change a position or wait for new
                          source observations, then capture a second snapshot.
                        </p>
                      </div>
                    )}
                  </section>
                  {changes && (
                    <>
                      <section className="panel">
                        <PanelTitle
                          title="Metric changes"
                          sub={changes.summary}
                        />
                        <table>
                          <thead>
                            <tr>
                              <th>METRIC</th>
                              <th>BEFORE</th>
                              <th>AFTER</th>
                              <th>CHANGE</th>
                            </tr>
                          </thead>
                          <tbody>
                            {changes.metrics.map((r) => {
                              const format = (v: number) =>
                                r.metric === "value" ||
                                r.metric === "var_dollars"
                                  ? money(v)
                                  : r.metric === "beta"
                                    ? num(v)
                                    : pct(v);
                              return (
                                <tr key={r.metric}>
                                  <td>{r.metric.replaceAll("_", " ")}</td>
                                  <td>{format(r.before)}</td>
                                  <td>{format(r.after)}</td>
                                  <td>{format(r.delta)}</td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </section>
                      <div className="two-columns">
                        <section className="panel">
                          <PanelTitle
                            title="Allocation drift"
                            sub="Percentage points · additions and removals included"
                          />
                          {changes.allocation.map((r) => (
                            <div className="change-row" key={r.ticker}>
                              <b>{r.ticker}</b>
                              <span>
                                {pct(r.before)} → {pct(r.after)}
                              </span>
                              <span className={r.delta >= 0 ? "green" : "red"}>
                                {r.delta >= 0 ? "+" : ""}
                                {(r.delta * 100).toFixed(2)} pp
                              </span>
                            </div>
                          ))}
                        </section>
                        <section className="panel">
                          <PanelTitle
                            title="Macro & filing events"
                            sub="Observed source changes"
                          />
                          {changes.macro.map((r) => (
                            <div className="change-row" key={r.series}>
                              <b>{r.series}</b>
                              <span>
                                {r.before} → {r.after} {r.unit}
                              </span>
                            </div>
                          ))}
                          {changes.evidence_gaps &&
                            Object.keys(changes.evidence_gaps.before).length +
                              Object.keys(changes.evidence_gaps.after).length >
                              0 && (
                              <p className="alert">
                                Some macro or filing sources were unavailable
                                during capture. Missing evidence cannot
                                establish whether new events occurred.
                              </p>
                            )}
                          {changes.new_filings.map((r) => (
                            <div className="change-row" key={r.id}>
                              <b>{r.ticker}</b>
                              <span>New filing: {r.id}</span>
                            </div>
                          ))}
                          {!changes.new_filings.length && (
                            <p className="footnote">
                              No new IDs in the available filing evidence.
                            </p>
                          )}
                        </section>
                      </div>
                    </>
                  )}
                </>
              )}
              <footer>
                <span>
                  <span className="status-dot" />
                  {a.provenance.source} · as of {a.provenance.as_of}
                </span>
                <details>
                  <summary>Calculation methodology</summary>
                  <p>{a.methodology}</p>
                </details>
              </footer>
            </>
          )}
        </main>
      </div>
      {modal && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
          >
            <button
              className="close icon-button"
              aria-label="Close dialog"
              onClick={() => setModal(null)}
            >
              <X />
            </button>
            <h2 id="modal-title">
              {modal === "portfolio"
                ? "Create portfolio"
                : modal === "editPortfolio"
                  ? "Edit portfolio"
                  : editing
                    ? "Edit position"
                    : "Add position"}
            </h2>
            <form onSubmit={saveForm}>
              {modal === "portfolio" || modal === "editPortfolio" ? (
                <>
                  <label>
                    Portfolio name
                    <input
                      name="name"
                      required
                      maxLength={100}
                      defaultValue={
                        modal === "editPortfolio" ? selected?.name : ""
                      }
                    />
                  </label>
                  <label>
                    Benchmark ticker
                    <input
                      name="benchmark"
                      required
                      pattern="[A-Za-z][A-Za-z0-9.\-]{0,11}"
                      defaultValue={
                        modal === "editPortfolio" ? selected?.benchmark : "SPY"
                      }
                    />
                  </label>
                  <label>
                    Cash balance ($)
                    <input
                      type="number"
                      name="cash"
                      min={0}
                      max={1e12}
                      step="any"
                      required
                      defaultValue={
                        modal === "editPortfolio" ? selected?.cash : 10000
                      }
                    />
                  </label>
                </>
              ) : (
                <>
                  <label>
                    Ticker
                    <input
                      name="ticker"
                      required
                      pattern="[A-Za-z][A-Za-z0-9.\-]{0,11}"
                      defaultValue={editing?.ticker || "AAPL"}
                    />
                  </label>
                  <label>
                    Shares
                    <input
                      type="number"
                      name="quantity"
                      required
                      min={0.000001}
                      max={1e9}
                      step="any"
                      defaultValue={editing?.quantity || 10}
                    />
                  </label>
                  <label>
                    Cost basis per share ($)
                    <input
                      type="number"
                      name="cost_basis"
                      min={0}
                      max={1e7}
                      step="any"
                      required
                      defaultValue={editing?.cost_basis || 180}
                    />
                  </label>
                </>
              )}
              {error && (
                <p role="alert" className="red">
                  {error}
                </p>
              )}
              <button className="primary" disabled={busy}>
                Save {modal === "position" ? "position" : "portfolio"}
              </button>
            </form>
            {modal === "editPortfolio" && (
              <button
                className="danger"
                disabled={busy}
                onClick={() =>
                  run(async () => {
                    await api(`/portfolios/${id}`, { method: "DELETE" });
                    const p = await api<Portfolio[]>("/portfolios");
                    setPortfolios(p);
                    setId(p[0]?.id || 0);
                    setModal(null);
                    setNotice("Portfolio deleted.");
                  })
                }
              >
                <Trash2 size={14} />
                Delete portfolio and snapshots
              </button>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
const tooltipStyle = {
  background: "#172027",
  border: "1px solid #34414a",
  borderRadius: 8,
  color: "#dfe8e9",
  fontSize: 12,
};
function PanelTitle({
  title,
  sub,
  extra,
}: {
  title: string;
  sub: string;
  extra?: React.ReactNode;
}) {
  return (
    <div className="panel-title">
      <div>
        <h2>{title}</h2>
        <p>{sub}</p>
      </div>
      {extra}
    </div>
  );
}
function Metric({
  label,
  value,
  detail,
  positive,
  icon,
}: {
  label: string;
  value: string;
  detail: string;
  positive?: boolean;
  icon?: string;
}) {
  return (
    <div className="metric">
      <span>
        {label}
        {icon && <BriefcaseBusiness size={14} />}
      </span>
      <strong
        className={positive === undefined ? "" : positive ? "green" : "red"}
      >
        {value}
        {positive !== undefined &&
          (positive ? (
            <ArrowUpRight size={20} />
          ) : (
            <ArrowDownRight size={20} />
          ))}
      </strong>
      <small>{detail}</small>
    </div>
  );
}
