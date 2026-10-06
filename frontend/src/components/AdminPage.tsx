import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
import type {
  PlatformOverview,
  PlatformOrganization,
  PlatformUser,
  PlatformUpload,
  PlatformAuditLog,
  PlatformUserDetails,
  PlatformOrganizationDetails,
} from '../types';
import {
  Shield,
  Users,
  Building2,
  FileSpreadsheet,
  Activity,
  Search,
  RefreshCw,
  ShieldCheck,
  ShieldAlert,
  X,
  AlertCircle,
  Clock,
  Layers,
  ArrowRight,
  Filter,
} from 'lucide-react';

export const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'organizations' | 'uploads' | 'audit'>('overview');
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Platform Data
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [usersList, setUsersList] = useState<PlatformUser[]>([]);
  const [orgsList, setOrgsList] = useState<PlatformOrganization[]>([]);
  const [uploadsList, setUploadsList] = useState<PlatformUpload[]>([]);
  const [auditLogs, setAuditLogs] = useState<PlatformAuditLog[]>([]);

  // Filtering & Search
  const [userSearch, setUserSearch] = useState('');
  const [userRoleFilter, setUserRoleFilter] = useState<'all' | 'admin' | 'regular'>('all');
  const [orgSearch, setOrgSearch] = useState('');
  const [auditActionFilter, setAuditActionFilter] = useState<string>('all');
  const [auditSearch, setAuditSearch] = useState('');

  // Modals / Details
  const [selectedUser, setSelectedUser] = useState<PlatformUserDetails | null>(null);
  const [selectedOrg, setSelectedOrg] = useState<PlatformOrganizationDetails | null>(null);
  const [togglingAdmin, setTogglingAdmin] = useState(false);

  const fetchPlatformData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [ovRes, uRes, oRes, upRes, aRes] = await Promise.all([
        api.get('/admin/overview'),
        api.get('/admin/users?limit=100'),
        api.get('/admin/organizations?limit=100'),
        api.get('/admin/uploads?limit=100'),
        api.get('/admin/audit-logs?limit=150'),
      ]);

      setOverview(ovRes.data);
      setUsersList(uRes.data);
      setOrgsList(oRes.data);
      setUploadsList(upRes.data);
      setAuditLogs(aRes.data);
      setForbidden(false);
    } catch (err: any) {
      if (err.response?.status === 403) {
        setForbidden(true);
      } else {
        setErrorMsg(err.response?.data?.detail || 'Failed to load platform administration telemetry.');
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlatformData();
  }, []);

  const handleOpenUser = async (userId: string) => {
    try {
      const res = await api.get(`/admin/users/${userId}`);
      setSelectedUser(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load user details.');
    }
  };

  const handleOpenOrg = async (orgId: string) => {
    try {
      const res = await api.get(`/admin/organizations/${orgId}`);
      setSelectedOrg(res.data);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to load organization details.');
    }
  };

  const handleToggleAdmin = async (targetUserId: string, targetEmail: string) => {
    if (targetUserId === user?.id) {
      alert('You cannot change platform admin status on your own logged-in account.');
      return;
    }

    const confirmed = window.confirm(`Are you sure you want to toggle Platform Admin status for ${targetEmail}?`);
    if (!confirmed) return;

    setTogglingAdmin(true);
    try {
      const res = await api.post(`/admin/users/${targetUserId}/toggle-admin`);
      const newStatus = res.data.is_platform_admin;

      // Update in user list
      setUsersList(prev => prev.map(u => u.id === targetUserId ? { ...u, is_platform_admin: newStatus } : u));

      // Update in modal if open
      if (selectedUser && selectedUser.id === targetUserId) {
        setSelectedUser({ ...selectedUser, is_platform_admin: newStatus });
      }

      alert(res.data.message || 'Platform admin status updated successfully.');
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update platform admin status.');
    } finally {
      setTogglingAdmin(false);
    }
  };

  if (forbidden || (!loading && !user?.is_platform_admin)) {
    return (
      <div className="card p-12 max-w-lg mx-auto text-center space-y-4 my-12 animate-fadeIn">
        <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center bg-rose-50 border border-rose-100">
          <ShieldAlert className="w-8 h-8 text-rose-500" />
        </div>
        <h2 className="text-xl font-bold text-gray-900">Access Restricted</h2>
        <p className="text-[13px] text-gray-500 leading-relaxed">
          Platform administrator privileges are required to view this area. Your account does not have operator-level authority.
        </p>
        <div className="pt-2">
          <span className="text-[11px] font-mono text-gray-400 bg-gray-100 px-3 py-1 rounded-md">
            HTTP 403 Forbidden
          </span>
        </div>
      </div>
    );
  }

  // Filtered Users
  const filteredUsers = usersList.filter(u => {
    const q = userSearch.toLowerCase();
    const matchesSearch =
      u.name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      (u.organization_name && u.organization_name.toLowerCase().includes(q));

    if (userRoleFilter === 'admin') return matchesSearch && u.is_platform_admin;
    if (userRoleFilter === 'regular') return matchesSearch && !u.is_platform_admin;
    return matchesSearch;
  });

  // Filtered Organizations
  const filteredOrgs = orgsList.filter(o => {
    const q = orgSearch.toLowerCase();
    return o.name.toLowerCase().includes(q) || o.owner_email.toLowerCase().includes(q);
  });

  // Filtered Audit Logs
  const filteredLogs = auditLogs.filter(l => {
    const matchesAction = auditActionFilter === 'all' || l.action === auditActionFilter;
    const q = auditSearch.toLowerCase();
    const matchesSearch =
      !q ||
      l.action.toLowerCase().includes(q) ||
      l.resource_type.toLowerCase().includes(q) ||
      (l.ip_address && l.ip_address.toLowerCase().includes(q)) ||
      (l.user_id && l.user_id.toLowerCase().includes(q));
    return matchesAction && matchesSearch;
  });

  // Unique actions for audit log filter dropdown
  const auditActions = Array.from(new Set(auditLogs.map(l => l.action))).sort();

  return (
    <div className="space-y-6 animate-fadeIn pb-12">
      {/* ─── Platform Header ────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-gray-200">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center bg-indigo-600 text-white shadow-sm">
              <Shield className="w-4 h-4" />
            </div>
            <h1 className="text-xl font-bold text-gray-900">Platform Administration</h1>
            <span className="badge badge-indigo text-[11px]">System Operator</span>
          </div>
          <p className="text-[13px] text-gray-500 mt-1">
            Global telemetry, cross-tenant organizations, and compliance monitoring across Ordexa.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {overview?.timestamp && (
            <span className="text-[12px] text-gray-400 hidden md:inline-flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5" />
              Synced {new Date(overview.timestamp).toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchPlatformData}
            disabled={loading}
            className="btn-ghost border border-gray-200 bg-white hover:bg-gray-50 text-[13px] px-3 py-1.5"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-600' : 'text-gray-500'}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-100 text-rose-800 text-[13px] flex items-center gap-3">
          <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* ─── Navigation Tabs ──────────────────────────────────────────── */}
      <div className="flex items-center gap-1 border-b border-gray-200 overflow-x-auto pb-px">
        {[
          { id: 'overview', label: 'Overview', icon: Layers, count: null },
          { id: 'users', label: 'Users', icon: Users, count: usersList.length },
          { id: 'organizations', label: 'Organizations', icon: Building2, count: orgsList.length },
          { id: 'uploads', label: 'Upload Activity', icon: FileSpreadsheet, count: uploadsList.length },
          { id: 'audit', label: 'Audit Logs', icon: Activity, count: auditLogs.length },
        ].map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-2.5 text-[13px] font-semibold border-b-2 transition-all whitespace-nowrap ${
                isActive
                  ? 'border-indigo-600 text-indigo-600 bg-indigo-50/40 rounded-t-lg'
                  : 'border-transparent text-gray-500 hover:text-gray-800 hover:border-gray-300'
              }`}
            >
              <Icon className={`w-4 h-4 ${isActive ? 'text-indigo-600' : 'text-gray-400'}`} />
              <span>{tab.label}</span>
              {tab.count !== null && (
                <span className={`text-[11px] px-1.5 py-0.2 rounded-full font-bold ${
                  isActive ? 'bg-indigo-100 text-indigo-700' : 'bg-gray-100 text-gray-500'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ─── TAB 1: OVERVIEW ─────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* KPI Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="card p-5">
              <div className="flex items-center justify-between text-gray-500 mb-2">
                <span className="text-[12px] font-medium uppercase tracking-wider">Total Users</span>
                <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center text-indigo-600">
                  <Users className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-gray-900">{overview?.total_users ?? '—'}</div>
              <div className="text-[12px] text-gray-400 mt-1 flex items-center gap-1">
                <span>Active platform registrations</span>
              </div>
            </div>

            <div className="card p-5">
              <div className="flex items-center justify-between text-gray-500 mb-2">
                <span className="text-[12px] font-medium uppercase tracking-wider">Organizations</span>
                <div className="w-8 h-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600">
                  <Building2 className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-gray-900">{overview?.total_organizations ?? '—'}</div>
              <div className="text-[12px] text-gray-400 mt-1">Multi-tenant client workspaces</div>
            </div>

            <div className="card p-5">
              <div className="flex items-center justify-between text-gray-500 mb-2">
                <span className="text-[12px] font-medium uppercase tracking-wider">Total Uploads</span>
                <div className="w-8 h-8 rounded-lg bg-amber-50 flex items-center justify-center text-amber-600">
                  <FileSpreadsheet className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-gray-900">{overview?.total_uploads ?? '—'}</div>
              <div className="text-[12px] text-gray-400 mt-1">Ingested marketplace workbooks</div>
            </div>

            <div className="card p-5">
              <div className="flex items-center justify-between text-gray-500 mb-2">
                <span className="text-[12px] font-medium uppercase tracking-wider">Audit Events</span>
                <div className="w-8 h-8 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600">
                  <Activity className="w-4 h-4" />
                </div>
              </div>
              <div className="text-2xl font-bold text-gray-900">{overview?.total_audit_events ?? '—'}</div>
              <div className="text-[12px] text-gray-400 mt-1">Compliance & audit log trail</div>
            </div>
          </div>

          {/* Quick Previews: Recent Organizations & Recent Users */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Organizations Preview */}
            <div className="card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Building2 className="w-4 h-4 text-indigo-600" />
                  <h3 className="font-bold text-gray-900 text-[14px]">Recent Organizations</h3>
                </div>
                <button
                  onClick={() => setActiveTab('organizations')}
                  className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                >
                  <span>View All ({orgsList.length})</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="divide-y divide-gray-100">
                {orgsList.slice(0, 5).map(org => (
                  <div key={org.id} className="py-2.5 flex items-center justify-between gap-3 text-[13px]">
                    <div className="min-w-0">
                      <div className="font-semibold text-gray-900 truncate">{org.name}</div>
                      <div className="text-[12px] text-gray-400 truncate">{org.owner_email}</div>
                    </div>
                    <div className="text-right shrink-0">
                      <span className="text-[12px] font-medium text-gray-600">{org.upload_count} uploads</span>
                      <div className="text-[11px] text-gray-400">
                        {new Date(org.created_at).toLocaleDateString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Audit Activity */}
            <div className="card p-5 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-purple-600" />
                  <h3 className="font-bold text-gray-900 text-[14px]">Recent Platform Activity</h3>
                </div>
                <button
                  onClick={() => setActiveTab('audit')}
                  className="text-[12px] font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                >
                  <span>View All ({auditLogs.length})</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="divide-y divide-gray-100">
                {auditLogs.slice(0, 5).map(log => (
                  <div key={log.id} className="py-2.5 flex items-center justify-between gap-3 text-[13px]">
                    <div className="min-w-0 flex items-center gap-2">
                      <span className="badge badge-gray text-[10px] uppercase font-mono font-bold">
                        {log.action}
                      </span>
                      <span className="text-gray-600 text-[12px] truncate">{log.resource_type}</span>
                    </div>
                    <div className="text-[11px] text-gray-400 shrink-0">
                      {new Date(log.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 2: USERS ────────────────────────────────────────────── */}
      {activeTab === 'users' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search user by name, email, or company..."
                value={userSearch}
                onChange={e => setUserSearch(e.target.value)}
                className="input pl-9 text-[13px] py-2 w-full"
                style={{ paddingLeft: '36px' }}
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={userRoleFilter}
                onChange={e => setUserRoleFilter(e.target.value as any)}
                className="input text-[13px] py-1.5 px-3 bg-white"
              >
                <option value="all">All Roles ({usersList.length})</option>
                <option value="admin">Platform Admins ({usersList.filter(u => u.is_platform_admin).length})</option>
                <option value="regular">Standard Users ({usersList.filter(u => !u.is_platform_admin).length})</option>
              </select>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 text-gray-500 uppercase text-[11px] tracking-wider font-semibold">
                    <th className="px-4 py-3">Full Name</th>
                    <th className="px-4 py-3">Email Address</th>
                    <th className="px-4 py-3">Organization / Company</th>
                    <th className="px-4 py-3">Org Role</th>
                    <th className="px-4 py-3 text-center">Platform Admin</th>
                    <th className="px-4 py-3">Last Login</th>
                    <th className="px-4 py-3">Registered At</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredUsers.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-4 py-8 text-center text-gray-400">
                        No users match the search criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredUsers.map(u => (
                      <tr key={u.id} className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                          {u.name}
                        </td>
                        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                          {u.email}
                        </td>
                        <td className="px-4 py-3 text-gray-700 whitespace-nowrap">
                          {u.organization_name || '—'}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className="badge badge-gray uppercase text-[10px]">
                            {u.organization_role || 'member'}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap">
                          {u.is_platform_admin ? (
                            <span className="badge badge-indigo text-[11px] inline-flex items-center gap-1">
                              <ShieldCheck className="w-3 h-3 text-indigo-600" />
                              <span>Admin</span>
                            </span>
                          ) : (
                            <span className="text-[12px] text-gray-400">User</span>
                          )}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-[12px]">
                          {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : 'Never'}
                        </td>
                        <td className="px-4 py-3 text-gray-400 whitespace-nowrap text-[12px]">
                          {new Date(u.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleOpenUser(u.id)}
                              className="px-2.5 py-1 text-[12px] font-semibold text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                            >
                              Details
                            </button>
                            <button
                              onClick={() => handleToggleAdmin(u.id, u.email)}
                              disabled={togglingAdmin || u.id === user?.id}
                              title={u.id === user?.id ? "Cannot change your own admin status" : "Toggle platform admin"}
                              className={`px-2 py-1 text-[11px] font-semibold rounded-lg border transition-colors ${
                                u.id === user?.id
                                  ? 'opacity-40 cursor-not-allowed text-gray-400 border-gray-200'
                                  : u.is_platform_admin
                                  ? 'text-rose-600 border-rose-200 hover:bg-rose-50'
                                  : 'text-gray-700 border-gray-200 hover:bg-gray-100'
                              }`}
                            >
                              {u.is_platform_admin ? 'Demote' : 'Promote'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 3: ORGANIZATIONS ────────────────────────────────────── */}
      {activeTab === 'organizations' && (
        <div className="space-y-4">
          <div className="relative max-w-sm">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              placeholder="Search organization by company name or owner email..."
              value={orgSearch}
              onChange={e => setOrgSearch(e.target.value)}
              className="input pl-9 text-[13px] py-2 w-full"
              style={{ paddingLeft: '36px' }}
            />
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 text-gray-500 uppercase text-[11px] tracking-wider font-semibold">
                    <th className="px-4 py-3">Company Name</th>
                    <th className="px-4 py-3">Owner Email</th>
                    <th className="px-4 py-3">Sales Channels</th>
                    <th className="px-4 py-3 text-center">Members</th>
                    <th className="px-4 py-3 text-center">Uploads / Reports</th>
                    <th className="px-4 py-3">Created Date</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredOrgs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                        No organizations found matching search query.
                      </td>
                    </tr>
                  ) : (
                    filteredOrgs.map(org => (
                      <tr key={org.id} className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                          {org.name}
                        </td>
                        <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                          {org.owner_email}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap text-[12px]">
                          {org.sales_channels || 'Amazon, Flipkart, Shopify'}
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap font-medium text-gray-800">
                          {org.member_count}
                        </td>
                        <td className="px-4 py-3 text-center whitespace-nowrap font-medium text-gray-800">
                          {org.upload_count}
                        </td>
                        <td className="px-4 py-3 text-gray-400 whitespace-nowrap text-[12px]">
                          {new Date(org.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3 text-right whitespace-nowrap">
                          <button
                            onClick={() => handleOpenOrg(org.id)}
                            className="px-3 py-1 text-[12px] font-semibold text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                          >
                            View Workspace
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── TAB 4: UPLOAD ACTIVITY ─────────────────────────────────── */}
      {activeTab === 'uploads' && (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50 text-gray-500 uppercase text-[11px] tracking-wider font-semibold">
                  <th className="px-4 py-3">File Name</th>
                  <th className="px-4 py-3">Marketplace</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Rows Processed</th>
                  <th className="px-4 py-3 text-right">Rows Failed</th>
                  <th className="px-4 py-3">Uploaded Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {uploadsList.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
                      No report upload records logged across platform.
                    </td>
                  </tr>
                ) : (
                  uploadsList.map(up => (
                    <tr key={up.id} className="hover:bg-gray-50/60 transition-colors">
                      <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">
                        {up.filename}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="badge badge-gray uppercase text-[10px]">
                          {up.marketplace}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className={`badge ${
                          up.upload_status === 'COMPLETED'
                            ? 'badge-green'
                            : up.upload_status === 'FAILED'
                            ? 'badge-red'
                            : 'badge-amber'
                        }`}>
                          {up.upload_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap font-mono text-[12px] text-gray-700">
                        {up.rows_processed?.toLocaleString() ?? 0}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap font-mono text-[12px] text-rose-600">
                        {up.rows_failed?.toLocaleString() ?? 0}
                      </td>
                      <td className="px-4 py-3 text-gray-400 whitespace-nowrap text-[12px]">
                        {new Date(up.uploaded_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ─── TAB 5: AUDIT LOGS ───────────────────────────────────────── */}
      {activeTab === 'audit' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="relative flex-1 max-w-sm">
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input
                type="text"
                placeholder="Search audit trail by resource, IP, user ID..."
                value={auditSearch}
                onChange={e => setAuditSearch(e.target.value)}
                className="input pl-9 text-[13px] py-2 w-full"
                style={{ paddingLeft: '36px' }}
              />
            </div>

            <div className="flex items-center gap-2">
              <Filter className="w-4 h-4 text-gray-400" />
              <select
                value={auditActionFilter}
                onChange={e => setAuditActionFilter(e.target.value)}
                className="input text-[13px] py-1.5 px-3 bg-white"
              >
                <option value="all">All Actions ({auditLogs.length})</option>
                {auditActions.map(act => (
                  <option key={act} value={act}>{act}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-[13px]">
                <thead>
                  <tr className="border-b border-gray-200 bg-gray-50 text-gray-500 uppercase text-[11px] tracking-wider font-semibold">
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Resource Type</th>
                    <th className="px-4 py-3">Resource ID</th>
                    <th className="px-4 py-3">IP Address</th>
                    <th className="px-4 py-3">Metadata</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 font-mono text-[12px]">
                  {filteredLogs.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-8 text-center text-gray-400 font-sans">
                        No audit events match your filter criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredLogs.map(log => (
                      <tr key={log.id} className="hover:bg-gray-50/60 transition-colors">
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap">
                          <span className={`badge ${
                            log.action.includes('FAIL')
                              ? 'badge-red'
                              : log.action.includes('REGISTER') || log.action.includes('LOGIN')
                              ? 'badge-green'
                              : 'badge-indigo'
                          } text-[10px] uppercase font-bold tracking-tight`}>
                            {log.action}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-gray-700 whitespace-nowrap font-sans font-medium">
                          {log.resource_type}
                        </td>
                        <td className="px-4 py-3 text-gray-400 whitespace-nowrap">
                          {log.resource_id ? `${log.resource_id.substring(0, 8)}...` : '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-500 whitespace-nowrap">
                          {log.ip_address || '—'}
                        </td>
                        <td className="px-4 py-3 text-gray-600 truncate max-w-xs font-sans text-[11px]">
                          {log.metadata ? JSON.stringify(log.metadata) : '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ─── USER DETAILS MODAL ──────────────────────────────────────── */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 max-w-lg w-full p-6 space-y-5 animate-scaleUp max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-gray-400 font-bold">User Telemetry</span>
                <h3 className="text-xl font-bold text-gray-900 mt-0.5">{selectedUser.name}</h3>
                <p className="text-[13px] text-gray-500">{selectedUser.email}</p>
              </div>
              <button
                onClick={() => setSelectedUser(null)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 p-3.5 bg-gray-50 rounded-xl text-[12px]">
              <div>
                <span className="text-gray-400 block mb-0.5">Account Registered:</span>
                <span className="font-semibold text-gray-800">
                  {new Date(selectedUser.created_at).toLocaleDateString()}
                </span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Last Login:</span>
                <span className="font-semibold text-gray-800">
                  {selectedUser.last_login_at ? new Date(selectedUser.last_login_at).toLocaleString() : 'Never'}
                </span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">Platform Authority:</span>
                <span className="font-semibold text-gray-800">
                  {selectedUser.is_platform_admin ? 'Global Platform Admin' : 'Standard User'}
                </span>
              </div>
              <div>
                <span className="text-gray-400 block mb-0.5">User ID:</span>
                <span className="font-mono text-gray-600 text-[11px] truncate block">
                  {selectedUser.id}
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-[13px] font-bold text-gray-800 mb-2">Workspace Memberships</h4>
              {selectedUser.organizations?.length === 0 ? (
                <p className="text-[12px] text-gray-400 italic">No workspaces associated.</p>
              ) : (
                <div className="space-y-2">
                  {selectedUser.organizations?.map(o => (
                    <div key={o.organization_id} className="p-3 bg-white border border-gray-200 rounded-xl flex items-center justify-between text-[13px]">
                      <div>
                        <div className="font-semibold text-gray-900">{o.organization_name}</div>
                        <div className="text-[11px] text-gray-400">Joined {new Date(o.joined_at).toLocaleDateString()}</div>
                      </div>
                      <span className="badge badge-indigo text-[11px] uppercase">{o.role}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-2 flex items-center justify-between border-t border-gray-100">
              <button
                onClick={() => handleToggleAdmin(selectedUser.id, selectedUser.email)}
                disabled={togglingAdmin || selectedUser.id === user?.id}
                className={`px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-colors border ${
                  selectedUser.id === user?.id
                    ? 'opacity-40 cursor-not-allowed border-gray-200 text-gray-400'
                    : selectedUser.is_platform_admin
                    ? 'border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100'
                    : 'border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100'
                }`}
              >
                {selectedUser.is_platform_admin ? 'Revoke Platform Admin' : 'Grant Platform Admin'}
              </button>

              <button
                onClick={() => setSelectedUser(null)}
                className="btn-ghost border border-gray-200 text-[12px] px-3.5 py-1.5"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ─── ORGANIZATION DETAILS MODAL ──────────────────────────────── */}
      {selectedOrg && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 max-w-xl w-full p-6 space-y-5 animate-scaleUp max-h-[90vh] overflow-y-auto">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-gray-400 font-bold">Workspace Telemetry</span>
                <h3 className="text-xl font-bold text-gray-900 mt-0.5">{selectedOrg.name}</h3>
                <p className="text-[13px] text-gray-500">Owner: {selectedOrg.owner_email}</p>
              </div>
              <button
                onClick={() => setSelectedOrg(null)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Metrics Grid */}
            <div className="grid grid-cols-3 gap-3 p-3 bg-gray-50 rounded-xl text-center">
              <div>
                <span className="text-gray-400 text-[11px] block">Members</span>
                <span className="text-lg font-bold text-gray-900">{selectedOrg.member_count}</span>
              </div>
              <div>
                <span className="text-gray-400 text-[11px] block">Reports / Uploads</span>
                <span className="text-lg font-bold text-gray-900">{selectedOrg.upload_count}</span>
              </div>
              <div>
                <span className="text-gray-400 text-[11px] block">Active Products</span>
                <span className="text-lg font-bold text-gray-900">{selectedOrg.product_count}</span>
              </div>
            </div>

            {/* Members Section */}
            <div>
              <h4 className="text-[13px] font-bold text-gray-800 mb-2">Workspace Members ({selectedOrg.members.length})</h4>
              <div className="space-y-1.5 max-h-36 overflow-y-auto">
                {selectedOrg.members.map(m => (
                  <div key={m.user_id} className="p-2.5 bg-gray-50 rounded-lg flex items-center justify-between text-[12px]">
                    <div>
                      <span className="font-semibold text-gray-900">{m.name}</span>
                      <span className="text-gray-400 ml-2">({m.email})</span>
                    </div>
                    <span className="badge badge-gray uppercase text-[10px]">{m.role}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Uploads */}
            <div>
              <h4 className="text-[13px] font-bold text-gray-800 mb-2">Recent Report Uploads</h4>
              {selectedOrg.recent_uploads.length === 0 ? (
                <p className="text-[12px] text-gray-400 italic">No reports uploaded yet.</p>
              ) : (
                <div className="space-y-1.5 max-h-36 overflow-y-auto text-[12px]">
                  {selectedOrg.recent_uploads.map(up => (
                    <div key={up.id} className="p-2 bg-gray-50 rounded-lg flex items-center justify-between">
                      <span className="truncate max-w-[200px] font-medium text-gray-800">{up.filename}</span>
                      <div className="flex items-center gap-2">
                        <span className="badge badge-green text-[10px]">{up.upload_status}</span>
                        <span className="text-gray-400 text-[11px]">{new Date(up.uploaded_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end border-t border-gray-100">
              <button
                onClick={() => setSelectedOrg(null)}
                className="btn-ghost border border-gray-200 text-[12px] px-4 py-1.5"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
