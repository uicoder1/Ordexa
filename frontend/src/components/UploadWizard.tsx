import React, { useState, useCallback } from 'react';
import { api } from '../services/api';
import { UploadCloud, CheckCircle2, AlertTriangle, FileSpreadsheet, ArrowRight, Loader2, X, Sparkles } from 'lucide-react';

interface UploadWizardProps { onClose: () => void; onSuccess: () => void; }

export const UploadWizard: React.FC<UploadWizardProps> = ({ onClose, onSuccess }) => {
  const [step, setStep] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [marketplace, setMarketplace] = useState('Auto-Detect');
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDrag, setIsDrag] = useState(false);
  const [progressMsg, setProgressMsg] = useState('Initializing...');
  const [uploadData, setUploadData] = useState<any>(null);

  const marketplaces = [
    { value: 'Auto-Detect', label: 'Auto-Detect', emoji: '✨' },
    { value: 'Flipkart',    label: 'Flipkart',    emoji: '🛒' },
    { value: 'Amazon',      label: 'Amazon',      emoji: '📦' },
    { value: 'Meesho',      label: 'Meesho',      emoji: '🏪' },
    { value: 'Shopify',     label: 'Shopify',      emoji: '🛍️' },
    { value: 'Other',       label: 'Custom CSV',  emoji: '📄' },
  ];

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setIsDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f && ['csv','xlsx','xls'].includes(f.name.split('.').pop()?.toLowerCase() || '')) { setFile(f); setError(null); }
    else setError('Please upload an Excel or CSV report.');
  }, []);

  const handleStep1 = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { setError('Please select a report file.'); return; }
    setUploading(true); setError(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('marketplace', marketplace === 'Auto-Detect' ? 'Flipkart' : marketplace);
    try {
      const res = await api.post('/upload/file', fd, { headers: { 'Content-Type': 'multipart/form-data' } });
      setUploadData(res.data); setStep(2);
    } catch (err: any) { setError(err.response?.data?.detail || "We couldn't analyze this report. Please try again."); }
    finally { setUploading(false); }
  };

  const handleProcess = async () => {
    if (!uploadData) return;
    setProcessing(true); setStep(3); setError(null);
    const msgs = ['Finalizing analysis...','Syncing metrics...','Opening report...'];
    let i = 0;
    const iv = setInterval(() => { if (i < msgs.length - 1) setProgressMsg(msgs[++i]); else clearInterval(iv); }, 300);
    try {
      await api.post('/upload/process-mapping', { upload_id: uploadData.upload_id, marketplace: marketplace === 'Auto-Detect' ? 'Flipkart' : marketplace, mapping: uploadData.auto_mapping || {}, deduplication_mode: 'replace' });
      clearInterval(iv); setProgressMsg('Report ready!');
      setTimeout(() => { setProcessing(false); onSuccess(); onClose(); }, 400);
    } catch (err: any) {
      clearInterval(iv); setError(err.response?.data?.detail || "We couldn't analyze this report. Please try again."); setProcessing(false); setStep(2);
    }
  };

  const det = uploadData?.detection_summary;

  return (
    <div className="modal-overlay">
      <div className="modal-box max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-50 flex items-center justify-center">
              <UploadCloud className="w-4.5 h-4.5 text-indigo-600" />
            </div>
            <div>
              <h3 className="text-[15px] font-bold text-gray-900">Import Report</h3>
              <p className="text-[11px] text-gray-400">Drop any marketplace Excel or CSV — we'll figure it out</p>
            </div>
          </div>
          <button onClick={onClose} disabled={processing} className="btn-ghost p-1.5 text-gray-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        {error && (
          <div className="mx-6 mt-4 p-3 rounded-xl text-[12px] font-medium bg-red-50 text-red-700 border border-red-100 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />{error}
          </div>
        )}

        <div className="p-6">
          {/* Step 1 */}
          {step === 1 && (
            <form onSubmit={handleStep1} className="space-y-4">
              <div>
                <label className="block text-[13px] font-semibold text-gray-700 mb-2">Marketplace</label>
                <div className="grid grid-cols-3 gap-2">
                  {marketplaces.map(m => (
                    <button key={m.value} type="button" onClick={() => setMarketplace(m.value)}
                      className={`flex items-center gap-2 px-3 py-2.5 rounded-xl text-[12px] font-medium transition-all border ${marketplace === m.value ? 'bg-indigo-50 border-indigo-200 text-indigo-700' : 'bg-gray-50 border-gray-200 text-gray-600 hover:bg-gray-100'}`}>
                      <span>{m.emoji}</span><span>{m.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className={`dropzone ${isDrag ? 'active' : ''}`}
                onDragOver={e => { e.preventDefault(); setIsDrag(true); }} onDragLeave={() => setIsDrag(false)} onDrop={handleDrop}
                onClick={() => document.getElementById('file-inp')?.click()}>
                <input type="file" accept=".csv,.xlsx,.xls" id="file-inp" className="hidden" onChange={e => { if (e.target.files?.[0]) { setFile(e.target.files[0]); setError(null); } }} />
                <FileSpreadsheet className="w-10 h-10 text-indigo-300 mx-auto mb-3" />
                <p className="text-[14px] font-semibold text-gray-700 mb-1">Drop your report here</p>
                <p className="text-[12px] text-gray-400">.xlsx, .xls, or .csv · any layout works</p>
                {file && (
                  <div className="mt-4 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 text-[12px] font-semibold border border-emerald-100">
                    <CheckCircle2 className="w-4 h-4" />{file.name} ({(file.size / 1048576).toFixed(2)} MB)
                  </div>
                )}
              </div>

              <div className="flex justify-end">
                <button type="submit" disabled={uploading || !file} className="btn-primary">
                  {uploading ? <><Loader2 className="w-4 h-4 animate-spin" />Analyzing your report...</> : <><Sparkles className="w-4 h-4" />Analyze Report</>}
                </button>
              </div>
            </form>
          )}

          {/* Step 2 */}
          {step === 2 && uploadData && (
            <div className="space-y-4 animate-slideUp">
              <div className="card-flat p-4 space-y-3">
                <div className="flex justify-between items-center pb-3 border-b border-gray-100">
                  <span className="text-[14px] font-bold text-gray-900">Your report is ready</span>
                  <span className="badge badge-indigo text-[11px]">{uploadData.filename}</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    `${det?.rows_count?.toLocaleString()} rows detected`,
                    `${det?.orders_count?.toLocaleString()} orders`,
                    `${det?.skus_count} unique SKUs`,
                    det?.sales_detected ? '✓ Sales data found' : '⚠ No sales',
                    det?.returns_detected ? '✓ Returns data found' : '⚠ No returns',
                    det?.cancellations_detected ? '✓ Cancellations found' : '⚠ No cancellations',
                  ].map((txt, i) => (
                    <div key={i} className="flex items-center gap-2 text-[12px] text-gray-600">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0" />{txt}
                    </div>
                  ))}
                </div>
                {det?.missing_warnings?.length > 0 && (
                  <div className="p-3 rounded-xl bg-amber-50 border border-amber-100 space-y-1">
                    <p className="text-[12px] font-semibold text-amber-700 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> Notices</p>
                    {det.missing_warnings.map((w: string) => (
                      <p key={w} className="text-[11px] text-amber-600">⚠ {w}: Not present in this report</p>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex justify-between">
                <button onClick={() => setStep(1)} className="btn-secondary">Back</button>
                <button onClick={handleProcess} className="btn-primary">View Report <ArrowRight className="w-4 h-4" /></button>
              </div>
            </div>
          )}

          {/* Step 3 */}
          {step === 3 && (
            <div className="py-12 text-center space-y-4 animate-fadeIn">
              <div className="w-14 h-14 rounded-2xl mx-auto bg-indigo-50 flex items-center justify-center">
                <Loader2 className="w-7 h-7 animate-spin text-indigo-500" />
              </div>
              <h4 className="text-[16px] font-bold text-gray-900">Opening Report...</h4>
              <p className="text-[13px] text-indigo-500 font-medium animate-pulse">{progressMsg}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
