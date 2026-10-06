import React, { useEffect, useState, useCallback } from 'react';
import { api } from '../services/api';
import {
  ArrowLeft, TrendingUp, RotateCcw, AlertTriangle,
  CheckCircle2, Info, ShieldAlert, Layers, MapPin, HelpCircle,
  Search, RefreshCw, Package, ChevronDown, ChevronUp
} from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';

interface Props { sku: string; onBack: () => void; }

// ── Tiny helpers ──────────────────────────────────────────────────────────

const TooltipIcon: React.FC<{ text: string }> = ({ text }) => {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex">
      <button onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
        <HelpCircle className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 cursor-pointer transition-colors" />
      </button>
      {show && <span className="tooltip-box left-5 top-0">{text}</span>}
    </span>
  );
};

const StatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, string> = { 'Healthy': 'badge-green', 'Watch': 'badge-amber', 'High Return': 'badge-red', 'Loss Making': 'badge-rose', 'Insufficient Data': 'badge-gray' };
  const icons: Record<string, React.ReactNode> = { 'Healthy': <CheckCircle2 className="w-3 h-3" />, 'Watch': <Info className="w-3 h-3" />, 'High Return': <AlertTriangle className="w-3 h-3" />, 'Loss Making': <ShieldAlert className="w-3 h-3" />, 'Insufficient Data': <Info className="w-3 h-3" /> };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{icons[status]}{status}</span>;
};

const ConfBadge = ({ conf }: { conf: string }) => {
  const map: Record<string, string> = { HIGH: 'badge-green', GOOD: 'badge-indigo', NORMAL: 'badge-indigo', MODERATE: 'badge-amber', INSUFFICIENT: 'badge-gray' };
  const labels: Record<string, string> = { HIGH: 'HIGH (50+)', GOOD: 'GOOD (30+)', NORMAL: 'NORMAL', MODERATE: 'MODERATE (10–29)', INSUFFICIENT: 'INSUFFICIENT (<10)' };
  const key = conf.toUpperCase();
  return <span className={`badge ${map[key] || 'badge-gray'}`}>{labels[key] || conf}</span>;
};

const MiniCard: React.FC<{ label: string; value: React.ReactNode; sub?: string; color?: string }> = ({ label, value, sub, color }) => (
  <div className="card-flat p-4">
    <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-2">{label}</div>
    <div className="text-xl font-bold" style={{ color: color || '#111827' }}>{value}</div>
    {sub && <div className="text-[11px] text-gray-400 mt-1">{sub}</div>}
  </div>
);

// ── Reusable event ledger table ─────────────────────────────────────────

interface LedgerRow {
  order_id: string; order_item_id: string; order_date: string;
  order_type: string; quantity: number; invoice_amount: number;
  buyer_invoice_amount: number; customer_delivery_state: string;
  return_reason_note?: string;
}

