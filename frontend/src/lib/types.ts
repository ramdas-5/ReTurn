export type Role = "customer" | "partner" | "admin";
export type ServiceType = "return" | "parcel";

export type RequestStatus =
  | "pending_matching"
  | "batched"
  | "assigned"
  | "in_progress"
  | "completed"
  | "cancelled"
  | "failed";

export type BatchStatus =
  | "proposed"
  | "offered"
  | "accepted"
  | "in_progress"
  | "completed"
  | "declined"
  | "cancelled";

export type ParcelStatus =
  | "pending"
  | "assigned"
  | "partner_accepted"
  | "pickup_arrived"
  | "picked_up"
  | "in_transit"
  | "delivered"
  | "failed";

export interface ApiUser {
  id: number;
  name: string;
  email: string;
  role: Role;
  timezone: string;
  phone?: string | null;
  notify_email?: boolean;
  notify_in_app?: boolean;
  created_at: string | null;
  last_login_at?: string | null;
  disabled: boolean;
  disabled_at?: string | null;
}

export interface Location {
  id?: number;
  label: string;
  address_line: string;
  area: string;
  city: string;
  postal_code?: string | null;
  latitude: number;
  longitude: number;
  source?: string;
  is_sample?: boolean;
}

export interface Parcel {
  id: number;
  code: string;
  tracking_number: string;
  description: string;
  category: string;
  weight_kg: number;
  volume_m3: number;
  size_class: string;
  handling: string[];
  status: ParcelStatus;
  declared_value_inr?: number | null;
  updated_at: string;
  events?: TrackingEvent[];
}

export interface TrackingEvent {
  id: number;
  event_type: string;
  notes: string | null;
  created_at: string;
  actor_name: string;
  actor_role: string;
}

export interface BatchSummary {
  id: number;
  code: string;
  status: BatchStatus;
  partner_id: number | null;
  partner_name: string | null;
  distance_km: number;
  baseline_km: number;
  savings_km: number;
  savings_percent: number;
  distance_source: "osrm" | "estimated";
  created_at: string;
  stop_count: number;
}

export interface BatchStop {
  id: number;
  sequence: number;
  kind: "pickup" | "dropoff";
  status: string;
  request_id: number;
  planned_arrival: string;
  planned_departure: string;
  service_minutes: number;
  leg_distance_km: number;
  leg_duration_minutes: number;
  load_weight_kg: number;
  load_volume_m3: number;
  completed_at?: string | null;
  notes?: string | null;
  location: Location;
  request?: {
    id: number;
    code: string;
    type: ServiceType;
    status: RequestStatus;
    parcel_id?: number | null;
    parcel_code?: string | null;
    parcel_status?: ParcelStatus | null;
    parcel_description?: string | null;
    weight_kg?: number | null;
  };
}

export interface CustomerBatchContext {
  id: number;
  code: string;
  status: BatchStatus;
  distance_km: number;
  savings_percent: number;
  distance_source: string;
  partner: { name: string; phone: string | null; email: string } | null;
  stops: BatchStop[];
  parcel_count: number;
  estimated: boolean;
}

export interface DeliveryRequest {
  id: number;
  code: string;
  type: ServiceType;
  status: RequestStatus;
  created_at: string;
  updated_at: string;
  pickup_window_start: string;
  pickup_window_end: string;
  delivery_deadline: string;
  notes: string | null;
  pickup: Location;
  destination: Location;
  parcel: Parcel;
  return_detail: {
    authorized_hub_name: string;
    return_reference: string | null;
    retailer: string | null;
  } | null;
  recipient: {
    name: string;
    phone: string | null;
    instructions: string | null;
  } | null;
  customer: { id: number; name: string; email?: string; phone?: string | null } | null;
  cancelled_at: string | null;
  cancellation_reason: string | null;
  failure_reason: string | null;
  next_step: string;
  batch: CustomerBatchContext | BatchSummary | null;
  batch_detail?: Batch;
  tracking?: TrackingEvent[];
}

export interface Batch {
  id: number;
  code: string;
  status: BatchStatus;
  partner_id: number | null;
  partner_name: string | null;
  partner: { id: number; name: string; phone: string | null; email: string | null } | null;
  distance_km: number;
  baseline_km: number;
  savings_km: number;
  savings_percent: number;
  distance_source: "osrm" | "estimated";
  geometry_source: "osrm" | "estimated";
  duration_minutes: number;
  route_method: string;
  explanation: {
    included_reasons?: string[];
    distance_source_label?: string;
    routing_notes?: string[];
    detour_km?: Record<string, number>;
    minimum_savings_pct?: number;
    note?: string;
  };
  assumptions: string[];
  load_profile: Array<{
    sequence: number;
    kind: string;
    request_code: string;
    weight_kg: number;
    volume_m3: number;
  }>;
  geometry: { type: string; coordinates: number[][] } | null;
  stops: BatchStop[];
  requests: DeliveryRequest[];
  assignment_history: Array<{
    id: number;
    action: string;
    partner_id: number | null;
    partner_name: string | null;
    actor_name: string;
    reason: string | null;
    created_at: string;
  }>;
  offered_at: string | null;
  accepted_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  declined_reason: string | null;
  cancelled_reason: string | null;
  created_at: string;
  request_count?: number;
  eligibility?: {
    eligible: boolean;
    reason: string | null;
    offered_to_me: boolean;
    can_accept: boolean;
  };
}

