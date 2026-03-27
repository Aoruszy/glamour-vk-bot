import { useEffect, useState } from "react";

import { LoginScreen } from "./components/LoginScreen";
import { SectionPanel } from "./components/SectionPanel";
import { StatCard } from "./components/StatCard";
import { api, ApiError } from "./lib/api";
import type {
  Appointment,
  AvailabilityGroup,
  Client,
  Master,
  Service,
  ServiceCategory,
  StatsSummary
} from "./lib/types";

type Snapshot = {
  stats: StatsSummary | null;
  clients: Client[];
  categories: ServiceCategory[];
  services: Service[];
  masters: Master[];
  appointments: Appointment[];
};

type SectionId = "overview" | "appointments" | "catalog" | "clients" | "calendar";

const SECTIONS: Array<{ id: SectionId; label: string; note: string }> = [
  { id: "overview", label: "Обзор", note: "Ключевые цифры и недавние события" },
  { id: "appointments", label: "Записи", note: "Создание, перенос и статусы" },
  { id: "catalog", label: "Каталог", note: "Категории, услуги и мастера" },
  { id: "clients", label: "Клиенты", note: "База клиентов из VK" },
  { id: "calendar", label: "Календарь", note: "Записи по дням и времени" }
];

function monthBounds() {
  const today = new Date();
  return {
    start: new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10),
    end: new Date(today.getFullYear(), today.getMonth() + 1, 0).toISOString().slice(0, 10)
  };
}

function emptySnapshot(): Snapshot {
  return {
    stats: null,
    clients: [],
    categories: [],
    services: [],
    masters: [],
    appointments: []
  };
}

function appointmentStatusLabel(status: string) {
  return (
    {
      new: "Новая",
      confirmed: "Подтверждена",
      completed: "Завершена",
      canceled_by_client: "Отменена клиентом",
      canceled_by_admin: "Отменена салоном",
      rescheduled: "Перенесена",
      no_show: "Неявка"
    }[status] ?? status
  );
}

function formatDateTime(dateValue: string, timeValue: string) {
  return `${dateValue} в ${timeValue.slice(0, 5)}`;
}

