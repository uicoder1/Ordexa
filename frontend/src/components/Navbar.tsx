import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Radar, Plus, LogOut, ChevronDown, Building2, ShieldCheck, LayoutDashboard, Package, RotateCcw, DollarSign, History, FileBarChart2, Settings, Shield } from 'lucide-react';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onOpenUpload: () => void;
  selectedChannel?: string;
  onSelectChannel?: (channel: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, onOpenUpload, selectedChannel = 'All', onSelectChannel }) => {
  const { user, activeOrg, organizations, switchOrganization, logout } = useAuth();
  const [showOrg, setShowOrg] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setShowOrg(false); };
    document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, []);

  const baseNavItems = [
    { id: 'overview',   label: 'Overview',   icon: LayoutDashboard },
    { id: 'products',   label: 'Products',   icon: Package },
    { id: 'returns',    label: 'Returns',    icon: RotateCcw },
    { id: 'financials', label: 'Financials', icon: DollarSign },
    { id: 'imports',    label: 'Imports',    icon: History },
    { id: 'reports',    label: 'Reports',    icon: FileBarChart2 },
    { id: 'settings',  label: 'Settings',   icon: Settings },
  ];

  const navItems = user?.is_platform_admin
    ? [...baseNavItems, { id: 'admin', label: 'Admin', icon: Shield }]
    : baseNavItems;

  const channels = ['All', 'Flipkart', 'Amazon', 'Meesho', 'Shopify'];

  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40" style={{ boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
      <div className="max-w-screen-xl mx-auto px-6">
        <div className="flex items-center justify-between h-14 gap-4">

          {/* Brand */}
          <div className="flex items-center gap-2.5 shrink-0 cursor-pointer" onClick={() => setActiveTab('overview')}>
            <div className="w-8 h-8 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}>
              <Radar className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-[16px] text-gray-900 tracking-tight">Ordexa</span>
          </div>

          {/* Store selector */}
          <div className="relative shrink-0" ref={ref}>
            {activeOrg && (
              <button
                onClick={() => setShowOrg(!showOrg)}
                className="flex items-center gap-2 text-[13px] font-medium px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-gray-700 transition-colors"
              >
                <Building2 className="w-3.5 h-3.5 text-gray-400" />
                <span className="max-w-[120px] truncate">{activeOrg.name}</span>
                <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${showOrg ? 'rotate-180' : ''}`} />
              </button>
            )}
            {showOrg && (
              <div className="dropdown absolute left-0 mt-2 w-56 py-1.5 animate-fadeInUp">
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-gray-400">Store</div>
                {organizations.map(org => (
                  <button key={org.id} onClick={() => { switchOrganization(org.id); setShowOrg(false); }}
                    className="w-full text-left px-3 py-2 text-[13px] flex items-center justify-between hover:bg-gray-50 transition-colors"
                    style={{ color: activeOrg?.id === org.id ? '#4f46e5' : '#374151' }}>
                    <span className="truncate font-medium">{org.name}</span>
                    {activeOrg?.id === org.id && <ShieldCheck className="w-3.5 h-3.5" style={{ color: '#4f46e5' }} />}
                  </button>
                ))}
                <div className="divider my-1.5" />
                <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-gray-400">Channel</div>
                {channels.map(ch => (
                  <button key={ch} onClick={() => { onSelectChannel?.(ch); setShowOrg(false); }}
                    className="w-full text-left px-3 py-1.5 text-[13px] hover:bg-gray-50 transition-colors"
                    style={{ color: selectedChannel === ch ? '#4f46e5' : '#4b5563', fontWeight: selectedChannel === ch ? 600 : 400 }}>
                    {ch}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Nav */}
          <nav className="hidden lg:flex items-center gap-0.5 flex-1 justify-center">
            {navItems.map(({ id, label }) => (
              <button key={id} onClick={() => setActiveTab(id)} className={`nav-pill ${activeTab === id ? 'active' : ''}`}>
                {label}
              </button>
            ))}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-3 shrink-0">
            <button onClick={onOpenUpload} className="btn-primary">
              <Plus className="w-4 h-4" />
              <span>Import Data</span>
            </button>
            <div className="flex items-center gap-2 pl-3 border-l border-gray-100">
              {user?.is_platform_admin && (
                <button
                  onClick={() => setActiveTab('admin')}
                  title="Platform Admin Console"
                  className={`px-2 py-0.5 rounded-full text-[11px] font-semibold border flex items-center gap-1 transition-all ${
                    activeTab === 'admin'
                      ? 'bg-indigo-600 text-white border-indigo-600 shadow-sm'
                      : 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
                  }`}
                >
                  <Shield className="w-3 h-3" />
                  <span>Admin</span>
                </button>
              )}
              <div className="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-bold" style={{ background: '#eef2ff', color: '#4f46e5' }}>
                {user?.name?.charAt(0) || 'U'}
              </div>
              <button onClick={logout} title="Sign out" className="btn-ghost p-1.5">
                <LogOut className="w-4 h-4 text-gray-400 hover:text-rose-500 transition-colors" />
              </button>
            </div>
          </div>

        </div>
      </div>
    </header>
  );
};
