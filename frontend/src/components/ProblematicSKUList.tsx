import React from 'react';
import type { SKUMetric } from '../types';
import { AlertTriangle, ArrowRight } from 'lucide-react';

interface ProblematicSKUListProps {
  metrics: SKUMetric[];
  onSelectSKU: (sku: string) => void;
}

export const ProblematicSKUList: React.FC<ProblematicSKUListProps> = ({ metrics, onSelectSKU }) => {
  if (!metrics || metrics.length === 0) {
    return (
      <div className="bg-emerald-50/50 border border-emerald-200 rounded-xl p-6 text-center my-6">
        <div className="w-10 h-10 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center mx-auto mb-2 font-bold">
          ✓
        </div>
        <h3 className="text-sm font-bold text-emerald-900">Great job! No critical profit leakage detected.</h3>
        <p className="text-xs text-emerald-700 mt-1">
          All your uploaded SKUs have healthy margins and acceptable return rates.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden my-6">
      <div className="px-6 py-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-600" />
            Products Eating Your Profit
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            SKUs generating high return charges, logistics costs, or negative profit margins.
          </p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 bg-rose-100 text-rose-800 rounded-full">
          {metrics.length} Problematic SKUs
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
            <tr>
              <th className="px-4 py-3">SKU</th>
              <th className="px-4 py-3">Product Name</th>
              <th className="px-4 py-3 text-right">Revenue</th>
              <th className="px-4 py-3 text-center">Return Rate</th>
              <th className="px-4 py-3 text-center">RTO Rate</th>
              <th className="px-4 py-3 text-right">Actual Profit</th>
              <th className="px-4 py-3 text-right">Margin</th>
              <th className="px-4 py-3 text-right">Est. Leakage</th>
              <th className="px-4 py-3 text-center">Risk Level</th>
              <th className="px-4 py-3 text-center">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {metrics.map((item) => {
              const isLoss = item.actual_profit < 0;
              return (
                <tr
                  key={item.id}
                  onClick={() => onSelectSKU(item.sku)}
                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3.5 font-bold text-slate-900 font-mono text-[11px]">
                    {item.sku}
                  </td>
                  <td className="px-4 py-3.5 max-w-[200px] truncate font-medium text-slate-900" title={item.product_name}>
                    {item.product_name}
                  </td>
                  <td className="px-4 py-3.5 text-right font-semibold">
                    ₹{item.revenue.toLocaleString()}
                  </td>
                  <td className={`px-4 py-3.5 text-center font-bold ${item.return_rate > 20 ? 'text-rose-600' : 'text-slate-700'}`}>
                    {item.return_rate.toFixed(1)}%
                  </td>
                  <td className={`px-4 py-3.5 text-center font-semibold ${item.rto_rate > 10 ? 'text-amber-600' : 'text-slate-700'}`}>
                    {item.rto_rate.toFixed(1)}%
                  </td>
                  <td className={`px-4 py-3.5 text-right font-bold ${isLoss ? 'text-rose-600' : 'text-slate-900'}`}>
                    ₹{item.actual_profit.toLocaleString()}
                  </td>
                  <td className={`px-4 py-3.5 text-right font-bold ${item.profit_margin < 5 ? 'text-rose-600' : 'text-slate-900'}`}>
                    {item.profit_margin.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3.5 text-right font-semibold text-rose-600">
                    ₹{item.profit_leakage.toLocaleString()}
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide ${
                        item.risk_level === 'CRITICAL'
                          ? 'bg-rose-100 text-rose-800 border border-rose-200'
                          : 'bg-amber-100 text-amber-800 border border-amber-200'
                      }`}
                    >
                      {item.risk_level}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-center">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectSKU(item.sku);
                      }}
                      className="inline-flex items-center space-x-1 text-xs font-semibold text-emerald-700 hover:text-emerald-900"
                    >
                      <span>{item.recommended_action}</span>
                      <ArrowRight className="w-3 h-3" />
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