function monthKey(dateValue: Date) {
  const year = dateValue.getFullYear();
  const month = String(dateValue.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

export default function App() {
  const [snapshot, setSnapshot] = useState<Snapshot>(emptySnapshot);
  const [loading, setLoading] = useState(api.hasSession());
  const [refreshing, setRefreshing] = useState(false);
  const [loggingIn, setLoggingIn] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(api.hasSession());
  const [adminName, setAdminName] = useState("admin");
  const [error, setError] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [slotPreview, setSlotPreview] = useState<AvailabilityGroup[]>([]);
  const [slotLoading, setSlotLoading] = useState(false);
  const [dateRange, setDateRange] = useState(monthBounds());
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "" });
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null);
  const [editingServiceId, setEditingServiceId] = useState<number | null>(null);
  const [editingMasterId, setEditingMasterId] = useState<number | null>(null);
  const [calendarMonth, setCalendarMonth] = useState(() => monthKey(new Date()));
  const [selectedCalendarDate, setSelectedCalendarDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [categoryForm, setCategoryForm] = useState({ name: "", description: "" });
  const [serviceForm, setServiceForm] = useState({
    category_id: "",
    name: "",
    description: "",
    duration_minutes: "60",
    price: "1500.00"
  });
  const [masterForm, setMasterForm] = useState({
    category_id: "",
    full_name: "",
    specialization: "",
    phone: "",
    experience_years: "3",
    service_ids: [] as number[]
  });
  const [appointmentForm, setAppointmentForm] = useState({
    vk_user_id: "",
    service_id: "",
    master_id: "",
    appointment_date: new Date().toISOString().slice(0, 10),
    start_time: "",
    comment: ""
  });
  const [manageForm, setManageForm] = useState({
    appointment_id: "",
    appointment_date: new Date().toISOString().slice(0, 10),
    start_time: "10:00:00",
    master_id: "",
    status: "confirmed",
    comment: ""
  });

  useEffect(() => {
    if (api.hasSession()) {
      void bootstrapSession();
    }
  }, []);

  useEffect(() => {
    const manageableAppointments = snapshot.appointments.filter(
      (item) => !["canceled_by_client", "canceled_by_admin"].includes(item.status)
    );
    if (manageableAppointments.length === 0 || manageForm.appointment_id) {
      return;
    }
    const first = manageableAppointments[0];
    setManageForm((current) => ({
      ...current,
      appointment_id: String(first.id),
      appointment_date: first.appointment_date,
      start_time: first.start_time,
      master_id: String(first.master_id),
      status: first.status,
      comment: first.comment || ""
    }));
  }, [snapshot.appointments, manageForm.appointment_id]);

  useEffect(() => {
    if (!appointmentForm.service_id || !appointmentForm.master_id) {
      return;
    }
    const selectedServiceId = Number(appointmentForm.service_id);
    const selectedMasterId = Number(appointmentForm.master_id);
    const matchesService = snapshot.masters.some(
      (master) => master.id === selectedMasterId && master.service_ids.includes(selectedServiceId)
    );
    if (!matchesService) {
      setAppointmentForm((current) => ({ ...current, master_id: "" }));
    }
  }, [appointmentForm.service_id, appointmentForm.master_id, snapshot.masters]);

  useEffect(() => {
    let cancelled = false;

    async function loadSlots() {
      if (!appointmentForm.service_id || !appointmentForm.appointment_date) {
        setSlotPreview([]);
        setAppointmentForm((current) => ({ ...current, start_time: "" }));
        return;
      }

      setSlotLoading(true);
      try {
        const slots = await api.getAvailableSlots(
          Number(appointmentForm.service_id),
          appointmentForm.appointment_date,
          appointmentForm.master_id ? Number(appointmentForm.master_id) : undefined
        );
        if (cancelled) {
          return;
        }
        setSlotPreview(slots);
        setAppointmentForm((current) => {
          const hasCurrentSlot = slots.some((slot) => slot.start_time === current.start_time);
          return {
            ...current,
            start_time: hasCurrentSlot ? current.start_time : (slots[0]?.start_time ?? "")
          };
        });
      } catch {
        if (!cancelled) {
          setSlotPreview([]);
          setAppointmentForm((current) => ({ ...current, start_time: "" }));
        }
      } finally {
        if (!cancelled) {
          setSlotLoading(false);
        }
      }
    }

    void loadSlots();

    return () => {
      cancelled = true;
    };
  }, [appointmentForm.service_id, appointmentForm.appointment_date, appointmentForm.master_id]);

  async function bootstrapSession() {
    try {
      const admin = await api.getCurrentAdmin();
      setAdminName(admin.username);
      setIsAuthenticated(true);
      await refreshAll(true);
    } catch {
      handleLogout();
    }
  }

  function handleLogout() {
    api.clearSession();
    setIsAuthenticated(false);
    setAdminName("admin");
    setSnapshot(emptySnapshot());
    setLoading(false);
    setRefreshing(false);
    setError("");
    setStatusMessage("");
  }

  async function refreshAll(initial = false) {
    initial ? setLoading(true) : setRefreshing(true);
    setError("");
    try {
      const [stats, clients, categories, services, masters, appointments] = await Promise.all([
        api.getStats(dateRange.start, dateRange.end),
        api.listClients(),
        api.listCategories(),
        api.listServices(),
        api.listMasters(),
        api.listAppointments()
      ]);
      setSnapshot({ stats, clients, categories, services, masters, appointments });
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        handleLogout();
        setError("Сессия администратора истекла. Войдите снова.");
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Не удалось загрузить панель.");
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  async function runAction(action: () => Promise<unknown>, message: string) {
    setError("");
    setStatusMessage("");
    try {
      await action();
      setStatusMessage(message);
      await refreshAll();
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        handleLogout();
        setError("Сессия администратора истекла. Войдите снова.");
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Произошла ошибка.");
      }
    }
  }

  async function runDeleteAction(action: () => Promise<unknown>, confirmText: string, message: string, onSuccess?: () => void) {
    if (!window.confirm(confirmText)) {
      return;
    }
    await runAction(action, message);
    onSuccess?.();
  }

  function shiftCalendarMonth(offset: number) {
    const nextMonth = new Date(calendarMonthDate);
    nextMonth.setMonth(nextMonth.getMonth() + offset);
    const nextMonthKey = monthKey(nextMonth);
    setCalendarMonth(nextMonthKey);
    if (!selectedCalendarDate.startsWith(nextMonthKey)) {
      setSelectedCalendarDate(`${nextMonthKey}-01`);
    }
  }

  async function handleLogin() {
    setLoggingIn(true);
    setError("");
    try {
      const session = await api.login(loginForm.username, loginForm.password);
      setAdminName(session.username);
      setIsAuthenticated(true);
      setLoginForm((current) => ({ ...current, password: "" }));
      await refreshAll(true);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось выполнить вход.");
    } finally {
      setLoggingIn(false);
    }
  }

  async function previewSlots() {
    if (!appointmentForm.service_id || !appointmentForm.appointment_date) {
      setError("Выберите услугу и дату перед просмотром свободных окон.");
      return;
    }
    try {
      const slots = await api.getAvailableSlots(
        Number(appointmentForm.service_id),
        appointmentForm.appointment_date,
        appointmentForm.master_id ? Number(appointmentForm.master_id) : undefined
      );
      setSlotPreview(slots);
      setStatusMessage(`Найдено свободных окон: ${slots.length}.`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось загрузить слоты.");
    }
  }

  const selectedAppointment = snapshot.appointments.find((item) => item.id === Number(manageForm.appointment_id));
  const activeManageableAppointments = snapshot.appointments.filter(
    (item) => !["canceled_by_client", "canceled_by_admin"].includes(item.status)
  );
  const overviewAppointments = activeManageableAppointments.slice(0, 8);
  const recentAppointments = snapshot.appointments.slice(0, 8);
  const recentClients = snapshot.clients;
  const appointmentMasters = appointmentForm.service_id
    ? snapshot.masters.filter((master) => master.service_ids.includes(Number(appointmentForm.service_id)))
    : snapshot.masters;
  const masterCategoryServices = masterForm.category_id
    ? snapshot.services.filter((service) => service.category_id === Number(masterForm.category_id))
    : [];
  const todayIso = new Date().toISOString().slice(0, 10);
  const sortedAppointments = [...snapshot.appointments].sort((left, right) => {
    const leftValue = `${left.appointment_date}T${left.start_time}`;
    const rightValue = `${right.appointment_date}T${right.start_time}`;
    return leftValue.localeCompare(rightValue);
  });
  const appointmentsByDate = sortedAppointments.reduce<Record<string, Appointment[]>>((accumulator, appointment) => {
    accumulator[appointment.appointment_date] = [...(accumulator[appointment.appointment_date] ?? []), appointment];
    return accumulator;
  }, {});
  const calendarMonthDate = new Date(`${calendarMonth}-01T00:00:00`);
  const calendarMonthLabel = calendarMonthDate.toLocaleDateString("ru-RU", { month: "long", year: "numeric" });
  const calendarYear = calendarMonthDate.getFullYear();
  const calendarMonthIndex = calendarMonthDate.getMonth();
  const calendarDaysInMonth = new Date(calendarYear, calendarMonthIndex + 1, 0).getDate();
  const calendarOffset = (new Date(calendarYear, calendarMonthIndex, 1).getDay() + 6) % 7;
  const calendarCells = [
    ...Array.from({ length: calendarOffset }, (_, index) => ({ key: `empty-${index}`, date: null })),
    ...Array.from({ length: calendarDaysInMonth }, (_, index) => {
      const day = index + 1;
      const iso = `${calendarMonth}-${String(day).padStart(2, "0")}`;
      return { key: iso, date: iso };
    })
  ];
  const selectedCalendarAppointments = appointmentsByDate[selectedCalendarDate] ?? [];

  const clientLabel = (appointment: Appointment) =>
    appointment.client_name ? `${appointment.client_name} · VK ID ${appointment.client_vk_user_id}` : `VK ID ${appointment.client_vk_user_id}`;
  const clientOptionLabel = (client: Client) => {
    const title = client.full_name || `VK ID ${client.vk_user_id}`;
    const phone = client.phone ? ` · ${client.phone}` : "";
    return `${title} · VK ID ${client.vk_user_id}${phone}`;
  };
  const serviceName = (serviceId: number) => snapshot.services.find((item) => item.id === serviceId)?.name || `Услуга №${serviceId}`;
  const masterName = (masterId: number) => snapshot.masters.find((item) => item.id === masterId)?.full_name || `Мастер №${masterId}`;
  const masterListLabel = (masterIds: number[]) =>
    masterIds.map((masterId) => masterName(masterId)).join(", ");
  const resetCategoryForm = () => {
    setCategoryForm({ name: "", description: "" });
    setEditingCategoryId(null);
  };
  const resetServiceForm = () => {
    setServiceForm({
      category_id: "",
      name: "",
      description: "",
      duration_minutes: "60",
      price: "1500.00"
    });
    setEditingServiceId(null);
  };
  const resetMasterForm = () => {
    setMasterForm({
      category_id: "",
      full_name: "",
      specialization: "",
      phone: "",
      experience_years: "3",
      service_ids: []
    });
    setEditingMasterId(null);
  };

  if (!isAuthenticated) {
    return (
      <LoginScreen
        username={loginForm.username}
        password={loginForm.password}
        loading={loggingIn}
        error={error}
        onUsernameChange={(value) => setLoginForm((current) => ({ ...current, username: value }))}
        onPasswordChange={(value) => setLoginForm((current) => ({ ...current, password: value }))}
        onSubmit={() => void handleLogin()}
      />
    );
  }

  if (loading) {
    return (
      <main className="app-shell">
        <div className="hero">
          <p className="eyebrow">Админ-панель Glamour</p>
          <h1>Подготавливаем данные салона.</h1>
          <p>Загружаем записи, каталог услуг и контур уведомлений.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <header className="hero">
        <div>
          <p className="eyebrow">Админ-панель Glamour</p>
          <h1>Рабочее место администратора салона.</h1>
          <p>
            Вы вошли как <strong>{adminName}</strong>. Управляйте записями, каталогом, клиентами и
            календарем салона без длинной прокрутки.
          </p>
        </div>
        <div className="hero-actions">
          <label>
            <span>С</span>
            <input type="date" value={dateRange.start} onChange={(event) => setDateRange((current) => ({ ...current, start: event.target.value }))} />
          </label>
          <label>
            <span>По</span>
            <input type="date" value={dateRange.end} onChange={(event) => setDateRange((current) => ({ ...current, end: event.target.value }))} />
          </label>
          <button className="button primary" onClick={() => void refreshAll()}>
            {refreshing ? "Обновляем..." : "Обновить"}
          </button>
          <button className="button ghost" onClick={handleLogout}>
            Выйти
          </button>
        </div>
      </header>

      {error ? <div className="banner banner-error">{error}</div> : null}
      {statusMessage ? <div className="banner banner-success">{statusMessage}</div> : null}

      <section className="section-tabs">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            type="button"
            className={`section-tab ${activeSection === section.id ? "section-tab-active" : ""}`}
            onClick={() => setActiveSection(section.id)}
          >
            <strong>{section.label}</strong>
            <span>{section.note}</span>
          </button>
        ))}
      </section>

      {activeSection === "overview" ? (
        <>
          <section className="stats-grid">
            <StatCard label="Записи" value={snapshot.stats?.total_appointments ?? 0} note="Все визиты за выбранный период." />
            <StatCard label="Отмены" value={snapshot.stats?.canceled_appointments ?? 0} note="Инициированы клиентом или салоном." />
            <StatCard label="Новые клиенты" value={snapshot.stats?.new_clients ?? 0} note="Карточки из VK и админки." />
            <StatCard label="Команда" value={`${snapshot.stats?.active_masters ?? 0} / ${snapshot.stats?.active_services ?? 0}`} note="Активные мастера и услуги." />
          </section>
          <div className="dashboard-grid">
            <SectionPanel title="Ближайшие события" subtitle="Короткий обзор текущего состояния без длинной прокрутки.">
              <div className="mini-grid">
                <div className="mini-panel">
                  <h3>Ближайшие записи</h3>
                  {overviewAppointments.length === 0 ? (
                    <p>Активных записей на ближайший период пока нет.</p>
                  ) : (
                    <ul className="list">
                      {overviewAppointments.map((appointment) => (
                        <li key={appointment.id}>
                          <strong>№{appointment.id} · {serviceName(appointment.service_id)}</strong>
                          <span>{clientLabel(appointment)} · {masterName(appointment.master_id)}</span>
                          <span>{formatDateTime(appointment.appointment_date, appointment.start_time)} · {appointmentStatusLabel(appointment.status)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="mini-panel">
                  <h3>Автоуведомления</h3>
                  <ul className="list">
                    <li>
                      <strong>После записи</strong>
                      <span>Клиент сразу получает подтверждение во VK с услугой, мастером и временем.</span>
                    </li>
                    <li>
                      <strong>При изменениях</strong>
                      <span>Перенос, отмена и смена статуса отправляются автоматически без действий администратора.</span>
                    </li>
                    <li>
                      <strong>Напоминания</strong>
                      <span>За 24 часа и за 2 часа до визита бот сам отправляет напоминание клиенту.</span>
                    </li>
                  </ul>
                </div>
              </div>
            </SectionPanel>
          </div>
        </>
      ) : null}

      {activeSection === "appointments" ? (
        <div className="dashboard-grid">
          <SectionPanel title="Записи" subtitle="Создание, перенос, смена статуса и быстрый просмотр свободных окон." aside={<button className="button ghost" onClick={() => void previewSlots()}>Показать слоты</button>}>
            <div className="two-column">
              <form className="form-grid" onSubmit={(event) => {
                event.preventDefault();
                if (!appointmentForm.vk_user_id) {
                  setError("Выберите клиента из зарегистрированной базы.");
                  return;
                }
                if (!appointmentForm.start_time) {
                  setError("Для выбранной даты нет свободного времени. Выберите другой день или мастера.");
                  return;
                }
                void runAction(() => api.createAppointment({
                  vk_user_id: Number(appointmentForm.vk_user_id),
                  service_id: Number(appointmentForm.service_id),
                  appointment_date: appointmentForm.appointment_date,
                  start_time: appointmentForm.start_time,
                  master_id: appointmentForm.master_id ? Number(appointmentForm.master_id) : undefined,
                  comment: appointmentForm.comment || undefined,
                  created_by: "admin"
                }), "Запись создана, клиент уведомлен.");
              }}>
                <label>
                  <span>Клиент</span>
                  <select
                    value={appointmentForm.vk_user_id}
                    onChange={(event) => setAppointmentForm((current) => ({ ...current, vk_user_id: event.target.value }))}
                    required
                  >
                    <option value="">Выберите клиента</option>
                    {snapshot.clients.map((client) => (
                      <option key={client.id} value={client.vk_user_id}>
                        {clientOptionLabel(client)}
                      </option>
                    ))}
                  </select>
                </label>
                <label><span>Услуга</span><select value={appointmentForm.service_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, service_id: event.target.value }))}><option value="">Выберите услугу</option>{snapshot.services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
                <label><span>Мастер</span><select value={appointmentForm.master_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, master_id: event.target.value }))}><option value="">Любой свободный мастер</option>{appointmentMasters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}</select></label>
                <label><span>Дата</span><input type="date" min={todayIso} value={appointmentForm.appointment_date} onChange={(event) => setAppointmentForm((current) => ({ ...current, appointment_date: event.target.value }))} /></label>
                <label><span>Время</span><select value={appointmentForm.start_time} onChange={(event) => setAppointmentForm((current) => ({ ...current, start_time: event.target.value }))} disabled={!appointmentForm.service_id || slotLoading || slotPreview.length === 0}><option value="">{slotLoading ? "Подбираем слоты..." : slotPreview.length === 0 ? "Нет свободных окон" : "Выберите время"}</option>{slotPreview.map((slot) => <option key={`${slot.work_date}-${slot.start_time}`} value={slot.start_time}>{slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)} · {masterListLabel(slot.master_ids)}</option>)}</select></label>
                <label className="full-width"><span>Комментарий</span><input value={appointmentForm.comment} onChange={(event) => setAppointmentForm((current) => ({ ...current, comment: event.target.value }))} /></label>
                <button className="button primary full-width" type="submit">Создать запись</button>
              </form>
              <div className="slot-preview"><h3>Свободные окна</h3>{slotPreview.length === 0 ? <p>Пока пусто. Выберите услугу и дату, затем нажмите кнопку просмотра.</p> : <ul>{slotPreview.slice(0, 8).map((slot) => <li key={`${slot.work_date}-${slot.start_time}`}><strong>{slot.start_time.slice(0, 5)} - {slot.end_time.slice(0, 5)} </strong><span>Мастер: {masterListLabel(slot.master_ids)}</span></li>)}</ul>}</div>
            </div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Дата</th><th>Клиент</th><th>Услуга</th><th>Мастер</th><th>Статус</th><th>Действие</th></tr></thead>
                <tbody>{recentAppointments.map((appointment) => {
                  const isCanceled = ["canceled_by_client", "canceled_by_admin"].includes(appointment.status);
                  return <tr key={appointment.id}><td>{formatDateTime(appointment.appointment_date, appointment.start_time)}</td><td>{clientLabel(appointment)}</td><td>{serviceName(appointment.service_id)}</td><td>{masterName(appointment.master_id)}</td><td><span className={`status-chip status-${appointment.status}`}>{appointmentStatusLabel(appointment.status)}</span></td><td>{isCanceled ? <span className="muted-action">Недоступно</span> : <button className="button subtle" onClick={() => void runAction(() => api.cancelAppointment(appointment.id, { actor_role: "admin", reason: "Отменено из админ-панели" }), `Запись №${appointment.id} отменена.`)}>Отменить</button>}</td></tr>;
                })}</tbody>
              </table>
            </div>
            <div className="two-column section-gap">
              <form className="form-grid compact" onSubmit={(event) => {
                event.preventDefault();
                if (!manageForm.appointment_id) {
                  setError("Выберите запись для переноса.");
                  return;
                }
                void runAction(() => api.rescheduleAppointment(Number(manageForm.appointment_id), {
                  appointment_date: manageForm.appointment_date,
                  start_time: manageForm.start_time,
                  master_id: manageForm.master_id ? Number(manageForm.master_id) : undefined,
                  comment: manageForm.comment || undefined,
                  actor_role: "admin"
                }), `Запись №${manageForm.appointment_id} перенесена.`);
              }}>
                <h3>Перенос</h3>
                <label className="full-width"><span>Запись</span><select value={manageForm.appointment_id} onChange={(event) => {
                  const appointment = snapshot.appointments.find((item) => item.id === Number(event.target.value));
                  setManageForm((current) => ({
                    ...current,
                    appointment_id: event.target.value,
                    appointment_date: appointment?.appointment_date || current.appointment_date,
                    start_time: appointment?.start_time || current.start_time,
                    master_id: appointment ? String(appointment.master_id) : "",
                    status: appointment?.status || current.status,
                    comment: appointment?.comment || ""
                  }));
                }}><option value="">Выберите запись</option>{activeManageableAppointments.map((appointment) => <option key={appointment.id} value={appointment.id}>№{appointment.id} · {clientLabel(appointment)} · {formatDateTime(appointment.appointment_date, appointment.start_time)}</option>)}</select></label>
                <label><span>Новая дата</span><input type="date" value={manageForm.appointment_date} onChange={(event) => setManageForm((current) => ({ ...current, appointment_date: event.target.value }))} /></label>
                <label><span>Новое время</span><input type="time" value={manageForm.start_time.slice(0, 5)} onChange={(event) => setManageForm((current) => ({ ...current, start_time: `${event.target.value}:00` }))} /></label>
                <label><span>Мастер</span><select value={manageForm.master_id} onChange={(event) => setManageForm((current) => ({ ...current, master_id: event.target.value }))}><option value="">Сохранить текущего</option>{snapshot.masters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}</select></label>
                <label><span>Комментарий</span><input value={manageForm.comment} onChange={(event) => setManageForm((current) => ({ ...current, comment: event.target.value }))} /></label>
                <button className="button primary" type="submit">Сохранить перенос</button>
              </form>
              <form className="form-grid compact" onSubmit={(event) => {
                event.preventDefault();
                if (!manageForm.appointment_id) {
                  setError("Выберите запись для смены статуса.");
                  return;
                }
                void runAction(() => api.updateAppointmentStatus(Number(manageForm.appointment_id), {
                  status: manageForm.status,
                  actor_role: "admin",
                  comment: manageForm.comment || undefined
                }), `Статус записи №${manageForm.appointment_id} обновлен.`);
              }}>
                <h3>Статус</h3>
                <label className="full-width"><span>Выбранная запись</span><div className="slot-preview">{selectedAppointment ? <p>№{selectedAppointment.id} · {clientLabel(selectedAppointment)} · {serviceName(selectedAppointment.service_id)} · {formatDateTime(selectedAppointment.appointment_date, selectedAppointment.start_time)}</p> : <p>Запись пока не выбрана.</p>}</div></label>
                <label><span>Новый статус</span><select value={manageForm.status} onChange={(event) => setManageForm((current) => ({ ...current, status: event.target.value }))}><option value="confirmed">Подтверждена</option><option value="completed">Завершена</option><option value="no_show">Неявка</option><option value="canceled_by_admin">Отменена салоном</option></select></label>
                <label className="full-width"><span>Комментарий</span><input value={manageForm.comment} onChange={(event) => setManageForm((current) => ({ ...current, comment: event.target.value }))} /></label>
                <button className="button primary full-width" type="submit">Обновить статус</button>
              </form>
            </div>
          </SectionPanel>
        </div>
      ) : null}

      {activeSection === "catalog" ? (
        <div className="dashboard-grid">
          <SectionPanel title="Каталог" subtitle="Три рабочие формы: добавить новое или выбрать существующую сущность и изменить ее.">
            <div className="catalog-grid">
              <div className="catalog-forms">
                <form className="form-grid compact catalog-form" onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    () =>
                      editingCategoryId !== null
                        ? api.updateCategory(editingCategoryId, {
                            name: categoryForm.name,
                            description: categoryForm.description || undefined
                          })
                        : api.createCategory({
                            name: categoryForm.name,
                            description: categoryForm.description || undefined
                          }),
                    editingCategoryId !== null ? "Категория обновлена." : "Категория создана."
                  ).then(() => resetCategoryForm());
                }}>
                  <h3>{editingCategoryId !== null ? "Редактирование категории" : "Новая категория"}</h3>
                  <label className="full-width">
                    <span>Существующая категория</span>
                    <select
                      value={editingCategoryId ?? ""}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          resetCategoryForm();
                          return;
                        }
                        const category = snapshot.categories.find((item) => item.id === Number(value));
                        if (!category) {
                          return;
                        }
                        setEditingCategoryId(category.id);
                        setCategoryForm({
                          name: category.name,
                          description: category.description || ""
                        });
                      }}
                    >
                      <option value="">Создать новую категорию</option>
                      {snapshot.categories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label><span>Название</span><input value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} /></label>
                  <label className="full-width"><span>Описание</span><input value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} /></label>
                  {editingCategoryId !== null ? <button className="button ghost full-width" type="button" onClick={resetCategoryForm}>Отменить редактирование</button> : null}
                  {editingCategoryId !== null ? <button className="button subtle full-width" type="button" onClick={() => void runDeleteAction(() => api.deleteCategory(editingCategoryId), `Удалить категорию «${categoryForm.name || "без названия"}»?`, "Категория удалена.", resetCategoryForm)}>Удалить категорию</button> : null}
                  <button className="button primary full-width" type="submit">{editingCategoryId !== null ? "Сохранить категорию" : "Добавить категорию"}</button>
                </form>
                <form className="form-grid compact catalog-form" onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    () =>
                      editingServiceId !== null
                        ? api.updateService(editingServiceId, {
                            category_id: Number(serviceForm.category_id),
                            name: serviceForm.name,
                            description: serviceForm.description || undefined,
                            duration_minutes: Number(serviceForm.duration_minutes),
                            price: serviceForm.price
                          })
                        : api.createService({
                            category_id: Number(serviceForm.category_id),
                            name: serviceForm.name,
                            description: serviceForm.description || undefined,
                            duration_minutes: Number(serviceForm.duration_minutes),
                            price: serviceForm.price
                          }),
                    editingServiceId !== null ? "Услуга обновлена." : "Услуга создана."
                  ).then(() => resetServiceForm());
                }}>
                  <h3>{editingServiceId !== null ? "Редактирование услуги" : "Новая услуга"}</h3>
                  <label className="full-width">
                    <span>Существующая услуга</span>
                    <select
                      value={editingServiceId ?? ""}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          resetServiceForm();
                          return;
                        }
                        const service = snapshot.services.find((item) => item.id === Number(value));
                        if (!service) {
                          return;
                        }
                        setEditingServiceId(service.id);
                        setServiceForm({
                          category_id: String(service.category_id),
                          name: service.name,
                          description: service.description || "",
                          duration_minutes: String(service.duration_minutes),
                          price: String(service.price)
                        });
                      }}
                    >
                      <option value="">Создать новую услугу</option>
                      {snapshot.services.map((service) => (
                        <option key={service.id} value={service.id}>
                          {service.name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label><span>Категория</span><select value={serviceForm.category_id} onChange={(event) => setServiceForm((current) => ({ ...current, category_id: event.target.value }))}><option value="">Выберите категорию</option>{snapshot.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label><span>Название</span><input value={serviceForm.name} onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))} /></label>
                  <label className="full-width"><span>Описание</span><input value={serviceForm.description} onChange={(event) => setServiceForm((current) => ({ ...current, description: event.target.value }))} /></label>
                  <label><span>Длительность</span><input type="number" value={serviceForm.duration_minutes} onChange={(event) => setServiceForm((current) => ({ ...current, duration_minutes: event.target.value }))} /></label>
                  <label><span>Цена</span><input value={serviceForm.price} onChange={(event) => setServiceForm((current) => ({ ...current, price: event.target.value }))} /></label>
                  {editingServiceId !== null ? <button className="button ghost full-width" type="button" onClick={resetServiceForm}>Отменить редактирование</button> : null}
                  {editingServiceId !== null ? <button className="button subtle full-width" type="button" onClick={() => void runDeleteAction(() => api.deleteService(editingServiceId), `Удалить услугу «${serviceForm.name || "без названия"}»?`, "Услуга удалена.", resetServiceForm)}>Удалить услугу</button> : null}
                  <button className="button primary full-width" type="submit">{editingServiceId !== null ? "Сохранить услугу" : "Добавить услугу"}</button>
                </form>
                <form className="form-grid compact catalog-form" onSubmit={(event) => {
                  event.preventDefault();
                  void runAction(
                    () =>
                      editingMasterId !== null
                        ? api.updateMaster(editingMasterId, {
                            full_name: masterForm.full_name,
                            specialization: masterForm.specialization || undefined,
                            phone: masterForm.phone || undefined,
                            experience_years: Number(masterForm.experience_years),
                            service_ids: masterForm.service_ids
                          })
                        : api.createMaster({
                            full_name: masterForm.full_name,
                            specialization: masterForm.specialization || undefined,
                            phone: masterForm.phone || undefined,
                            experience_years: Number(masterForm.experience_years),
                            service_ids: masterForm.service_ids
                          }),
                    editingMasterId !== null ? "Мастер обновлен." : "Мастер добавлен."
                  ).then(() => resetMasterForm());
                }}>
                  <h3>{editingMasterId !== null ? "Редактирование мастера" : "Новый мастер"}</h3>
                  <label className="full-width">
                    <span>Существующий мастер</span>
                    <select
                      value={editingMasterId ?? ""}
                      onChange={(event) => {
                        const value = event.target.value;
                        if (!value) {
                          resetMasterForm();
                          return;
                        }
                        const master = snapshot.masters.find((item) => item.id === Number(value));
                        if (!master) {
                          return;
                        }
                        setEditingMasterId(master.id);
                        const masterServices = snapshot.services.filter((service) => master.service_ids.includes(service.id));
                        setMasterForm({
                          category_id: masterServices[0] ? String(masterServices[0].category_id) : "",
                          full_name: master.full_name,
                          specialization: master.specialization || "",
                          phone: master.phone || "",
                          experience_years: String(master.experience_years ?? 3),
                          service_ids: master.service_ids
                        });
                      }}
                    >
                      <option value="">Создать нового мастера</option>
                      {snapshot.masters.map((master) => (
                        <option key={master.id} value={master.id}>
                          {master.full_name}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label><span>ФИО</span><input value={masterForm.full_name} onChange={(event) => setMasterForm((current) => ({ ...current, full_name: event.target.value }))} /></label>
                  <label><span>Специализация</span><input value={masterForm.specialization} onChange={(event) => setMasterForm((current) => ({ ...current, specialization: event.target.value }))} /></label>
                  <label><span>Телефон</span><input value={masterForm.phone} onChange={(event) => setMasterForm((current) => ({ ...current, phone: event.target.value }))} /></label>
                  <label><span>Стаж, лет</span><input type="number" value={masterForm.experience_years} onChange={(event) => setMasterForm((current) => ({ ...current, experience_years: event.target.value }))} /></label>
                  <label><span>Категория мастера</span><select value={masterForm.category_id} onChange={(event) => setMasterForm((current) => ({ ...current, category_id: event.target.value, service_ids: current.service_ids.filter((serviceId) => snapshot.services.some((service) => service.id === serviceId && service.category_id === Number(event.target.value))) }))}><option value="">Выберите категорию</option>{snapshot.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label className="full-width"><span>Услуги мастера</span><select multiple value={masterForm.service_ids.map(String)} onChange={(event) => setMasterForm((current) => ({ ...current, service_ids: Array.from(event.target.selectedOptions).map((option) => Number(option.value)) }))} disabled={!masterForm.category_id}>{masterCategoryServices.length === 0 ? <option value="">Сначала выберите категорию</option> : null}{masterCategoryServices.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
                  {editingMasterId !== null ? <button className="button ghost full-width" type="button" onClick={resetMasterForm}>Отменить редактирование</button> : null}
                  {editingMasterId !== null ? <button className="button subtle full-width" type="button" onClick={() => void runDeleteAction(() => api.deleteMaster(editingMasterId), `Удалить мастера «${masterForm.full_name || "без имени"}»?`, "Мастер удален.", resetMasterForm)}>Удалить мастера</button> : null}
                  <button className="button primary full-width" type="submit">{editingMasterId !== null ? "Сохранить мастера" : "Добавить мастера"}</button>
                </form>
              </div>
            </div>
          </SectionPanel>
        </div>
      ) : null}

      {activeSection === "clients" ? (
        <div className="dashboard-grid">
          <SectionPanel title="Клиенты" subtitle="Все зарегистрированные клиенты, которые уже писали в VK-бот или были добавлены администратором.">
            <div className="client-cards">
              {recentClients.length === 0 ? (
                <p className="empty-state">Клиентская база пока пуста.</p>
              ) : (
                recentClients.map((client) => (
                  <article key={client.id} className="client-card">
                    <strong>{client.full_name || `VK ID ${client.vk_user_id}`}</strong>
                    <span>VK ID: {client.vk_user_id}</span>
                    <span>{client.phone || "Телефон не указан"}</span>
                    <span>
                      {client.status === "vip"
                        ? "VIP"
                        : client.status === "blocked"
                          ? "Заблокирован"
                          : client.status === "active"
                            ? "Активный"
                            : "Новый"}
                    </span>
                  </article>
                ))
              )}
            </div>
          </SectionPanel>
        </div>
      ) : null}

      {activeSection === "calendar" ? (
        <div className="dashboard-grid">
          <SectionPanel
            title="Календарь записей"
            subtitle="Календарный вид помогает быстро увидеть загруженность по дням и открыть список визитов на выбранную дату."
            aside={
              <div className="calendar-toolbar">
                <button className="button ghost" type="button" onClick={() => shiftCalendarMonth(-1)}>
                  Назад
                </button>
                <strong>{calendarMonthLabel}</strong>
                <button className="button ghost" type="button" onClick={() => shiftCalendarMonth(1)}>
                  Вперед
                </button>
              </div>
            }
          >
            <div className="calendar-layout">
              <div className="calendar-board">
                <div className="calendar-weekdays">
                  {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
                    <span key={day}>{day}</span>
                  ))}
                </div>
                <div className="calendar-grid">
                  {calendarCells.map((cell) => {
                    if (!cell.date) {
                      return <div key={cell.key} className="calendar-day calendar-day-empty" />;
                    }
                    const items = appointmentsByDate[cell.date] ?? [];
                    const isToday = cell.date === todayIso;
                    const isActive = cell.date === selectedCalendarDate;
                    return (
                      <button
                        key={cell.key}
                        type="button"
                        className={`calendar-day ${isActive ? "calendar-day-active" : ""} ${items.length > 0 ? "calendar-day-busy" : ""} ${isToday ? "calendar-day-today" : ""}`}
                        onClick={() => setSelectedCalendarDate(cell.date)}
                      >
                        <strong>{Number(cell.date.slice(-2))}</strong>
                        <span>{items.length > 0 ? `${items.length} запис${items.length === 1 ? "ь" : items.length < 5 ? "и" : "ей"}` : "Свободно"}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
              <div className="mini-panel calendar-agenda">
                <h3>Записи на {selectedCalendarDate}</h3>
                {selectedCalendarAppointments.length === 0 ? (
                  <p>На выбранную дату записей пока нет.</p>
                ) : (
                  <ul className="list">
                    {selectedCalendarAppointments.map((appointment) => (
                      <li key={appointment.id}>
                        <strong>№{appointment.id} · {appointment.start_time.slice(0, 5)} · {serviceName(appointment.service_id)}</strong>
                        <span>{clientLabel(appointment)} · {masterName(appointment.master_id)}</span>
                        <span>{appointmentStatusLabel(appointment.status)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </SectionPanel>
        </div>
      ) : null}
    </main>
  );
}
