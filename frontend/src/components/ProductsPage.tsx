import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Search, Plus, CheckCircle2, Info, AlertTriangle, ShieldAlert } from 'lucide-react';

interface ProductMetric {
  sku: string; product_name: string; sold_items: number; sales_amount: number;
  returned_items: number; sale_linked_return_pct: number; cancellations: number;
  return_value: number; cogs: number | null; cogs_available: boolean;
  actual_profit: number | null; margin_pct: number | null;
  data_confidence?: string; status: string; reason: string;
}
interface Props { onOpenUpload: () => void; onSelectProduct?: (sku: string) => void; }

const StatusBadge = ({ status }: { status: string }) => {
  const map: Record<string, string> = { 'Healthy': 'badge-green', 'Watch': 'badge-amber', 'High Return': 'badge-red', 'Loss Making': 'badge-rose', 'Insufficient Data': 'badge-gray' };
  const icons: Record<string, React.ReactNode> = { 'Healthy': <CheckCircle2 className="w-3 h-3" />, 'Watch': <Info className="w-3 h-3" />, 'High Return': <AlertTriangle className="w-3 h-3" />, 'Loss Making': <ShieldAlert className="w-3 h-3" />, 'Insufficient Data': <Info className="w-3 h-3" /> };
  return <span className={`badge ${map[status] || 'badge-gray'}`}>{icons[status]}{status}</span>;
};

export const ProductsPage: React.FC<Props> = ({ onOpenUpload, onSelectProduct }) => {
  const [products, setProducts] = useState<ProductMetric[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [costInput, setCostInput] = useState('');

  const fetchProducts = async () => {
    try { const r = await api.get('/dashboard/skus', { params: search ? { search } : {} }); setProducts(r.data); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchProducts(); }, [search]);

  const saveCost = async (sku: string) => {
    const v = parseFloat(costInput);
    if (isNaN(v) || v < 0) return;
    try { await api.post('/products/update-sku-cost', null, { params: { sku, purchase_cost: v } }); setEditing(null); setCostInput(''); fetchProducts(); }
    catch { alert('Failed to update cost'); }
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid #e5e7eb', borderTopColor: '#4f46e5' }} />
    </div>
  );

  return (
    <div className="space-y-4 animate-fadeInUp">
      <div className="card-flat px-5 py-3.5 flex flex-wrap justify-between items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input type="text" placeholder="Search SKU or product..." value={search} onChange={e => setSearch(e.target.value)} className="input pl-9" />
        </div>
        <div className="flex gap-2">
          <button onClick={onOpenUpload} className="btn-secondary"><Plus className="w-4 h-4 text-gray-500" />Upload Cost File</button>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="table-white">
            <thead>
              <tr>
                <th>SKU / Product</th><th>Sold</th><th>Revenue</th><th>Returns</th>
                <th>Return %</th><th>Cancellations</th><th>Return Value</th>
                <th>COGS</th><th>Profit</th><th>Margin</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {products.map(item => (
                <tr key={item.sku}>
                  <td>
                    <button onClick={() => onSelectProduct?.(item.sku)} className="font-bold text-indigo-600 hover:text-indigo-800 text-[13px] transition-colors text-left">
                      {item.sku}
                    </button>
                    <div className="text-[11px] text-gray-400 max-w-[180px] truncate mt-0.5">{item.product_name}</div>
                  </td>
                  <td className="font-semibold text-gray-800">{item.sold_items}</td>
                  <td className="font-semibold text-gray-800">₹{item.sales_amount.toLocaleString('en-IN')}</td>
                  <td className="font-semibold text-rose-600">{item.returned_items}</td>
                  <td>
                    <span className={`font-bold text-[13px] ${item.sale_linked_return_pct >= 25 ? 'text-rose-600' : item.sale_linked_return_pct >= 15 ? 'text-amber-600' : 'text-gray-700'}`}>
                      {item.sale_linked_return_pct}%
                    </span>
                  </td>
                  <td className="text-gray-500">{item.cancellations}</td>
                  <td className="font-semibold text-gray-800">₹{item.return_value.toLocaleString('en-IN')}</td>
                  <td>
                    {editing === item.sku ? (
                      <div className="flex items-center gap-1">
                        <input type="number" value={costInput} onChange={e => setCostInput(e.target.value)} placeholder="₹" className="input w-16 py-1 px-2 text-[12px]" />
                        <button onClick={() => saveCost(item.sku)} className="btn-primary py-1 px-2 text-[11px]">Save</button>
                      </div>
                    ) : item.cogs ? (
                      <div className="flex items-center gap-1">
                        <span className="font-semibold text-gray-800">₹{item.cogs}</span>
                        <button onClick={() => { setEditing(item.sku); setCostInput(String(item.cogs)); }} className="text-[10px] text-gray-400 hover:text-gray-600 underline">edit</button>
                      </div>
                    ) : (
                      <button onClick={() => { setEditing(item.sku); setCostInput(''); }} className="badge badge-indigo text-[11px] cursor-pointer hover:bg-indigo-100 transition-colors">+ Add</button>
                    )}
                  </td>
                  <td>
                    {item.actual_profit !== null ? (
                      <span className={`font-bold ${item.actual_profit >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>₹{item.actual_profit.toLocaleString('en-IN')}</span>
                    ) : <span className="text-gray-300 text-[11px]">—</span>}
                  </td>
                  <td>
                    {item.margin_pct !== null ? <span className="font-semibold text-gray-600">{item.margin_pct}%</span> : <span className="text-gray-300 text-[11px]">—</span>}
                  </td>
                  <td>
                    <StatusBadge status={item.status} />
                    <div className="text-[10px] text-gray-400 mt-0.5 max-w-[120px] truncate">{item.reason}</div>
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
