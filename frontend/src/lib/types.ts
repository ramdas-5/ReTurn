export type Role = "consumer" | "driver" | "manager" | "admin";
export type ServiceType = "return" | "parcel";

export interface ApiUser {
  id: number;
  full_name: string;
  email: string;
  phone?: string | null;
  role: Role;
  role_label?: string;
  status: string;
  must_change_password?: boolean;
  notify_email?: boolean;
  notify_in_app?: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
  permissions?: string[];
  business_profile?: BusinessProfile | null;
  consumer_profile?: { id: number; account_type: string } | null;
  driver_profile?: DriverProfile | null;
  manager_profile?: {
    employee_code?: string | null;
    contact_phone?: string | null;
    service_areas?: ServiceArea[];
  } | null;
}

export interface AuthMe {
  user: ApiUser;
  csrf_token?: string | null;
}

export interface BusinessProfile {
  id: number;
  business_name: string;
  category?: string | null;
  contact_phone?: string | null;
  contact_email?: string | null;
  address_line?: string | null;
  area?: string | null;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  location?: { latitude: number | null; longitude: number | null };
  verification_status?: string;
  tax_id?: string | null;
  registration_number?: string | null;
}

export interface Vehicle {
  id: number;
  vehicle_type: string;
  registration_number: string;
  make?: string | null;
  model?: string | null;
  color?: string | null;
  year?: number | null;
  verification_status: string;
  is_active: boolean;
  capacity?: {
    name: string;
    max_weight_kg: number;
    max_volume_m3: number;
    max_parcels: number;
    supports_fragile: boolean;
    supports_restricted: boolean;
  } | null;
}

export interface DriverProfile {
  id: number;
  verification_status: string;
  verification_note?: string | null;
  rating?: number | null;
  completed_deliveries: number;
  duty_status: string;
  duty_session?: {
    id: number;
    status: string;
    started_at: string;
    last_heartbeat_at: string;
  } | null;
  service_areas: ServiceArea[];
  vehicles: Vehicle[];
  user?: ApiUser;
}

export interface ServiceArea {
  id: number;
  name: string;
  city: string;
  state?: string;
  postal_codes?: string[];
  center?: { latitude: number | null; longitude: number | null };
  center_latitude?: number | null;
  center_longitude?: number | null;
  radius_km: number;
  is_active: boolean;
  manager_count?: number;
  driver_count?: number;
}

export interface AddressSnapshot {
  contact_name: string;
  contact_phone: string;
  address_line: string;
  address_line2?: string | null;
  area: string;
  city?: string | null;
  state?: string | null;
  postal_code?: string | null;
  latitude: number | null;
  longitude: number | null;
  instructions?: string | null;
}

export interface Parcel {
  name: string;
  description?: string | null;
  category?: string;
  quantity: number;
  weight_kg: number;
  dimensions_cm?: { length: number; width: number; height: number };
  volume_m3?: number;
  is_fragile?: boolean;
  handling?: string[];
  declared_value_inr?: number | null;
  photo_exception_reason?: string | null;
}

export interface OrderSummary {
  id: number;
  order_number: string;
  service_type: ServiceType;
  service_label?: string;
  status: string;
  status_label?: string;
  priority?: number;
  is_demo?: boolean;
  created_at: string;
  updated_at?: string;
  pickup: {
    area: string | null;
    city?: string | null;
    window_start: string | null;
    window_end: string | null;
  };
  delivery: {
    area: string | null;
    city?: string | null;
    deadline: string | null;
  };
  parcel: { name: string | null; weight_kg: number | null };
  has_photo?: boolean;
  assigned_driver?: Assignment | null;
  consumer?: {
    id: number;
    full_name: string;
    phone?: string | null;
    email?: string | null;
    account_type?: string;
  };
}

export interface StatusEvent {
  id: number;
  from_status: string | null;
  to_status: string;
  to_label: string;
  source: string;
  reason: string | null;
  actor: { id: number; full_name: string; role: string } | null;
  created_at: string;
}

export interface Assignment {
  id: number;
  status: string;
  assigned_at: string;
  accepted_at?: string | null;
  ended_at?: string | null;
  driver: { id: number; full_name: string; phone?: string | null } | null;
  vehicle: Vehicle | null;
}

export interface Proof {
  id: number;
  kind: string;
  status: string;
  captured_at: string | null;
  server_received_at: string | null;
  recipient_name?: string | null;
  image_url: string | null;
  location: {
    latitude: number | null;
    longitude: number | null;
    accuracy_m?: number | null;
  } | null;
}

