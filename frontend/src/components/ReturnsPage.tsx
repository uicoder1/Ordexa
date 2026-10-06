import React, { useEffect, useState, useMemo } from 'react';
import { api } from '../services/api';
import {
  RotateCcw, Package, AlertTriangle, CheckCircle2,
  Info, Search, Calendar, X, HelpCircle,
  RefreshCw, Eye
} from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

interface Props {
  onSelectProduct?: (sku: string) => void;
}

interface ReturnOrderRow {
  order_id: string;
  order_item_id: string;
  sku: string;
  product_name: string;
  order_date: string;
  return_date: string;
  order_type: string;
  quantity: number;
  return_value: number;
  customer_delivery_state: string;
  event: string;
  event_subtype: string;
  has_sale_event: boolean;
  sale_date: string | null;
  sale_value: number | null;
}

interface ProductReturnSummary {
  return_rank: number;
  sku: string;
  product_name: string;
  sale_items: number;
  returned_items: number;
  sale_linked_returns: number;
  sale_linked_return_rate: number;
  returned_value: number;
  revenue_generated: number;
}

export const ReturnsPage: React.FC<Props> = ({ onSelectProduct }) => {
  // Summary & KPIs
  const [summary, setSummary] = useState<any>(null);
  const [loadingSummary, setLoadingSummary] = useState(true);

  // Products with most returns
  const [products, setProducts] = useState<ProductReturnSummary[]>([]);
  const [loadingProducts, setLoadingProducts] = useState(true);
  const [productSearch, setProductSearch] = useState('');

  // Return Orders table
  const [orders, setOrders] = useState<ReturnOrderRow[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(true);

  // Filters for orders table
  const [search, setSearch] = useState('');
  const [eventFilter, setEventFilter] = useState<'RETURN' | 'CANCELLATION' | 'RETURN_CANCELLATION'>('RETURN');
  const [skuFilter, setSkuFilter] = useState('');
  const [orderTypeFilter, setOrderTypeFilter] = useState('ALL');
  const [stateFilter, setStateFilter] = useState('ALL');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Selected Order for Detail Modal
  const [selectedOrder, setSelectedOrder] = useState<ReturnOrderRow | null>(null);

  // Pagination for orders table
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // 1. Fetch Summary & KPIs
  useEffect(() => {
    setLoadingSummary(true);
    api.get('/dashboard/returns-summary')
      .then(res => setSummary(res.data))
      .catch(console.error)
      .finally(() => setLoadingSummary(false));
  }, []);

  // 2. Fetch Products with Most Returns
  useEffect(() => {
    setLoadingProducts(true);
    api.get('/dashboard/returns/products')
      .then(res => setProducts(res.data))
      .catch(console.error)
      .finally(() => setLoadingProducts(false));
  }, []);

  // 3. Fetch Return Orders Ledger
  const fetchOrders = () => {
    setLoadingOrders(true);
    const params: any = { event: eventFilter };
    if (search.trim()) params.search = search.trim();
    if (skuFilter.trim()) params.sku = skuFilter.trim();
    if (orderTypeFilter !== 'ALL') params.order_type = orderTypeFilter;
    if (stateFilter !== 'ALL') params.delivery_state = stateFilter;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;

    api.get('/dashboard/returns/orders', { params })
      .then(res => {
        setOrders(res.data);
        setPage(1);
      })
      .catch(console.error)
      .finally(() => setLoadingOrders(false));
  };

  useEffect(() => {
    fetchOrders();
  }, [eventFilter, skuFilter, orderTypeFilter, stateFilter, startDate, endDate]);

  // Debounced search trigger for orders table
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchOrders();
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Reset all filters
  const handleResetFilters = () => {
    setSearch('');
    setEventFilter('RETURN');
    setSkuFilter('');
    setOrderTypeFilter('ALL');
    setStateFilter('ALL');
    setStartDate('');
    setEndDate('');
  };

  const hasActiveFilters = Boolean(
    search || eventFilter !== 'RETURN' || skuFilter || orderTypeFilter !== 'ALL' ||
    stateFilter !== 'ALL' || startDate || endDate
  );

  // Filtered products list
  const filteredProducts = useMemo(() => {
    if (!productSearch.trim()) return products;
    const q = productSearch.toLowerCase().trim();
    return products.filter(p =>
      p.sku.toLowerCase().includes(q) || p.product_name.toLowerCase().includes(q)
    );
  }, [products, productSearch]);

  // Paginated orders
  const paginatedOrders = useMemo(() => {
    const start = (page - 1) * pageSize;
    return orders.slice(start, start + pageSize);
  }, [orders, page]);

  const totalPages = Math.ceil(orders.length / pageSize) || 1;

  if (loadingSummary && !summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 rounded-full animate-spin" style={{ border: '3px solid #e5e7eb', borderTopColor: '#4f46e5' }} />
      </div>
    );
  }

  // Top KPI Card metrics
  const totalReturnEvents = summary?.total_return_events ?? summary?.return_events_count ?? 0;
  const uniqueReturnedItems = summary?.unique_returned_order_items ?? summary?.returned_order_items_count ?? 0;
  const saleLinkedReturnedItems = summary?.sale_linked_returned_items ?? 0;
  const saleLinkedReturnRate = summary?.sale_linked_return_rate ?? 0;
  const returnedValue = summary?.returned_value ?? 0;
  const returnCancellations = summary?.return_cancellations ?? summary?.return_cancellation_events_count ?? 0;
  const cancellations = summary?.cancellations ?? summary?.cancellation_events_count ?? 0;

  return (
    <div className="space-y-6 animate-fadeInUp pb-12">

      {/* ─── 1. PAGE HEADER ────────────────────────────────────────── */}
      <div className="card p-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-rose-50 flex items-center justify-center shrink-0">
                <RotateCcw className="w-4 h-4 text-rose-500" />
              </div>
              <h1 className="text-xl font-bold text-gray-900">Returns & Reverse Logistics</h1>
            </div>
            <p className="text-[13px] text-gray-500 mt-1">
              Event Sub Type classified return orders, sale-to-return linking, and SKU frequency patterns
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-indigo">Flipkart Sales Report</span>
            <span className="badge badge-gray text-[11px]">Event Sub Type: Canonical</span>
          </div>
        </div>
      </div>

      {/* ─── 2. TOP KPI CARDS ──────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 stagger">
        {/* Total Return Events */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Return Events</span>
            <div className="w-7 h-7 rounded-lg bg-rose-50 flex items-center justify-center">
              <RotateCcw className="w-3.5 h-3.5 text-rose-500" />
            </div>
          </div>
          <div className="text-2xl font-bold text-gray-900">{totalReturnEvents.toLocaleString('en-IN')}</div>
          <div className="text-[11px] text-gray-400 mt-1">Event Sub Type = Return</div>
        </div>

        {/* Unique Returned Order Items */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Returned Items</span>
            <div className="w-7 h-7 rounded-lg bg-orange-50 flex items-center justify-center">
              <Package className="w-3.5 h-3.5 text-orange-500" />
            </div>
          </div>
          <div className="text-2xl font-bold text-gray-900">{uniqueReturnedItems.toLocaleString('en-IN')}</div>
          <div className="text-[11px] text-gray-400 mt-1">Unique order items</div>
        </div>

        {/* Sale-linked Returned Items */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Sale-Linked</span>
            <div className="w-7 h-7 rounded-lg bg-indigo-50 flex items-center justify-center">
              <CheckCircle2 className="w-3.5 h-3.5 text-indigo-500" />
            </div>
          </div>
          <div className="text-2xl font-bold text-indigo-600">{saleLinkedReturnedItems.toLocaleString('en-IN')}</div>
          <div className="text-[11px] text-gray-400 mt-1">Both Sale + Return</div>
        </div>

        {/* Sale-linked Return Rate */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Return Rate</span>
            <div className="w-7 h-7 rounded-lg bg-rose-50 flex items-center justify-center">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
            </div>
          </div>
          <div className="text-2xl font-bold" style={{ color: saleLinkedReturnRate >= 25 ? '#e11d48' : saleLinkedReturnRate >= 15 ? '#d97706' : '#4f46e5' }}>
            {saleLinkedReturnRate}%
          </div>
          <div className="text-[11px] text-gray-400 mt-1">sale-linked / sale items</div>
        </div>

        {/* Returned Value */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Returned Value</span>
            <div className="w-7 h-7 rounded-lg bg-rose-50 flex items-center justify-center">
              <span className="text-xs font-bold text-rose-600">₹</span>
            </div>
          </div>
          <div className="text-2xl font-bold text-rose-600">₹{Math.round(returnedValue).toLocaleString('en-IN')}</div>
          <div className="text-[11px] text-gray-400 mt-1">Return invoice sum</div>
        </div>

        {/* Return Cancellations */}
        <div className="stat-card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Return Cancels</span>
            <div className="w-7 h-7 rounded-lg bg-purple-50 flex items-center justify-center">
              <RefreshCw className="w-3.5 h-3.5 text-purple-600" />
            </div>
          </div>
          <div className="text-2xl font-bold text-purple-600">{returnCancellations.toLocaleString('en-IN')}</div>
          <div className="text-[11px] text-gray-400 mt-1">Event: Return Cancellation</div>
        </div>
      </div>

      {/* ─── 3. RETURN TIMELINE ────────────────────────────────────── */}
      <div className="card p-5 space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div>
            <h2 className="section-title">Returns by Date</h2>
            <p className="section-sub">Daily return events vs sale-linked returns across the reporting period</p>
          </div>
          <div className="flex items-center gap-4 text-[12px]">
            <span className="flex items-center gap-1.5 font-medium text-gray-600">
              <span className="w-3 h-0.5 bg-rose-500 inline-block rounded" /> All Return Events
            </span>
            <span className="flex items-center gap-1.5 font-medium text-gray-600">
              <span className="w-3 h-0.5 bg-indigo-600 inline-block rounded" /> Sale-linked Returns
            </span>
          </div>
        </div>

        {summary?.timeline_chart && summary.timeline_chart.length > 0 ? (
          <div className="h-64 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={summary.timeline_chart} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#64748b' }} stroke="#cbd5e1" />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} stroke="#cbd5e1" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    fontSize: 12,
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="returns"
                  name="Return Events"
                  stroke="#e11d48"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
                <Line
                  type="monotone"
                  dataKey="sale_linked_returns"
                  name="Sale-linked Returns"
                  stroke="#4f46e5"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                  dot={{ r: 2 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-32 flex items-center justify-center rounded-xl border border-dashed border-gray-200 text-[13px] text-gray-400">
            No timeline data available for the current period.
          </div>
        )}
      </div>

      {/* ─── 4. RETURN REASON (HONEST UNAVAILABILITY) ────────────────── */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-amber-50 flex items-center justify-center shrink-0">
            <HelpCircle className="w-4 h-4 text-amber-500" />
          </div>
          <div>
            <h2 className="section-title">Return Reason</h2>
            <p className="section-sub">Classification by cause — Customer Return · Delivery Failure / RTO · Unsold Goods</p>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { label: 'Customer Return', icon: '👤', desc: 'Buyer initiated return' },
            { label: 'Delivery Failure / RTO', icon: '🚚', desc: 'Undelivered courier return' },
            { label: 'Unsold Goods', icon: '📦', desc: 'Inventory recall / unfulfilled' },
          ].map(c => (
            <div key={c.label} className="card-flat p-4 bg-gray-50/50">
              <div className="flex items-center justify-between mb-2">
                <span className="text-2xl">{c.icon}</span>
                <span className="badge badge-gray text-[11px]">Unavailable</span>
              </div>
              <div className="text-[13px] font-semibold text-gray-800">{c.label}</div>
              <div className="text-[11px] text-gray-400 mt-0.5">{c.desc}</div>
            </div>
          ))}
        </div>

        <div className="rounded-xl bg-amber-50/70 border border-amber-100 p-4 flex items-start gap-3 text-[12px] text-amber-800 leading-relaxed">
          <Info className="w-4 h-4 shrink-0 mt-0.5 text-amber-500" />
          <div>
            The current Flipkart Sales Report identifies Return events using <strong>Event Sub Type = Return</strong>, but does not include explicit return reason or return disposition fields.
            Ordexa does not infer Customer Return, Delivery Failure / RTO, or Unsold Goods from generic Return events.
          </div>
        </div>
      </div>

      {/* ─── 5. RETURN PRODUCT SUMMARY ─────────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="section-title">Products With Most Returns</h2>
            <p className="section-sub">
              Descriptive ranking of SKUs by returned item count. Not ranked as best/worst.
            </p>
          </div>
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search SKU or title…"
              value={productSearch}
              onChange={e => setProductSearch(e.target.value)}
              className="input pl-9 text-[12px] py-1.5 w-60"
            />
          </div>
        </div>

        {loadingProducts ? (
          <div className="flex justify-center py-12"><RefreshCw className="w-6 h-6 animate-spin text-indigo-500" /></div>
        ) : filteredProducts.length === 0 ? (
          <div className="py-12 text-center text-[13px] text-gray-400">No products found with return records.</div>
        ) : (
          <div className="overflow-x-auto max-h-96">
            <table className="table-white">
              <thead>
                <tr>
                  <th className="w-14 text-center">Rank</th>
                  <th>SKU</th>
                  <th>Product Name</th>
                  <th className="text-center">Sale Items</th>
                  <th className="text-center">Returned Items</th>
                  <th className="text-right">Sale-linked Return %</th>
                  <th className="text-right">Returned Value (₹)</th>
                  <th className="text-right">Revenue Generated (₹)</th>
                  <th className="w-20 text-center">Filter</th>
                </tr>
              </thead>
              <tbody>
                {filteredProducts.map((p) => {
                  const rateColor = p.sale_linked_return_rate >= 25 ? '#e11d48' : p.sale_linked_return_rate >= 15 ? '#d97706' : '#10b981';
                  return (
                    <tr key={p.sku} className="hover:bg-gray-50/70 transition-colors">
                      <td className="text-center font-mono font-bold text-gray-400 text-[11px]">#{p.return_rank}</td>
                      <td>
                        <button
                          onClick={() => onSelectProduct ? onSelectProduct(p.sku) : setSkuFilter(p.sku)}
                          className="font-mono text-[12px] font-bold text-indigo-600 hover:text-indigo-800 hover:underline text-left inline-flex items-center gap-1"
                        >
                          {p.sku}
                        </button>
                      </td>
                      <td className="text-[12px] text-gray-700 max-w-[240px] truncate" title={p.product_name}>
                        {p.product_name}
                      </td>
                      <td className="text-center font-semibold text-gray-700">{p.sale_items}</td>
                      <td className="text-center font-bold text-rose-600">{p.returned_items}</td>
                      <td className="text-right font-bold text-[13px]" style={{ color: rateColor }}>
                        {p.sale_linked_return_rate}%
                      </td>
                      <td className="text-right font-semibold text-rose-600">
                        ₹{p.returned_value.toLocaleString('en-IN')}
                      </td>
                      <td className="text-right font-semibold text-emerald-600">
                        ₹{p.revenue_generated.toLocaleString('en-IN')}
                      </td>
                      <td className="text-center">
                        <button
                          onClick={() => setSkuFilter(p.sku)}
                          className="text-[11px] text-indigo-600 hover:text-indigo-800 font-semibold px-2 py-0.5 rounded hover:bg-indigo-50 transition-colors"
                          title="Filter orders ledger below by this SKU"
                        >
                          Orders
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <div className="px-6 py-2.5 border-t border-gray-100 flex items-center justify-between text-[11px] text-gray-400">
          <span>Showing {filteredProducts.length} returned SKUs</span>
          <span>Revenue Generated is from Sale events only · Returned Value is from Return events only</span>
        </div>
      </div>

      {/* ─── 6. ALL RETURN ORDERS TABLE ─────────────────────────────── */}
      <div className="card overflow-hidden">
        {/* Header & Event Filter Pills */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-wrap gap-3">
          <div>
            <h2 className="section-title">All Return Orders</h2>
            <p className="section-sub">
              Individual reverse logistics ledger records ({orders.length} matching rows)
            </p>
          </div>
          {/* Event Filter Pills */}
          <div className="flex items-center p-1 bg-gray-100 rounded-xl">
            <button
              onClick={() => setEventFilter('RETURN')}
              className={`px-3 py-1 text-[12px] font-semibold rounded-lg transition-all ${
                eventFilter === 'RETURN'
                  ? 'bg-white text-rose-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Return ({totalReturnEvents})
            </button>
            <button
              onClick={() => setEventFilter('CANCELLATION')}
              className={`px-3 py-1 text-[12px] font-semibold rounded-lg transition-all ${
                eventFilter === 'CANCELLATION'
                  ? 'bg-white text-amber-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Cancellation ({cancellations})
            </button>
            <button
              onClick={() => setEventFilter('RETURN_CANCELLATION')}
              className={`px-3 py-1 text-[12px] font-semibold rounded-lg transition-all ${
                eventFilter === 'RETURN_CANCELLATION'
                  ? 'bg-white text-purple-600 shadow-sm'
                  : 'text-gray-500 hover:text-gray-800'
              }`}
            >
              Return Cancellation ({returnCancellations})
            </button>
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="px-6 py-3.5 border-b border-gray-100 bg-gray-50/60 flex flex-wrap items-center gap-2.5 text-[12px]">
          {/* Search Input */}
          <div className="relative min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search Order ID, Item ID, SKU…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="input pl-9 text-[12px] py-1.5 w-full"
            />
          </div>

          {/* SKU Filter */}
          <select
            value={skuFilter}
            onChange={e => setSkuFilter(e.target.value)}
            className="input text-[12px] py-1.5 max-w-[170px]"
          >
            <option value="">All SKUs</option>
            {summary?.filter_options?.skus?.map((s: string) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>

          {/* Order Type Filter */}
          <select
            value={orderTypeFilter}
            onChange={e => setOrderTypeFilter(e.target.value)}
            className="input text-[12px] py-1.5"
          >
            <option value="ALL">All Order Types</option>
            {summary?.filter_options?.order_types?.map((ot: string) => (
              <option key={ot} value={ot}>{ot}</option>
            ))}
          </select>

          {/* State Filter */}
          <select
            value={stateFilter}
            onChange={e => setStateFilter(e.target.value)}
            className="input text-[12px] py-1.5 max-w-[150px]"
          >
            <option value="ALL">All States</option>
            {summary?.filter_options?.delivery_states?.map((st: string) => (
              <option key={st} value={st}>{st}</option>
            ))}
          </select>

          {/* Date range inputs */}
          <div className="flex items-center gap-1.5 bg-white border border-gray-200 rounded-xl px-2 py-1">
            <Calendar className="w-3.5 h-3.5 text-gray-400" />
            <input
              type="date"
              value={startDate}
              onChange={e => setStartDate(e.target.value)}
              className="text-[11px] text-gray-600 outline-none bg-transparent"
              title="Start date"
            />
            <span className="text-gray-300">to</span>
            <input
              type="date"
              value={endDate}
              onChange={e => setEndDate(e.target.value)}
              className="text-[11px] text-gray-600 outline-none bg-transparent"
              title="End date"
            />
          </div>

          {/* Reset Filters */}
          {hasActiveFilters && (
            <button
              onClick={handleResetFilters}
              className="btn-ghost text-[11px] text-rose-600 hover:text-rose-700 py-1 px-2.5 flex items-center gap-1"
            >
              <X className="w-3.5 h-3.5" /> Reset Filters
            </button>
          )}
        </div>

        {/* Ledger Table */}
        {loadingOrders ? (
          <div className="flex justify-center py-16"><RefreshCw className="w-6 h-6 animate-spin text-indigo-500" /></div>
        ) : orders.length === 0 ? (
          <div className="py-16 text-center text-[13px] text-gray-400">
            {eventFilter === 'CANCELLATION' ? 'No cancellation orders match your selected filters.' : 'No return orders match your selected filters.'}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="table-white">
              <thead>
                <tr>
                  <th>Order ID</th>
                  <th>Order Item ID</th>
                  <th>SKU</th>
                  <th>Product Name</th>
                  <th>{eventFilter === 'CANCELLATION' ? 'Cancel Date' : 'Return Date'}</th>
                  <th>Order Type</th>
                  <th className="text-center">Qty</th>
                  <th className="text-right">{eventFilter === 'CANCELLATION' ? 'Invoice Amount (₹)' : 'Return Value (₹)'}</th>
                  <th>Delivery State</th>
                  <th className="text-center">Event</th>
                  <th className="w-16 text-center">Action</th>
                </tr>
              </thead>
              <tbody>
                {paginatedOrders.map((row) => (
                  <tr
                    key={row.order_item_id}
                    onClick={() => setSelectedOrder(row)}
                    className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                  >
                    <td className="font-mono text-[11px] text-gray-700 max-w-[130px] truncate" title={row.order_id}>
                      {row.order_id}
                    </td>
                    <td className="font-mono text-[11px] text-gray-500 max-w-[110px] truncate" title={row.order_item_id}>
                      {row.order_item_id}
                    </td>
                    <td>
                      <span className="font-mono text-[12px] font-semibold text-indigo-600">
                        {row.sku}
                      </span>
                    </td>
                    <td className="text-[12px] text-gray-700 max-w-[170px] truncate" title={row.product_name}>
                      {row.product_name}
                    </td>
                    <td className="text-[12px] whitespace-nowrap text-gray-600">{row.return_date}</td>
                    <td className="text-[12px] text-gray-500">{row.order_type}</td>
                    <td className="text-center font-semibold text-gray-700">{row.quantity}</td>
                    <td className="text-right font-bold text-gray-900">
                      ₹{row.return_value.toLocaleString('en-IN')}
                    </td>
                    <td className="text-[12px] text-gray-500 whitespace-nowrap">{row.customer_delivery_state}</td>
                    <td className="text-center">
                      <span className={`badge ${row.event === 'RETURN' ? 'badge-red' : 'badge-purple'} text-[10px]`}>
                        {row.event}
                      </span>
                    </td>
                    <td className="text-center">
                      <button
                        onClick={(e) => { e.stopPropagation(); setSelectedOrder(row); }}
                        className="btn-ghost p-1 text-gray-400 hover:text-indigo-600"
                        title="View order detail modal"
                      >
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Bar */}
        <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between flex-wrap gap-2 text-[12px] text-gray-500">
          <div>
            Showing {orders.length > 0 ? (page - 1) * pageSize + 1 : 0} to {Math.min(page * pageSize, orders.length)} of {orders.length} return orders
          </div>
          {totalPages > 1 && (
            <div className="flex items-center gap-1.5">
              <button
                disabled={page <= 1}
                onClick={() => setPage(p => p - 1)}
                className="btn-ghost text-[11px] py-1 px-2.5 disabled:opacity-30"
              >
                Previous
              </button>
              <span className="text-[11px] font-medium text-gray-700 px-2">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage(p => p + 1)}
                className="btn-ghost text-[11px] py-1 px-2.5 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ─── 7. RETURN DATA COVERAGE (DATA QUALITY) ─────────────────── */}
      <div className="card p-5 space-y-3">
        <h2 className="section-title flex items-center gap-2">
          <Package className="w-4 h-4 text-indigo-500" /> Return Data Coverage
        </h2>
        <p className="section-sub">Field availability and tracking precision from the imported report</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
          <div className="flex items-center gap-2 text-[12px] font-medium px-3.5 py-2.5 rounded-xl border bg-emerald-50 border-emerald-100 text-emerald-700">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>Return events available</span>
          </div>
          <div className="flex items-center gap-2 text-[12px] font-medium px-3.5 py-2.5 rounded-xl border bg-emerald-50 border-emerald-100 text-emerald-700">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>Sale events available</span>
          </div>
          <div className="flex items-center gap-2 text-[12px] font-medium px-3.5 py-2.5 rounded-xl border bg-emerald-50 border-emerald-100 text-emerald-700">
            <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0" />
            <span>Sale-linked returns available</span>
          </div>
          <div className="flex items-center gap-2 text-[12px] font-medium px-3.5 py-2.5 rounded-xl border bg-rose-50 border-rose-100 text-rose-700">
            <AlertTriangle className="w-4 h-4 text-rose-500 shrink-0" />
            <span>Return reason: NOT AVAILABLE</span>
          </div>
        </div>
        <p className="text-[12px] text-gray-500 pt-1">
          <strong>Note:</strong> The current Flipkart Sales Report does not provide an explicit return reason/type.
        </p>
      </div>

      {/* ─── 8. RETURN ORDER DETAIL MODAL ────────────────────────────── */}
      {selectedOrder && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4 animate-fadeIn">
          <div className="bg-white rounded-2xl shadow-2xl border border-gray-200 max-w-xl w-full p-6 space-y-5 animate-scaleUp">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-gray-900">Return Order Detail</h3>
                <p className="text-[12px] text-gray-400 font-mono mt-0.5">Order #{selectedOrder.order_id}</p>
              </div>
              <button
                onClick={() => setSelectedOrder(null)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Sale Linking Highlight Card (Section 9 Requirement) */}
            <div className={`rounded-xl p-4 border ${
              selectedOrder.has_sale_event
                ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                : 'bg-amber-50 border-amber-200 text-amber-900'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold uppercase tracking-wider">
                  Was there a Sale event for this Order Item?
                </span>
                <span className={`badge ${selectedOrder.has_sale_event ? 'badge-green' : 'badge-amber'} text-xs font-bold`}>
                  {selectedOrder.has_sale_event ? 'YES' : 'NO'}
                </span>
              </div>
              {selectedOrder.has_sale_event ? (
                <div className="mt-2.5 pt-2.5 border-t border-emerald-200 flex items-center justify-between text-[12px]">
                  <div>
                    <span className="text-emerald-700">Sale Date: </span>
                    <strong>{selectedOrder.sale_date}</strong>
                  </div>
                  <div>
                    <span className="text-emerald-700">Sale Value: </span>
                    <strong>₹{selectedOrder.sale_value?.toLocaleString('en-IN')}</strong>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-amber-700 mt-2">
                  No prior Sale event was recorded for this Order Item ID in the current reporting period. The original purchase likely took place before the dataset start date.
                </p>
              )}
            </div>

            {/* Order Attributes Grid */}
            <div className="grid grid-cols-2 gap-3 text-[12px]">
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Order Item ID</div>
                <div className="font-mono text-gray-800 break-all">{selectedOrder.order_item_id}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">SKU</div>
                <div className="font-mono font-bold text-indigo-600">{selectedOrder.sku}</div>
              </div>
              <div className="card-flat p-3 col-span-2">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Product Name</div>
                <div className="font-medium text-gray-800">{selectedOrder.product_name}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Order Date</div>
                <div className="font-semibold text-gray-800">{selectedOrder.order_date}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Return Date</div>
                <div className="font-semibold text-rose-600">{selectedOrder.return_date}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Order Type</div>
                <div className="font-semibold text-gray-800">{selectedOrder.order_type}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Quantity</div>
                <div className="font-semibold text-gray-800">{selectedOrder.quantity} unit</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Return Value</div>
                <div className="font-bold text-rose-600 text-base">₹{selectedOrder.return_value.toLocaleString('en-IN')}</div>
              </div>
              <div className="card-flat p-3">
                <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Delivery State</div>
                <div className="font-semibold text-gray-800">{selectedOrder.customer_delivery_state}</div>
              </div>
              <div className="card-flat p-3 col-span-2 flex items-center justify-between">
                <div>
                  <div className="text-[11px] text-gray-400 font-medium uppercase mb-0.5">Event Sub Type</div>
                  <div className="font-mono text-gray-800 font-bold">{selectedOrder.event_subtype}</div>
                </div>
                <span className={`badge ${selectedOrder.event === 'RETURN' ? 'badge-red' : 'badge-purple'}`}>
                  {selectedOrder.event}
                </span>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="pt-2 flex items-center justify-end gap-2">
              {onSelectProduct && (
                <button
                  onClick={() => {
                    const s = selectedOrder.sku;
                    setSelectedOrder(null);
                    onSelectProduct(s);
                  }}
                  className="btn-secondary text-[12px]"
                >
                  View Product Detail
                </button>
              )}
              <button
                onClick={() => setSelectedOrder(null)}
                className="btn-primary text-[12px]"
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