const EventLedger: React.FC<{
  endpoint: string; sku: string;
  title: string; description: string;
  accentColor: string; accentBg?: string;
  emptyMsg: string;
}> = ({ endpoint, sku, title, description, accentColor, emptyMsg }) => {
  const [rows, setRows] = useState<LedgerRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [orderId, setOrderId] = useState('');
  const [orderItemId, setOrderItemId] = useState('');
  const [open, setOpen] = useState(true);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { sku };
      if (orderId) params.order_id = orderId;
      if (orderItemId) params.order_item_id = orderItemId;
      const r = await api.get(endpoint, { params });
      setRows(r.data);
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  }, [endpoint, sku, orderId, orderItemId]);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <div className="card overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full px-6 py-4 border-b border-gray-100 flex items-center justify-between hover:bg-gray-50 transition-colors text-left"
      >
        <div>
          <h2 className="section-title" style={{ color: accentColor }}>{title}</h2>
          <p className="section-sub">{description} — {loading ? '…' : rows.length} records</p>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>

      {open && (
        <>
          {/* Search filters */}
          <div className="px-5 py-3 border-b border-gray-100 flex flex-wrap gap-2 bg-gray-50">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text" placeholder="Order ID…" value={orderId}
                onChange={e => setOrderId(e.target.value)}
                className="input pl-9 text-[12px] py-1.5 w-44"
              />
            </div>
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text" placeholder="Order Item ID…" value={orderItemId}
                onChange={e => setOrderItemId(e.target.value)}
                className="input pl-9 text-[12px] py-1.5 w-44"
              />
            </div>
            {(orderId || orderItemId) && (
              <button onClick={() => { setOrderId(''); setOrderItemId(''); }} className="btn-ghost text-[12px]">Clear</button>
            )}
          </div>

          {loading ? (
            <div className="flex justify-center py-10"><RefreshCw className="w-5 h-5 animate-spin text-indigo-400" /></div>
          ) : rows.length === 0 ? (
            <div className="py-10 text-center text-[13px] text-gray-400">{emptyMsg}</div>
          ) : (
            <div className="overflow-x-auto max-h-80">
              <table className="table-white">
                <thead>
                  <tr>
                    <th>Order ID</th>
                    <th>Order Item ID</th>
                    <th>Order Date</th>
                    <th>Order Type</th>
                    <th>Qty</th>
                    <th>Final Invoice (₹)</th>
                    <th>Buyer Invoice (₹)</th>
                    <th>Delivery State</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i}>
                      <td className="font-mono text-[11px] text-gray-600 max-w-[130px] truncate" title={row.order_id}>{row.order_id}</td>
                      <td className="font-mono text-[11px] text-gray-500 max-w-[110px] truncate" title={row.order_item_id}>{row.order_item_id}</td>
                      <td className="text-[12px] whitespace-nowrap text-gray-600">{row.order_date}</td>
                      <td className="text-[12px] text-gray-500">{row.order_type}</td>
                      <td className="text-center font-semibold text-gray-700">{row.quantity}</td>
                      <td className="font-semibold text-gray-800">₹{row.invoice_amount.toLocaleString('en-IN')}</td>
                      <td className="font-semibold text-gray-700">₹{row.buyer_invoice_amount.toLocaleString('en-IN')}</td>
                      <td className="text-[12px] text-gray-500">{row.customer_delivery_state}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="px-5 py-2.5 border-t border-gray-100 text-[11px] text-gray-400">
            {rows.length} {title.toLowerCase()} events for this SKU
          </div>
        </>
      )}
    </div>
  );
};

// ── Main page ────────────────────────────────────────────────────────────

