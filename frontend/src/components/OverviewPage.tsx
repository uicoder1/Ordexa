import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ShoppingBag, RotateCcw, XCircle, DollarSign, Package, Calendar, HelpCircle, ArrowRight, CheckCircle2, AlertTriangle, Info, ShieldAlert, TrendingDown, Plus } from 'lucide-react';

interface OverviewSummary {
  sales_value: number; units_sold: number; sale_events_count: number;
  unique_sale_order_items_count?: number;
  return_events_count: number; returned_order_items_count: number;
  cancellation_events_count: number; return_cancellation_events_count: number;
  returned_value: number; unique_orders_count: number;
  unique_order_items_count: number; unique_skus_count: number;
  data_period: string; sale_linked_returns_count: number;
  sale_linked_return_rate?: number; unlinked_returns_count: number;
  rto_available: boolean; rto_message: string;
  cogs_available: boolean; actual_profit_message: string | null;
  settlement_available: boolean; settlement_message: string | null;
}
interface ProductAttention {
  sku: string; product_name: string; purchase_cost: number; cogs_available: boolean;
  sales_count: number; sales_revenue: number; returned_units: number;
  cancellation_units: number; return_value: number; sale_linked_return_rate: number;
  data_confidence?: string; status: string; reason: string;
  order_type_breakdown: Record<string, number>; state_breakdown: string;
}
interface OverviewPageProps {
  onOpenUpload?: () => void;
  onNavigateToProducts?: () => void;
  onSelectProduct?: (sku: string) => void;
}

const StatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, string> = { 'Healthy': 'badge-green', 'Watch': 'badge-amber', 'High Return': 'badge-red', 'Loss Making': 'badge-rose', 'Insufficient Data': 'badge-gray' };
  const iconMap: Record<string, React.ReactNode> = { 'Healthy': <CheckCircle2 className="w-3 h-3" />, 'Watch': <Info className="w-3 h-3" />, 'High Return': <AlertTriangle className="w-3 h-3" />, 'Loss Making': <ShieldAlert className="w-3 h-3" />, 'Insufficient Data': <Info className="w-3 h-3" /> };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{iconMap[status]}{status}</span>;
};

