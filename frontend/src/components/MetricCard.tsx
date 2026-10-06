import React from 'react';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: string;
  isPositiveTrend?: boolean;
  type?: 'profit' | 'loss' | 'warning' | 'info' | 'neutral';
  icon?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  subtitle,
  trend,
  isPositiveTrend = true,
  type = 'neutral',
  icon
}) => {
  let valueColor = 'text-slate-900';
  let borderTopColor = 'border-slate-200';

  if (type === 'profit') {
    valueColor = 'text-emerald-700';
    borderTopColor = 'border-emerald-500';
  } else if (type === 'loss') {
    valueColor = 'text-rose-700';
    borderTopColor = 'border-rose-500';
  } else if (type === 'warning') {
    valueColor = 'text-amber-700';
    borderTopColor = 'border-amber-500';
  } else if (type === 'info') {
    valueColor = 'text-indigo-700';
    borderTopColor = 'border-indigo-500';
  }

  return (
    <div className={`bg-white p-5 rounded-xl border border-slate-200 shadow-xs border-t-4 ${borderTopColor} transition-all hover:shadow-sm`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 tracking-wide uppercase">{title}</span>
        {icon && <div className="text-slate-400">{icon}</div>}
      </div>

      <div className={`mt-2 text-2xl font-bold tracking-tight ${valueColor}`}>
        {value}
      </div>

      {(subtitle || trend) && (
        <div className="mt-2 flex items-center justify-between text-xs">
          {trend && (
            <span
              className={`font-semibold flex items-center ${
                isPositiveTrend ? 'text-emerald-600' : 'text-rose-600'
              }`}
            >
              {isPositiveTrend ? '↑' : '↓'} {trend}
            </span>
          )}
          {subtitle && <span className="text-slate-400 text-[11px]">{subtitle}</span>}
        </div>
      )}
    </div>
  );
};