export interface OrderDetail extends OrderSummary {
  pickup_address: AddressSnapshot | null;
  delivery_address: AddressSnapshot | null;
  parcel: Parcel;
  return_request?: {
    product_name: string;
    original_order_reference?: string | null;
    reason: string;
    return_authorization_reference?: string | null;
    merchant_name?: string | null;
    destination_type?: string;
    authorization_confirmed?: boolean;
    approval_status?: string;
  } | null;
  images: Array<{ id: number; url: string | null; is_primary: boolean; created_at: string }>;
  business?: BusinessProfile | null;
  business_order_reference?: string | null;
  service_notes?: string | null;
  special_requirements?: string | null;
  assignment: Assignment | null;
  assignment_history: Assignment[];
  batch: {
    id: number;
    batch_number: string;
    status: string;
    status_label: string;
    planned_start?: string | null;
    planned_end?: string | null;
  } | null;
  delivered_at?: string | null;
  cancelled_at?: string | null;
  cancellation_reason?: string | null;
  failure_reason?: string | null;
  pickup_proof: Proof | null;
  delivery_proof: Proof | null;
  status_history: StatusEvent[];
  suggestions?: MatchingSuggestion[];
}

export interface RouteStop {
  id: number;
  kind: "pickup" | "delivery";
  sequence: number;
  label: string;
  contact_name: string | null;
  contact_phone: string | null;
  address: {
    address_line: string;
    area: string;
    city: string;
    latitude: number | null;
    longitude: number | null;
  };
  planned_arrival: string;
  planned_departure: string;
  leg_distance_km: number;
  leg_duration_minutes: number;
  status: string;
  order: { id: number; order_number: string; status: string; status_label: string } | null;
  navigation_url: string | null;
}

export interface RoutePlan {
  id: number;
  version: number;
  status: string;
  algorithm: string;
  distance_km: number;
  duration_minutes: number;
  distance_source: string;
  geometry: { type: string; coordinates: number[][] } | null;
  stops: RouteStop[];
}

export interface BatchSummary {
  id: number;
  batch_number: string;
  status: string;
  status_label: string;
  driver: { id: number; full_name: string } | null;
  vehicle: Vehicle | null;
  service_area: ServiceArea | null;
  planned_start: string | null;
  planned_end: string | null;
  started_at: string | null;
  completed_at: string | null;
  order_count: number;
  pickup_count: number;
  delivery_count: number;
  completed_stops: number;
  total_stops: number;
  distance_km: number;
  duration_minutes: number;
  distance_source: string;
  algorithm: string;
  route_plan_id: number | null;
}

export interface BatchDetail extends BatchSummary {
  route_plan: RoutePlan | null;
  geometry: { type: string; coordinates: number[][] } | null;
  explanation: Record<string, unknown>;
  notes?: string | null;
  orders: OrderSummary[];
}

export interface MatchingSuggestion {
  id: number;
  status: string;
  score: number | null;
  detour_km: number | null;
  added_duration_minutes: number | null;
  distance_source: string;
  reasons: Array<{ code: string; label: string }>;
  blockers: Array<{ code: string; label: string; detail?: string }>;
  driver: { id: number; full_name: string; phone?: string; email?: string } | null;
  batch_id: number | null;
  order?: OrderSummary;
  expires_at: string | null;
  created_at: string;
}

export interface DeliveryException {
  id: number;
  order_id: number;
  order_number: string | null;
  driver: { id: number; full_name: string } | null;
  exception_type: string;
  description: string;
  status: string;
  resolution_note: string | null;
  resolved_by: { id: number; full_name: string } | null;
  resolved_at: string | null;
  created_at: string;
}

export interface Issue {
  id: number;
  category: string;
  severity: string;
  subject: string;
  description: string;
  status: string;
  resolution_note: string | null;
  order_id: number | null;
  order_number: string | null;
  reporter: { id: number; full_name: string; role: string } | null;
  resolved_by: { id: number; full_name: string } | null;
  resolved_at: string | null;
  created_at: string;
}

export interface AppNotification {
  id: number;
  type: string;
  title: string;
  body: string;
  link: string | null;
  read_at: string | null;
  created_at: string;
}

export interface SavedAddress {
  id: number;
  label: string;
  contact_name: string;
  contact_phone: string;
  address_line: string;
  address_line2?: string | null;
  area: string;
  city: string;
  state: string;
  postal_code?: string | null;
  latitude: number;
  longitude: number;
  is_default_pickup: boolean;
}