export const OverviewPage: React.FC<OverviewPageProps> = ({ onOpenUpload, onNavigateToProducts, onSelectProduct }) => {
  const [summary, setSummary] = useState<OverviewSummary | null>(null);
  const [products, setProducts] = useState<ProductAttention[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTip, setShowTip] = useState(false);

  useEffect(() => {
    (async () => {
      const [s, p] = await Promise.allSettled([api.get('/dashboard/overview'), api.get('/dashboard/products-needing-attention')]);
      if (s.status === 'fulfilled') setSummary(s.value.data);
      if (p.status === 'fulfilled') setProducts(p.value.data);
      setLoading(false);
    })();
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid #e5e7eb', borderTopColor: '#4f46e5' }} />
    </div>
  );

  const isEmptyWorkspace = Boolean(
    !summary || (
      summary.sale_events_count === 0 &&
      summary.return_events_count === 0 &&
      summary.cancellation_events_count === 0 &&
      (!summary.unique_skus_count || summary.unique_skus_count === 0)
    )
  );

  if (isEmptyWorkspace) {
    return (
      <div className="card p-12 max-w-xl mx-auto text-center space-y-5 animate-fadeInUp mt-8">
        <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center bg-indigo-50 border border-indigo-100">
          <Package className="w-8 h-8 text-indigo-600" />
        </div>
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Your workspace is ready.</h2>
          <p className="text-[14px] text-gray-500 mt-2 max-w-md mx-auto leading-relaxed">
            Import your first marketplace report to start analyzing your business.
          </p>
        </div>
        <div className="pt-2">
          <button onClick={onOpenUpload} className="btn-primary mx-auto text-[13px] py-2.5 px-5">
            <Plus className="w-4 h-4" />
            <span>+ Import Data</span>
          </button>
        </div>
      </div>
    );
  }

  const returnRate = summary?.sale_linked_return_rate !== undefined ? summary.sale_linked_return_rate.toFixed(1) : '0.0';

  const kpis = [
    { label: 'Sales Revenue', value: `₹${(summary?.sales_value || 0).toLocaleString('en-IN')}`, sub: `${summary?.sale_events_count || 0} sale items`, icon: ShoppingBag, color: '#4f46e5', bg: '#eef2ff' },
    { label: 'Return Events', value: summary?.return_events_count || 0, sub: `${summary?.returned_order_items_count || 0} returned items`, icon: RotateCcw, color: '#e11d48', bg: '#fff1f2' },
    { label: 'Cancellations', value: summary?.cancellation_events_count || 0, sub: 'Order cancellations', icon: XCircle, color: '#d97706', bg: '#fffbeb' },
    { label: 'Returned Value', value: `₹${(summary?.returned_value || 0).toLocaleString('en-IN')}`, sub: 'Return invoice sum', icon: DollarSign, color: '#e11d48', bg: '#fff1f2' },
    { label: 'Products', value: summary?.unique_skus_count || 0, sub: 'Unique SKUs tracked', icon: Package, color: '#059669', bg: '#ecfdf5' },
    { label: 'Data Period', value: null, customValue: summary?.data_period?.split(' to ')[0], sub: `${(summary?.unique_orders_count || 0).toLocaleString()} orders`, icon: Calendar, color: '#7c3aed', bg: '#f5f3ff' },
  ];

  return (
    <div className="space-y-6 animate-fadeInUp">

      {/* Period banner */}
      <div className="flex flex-wrap items-center justify-between gap-3 card-flat px-5 py-3.5">
        <div className="flex items-center gap-3">
          <span className="badge badge-indigo text-[11px] font-bold uppercase tracking-wider">Marketplace Report</span>
          <span className="text-[13px] font-semibold text-gray-700">{summary?.data_period || '—'}</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="badge badge-gray text-[11px]">⚠ RTO unavailable</span>
          {!summary?.cogs_available && <span className="badge badge-amber text-[11px]">⚠ COGS missing</span>}
          {!summary?.settlement_available && <span className="badge badge-gray text-[11px]">⚠ Settlement missing</span>}
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 stagger">
        {kpis.map((k, i) => {
          const Icon = k.icon;
          return (
            <div key={i} className="stat-card animate-fadeInUp">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider leading-tight">{k.label}</span>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: k.bg }}>
                  <Icon className="w-4 h-4" style={{ color: k.color }} />
                </div>
              </div>
              {k.customValue ? (
                <div className="text-[14px] font-bold text-gray-900 leading-snug">{k.customValue}</div>
              ) : (
                <div className="text-2xl font-bold text-gray-900">{k.value}</div>
              )}
              <div className="text-[11px] text-gray-400 mt-1 font-medium">{k.sub}</div>
            </div>
          );
        })}
      </div>

      {/* Return rate banner */}
      <div className="card px-6 py-5 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown className="w-4 h-4 text-rose-500" />
            <span className="text-[13px] font-semibold text-gray-700">Sale-Linked Return Activity</span>
            <button className="relative" onMouseEnter={() => setShowTip(true)} onMouseLeave={() => setShowTip(false)}>
              <HelpCircle className="w-3.5 h-3.5 text-gray-300 hover:text-gray-500 transition-colors" />
              {showTip && (
                <div className="tooltip-box left-6 top-0">
                  Counts order items where both a Sale and Return event exist in the reporting period. Not a cohort return rate.
                </div>
              )}
            </button>
          </div>
          <p className="text-[13px] text-gray-500">
            <span className="font-bold text-gray-800">{summary?.sale_linked_returns_count || 0}</span> order items had both a Sale and Return event in this period.
          </p>
        </div>
        <div className="text-right shrink-0">
          <div className="text-4xl font-extrabold" style={{ color: Number(returnRate) >= 25 ? '#e11d48' : Number(returnRate) >= 15 ? '#d97706' : '#4f46e5' }}>
            {returnRate}%
          </div>
          <div className="text-[11px] text-gray-400 font-medium mt-0.5">sale-linked return activity</div>
        </div>
      </div>

      {/* Products Needing Attention */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex justify-between items-center">
          <div>
            <h2 className="section-title">Products Needing Attention</h2>
            <p className="section-sub">Ranked by return activity · minimum sample thresholds applied</p>
          </div>
          {onNavigateToProducts && (
            <button onClick={onNavigateToProducts} className="btn-ghost text-[13px]">
              View all <ArrowRight className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="overflow-x-auto">
          <table className="table-white">
            <thead>
              <tr>
                <th>SKU / Product</th><th>Sale Items</th><th>Returns</th>
                <th>Return %</th><th>Cancellations</th><th>Return Value</th>
                <th>Status</th><th className="text-right">Detail</th>
              </tr>
            </thead>
            <tbody>
              {products.length === 0 ? (
                <tr><td colSpan={8} className="text-center py-12 text-[13px] text-gray-400">No data yet — import a marketplace report to get started.</td></tr>
              ) : products.map(item => (
                <tr key={item.sku}>
                  <td>
                    <div className="font-semibold text-gray-900 text-[13px]">{item.sku}</div>
                    <div className="text-[11px] text-gray-400 max-w-[200px] truncate" title={item.product_name}>{item.product_name}</div>
                  </td>
                  <td>
                    <span className="font-semibold text-gray-800">{item.sales_count}</span>
                    <div className="text-[11px] text-gray-400">₹{item.sales_revenue.toLocaleString('en-IN')}</div>
                  </td>
                  <td><span className="font-semibold text-rose-600">{item.returned_units}</span></td>
                  <td>
                    <span className={`font-bold text-[13px] ${item.sale_linked_return_rate >= 25 ? 'text-rose-600' : item.sale_linked_return_rate >= 15 ? 'text-amber-600' : 'text-gray-700'}`}>
                      {item.sale_linked_return_rate}%
                    </span>
                  </td>
                  <td className="text-gray-500">{item.cancellation_units}</td>
                  <td className="font-semibold text-gray-800">₹{item.return_value.toLocaleString('en-IN')}</td>
                  <td>
                    <div className="space-y-0.5">
                      <StatusBadge status={item.status} />
                      <div className="text-[11px] text-gray-400 max-w-[160px] truncate">{item.reason}</div>
                    </div>
                  </td>
                  <td className="text-right">
                    <button
                      onClick={() => onSelectProduct?.(item.sku)}
                      className="btn-ghost text-[12px] font-semibold text-indigo-600 hover:text-indigo-800 hover:bg-indigo-50">
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
