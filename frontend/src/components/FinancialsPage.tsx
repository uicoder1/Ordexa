import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { DollarSign, ShieldAlert, Receipt, Tag, FileText, AlertTriangle, Upload } from 'lucide-react';

export const FinancialsPage: React.FC<{ onOpenUpload: () => void }> = ({ onOpenUpload }) => {
  const [fin, setFin] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/dashboard/financials-summary').then(r => setFin(r.data)).catch(console.error).finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid #e5e7eb', borderTopColor: '#4f46e5' }} />
    </div>
  );

  return (
    <div className="space-y-6 animate-fadeInUp">
      <div className="card p-6 space-y-4">
        <div>
          <h2 className="section-title">Financial Settlement & Profit</h2>
          <p className="section-sub">Ordexa separates operational revenue from audited financial profit</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* COGS */}
          <div className="rounded-xl border border-amber-100 bg-amber-50 p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-amber-700 mb-2">
              <AlertTriangle className="w-4 h-4" /> Product Cost (COGS)
            </div>
            {fin?.cogs_available ? (
              <p className="text-[12px] font-semibold text-emerald-600">✓ Product costs uploaded</p>
            ) : (
              <div className="space-y-2">
                <p className="text-[12px] text-amber-600">{fin?.cogs_message}</p>
                <button onClick={onOpenUpload} className="btn-secondary text-[12px] py-1.5 border-amber-200 text-amber-700 hover:bg-amber-100">
                  <Upload className="w-3.5 h-3.5" /> Upload Cost File
                </button>
              </div>
            )}
          </div>
          {/* Settlement */}
          <div className="rounded-xl border border-indigo-100 bg-indigo-50 p-4">
            <div className="flex items-center gap-2 text-[13px] font-semibold text-indigo-700 mb-2">
              <ShieldAlert className="w-4 h-4" /> Settlement Report
            </div>
            {fin?.settlement_available ? (
              <p className="text-[12px] font-semibold text-emerald-600">✓ Settlement reconciled</p>
            ) : (
              <div className="space-y-2">
                <p className="text-[12px] text-indigo-600">{fin?.settlement_message}</p>
                <button onClick={onOpenUpload} className="btn-secondary text-[12px] py-1.5 border-indigo-200 text-indigo-700 hover:bg-indigo-100">
                  <Upload className="w-3.5 h-3.5" /> Upload Settlement
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
        {[
          { label: 'Total Invoice Amount', value: `₹${(fin?.total_invoice_amount || 0).toLocaleString('en-IN')}`, sub: 'Gross sales (sale items)', icon: Receipt, color: '#059669', bg: '#ecfdf5' },
          { label: 'Taxable Base Value', value: `₹${(fin?.total_taxable_value || 0).toLocaleString('en-IN')}`, sub: 'Net of taxes', icon: FileText, color: '#4f46e5', bg: '#eef2ff' },
          { label: 'Customer Discounts', value: `₹${(fin?.total_discounts || 0).toLocaleString('en-IN')}`, sub: 'Promotional deductions', icon: Tag, color: '#d97706', bg: '#fffbeb' },
          { label: 'TCS / TDS Deducted', value: `TCS ₹${(fin?.total_tcs_deducted || 0).toLocaleString('en-IN')}`, sub: `TDS ₹${(fin?.total_tds_deducted || 0).toLocaleString('en-IN')} · ${fin?.cashback_entries_count || 0} cashback entries`, icon: DollarSign, color: '#7c3aed', bg: '#f5f3ff' },
        ].map((card, i) => {
          const Icon = card.icon;
          return (
            <div key={i} className="stat-card animate-fadeInUp">
              <div className="flex items-center justify-between mb-3">
                <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">{card.label}</span>
                <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: card.bg }}>
                  <Icon className="w-4 h-4" style={{ color: card.color }} />
                </div>
              </div>
              <div className="text-xl font-bold text-gray-900">{card.value}</div>
              <div className="text-[11px] text-gray-400 mt-1 font-medium">{card.sub}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
