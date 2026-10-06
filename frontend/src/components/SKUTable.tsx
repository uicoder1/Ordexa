import React, { useState } from 'react';
import type { SKUMetric } from '../types';
import { Search, ChevronRight, Download } from 'lucide-react';

interface SKUTableProps {
  metrics: SKUMetric[];
  onSelectSKU: (sku: string) => void;
  onExport: () => void;
}

export const SKUTable: React.FC<SKUTableProps> = ({ metrics, onSelectSKU, onExport }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [riskFilter, setRiskFilter] = useState<string>('ALL');
  const [sortBy, setSortBy] = useState<string>('revenue_desc');

  const filtered = metrics.filter((m) => {
    const matchesSearch =
      m.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (m.product_name && m.product_name.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesRisk = riskFilter === 'ALL' || m.risk_level === riskFilter;
    return matchesSearch && matchesRisk;
  });

  const sorted = [...filtered].sort((a, b) => {
    if (sortBy === 'revenue_desc') return b.revenue - a.revenue;
    if (sortBy === 'revenue_asc') return a.revenue - b.revenue;
    if (sortBy === 'profit_desc') return b.actual_profit - a.actual_profit;
    if (sortBy === 'profit_asc') return a.actual_profit - b.actual_profit;
    if (sortBy === 'return_desc') return b.return_rate - a.return_rate;
    if (sortBy === 'rto_desc') return b.rto_rate - a.rto_rate;
    if (sortBy === 'leakage_desc') return b.profit_leakage - a.profit_leakage;
    return 0;
  });

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden my-6">
      <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900">All Products Profitability</h2>
          <p className="text-xs text-slate-500">
            Showing {sorted.length} of {metrics.length} SKUs calculated across settlements.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search SKU or product..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 w-48 sm:w-60"
            />
          </div>

          <select
            value={riskFilter}
            onChange={(e) => setRiskFilter(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="ALL">All Risk Levels</option>
            <option value="CRITICAL">Critical Loss Only</option>
            <option value="WARNING">Warning Only</option>
            <option value="HEALTHY">Healthy Only</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          >
            <option value="revenue_desc">Sort: Highest Revenue</option>
            <option value="profit_desc">Sort: Highest Profit</option>
            <option value="profit_asc">Sort: Lowest Profit (Loss First)</option>
            <option value="return_desc">Sort: Highest Return Rate</option>
            <option value="rto_desc">Sort: Highest RTO Rate</option>
            <option value="leakage_desc">Sort: Highest Profit Leakage</option>
          </select>

          <button
            onClick={onExport}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shadow-xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100/80 text-slate-600 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
            <tr>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Product Name</th>
              <th className="px-4 py-3 text-right">Cost</th>
              <th className="px-4 py-3 text-center">Orders</th>
              <th className="px-4 py-3 text-right">Revenue</th>
              <th className="px-4 py-3 text-right">Net Settlement</th>
              <th className="px-4 py-3 text-center">Return %</th>
              <th className="px-4 py-3 text-center">RTO %</th>
              <th className="px-4 py-3 text-right">Actual Profit</th>
              <th className="px-4 py-3 text-right">Margin %</th>
              <th className="px-4 py-3 text-center">Risk</th>
              <th className="px-4 py-3 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {sorted.map((item) => {
              const isNegative = item.actual_profit < 0;
              return (
                <tr
                  key={item.id}
                  onClick={() => onSelectSKU(item.sku)}
                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-bold font-mono text-slate-900 text-[11px]">
                    {item.sku}
                  </td>
                  <td className="px-4 py-3 font-medium text-slate-900 max-w-[180px] truncate" title={item.product_name}>
                    {item.product_name}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-600">
                    ₹{item.purchase_cost ? item.purchase_cost.toLocaleString() : '0'}
                  </td>
                  <td className="px-4 py-3 text-center font-semibold text-slate-700">
                    {item.units_sold}
                  </td>
                  <td className="px-4 py-3 text-right font-semibold">
                    ₹{item.revenue.toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-right text-slate-700">
                    ₹{item.net_settlement.toLocaleString()}
                  </td>
                  <td className={`px-4 py-3 text-center font-bold ${item.return_rate > 15 ? 'text-rose-600' : 'text-slate-700'}`}>
                    {item.return_rate.toFixed(1)}%
                  </td>
                  <td className={`px-4 py-3 text-center font-semibold ${item.rto_rate > 10 ? 'text-amber-600' : 'text-slate-700'}`}>
                    {item.rto_rate.toFixed(1)}%
                  </td>
                  <td className={`px-4 py-3 text-right font-bold ${isNegative ? 'text-rose-600' : 'text-emerald-700'}`}>
                    ₹{item.actual_profit.toLocaleString()}
                  </td>
                  <td className={`px-4 py-3 text-right font-bold ${item.profit_margin < 5 ? 'text-rose-600' : 'text-slate-900'}`}>
                    {item.profit_margin.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                        item.risk_level === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800'
                          : item.risk_level === 'WARNING'
                          ? 'bg-amber-100 text-amber-800'
                          : 'bg-emerald-100 text-emerald-800'
                      }`}
                    >
                      {item.risk_level}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectSKU(item.sku);
                      }}
                      className="p-1 hover:bg-slate-200 rounded text-slate-600 hover:text-slate-900"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
