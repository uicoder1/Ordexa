import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { api } from './services/api';
import { Navbar } from './components/Navbar';
import { OverviewPage } from './components/OverviewPage';
import { ProductsPage } from './components/ProductsPage';
import { ReturnsPage } from './components/ReturnsPage';
import { FinancialsPage } from './components/FinancialsPage';
import { ImportHistoryPage } from './components/ImportHistoryPage';
import { SettingsPage } from './components/SettingsPage';
import { UploadWizard } from './components/UploadWizard';
import { AuthModal } from './components/AuthModal';
import { SKUDetailPage } from './components/SKUDetailPage';
import { useState } from 'react';
import { Radar, Download, FileBarChart2 } from 'lucide-react';

const DashboardContent: React.FC = () => {
  const { user, activeOrg, isLoading: authLoading } = useAuth();
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedChannel, setSelectedChannel] = useState('All');
  const [showUpload, setShowUpload] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  const [selectedSku, setSelectedSku] = useState<string | null>(() => {
    if (typeof window !== 'undefined' && window.location.pathname.startsWith('/products/'))
      return decodeURIComponent(window.location.pathname.replace('/products/', ''));
    return null;
  });

  const handleSelectProduct = (sku: string) => {
    setSelectedSku(sku);
    window.history.pushState({}, '', `/products/${encodeURIComponent(sku)}`);
  };
  const handleBackToProducts = () => {
    setSelectedSku(null);
    window.history.pushState({}, '', '/');
  };

  if (authLoading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#4f46e5,#7c3aed)' }}>
          <Radar className="w-5 h-5 text-white" />
        </div>
        <span className="text-[13px] text-gray-400 font-medium">Loading Ordexa...</span>
      </div>
    </div>
  );

  if (!user) return <AuthModal />;

  const handleExportCSV = async () => {
    try {
      const res = await api.get('/reports/export-sku-profitability', { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Ordexa_${activeOrg?.name}_SKU_Report.csv`);
      document.body.appendChild(link); link.click(); link.remove();
    } catch { alert('Failed to export CSV.'); }
  };

  return (
    <div className="page-wrapper">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} onOpenUpload={() => setShowUpload(true)} selectedChannel={selectedChannel} onSelectChannel={setSelectedChannel} />

      <main className="max-w-screen-xl mx-auto px-6 py-6">
        {selectedSku ? (
          <SKUDetailPage sku={selectedSku} onBack={handleBackToProducts} />
        ) : (
          <>
            {activeTab === 'overview'   && <OverviewPage key={refreshKey} onOpenUpload={() => setShowUpload(true)} onNavigateToProducts={() => setActiveTab('products')} onSelectProduct={handleSelectProduct} />}
            {activeTab === 'products'   && <ProductsPage onOpenUpload={() => setShowUpload(true)} onSelectProduct={handleSelectProduct} />}
            {activeTab === 'returns'    && <ReturnsPage onSelectProduct={handleSelectProduct} />}
            {activeTab === 'financials' && <FinancialsPage onOpenUpload={() => setShowUpload(true)} />}
            {activeTab === 'imports'    && <ImportHistoryPage onRefreshMetrics={() => {}} />}
            {activeTab === 'settings'   && <SettingsPage />}
            {activeTab === 'reports'    && (
              <div className="card p-10 max-w-lg mx-auto text-center space-y-4">
                <div className="w-14 h-14 rounded-2xl mx-auto flex items-center justify-center bg-indigo-50">
                  <FileBarChart2 className="w-7 h-7 text-indigo-500" />
                </div>
                <h2 className="text-xl font-bold text-gray-900">Export Reports</h2>
                <p className="text-[13px] text-gray-500">Download SKU profitability and return ledger as CSV.</p>
                <button onClick={handleExportCSV} className="btn-primary mx-auto">
                  <Download className="w-4 h-4" /> Download SKU Report
                </button>
              </div>
            )}
          </>
        )}
      </main>

      {showUpload && (
        <UploadWizard onClose={() => setShowUpload(false)} onSuccess={() => { setShowUpload(false); setActiveTab('overview'); setRefreshKey(p => p + 1); }} />
      )}
    </div>
  );
};

export default function App() {
  return <AuthProvider><DashboardContent /></AuthProvider>;
}