export const SKUDetailPage: React.FC<Props> = ({ sku, onBack }) => {
  const [data, setData] = useState<any>(null);
  const [revenue, setRevenue] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isNotFound, setIsNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true); setIsNotFound(false); setError(null);
      const enc = encodeURIComponent(sku);
      const [d, r] = await Promise.allSettled([
        api.get(`/dashboard/products/detail?sku=${enc}`),
        api.get(`/dashboard/products/revenue-summary?sku=${enc}`),
      ]);
      if (d.status === 'fulfilled') setData(d.value.data);
      else {
        if ((d.reason as any)?.response?.status === 404) setIsNotFound(true);
        else setError((d.reason as any)?.response?.data?.detail || 'Failed to load product detail.');
      }
      if (r.status === 'fulfilled') setRevenue(r.value.data);
      setLoading(false);
    })();
  }, [sku]);

  // ── Loading / error states ──
  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid #e5e7eb', borderTopColor: '#4f46e5' }} />
    </div>
  );
  if (isNotFound) return (
    <div className="card p-10 max-w-md mx-auto text-center space-y-4 animate-fadeInUp">
      <AlertTriangle className="w-10 h-10 text-amber-500 mx-auto" />
      <h2 className="text-xl font-bold text-gray-900">Product Not Found</h2>
      <p className="text-[13px] text-gray-500">SKU "{sku}" not found in current imported dataset.</p>
      <button onClick={onBack} className="btn-secondary mx-auto"><ArrowLeft className="w-4 h-4" />Back</button>
    </div>
  );
  if (error || !data) return (
    <div className="card p-10 max-w-md mx-auto text-center space-y-4 border-red-100 animate-fadeInUp">
      <ShieldAlert className="w-10 h-10 text-rose-500 mx-auto" />
      <h2 className="text-xl font-bold text-gray-900">Failed to Load</h2>
      <p className="text-[13px] text-rose-600">{error || 'No data available.'}</p>
      <button onClick={onBack} className="btn-secondary mx-auto"><ArrowLeft className="w-4 h-4" />Back</button>
    </div>
  );

  const { top_summary, cancellations, trend_chart, order_type_analysis, state_analysis, insight, data_quality } = data;
  const returnRate = top_summary.sale_linked_return_rate;
  const returnColor = returnRate >= 25 ? '#e11d48' : returnRate >= 15 ? '#d97706' : '#4f46e5';

  return (
    <div className="space-y-5 animate-fadeInUp">

      {/* ─── 1. PRODUCT HEADER ─────────────────────────────────────────── */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <button onClick={onBack} className="btn-ghost"><ArrowLeft className="w-4 h-4" />Back to Products</button>
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={data.status} />
            <ConfBadge conf={data.data_confidence} />
          </div>
        </div>
        <div className="border-t border-gray-100 pt-4">
          <h1 className="text-xl font-bold text-gray-900 leading-tight">{data.product_name}</h1>
          <div className="flex flex-wrap items-center gap-3 mt-2 text-[13px] text-gray-500">
            <span className="font-mono bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-lg text-[12px] font-bold">SKU: {data.sku}</span>
            <span>Marketplace: <strong className="text-gray-700">{data.marketplace}</strong></span>
            {data.purchase_cost > 0 && <span>Unit Cost: <strong className="text-gray-700">₹{data.purchase_cost}</strong></span>}
          </div>
          <p className="text-[13px] text-gray-600 mt-2 font-medium">{insight.headline}</p>
        </div>
      </div>

      {/* ─── 2. REVENUE & SALES (Sale events only) ─────────────────────── */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-emerald-50 flex items-center justify-center shrink-0">
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <h2 className="section-title flex items-center gap-2">
              Revenue & Sales
              <TooltipIcon text="Revenue Generated is the sum of Final Invoice Amounts for Sale events (Event Sub Type = Sale) only. It is not profit. Return and Cancellation events are excluded." />
            </h2>
            <p className="section-sub">Event Sub Type = Sale · Return events excluded</p>
          </div>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 stagger">
          <MiniCard label="Revenue Generated" value={`₹${(revenue?.revenue_generated || top_summary.sales_revenue).toLocaleString('en-IN')}`} sub="Final Invoice sum (Sale)" color="#059669" />
          <MiniCard label="Sale Items" value={revenue?.sale_items ?? top_summary.sale_items} sub="Unique order items" color="#4f46e5" />
          <MiniCard label="Units Sold" value={revenue?.units_sold ?? '—'} sub="Item quantity total" color="#7c3aed" />
          <MiniCard label="Avg Revenue / Item" value={`₹${(revenue?.avg_revenue_per_sale_item || 0).toLocaleString('en-IN')}`} sub="Per sale order item" color="#059669" />
        </div>
      </div>

      {/* ─── 3. RETURN & EVENT ACTIVITY ────────────────────────────────── */}
      <div className="card p-5 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-rose-50 flex items-center justify-center shrink-0">
              <RotateCcw className="w-4 h-4 text-rose-500" />
            </div>
            <div>
              <h2 className="section-title">Return & Event Activity</h2>
              <p className="section-sub">
                Classified by Event Sub Type — Sale · Return · Cancellation · Return Cancellation kept separate
              </p>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className="text-3xl font-extrabold" style={{ color: returnColor }}>{returnRate}%</div>
            <div className="text-[11px] text-gray-400 mt-0.5 font-medium">sale-linked return rate</div>
          </div>
        </div>

        {/* Event counters — one per event_subtype */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {/* Sales */}
          <div className="card-flat p-4 border-indigo-100">
            <div className="flex items-center gap-1.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-indigo-400" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-600">Sale</span>
            </div>
            <div className="text-2xl font-bold text-gray-900">{top_summary.sale_items}</div>
            <div className="text-[11px] text-gray-400 mt-1">Unique sale items</div>
            <div className="text-[11px] font-semibold text-emerald-600 mt-0.5">
              ₹{(revenue?.revenue_generated || top_summary.sales_revenue).toLocaleString('en-IN')}
            </div>
          </div>

          {/* Return */}
          <div className="card-flat p-4 border-rose-100 bg-rose-50/30">
            <div className="flex items-center gap-1.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-rose-500" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600">Return</span>
            </div>
            <div className="text-2xl font-bold text-rose-700">{top_summary.return_events}</div>
            <div className="text-[11px] text-gray-400 mt-1">Return rows (Event Sub Type)</div>
            <div className="text-[11px] font-semibold text-rose-600 mt-0.5">
              ₹{top_summary.returned_value.toLocaleString('en-IN')} returned
            </div>
          </div>

          {/* Cancellation */}
          <div className="card-flat p-4 border-amber-100 bg-amber-50/30">
            <div className="flex items-center gap-1.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-amber-700">Cancellation</span>
            </div>
            <div className="text-2xl font-bold text-amber-700">{top_summary.cancellation_events}</div>
            <div className="text-[11px] text-gray-400 mt-1">Cancellation rows (Event Sub Type)</div>
            <div className="text-[11px] text-amber-600 font-medium mt-0.5">{cancellations.cancellation_rate}% cancellation rate</div>
          </div>

          {/* Return Cancellation */}
          <div className="card-flat p-4 border-violet-100 bg-violet-50/30">
            <div className="flex items-center gap-1.5 mb-2">
              <div className="w-2 h-2 rounded-full bg-violet-500" />
              <span className="text-[11px] font-bold uppercase tracking-wider text-violet-700">Return Cancel</span>
            </div>
            <div className="text-2xl font-bold text-violet-700">{top_summary.return_cancellation_events}</div>
            <div className="text-[11px] text-gray-400 mt-1">Separate from Return & Cancellation</div>
            <div className="text-[11px] text-violet-600 font-medium mt-0.5">Distinct event type</div>
          </div>
        </div>

        {/* Sale-linked return detail */}
        <div className="rounded-xl bg-gray-50 border border-gray-200 px-5 py-4 flex flex-wrap gap-6">
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Sale-linked Returns</div>
            <div className="text-xl font-bold text-gray-900">{Math.round((returnRate / 100) * top_summary.sale_items)}</div>
            <div className="text-[11px] text-gray-400">Items with both Sale + Return event</div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Avg Return Value</div>
            <div className="text-xl font-bold text-gray-900">₹{top_summary.avg_return_value.toLocaleString('en-IN')}</div>
            <div className="text-[11px] text-gray-400">Per returned item</div>
          </div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider text-gray-400 mb-1">Total Returned Value</div>
            <div className="text-xl font-bold text-rose-600">₹{top_summary.returned_value.toLocaleString('en-IN')}</div>
            <div className="text-[11px] text-gray-400">Invoice sum of Return events</div>
          </div>
        </div>
      </div>

      {/* ─── 4. RETURN REASON (honest unavailability) ──────────────────── */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-amber-50 flex items-center justify-center shrink-0">
            <HelpCircle className="w-4 h-4 text-amber-500" />
          </div>
          <div>
            <h2 className="section-title">Return Reason</h2>
            <p className="section-sub">Classification by cause — Customer Return · Delivery Failure / RTO · Unsold Goods</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Customer Return', icon: '👤' },
            { label: 'Delivery Failure / RTO', icon: '🚚' },
            { label: 'Unsold Goods', icon: '📦' },
          ].map(c => (
            <div key={c.label} className="card-flat p-4">
              <div className="text-2xl mb-2">{c.icon}</div>
              <div className="text-[13px] font-semibold text-gray-700 mb-1">{c.label}</div>
              <span className="badge badge-gray text-[11px]">Unavailable</span>
            </div>
          ))}
        </div>

        <div className="rounded-xl bg-amber-50 border border-amber-100 p-4 flex items-start gap-3 text-[12px] text-amber-800 leading-relaxed">
          <Info className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
          <span>
            The current Flipkart Sales Report identifies Return events using <strong>Event Sub Type = Return</strong> but does not provide an explicit return reason or return type field.
            Ordexa does not infer Customer Return, Delivery Failure / RTO, or Unsold Goods from a generic Return event.
            When a future marketplace report provides an explicit return reason column, these categories will be populated automatically.
          </span>
        </div>
      </div>

      {/* ─── 5. RETURN LEDGER (Event Sub Type = Return only) ───────────── */}
      <EventLedger
        endpoint="/dashboard/products/return-ledger"
        sku={sku}
        title="Return Ledger"
        description="Event Sub Type = Return only"
        accentColor="#e11d48"
        accentBg="#fff1f2"
        emptyMsg="No Return events found for this SKU."
      />

      {/* ─── 6. CANCELLATION LEDGER (Event Sub Type = Cancellation only) ── */}
      <EventLedger
        endpoint="/dashboard/products/cancellation-ledger"
        sku={sku}
        title="Cancellation Activity"
        description="Event Sub Type = Cancellation only · separate from Return events"
        accentColor="#d97706"
        accentBg="#fffbeb"
        emptyMsg="No Cancellation events found for this SKU."
      />

      {/* ─── 7. RETURN CANCELLATION (Event Sub Type = Return Cancellation) ─ */}
      <EventLedger
        endpoint="/dashboard/products/return-cancellation-ledger"
        sku={sku}
        title="Return Cancellation Activity"
        description="Event Sub Type = Return Cancellation · not counted as Return or Cancellation"
        accentColor="#7c3aed"
        accentBg="#f5f3ff"
        emptyMsg="No Return Cancellation events found for this SKU."
      />

      {/* ─── 8. RETURN TREND ──────────────────────────────────────────── */}
      <div className="card p-5 space-y-4">
        <h2 className="section-title">Return Activity Timeline</h2>
        <p className="section-sub">Sale items vs return items by order date</p>
        {trend_chart.length > 0 ? (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={trend_chart} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="sale_items" name="Sale Items" stroke="#4f46e5" strokeWidth={2} dot={{ r: 2 }} />
                <Line type="monotone" dataKey="return_items" name="Return Items" stroke="#e11d48" strokeWidth={2} dot={{ r: 2 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-20 flex items-center justify-center rounded-xl border border-dashed border-gray-200 text-[12px] text-gray-400">
            No timeline data available
          </div>
        )}
      </div>

      {/* ─── 9. ORDER TYPE + STATE ANALYSIS ────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="section-title flex items-center gap-2"><Layers className="w-4 h-4 text-indigo-500" />Order Type Analysis</h3>
            <p className="section-sub">Return rate split by payment type</p>
          </div>
          <table className="table-white">
            <thead><tr><th>Order Type</th><th>Sales</th><th>Returns</th><th className="text-right">Rate %</th></tr></thead>
            <tbody>
              {order_type_analysis.length === 0 ? (
                <tr><td colSpan={4} className="text-center py-8 text-[12px] text-gray-400">No data</td></tr>
              ) : order_type_analysis.map((ot: any) => (
                <tr key={ot.order_type}>
                  <td className="font-semibold text-gray-900">{ot.order_type}</td>
                  <td className="font-semibold text-gray-700">{ot.sale_items}</td>
                  <td className="font-semibold text-rose-600">{ot.returned_items}</td>
                  <td className="text-right font-bold" style={{ color: ot.return_rate >= 25 ? '#e11d48' : ot.return_rate >= 15 ? '#d97706' : '#374151' }}>{ot.return_rate}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="section-title flex items-center gap-2"><MapPin className="w-4 h-4 text-violet-500" />Delivery State Analysis</h3>
            <p className="section-sub">Top states sorted by return volume</p>
          </div>
          <div className="overflow-y-auto max-h-60">
            <table className="table-white">
              <thead><tr><th>State</th><th>Sales</th><th>Returns</th><th className="text-right">Rate %</th></tr></thead>
              <tbody>
                {state_analysis.length === 0 ? (
                  <tr><td colSpan={4} className="text-center py-8 text-[12px] text-gray-400">No data</td></tr>
                ) : state_analysis.slice(0, 10).map((st: any) => (
                  <tr key={st.state}>
                    <td className="font-semibold text-gray-900">{st.state}</td>
                    <td className="font-semibold text-gray-700">{st.sale_items}</td>
                    <td className="font-semibold text-rose-600">{st.returned_items}</td>
                    <td className="text-right font-bold" style={{ color: st.return_rate >= 25 ? '#e11d48' : st.return_rate >= 15 ? '#d97706' : '#374151' }}>{st.return_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ─── 10. DATA QUALITY ───────────────────────────────────────────── */}
      <div className="card p-5 space-y-3">
        <h2 className="section-title flex items-center gap-2"><Package className="w-4 h-4 text-indigo-500" />Data Quality</h2>
        <p className="section-sub">Field availability from the imported report</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { label: 'Sale Events', ok: data_quality.sale_events_available },
            { label: 'Return Events', ok: data_quality.return_events_available },
            { label: 'Order Type', ok: data_quality.order_type_available },
            { label: 'Delivery State', ok: data_quality.delivery_state_available },
            { label: 'COGS', ok: data_quality.cogs_available },
            { label: 'Settlement', ok: data_quality.settlement_available },
            { label: 'RTO Data', ok: data_quality.rto_available },
          ].map((item, i) => (
            <div key={i} className={`flex items-center gap-2 text-[12px] font-medium px-3 py-2 rounded-xl border ${item.ok ? 'bg-emerald-50 border-emerald-100 text-emerald-700' : 'bg-amber-50 border-amber-100 text-amber-700'}`}>
              {item.ok ? <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" /> : <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />}
              {item.label}
            </div>
          ))}
        </div>
      </div>

    </div>
  );
};