export interface PartnerProfile {
  id: number;
  user_id: number;
  name: string;
  email: string;
  phone: string | null;
  company_name: string;
  vehicle_type: "bike" | "car" | "van" | "truck";
  max_weight_kg: number;
  max_volume_m3: number;
  accepts_fragile: boolean;
  accepts_restricted: boolean;
  service_areas: string[];
  availability: "available" | "unavailable" | "on_route";
  verification_status: "pending" | "verified" | "rejected";
  verification_note: string | null;
  verified_at: string | null;
  operating_hours: { start_hour: number; end_hour: number };
  created_at: string;
  user?: ApiUser | null;
}

export interface AuthMe {
  user: ApiUser;
  partner_profile: PartnerProfile | null;
  capabilities: Record<string, boolean>;
  csrf_token?: string | null;
}

export interface Issue {
  id: number;
  category: string;
  severity: "low" | "medium" | "high";
  status: "open" | "in_review" | "resolved";
  description: string;
  resolution_note: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  reporter: ApiUser | null;
  resolved_by: { id: number; name: string } | null;
  request: {
    id: number;
    code: string;
    type: ServiceType;
    status: RequestStatus;
    customer_name?: string | null;
  } | null;
  batch: { id: number; code: string; status: BatchStatus } | null;
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

export interface PreviewStop {
  request_id: number;
  request_code: string;
  kind: "pickup" | "dropoff";
  location_id: number;
  location: Location;
  arrival: string;
  departure: string;
  leg_distance_km: number;
  leg_duration_minutes: number;
  load_weight_kg: number;
  load_volume_m3: number;
}

export interface PreviewGroup {
  request_ids: number[];
  group_key: string;
  requests: Array<{
    id: number;
    code: string;
    type: ServiceType;
    status: RequestStatus;
    customer_name: string | null;
    parcel: {
      id: number;
      code: string;
      description: string;
      weight_kg: number;
      volume_m3: number;
      handling: string[];
    } | null;
    pickup: Location;
    destination: Location;
    authorized_hub: string | null;
    recipient_name: string | null;
    pickup_window_start: string;
    pickup_window_end: string;
    delivery_deadline: string;
  }>;
  stops: PreviewStop[];
  distance_km: number;
  baseline_km: number;
  savings_km: number;
  savings_percent: number;
  duration_minutes: number;
  load_profile: Array<{
    sequence: number;
    kind: string;
    request_code: string;
    weight_kg: number;
    volume_m3: number;
  }>;
  max_load_weight_kg: number;
  max_load_volume_m3: number;
  detour_km: Record<string, number>;
  vehicle: Record<string, unknown> & {
    max_weight_kg: number;
    max_volume_m3: number;
    label: string;
  };
  distance_source: "osrm" | "estimated";
  distance_source_label: string;
  routing_notes: string[];
  partner_options: Array<{
    partner_id: number;
    profile_id: number;
    name: string;
    vehicle_type: string;
    max_weight_kg: number;
    max_volume_m3: number;
    availability: string;
    reasons: string[];
  }>;
  included_reasons: string[];
  assumptions: string[];
  estimated_fuel_saved_l: number;
  estimated_co2e_avoided_kg: number;
  minimum_savings_pct: number;
  service_minutes: number;
  feasible: boolean;
}

export interface PreviewResult {
  run_id: number | null;
  generated_at: string;
  settings: Record<string, number | string>;
  vehicle: Record<string, unknown>;
  distance_source: "osrm" | "estimated";
  distance_source_label: string;
  routing_notes: string[];
  pending_count: number;
  groups: PreviewGroup[];
  near_misses: Array<{
    request_ids: number[];
    reason_code: string;
    message: string;
  }>;
  unmatched: Array<{
    request_id: number;
    code: string;
    reason: string;
    message: string;
  }>;
  excluded: Array<{
    request_id: number;
    code: string;
    reason: string;
    message: string;
  }>;
  assumptions: string[];
}

export interface AnalyticsSummary {
  generated_at: string;
  request_counts: Record<string, number>;
  batch_counts: Record<string, number>;
  pending_requests: number;
  proposed_batches: number;
  active_routes: number;
  completed_parcels: number;
  failed_parcels: number;
  open_issues: number;
  pending_partner_verifications: number;
  customers: number;
  partners: number;
  batched_requests: number;
  in_progress_requests: number;
  completed_requests: number;
  failed_requests: number;
  average_savings_percent: number;
  request_volume: Array<{ day: string; count: number }>;
  service_mix: Array<{ type: string; count: number }>;
  recent_batches: BatchSummary[] & Array<{ request_count: number; partner_name: string | null }>;
  recent_issues: Array<{
    id: number;
    category: string;
    severity: string;
    status: string;
    created_at: string;
    request_code: string | null;
  }>;
  pending_partners?: PartnerProfile[];
  recent_audit?: Array<{
    id: number;
    action: string;
    entity_type: string;
    entity_id: number | null;
    summary: string;
    reason: string | null;
    actor_name: string;
    actor_role: string;
    created_at: string;
  }>;
  active_batches?: Batch[];
  disclaimer: string;
}

export interface Sustainability {
  generated_at: string;
  measured: boolean;
  labelled: string;
  factors: { fuel_l_per_km: number; kg_co2e_per_litre: number };
  totals: {
    batches: number;
    baseline_km: number;
    shared_km: number;
    estimated_distance_saved_km: number;
    estimated_savings_percent: number;
    estimated_fuel_saved_l: number;
    estimated_co2e_avoided_kg: number;
  };
  batches: Array<{
    batch_id: number;
    code: string;
    status: string;
    created_at: string;
    request_count: number;
    baseline_km: number;
    shared_km: number;
    saved_km: number;
    savings_percent: number;
    estimated_fuel_saved_l: number;
    estimated_co2e_avoided_kg: number;
    distance_source: string;
  }>;
  methodology: string[];
  disclaimer: string;
}
