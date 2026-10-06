import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import type { Product } from '../types';
import { Save, Search, Plus, CheckCircle2 } from 'lucide-react';

interface ProductCostManagerProps {
  onProductsUpdated: () => void;
}

export const ProductCostManager: React.FC<ProductCostManagerProps> = ({ onProductsUpdated }) => {
  const [products, setProducts] = useState<Product[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [editingCosts, setEditingCosts] = useState<Record<string, number>>({});
  const [savingStatus, setSavingStatus] = useState<string | null>(null);
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const [newSKU, setNewSKU] = useState('');
  const [newName, setNewName] = useState('');
  const [newCost, setNewCost] = useState<number>(0);
  const [newCategory] = useState('General');

  const fetchProducts = async () => {
    try {
      const res = await api.get('/products');
      setProducts(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchProducts();
  }, []);

  const handleCostChange = (productId: string, cost: number) => {
    setEditingCosts((prev) => ({ ...prev, [productId]: cost }));
  };

  const handleSaveCost = async (product: Product) => {
    const newCostVal = editingCosts[product.id];
    if (newCostVal === undefined) return;

    try {
      setSavingStatus(`Saving SKU ${product.sku}...`);
      await api.put(`/products/${product.id}`, { purchase_cost: newCostVal });
      setSavingStatus('Cost updated! Metrics recalculated.');
      fetchProducts();
      onProductsUpdated();
      setTimeout(() => setSavingStatus(null), 3000);
    } catch (err: any) {
      setSavingStatus('Failed to update cost.');
    }
  };

  const handleBulkUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!bulkFile) return;

    const formData = new FormData();
    formData.append('file', bulkFile);

    try {
      setSavingStatus('Uploading cost file...');
      const res = await api.post('/products/bulk-cost-upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setSavingStatus(res.data.message);
      fetchProducts();
      onProductsUpdated();
      setBulkFile(null);
      setTimeout(() => setSavingStatus(null), 3000);
    } catch (err: any) {
      setSavingStatus(err.response?.data?.detail || 'Bulk upload failed.');
    }
  };

  const handleAddProduct = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSKU || !newName) return;

    try {
      await api.post('/products', {
        sku: newSKU,
        product_name: newName,
        purchase_cost: newCost,
        category: newCategory,
      });
      setShowAddModal(false);
      setNewSKU('');
      setNewName('');
      setNewCost(0);
      fetchProducts();
      onProductsUpdated();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add product.');
    }
  };

  const filteredProducts = products.filter(
    (p) =>
      p.sku.toLowerCase().includes(searchTerm.toLowerCase()) ||
      p.product_name.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-xs flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900">Product Purchase Costs</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Enter unit purchase costs so Ordexa can accurately calculate actual profit margins.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <form onSubmit={handleBulkUpload} className="flex items-center space-x-2">
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setBulkFile(e.target.files?.[0] || null)}
              id="bulk-cost-file"
              className="hidden"
            />
            <label
              htmlFor="bulk-cost-file"
              className="px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer border border-slate-200"
            >
              {bulkFile ? bulkFile.name : 'Bulk Cost CSV'}
            </label>
            {bulkFile && (
              <button
                type="submit"
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-xs font-semibold"
              >
                Upload
              </button>
            )}
          </form>

          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center space-x-1.5 px-3.5 py-1.5 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold shadow-xs"
          >
            <Plus className="w-4 h-4" />
            <span>Add Single SKU</span>
          </button>
        </div>
      </div>

      {savingStatus && (
        <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-900 rounded-lg text-xs font-semibold flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{savingStatus}</span>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 bg-slate-50 border-b border-slate-200 flex justify-between items-center">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
            <input
              type="text"
              placeholder="Search product cost list..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 w-64"
            />
          </div>
          <span className="text-xs text-slate-500 font-semibold">{filteredProducts.length} SKUs Cataloged</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/70 text-slate-600 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="px-4 py-3">SKU</th>
                <th className="px-4 py-3">Product Name</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3 text-right">Selling Price</th>
                <th className="px-4 py-3 text-right">Unit Purchase Cost (INR)</th>
                <th className="px-4 py-3 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {filteredProducts.map((p) => {
                const currentEditCost = editingCosts[p.id] !== undefined ? editingCosts[p.id] : p.purchase_cost;
                const isModified = editingCosts[p.id] !== undefined && editingCosts[p.id] !== p.purchase_cost;

                return (
                  <tr key={p.id} className="hover:bg-slate-50 transition-colors">
                    <td className="px-4 py-3 font-bold font-mono text-slate-900">{p.sku}</td>
                    <td className="px-4 py-3 font-medium text-slate-900 max-w-[240px] truncate">{p.product_name}</td>
                    <td className="px-4 py-3 text-slate-500">{p.category}</td>
                    <td className="px-4 py-3 text-right text-slate-700">₹{p.selling_price || 0}</td>
                    <td className="px-4 py-3 text-right">
                      <input
                        type="number"
                        step="0.01"
                        value={currentEditCost}
                        onChange={(e) => handleCostChange(p.id, parseFloat(e.target.value) || 0)}
                        className={`w-28 text-right px-2 py-1 border rounded text-xs font-bold ${
                          isModified ? 'border-amber-500 bg-amber-50 text-amber-900' : 'border-slate-300 text-slate-900'
                        }`}
                      />
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isModified && (
                        <button
                          onClick={() => handleSaveCost(p)}
                          className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-xs font-semibold inline-flex items-center space-x-1"
                        >
                          <Save className="w-3 h-3" />
                          <span>Save</span>
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {showAddModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl border border-slate-200 p-6 w-full max-w-md shadow-xl">
            <h3 className="text-base font-bold text-slate-900 mb-4">Add Product SKU</h3>
            <form onSubmit={handleAddProduct} className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-slate-700">SKU Code *</label>
                <input
                  type="text"
                  required
                  value={newSKU}
                  onChange={(e) => setNewSKU(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-medium"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Product Name *</label>
                <input
                  type="text"
                  required
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-medium"
                />
              </div>
              <div>
                <label className="block text-xs font-semibold text-slate-700">Unit Purchase Cost (INR)</label>
                <input
                  type="number"
                  step="0.01"
                  value={newCost}
                  onChange={(e) => setNewCost(parseFloat(e.target.value) || 0)}
                  className="w-full px-3 py-1.5 border border-slate-300 rounded text-xs font-medium"
                />
              </div>
              <div className="flex justify-end space-x-2 pt-3">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-1.5 border border-slate-300 text-slate-700 rounded text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-emerald-600 text-white rounded text-xs font-bold"
                >
                  Save Product
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
