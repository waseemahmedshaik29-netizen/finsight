export type Position = {
  id: number;
  ticker: string;
  quantity: number;
  cost_basis: number;
};
export type Portfolio = {
  id: number;
  name: string;
  benchmark: string;
  cash: number;
  positions: Position[];
};
export type Holding = Position & {
  name: string;
  sector: string;
  price: number;
  value: number;
  weight: number;
  pnl: number;
};
export type Analytics = {
  value: number;
  total_return: number;
  annual_return: number | null;
  volatility: number;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number;
  beta: number | null;
  alpha: number | null;
  var95: number;
  cvar95: number;
  var_dollars: number;
  weights: Record<string, number>;
  risk_contribution: Record<string, number>;
  correlations: Record<string, Record<string, number>>;
  curve: { date: string; portfolio: number; benchmark: number }[];
  rolling_volatility: { date: string; value: number }[];
  holdings: Holding[];
  portfolio: Portfolio;
  provenance: { mode: string; source: string; as_of: string };
  methodology: string;
  observations: number;
  start: string;
  end: string;
};
export type Macro = {
  source: string;
  series: {
    id: string;
    name: string;
    value: number;
    unit: string;
    date: string;
    url?: string;
  }[];
};
export type Fundamentals = {
  ticker: string;
  name: string;
  source: string;
  period: string;
  revenue: number | null;
  operating_income: number | null;
  net_income: number | null;
  cash: number | null;
  debt: number | null;
  assets: number | null;
  equity: number | null;
  operating_cash_flow: number | null;
  capex: number | null;
  free_cash_flow: number | null;
  shares: number | null;
  operating_margin: number | null;
  fcf_margin: number | null;
  roe: number | null;
  history: { date: string; revenue: number }[];
  url?: string;
  debt_note?: string;
};
export type Filing = {
  id: string;
  form: string;
  date: string;
  url: string;
  title: string;
};
export type Citation = {
  document_id: string;
  form: string;
  date: string;
  url: string;
  offset: number;
  text: string;
  citation: string;
  score: number;
};
export type Snapshot = {
  id: number;
  created_at: string;
  mode: string;
  value: number;
};
export type Changes = {
  evidence_gaps?: {
    before: Record<string, string>;
    after: Record<string, string>;
  };
  metrics: { metric: string; before: number; after: number; delta: number }[];
  allocation: {
    ticker: string;
    before: number;
    after: number;
    delta: number;
  }[];
  macro: {
    series: string;
    before: number;
    after: number;
    delta: number;
    unit: string;
  }[];
  new_filings: { ticker: string; id: string }[];
  summary: string;
  mode: string;
};
export type DCFInputs = {
  revenue: number;
  growth: number;
  margin: number;
  tax_rate: number;
  da_ratio: number;
  capex_ratio: number;
  working_capital_ratio: number;
  wacc: number;
  terminal_growth: number;
  net_debt: number;
  shares: number;
};
export type DCF = {
  price: number;
  enterprise_value: number;
  equity_value: number;
  terminal_value: number;
  forecast: {
    year: number;
    revenue: number;
    fcf: number;
    present_value: number;
  }[];
  sensitivity: { wacc: number; values: (number | null)[] }[];
  growth_columns: number[];
};
export type Stress = {
  impact: number;
  return: number;
  positions: { ticker: string; shock: number; impact: number }[];
  method: string;
};
export type Answer = {
  answer: string;
  engine: string;
  tools: { name: string; endpoint?: string; ticker?: string }[];
  citations: Citation[];
  limitation: string;
  warning?: string | null;
};
