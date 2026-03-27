export type StatsSummary = {
  date_from: string;
  date_to: string;
  total_appointments: number;
  canceled_appointments: number;
  completed_appointments: number;
  new_clients: number;
  active_masters: number;
  active_services: number;
};

export type Client = {
  id: number;
  vk_user_id: number;
  full_name: string | null;
  phone: string | null;
  notes: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type ServiceCategory = {
  id: number;
  name: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Service = {
  id: number;
  category_id: number;
  name: string;
  description: string | null;
  duration_minutes: number;
  price: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type Master = {
  id: number;
  full_name: string;
  specialization: string | null;
  description: string | null;
  phone: string | null;
  experience_years: number | null;
  is_active: boolean;
  service_ids: number[];
  created_at: string;
  updated_at: string;
};

export type Schedule = {
  id: number;
  master_id: number;
  work_date: string;
  start_time: string;
  end_time: string;
  is_working_day: boolean;
  created_at: string;
  updated_at: string;
};

export type Appointment = {
  id: number;
  client_id: number;
  master_id: number;
  service_id: number;
  appointment_date: string;
  start_time: string;
  end_time: string;
  status: string;
  comment: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
};

export type Notification = {
  id: number;
  appointment_id: number;
  type: string;
  send_at: string;
  status: string;
  channel: string;
  message: string | null;
  created_at: string;
  updated_at: string;
};

export type AvailabilityGroup = {
  work_date: string;
  start_time: string;
  end_time: string;
  master_ids: number[];
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  username: string;
};

export type AdminIdentity = {
  username: string;
  role: string;
};

export type NotificationProcessResult = {
  processed: number;
  sent: number;
  skipped: number;
  failed: number;
};
