import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type { CalculationConfig, SubscriptionStatus } from '../types';
import { Settings, Save, CheckCircle2, Zap } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  const { activeOrg } = useAuth();
  const [config, setConfig] = useState<CalculationConfig | null>(null);
  const [subStatus, setSubStatus] = useState<SubscriptionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        const [configRes, subRes] = await Promise.all([
          api.get('/organizations/config'),
          api.get('/subscription/status'),
        ]);
        setConfig(configRes.data);
        setSubStatus(subRes.data);
      } catch (err) {
        console.error(err);
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!config) return;

    try {
      await api.put('/organizations/config', config);
      setSavedMsg('Calculation rules updated & metrics recalculated!');
      setTimeout(() => setSavedMsg(null), 3000);
    } catch (err) {
      alert('Failed to update config.');
    }
  };

  if (isLoading || !config) return null;

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs">
        <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
          <Settings className="w-5 h-5 text-emerald-600" />
          Settings & Financial Calculation Rules
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Configure how Ordexa evaluates net settlements, reverse logistics fees, and risk thresholds.
        </p>
      </div>

      {savedMsg && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg text-xs font-semibold flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{savedMsg}</span>
        </div>
      )}

      <form onSubmit={handleSaveConfig} className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-6">
        <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">
          Marketplace Settlement & Deductions Rules
        </h3>

        <div className="space-y-4 text-xs">
          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={config.settlement_is_net}
              onChange={(e) => setConfig({ ...config, settlement_is_net: e.target.checked })}
              className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
            />
            <div>
              <span className="font-semibold text-slate-900 block">Report contains Net Settlement values</span>
              <span className="text-slate-500 text-[11px]">
                When checked, marketplace payouts already include deducted commission/shipping fees.
              </span>
            </div>
          </label>

          <label className="flex items-center space-x-3 cursor-pointer">
            <input
              type="checkbox"
              checked={config.include_return_cost}
              onChange={(e) => setConfig({ ...config, include_return_cost: e.target.checked })}
              className="w-4 h-4 text-emerald-600 rounded border-slate-300 focus:ring-emerald-500"
            />
            <div>
              <span className="font-semibold text-slate-900 block">Deduct Reverse Shipping / Return Charges</span>
              <span className="text-slate-500 text-[11px]">
                Subtract courier return fees from product profit calculation.
              </span>
            </div>
          </label>
        </div>

        <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 pt-2">
          Deterministic Risk Engine Thresholds
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Critical Profit Margin (%)
            </label>
            <input
              type="number"
              step="0.5"
              value={config.critical_risk_margin_threshold}
              onChange={(e) => setConfig({ ...config, critical_risk_margin_threshold: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-semibold"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Below this % is CRITICAL</span>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Warning Return Rate (%)
            </label>
            <input
              type="number"
              step="0.5"
              value={config.warning_risk_return_rate_threshold}
              onChange={(e) => setConfig({ ...config, warning_risk_return_rate_threshold: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-semibold"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Above this % triggers WARNING</span>
          </div>

          <div>
            <label className="block font-semibold text-slate-700 mb-1">
              Warning RTO Rate (%)
            </label>
            <input
              type="number"
              step="0.5"
              value={config.warning_risk_rto_rate_threshold}
              onChange={(e) => setConfig({ ...config, warning_risk_rto_rate_threshold: parseFloat(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-semibold"
            />
            <span className="text-[10px] text-slate-400 mt-0.5 block">Above this % triggers WARNING</span>
          </div>
        </div>

        <div className="pt-4 border-t border-slate-100 flex justify-end">
          <button
            type="submit"
            className="flex items-center space-x-1.5 px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-bold shadow-xs"
          >
            <Save className="w-4 h-4" />
            <span>Save Rules & Recalculate</span>
          </button>
        </div>
      </form>

      {subStatus && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-1.5">
                <Zap className="w-4 h-4 text-emerald-600" />
                Subscription & Usage Limits
              </h3>
              <p className="text-xs text-slate-500">Current tier allocation for {activeOrg?.name}</p>
            </div>
            <span className="px-3 py-1 bg-emerald-100 text-emerald-800 text-xs font-bold rounded-full uppercase">
              {subStatus.plan_name} (₹{subStatus.price_inr}/mo)
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 text-xs bg-slate-50 p-4 rounded-lg border border-slate-200">
            <div>
              <span className="text-slate-500 font-semibold block">SKUs Tracked</span>
              <span className="font-bold text-slate-900 text-sm">
                {subStatus.usage.skus_used} / {subStatus.usage.max_skus}
              </span>
            </div>
            <div>
              <span className="text-slate-500 font-semibold block">Monthly Uploads</span>
              <span className="font-bold text-slate-900 text-sm">
                {subStatus.usage.uploads_used} / {subStatus.usage.max_uploads}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
