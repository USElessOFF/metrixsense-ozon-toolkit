export interface User {
  id: number
  username: string
  is_active: boolean
  created_at: string
}

export interface SectionMeta {
  section: string
  generated_at: string
  row_count: number
  warnings: string[]
}

export interface DateRange {
  date_from: string
  date_to: string
}

export interface PricesCommissionsRow {
  product_id: number | null
  offer_id: string | null
  price: number | null
  old_price: number | null
  min_price: number | null
  marketing_price: number | null
  commission_fbo_percent: number | null
  commission_fbs_percent: number | null
  acquiring_percent: number | null
  logistics_fbo_range: string | null
  logistics_fbs_first_mile_range: string | null
  delivery_fbo: number | null
  return_flow_fbo: number | null
  volume_weight_l: number | null
}

export interface PricesCommissionsSection extends SectionMeta {
  data: PricesCommissionsRow[]
}

export interface ProductCardRow {
  sku: number | null
  name: string | null
  offer_id: string | null
  price: number | null
  old_price: number | null
  min_price: number | null
  volume_weight_l: number | null
  commission_fbo_percent: number | null
  commission_fbs_percent: number | null
  delivery_fbo: number | null
  return_fbo: number | null
  local_length_mm: number | null
  local_width_mm: number | null
  local_height_mm: number | null
  local_weight_g: number | null
  local_volume_l: number | null
  oversize: boolean | null
}

export interface ProductCardsSection extends SectionMeta {
  data: ProductCardRow[]
}

export interface FinanceExpenseRow {
  sku: number | null
  sale_commission: number | null
  delivery: number | null
  return_delivery: number | null
  services: number | null
  accruals_for_sale: number | null
  actual_logistics_per_unit: number | null
}

export interface FinanceExpensesSection extends SectionMeta {
  date_from: string
  date_to: string
  totals: Record<string, number | string>
  data: FinanceExpenseRow[]
}

export interface SellerRatingRow {
  group_name: string | null
  rating_type: string | null
  score: number | null
  description: string | null
}

export interface SellerRatingSection extends SectionMeta {
  data: SellerRatingRow[]
}

export interface StockWarehouseRow {
  name: string | null
  present: number | null
  reserved: number | null
}

export interface PlanSummary {
  skus_total: number
  skus_needs_reorder: number
  skus_critical: number
  total_units_to_ship: number
}

export interface StockPlanningRow {
  sku: number | null
  name: string | null
  offer_id: string | null
  current_stock: number | null
  ads: number | null
  days_of_stock: number | null
  idc: number | null
  idc_grade: string | null
  turnover: number | null
  recommended_stock: number | null
  recommended_units: number | null
  needs_reorder: boolean
  priority: string
  due_by: string | null
  warehouses: StockWarehouseRow[]
}

export interface StockPlanningSection extends SectionMeta {
  target_days: number
  critical_days: number
  plan_summary: PlanSummary
  data: StockPlanningRow[]
}

export interface SearchQueryRow {
  phrase: string | null
  sku: number | null
  offer_id: string | null
  category: string | null
  gmv: number | null
  position: number | null
  unique_search_users: number | null
  unique_view_users: number | null
  view_conversion: number | null
}

export interface SearchQueriesSection extends SectionMeta {
  date_from: string
  date_to: string
  data: SearchQueryRow[]
}

export interface CashFlowRow {
  date: string | null
  operation_type: string | null
  operation_type_name: string | null
  amount: number | null
  balance_after: number | null
}

export interface CashFlowSection extends SectionMeta {
  date_from: string
  date_to: string
  total_income: number
  total_expense: number
  net_flow: number
  type_summary: Record<string, number>
  data: CashFlowRow[]
}

export interface TopActionItem {
  action_type: string
  title: string
  priority: string
  sku_count: number
  skus: number[]
  impact: string
  details: Record<string, unknown>
}

export interface TopActionsSection extends SectionMeta {
  actions: TopActionItem[]
}

export interface CalculatorCostLine {
  name: string
  amount: number
  source: string
}

export interface CalculatorResult {
  mode: string
  sku: number | null
  revenue: number
  cost_lines: CalculatorCostLine[]
  total_costs: number
  pre_tax_profit: number
  tax: number
  tax_system: string
  profit: number
  margin_percent: number
  markup_percent: number
  warnings: string[]
}

export interface AnalogItem {
  sku: number
  name: string
  offer_id: string | null
  similarity: number
  price: number | null
}

export interface AnalogsResponse {
  sku: number
  name: string | null
  total_catalog: number
  analogs: AnalogItem[]
}

export interface ReportStatus {
  request_uuid: string
  status: string
  info: string | null
  created_at: string | null
  updated_at: string | null
  date_from: string | null
  date_to: string | null
}

export interface OnboardingStatus {
  seller_api: { required: boolean; configured: boolean }
  performance_api: { required: boolean; configured: boolean }
  unit_economics_settings: {
    required: boolean
    tax_system: string
    ad_budget_percent: number
    logistics_cost: number
    cost_price_share: number
    fbo: boolean
    is_default: boolean
  }
  ready_for_report: boolean
  next_steps: string[]
}

export interface AppSettings {
  tax_system: string
  ad_budget_percent: number
  logistics_cost: number
  cost_price_share: number
  fbo: boolean
  created_at: string | null
  updated_at: string | null
}

export interface Secrets {
  seller_client_id: string | null
  seller_api_key: string | null
  performance_client_id: string | null
  performance_secret: string | null
  seller_valid: boolean
  performance_valid: boolean
}