export interface ConsumerSummary {
  counts: {
    total: number;
    awaiting_review: number;
    awaiting_assignment: number;
    in_progress: number;
    delivered: number;
    returned: number;
    cancelled: number;
    returns: number;
  };
  active_orders: OrderSummary[];
  recent_orders: OrderSummary[];
  notifications: { unread: number; latest: AppNotification[] };
  profile: { account_type: string; has_business_profile: boolean; saved_addresses: number };
}

export interface DriverSummary {
  driver: {
    id: number;
    full_name: string;
    verification_status: string;
    rating: number | null;
    completed_deliveries: number;
  };
  duty: {
    id: number;
    status: string;
    status_label: string;
    started_at: string;
    last_heartbeat_at: string;
  } | null;
  vehicle: Vehicle | null;
  counts: {
    assigned_orders: number;
    pending_pickups: number;
    out_for_delivery: number;
    completed_today: number;
    completed_total: number;
    failed_orders: number;
  };
  vehicle_load: {
    parcels: number;
    weight_kg: number;
    volume_m3: number;
    max_parcels: number | null;
    max_weight_kg: number | null;
    max_volume_m3: number | null;
    weight_utilisation_pct: number | null;
  };
  next_stop: Record<string, any> | null;
  last_location: {
    latitude: number;
    longitude: number;
    received_at: string;
    is_recent: boolean;
    status_label: string;
  } | null;
  today: { active_batch: BatchSummary | null; route_distance_km: number | null };
  activity: Array<StatusEvent & { order_number: string | null }>;
}

export interface ManagerSummary {
  manager: { full_name: string; service_areas: string[] };
  drivers: {
    total: number;
    on_duty: number;
    available: number;
    busy: number;
    offline: number;
    with_active_batch: number;
    live: number;
  };
  orders: {
    new_today: number;
    pending: number;
    awaiting_assignment: number;
    assigned: number;
    in_progress: number;
    active: number;
    delivered_today: number;
    delivered_total: number;
    failed: number;
    delayed: number;
    needs_attention: number;
  };
  batches: { active: number; assigned: number; total: number };
  exceptions: { open: number };
  attention_orders: OrderSummary[];
}

export interface AdminOverview {
  generated_at: string;
  accounts: {
    consumers: number;
    business_consumers: number;
    managers: number;
    drivers: number;
    admins: number;
    suspended: number;
    pending_activation: number;
  };
  orders: {
    total: number;
    active: number;
    delivered: number;
    returned: number;
    failed: number;
    cancelled: number;
    today: number;
    delivered_today: number;
    by_status: Record<string, number>;
  };
  batches: { total: number; active: number; completed: number; by_status: Record<string, number> };
  fleet: {
    drivers: number;
    verified_drivers: number;
    on_duty: number;
    vehicles: number;
    active_vehicles: number;
  };
  matching: {
    suggestions: number;
    approval_rate_pct: number | null;
    average_added_detour_km: number | null;
    by_status: Record<string, number>;
  };
  sustainability: {
    batches_measured: number;
    baseline_km: number;
    shared_km: number;
    estimated_distance_saved_km: number;
    estimated_savings_percent: number;
    estimated_fuel_saved_l: number;
    estimated_co2e_avoided_kg: number;
    factors: { fuel_l_per_km: number; kg_co2e_per_litre: number };
    distance_sources: string[];
  };
  service_areas: Array<{
    id: number;
    name: string;
    city: string;
    orders: number;
    active: number;
    delivered: number;
    failed: number;
    drivers: number;
  }>;
  exceptions: { open: number; resolved: number };
  proofs: { total: number; pending: number; reviewed?: number };
  active_assignments?: number;
  open_exceptions?: number;
  disclaimer: string;
}

export interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: number | null;
  summary: string;
  reason: string | null;
  actor: { id: number; full_name: string; role: string } | null;
  ip_address?: string | null;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface ProofMediaRow {
  id: number;
  order_id: number;
  order_number: string | null;
  service_type: ServiceType;
  order_status: string;
  driver: { id: number; full_name: string } | null;
  proof_type: string;
  verification_status: string;
  captured_at: string | null;
  received_at: string | null;
  location: {
    latitude: number | null;
    longitude: number | null;
    accuracy_m: number | null;
    distance_from_stop_m: number | null;
  };
  image_url: string | null;
  notes: string | null;
  verified_at: string | null;
  verified_by: { id: number; full_name: string } | null;
}

export interface LiveDriver {
  driver: { id: number; full_name: string; phone: string | null };
  duty: { status: string; label: string; started_at: string; last_heartbeat_at: string };
  location: {
    latitude: number;
    longitude: number;
    received_at: string;
    is_recent: boolean;
    status_label: string;
  } | null;
  tracking_status: "live_recent" | "stale" | "unavailable";
  active_batch: BatchSummary | null;
}
