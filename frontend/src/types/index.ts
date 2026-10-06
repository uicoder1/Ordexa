export interface User {
  id: string;
  email: string;
  name: string;
  avatar_url?: string;
  is_platform_admin?: boolean;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  owner_id: string;
  sales_channels: string;
  role: string;
  created_at: string;
}

export interface Product {
  id: string;
  organization_id: string;
  sku: string;
  product_name: string;
  category: string;
  purchase_cost: number;
  selling_price: number;
  marketplace: string;
  created_at: string;
  updated_at: string;
}

export interface SKUMetric {
  id: string;
  organization_id: string;
  sku: string;
  product_name: string;
  category: string;
  purchase_cost: number;
  period_name: string;
  total_orders: number;
  units_sold: number;
  revenue: number;
  returns_count: number;
  return_rate: number;
  rto_count: number;
  rto_rate: number;
  total_product_cost: number;
  marketplace_fees: number;
  shipping_cost: number;
  return_cost: number;
  refund_amount: number;
  net_settlement: number;
  actual_profit: number;
  profit_margin: number;
  profit_leakage: number;
  risk_level: 'CRITICAL' | 'WARNING' | 'HEALTHY';
  recommended_action: string;
  calculated_at: string;
}

export interface DashboardSummary {
  total_revenue: number;
  net_settlement: number;
  actual_profit: number;
  profit_margin: number;
  total_orders: number;
  total_units_sold: number;
  return_rate: number;
  rto_rate: number;
  total_skus: number;
  critical_skus_count: number;
  warning_skus_count: number;
  healthy_skus_count: number;
  period_comparison: string;
  revenue_trend_pct: number;
  profit_trend_pct: number;
}

export interface ReturnReasonBreakdown {
  reason: string;
  count: number;
  percentage: number;
}

export interface SKUTrendPoint {
  month: string;
  revenue: number;
  profit: number;
  return_rate: number;
  profit_margin: number;
}

export interface AIExplanation {
  why_attention_needed: string;
  what_is_happening: string;
  possible_causes: string[];
  suggested_actions: string[];
}

export interface SKUDetail {
  metric: SKUMetric;
  product?: Product;
  return_reasons: ReturnReasonBreakdown[];
  monthly_trends: SKUTrendPoint[];
  ai_explanation: AIExplanation;
}

export interface UploadedFileRecord {
  id: string;
  organization_id: string;
  filename: string;
  marketplace: string;
  storage_path: string;
  file_type: string;
  file_size: number;
  upload_status: string;
  rows_processed: number;
  rows_failed: number;
  column_mapping?: string;
  error_message?: string;
  uploaded_at: string;
}

export interface CalculationConfig {
  id: string;
  organization_id: string;
  settlement_is_net: boolean;
  deduct_marketplace_fees: boolean;
  include_shipping: boolean;
  include_return_cost: boolean;
  critical_risk_margin_threshold: number;
  warning_risk_return_rate_threshold: number;
  warning_risk_rto_rate_threshold: number;
}

export interface SubscriptionStatus {
  organization_id: string;
  plan_key: string;
  plan_name: string;
  price_inr: number;
  status: string;
  billing_cycle: string;
  usage: {
    skus_used: number;
    max_skus: number;
    uploads_used: number;
    max_uploads: number;
  };
}

export interface PlatformOverview {
  platform_name: string;
  total_organizations: number;
  total_users: number;
  total_uploads: number;
  total_audit_events: number;
  timestamp: string;
}

export interface PlatformOrganization {
  id: string;
  name: string;
  owner_email: string;
  owner_id: string;
  sales_channels: string;
  member_count: number;
  upload_count: number;
  created_at: string;
}

export interface PlatformUser {
  id: string;
  email: string;
  name: string;
  organization_name?: string;
  organization_role?: string;
  is_platform_admin: boolean;
  created_at: string;
  last_login_at?: string | null;
}

export interface PlatformUpload {
  id: string;
  organization_id: string;
  filename: string;
  marketplace: string;
  file_type: string;
  file_size?: number;
  upload_status: string;
  rows_processed: number;
  rows_failed: number;
  uploaded_at: string;
  error_message?: string | null;
}

export interface PlatformAuditLog {
  id: string;
  organization_id?: string | null;
  user_id?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  metadata?: Record<string, any> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

export interface PlatformUserDetails extends PlatformUser {
  organizations: Array<{
    organization_id: string;
    organization_name: string;
    role: string;
    joined_at: string;
  }>;
}

export interface PlatformOrganizationDetails extends PlatformOrganization {
  product_count: number;
  members: Array<{
    user_id: string;
    name: string;
    email: string;
    role: string;
    joined_at: string;
  }>;
  recent_uploads: Array<{
    id: string;
    filename: string;
    marketplace: string;
    upload_status: string;
    rows_processed: number;
    uploaded_at: string;
  }>;
  recent_activity: Array<{
    id: string;
    action: string;
    resource_type: string;
    created_at: string;
  }>;
}
