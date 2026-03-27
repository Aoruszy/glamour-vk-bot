import type {
  AdminIdentity,
  Appointment,
  AvailabilityGroup,
  Client,
  Master,
  Notification,
  NotificationProcessResult,
  Schedule,
  Service,
  ServiceCategory,
  StatsSummary,
  TokenResponse
} from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ??
  (window.location.port === "5173"
    ? "http://127.0.0.1:8000/api/v1"
    : `${window.location.origin}/api/v1`);
const TOKEN_STORAGE_KEY = "glamour_admin_token";

let accessToken =
  typeof window !== "undefined" ? window.localStorage.getItem(TOKEN_STORAGE_KEY) : null;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function persistToken(token: string | null) {
  accessToken = token;
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    let message = `Ошибка запроса: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      const body = await response.text();
      if (body) {
        message = body;
      }
    }
    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  hasSession() {
    return Boolean(accessToken);
  },
  clearSession() {
    persistToken(null);
  },
  async login(username: string, password: string) {
    const session = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    });
    persistToken(session.access_token);
    return session;
  },
  getCurrentAdmin() {
    return request<AdminIdentity>("/auth/me");
  },
  getStats(dateFrom: string, dateTo: string) {
    return request<StatsSummary>(`/stats/summary?date_from=${dateFrom}&date_to=${dateTo}`);
  },
  listClients() {
    return request<Client[]>("/clients");
  },
  createClient(payload: {
    vk_user_id: number;
    full_name?: string;
    phone?: string;
    notes?: string;
  }) {
    return request<Client>("/clients", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listCategories() {
    return request<ServiceCategory[]>("/service-categories");
  },
  createCategory(payload: { name: string; description?: string; is_active?: boolean }) {
    return request<ServiceCategory>("/service-categories", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listServices() {
    return request<Service[]>("/services");
  },
  createService(payload: {
    category_id: number;
    name: string;
    description?: string;
    duration_minutes: number;
    price: string;
    is_active?: boolean;
  }) {
    return request<Service>("/services", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listMasters() {
    return request<Master[]>("/masters");
  },
  createMaster(payload: {
    full_name: string;
    specialization?: string;
    description?: string;
    phone?: string;
    experience_years?: number;
    is_active?: boolean;
    service_ids: number[];
  }) {
    return request<Master>("/masters", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listSchedules() {
    return request<Schedule[]>("/schedules");
  },
  createSchedule(payload: {
    master_id: number;
    work_date: string;
    start_time: string;
    end_time: string;
    is_working_day?: boolean;
  }) {
    return request<Schedule>("/schedules", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listAppointments() {
    return request<Appointment[]>("/appointments");
  },
  createAppointment(payload: {
    client_id: number;
    service_id: number;
    appointment_date: string;
    start_time: string;
    master_id?: number;
    comment?: string;
    created_by?: string;
  }) {
    return request<Appointment>("/appointments", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  cancelAppointment(appointmentId: number, payload: { actor_role: string; reason?: string }) {
    return request<Appointment>(`/appointments/${appointmentId}/cancel`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  rescheduleAppointment(
    appointmentId: number,
    payload: {
      appointment_date: string;
      start_time: string;
      master_id?: number;
      comment?: string;
      actor_role?: string;
    }
  ) {
    return request<Appointment>(`/appointments/${appointmentId}/reschedule`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  updateAppointmentStatus(
    appointmentId: number,
    payload: { status: string; actor_role?: string; comment?: string }
  ) {
    return request<Appointment>(`/appointments/${appointmentId}/status`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },
  listNotifications() {
    return request<Notification[]>("/notifications");
  },
  processNotifications() {
    return request<NotificationProcessResult>("/notifications/process", {
      method: "POST"
    });
  },
  getAvailableSlots(serviceId: number, workDate: string, masterId?: number) {
    const params = new URLSearchParams({
      service_id: String(serviceId),
      work_date: workDate
    });
    if (masterId) {
      params.set("master_id", String(masterId));
    }
    return request<AvailabilityGroup[]>(`/appointments/available-slots?${params.toString()}`);
  }
};
