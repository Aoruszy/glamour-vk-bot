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
  Notification,
  Schedule,
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
  schedules: Schedule[];
  appointments: Appointment[];
  notifications: Notification[];
};

type SectionId = "overview" | "appointments" | "catalog" | "clients" | "notifications";

const SECTIONS: Array<{ id: SectionId; label: string; note: string }> = [
  { id: "overview", label: "Обзор", note: "Ключевые цифры и недавние события" },
  { id: "appointments", label: "Записи", note: "Создание, перенос и статусы" },
  { id: "catalog", label: "Каталог", note: "Категории, услуги и мастера" },
  { id: "clients", label: "Клиенты", note: "База и рабочий график" },
  { id: "notifications", label: "Уведомления", note: "VK и очередь отправки" }
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
    schedules: [],
    appointments: [],
    notifications: []
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

function notificationTypeLabel(type: string) {
  return (
    {
      booking_confirmation: "Подтверждение записи",
      reminder_24h: "Напоминание за 24 часа",
      reminder_2h: "Напоминание за 2 часа",
      cancellation: "Отмена",
      reschedule: "Перенос",
      status_update: "Обновление статуса"
    }[type] ?? type
  );
}

function notificationStatusLabel(status: string) {
  return ({ pending: "Ожидает", sent: "Отправлено", skipped: "Пропущено", failed: "Ошибка" }[status] ?? status);
}

function formatDateTime(dateValue: string, timeValue: string) {
  return `${dateValue} в ${timeValue.slice(0, 5)}`;
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
  const [dateRange, setDateRange] = useState(monthBounds());
  const [activeSection, setActiveSection] = useState<SectionId>("overview");
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "" });
  const [categoryForm, setCategoryForm] = useState({ name: "", description: "" });
  const [serviceForm, setServiceForm] = useState({
    category_id: "",
    name: "",
    description: "",
    duration_minutes: "60",
    price: "1500.00"
  });
  const [masterForm, setMasterForm] = useState({
    full_name: "",
    specialization: "",
    phone: "",
    experience_years: "3",
    service_ids: [] as number[]
  });
  const [clientForm, setClientForm] = useState({ vk_user_id: "", full_name: "", phone: "" });
  const [scheduleForm, setScheduleForm] = useState({
    master_id: "",
    work_date: new Date().toISOString().slice(0, 10),
    start_time: "10:00:00",
    end_time: "18:00:00"
  });
  const [appointmentForm, setAppointmentForm] = useState({
    vk_user_id: "",
    service_id: "",
    master_id: "",
    appointment_date: new Date().toISOString().slice(0, 10),
    start_time: "10:00:00",
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
      const [stats, clients, categories, services, masters, schedules, appointments, notifications] = await Promise.all([
        api.getStats(dateRange.start, dateRange.end),
        api.listClients(),
        api.listCategories(),
        api.listServices(),
        api.listMasters(),
        api.listSchedules(),
        api.listAppointments(),
        api.listNotifications()
      ]);
      setSnapshot({ stats, clients, categories, services, masters, schedules, appointments, notifications });
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

  async function processNotificationQueue() {
    try {
      const result = await api.processNotifications();
      setStatusMessage(`Очередь обработана: отправлено ${result.sent}, пропущено ${result.skipped}, ошибок ${result.failed}.`);
      await refreshAll();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось обработать очередь.");
    }
  }

  const selectedAppointment = snapshot.appointments.find((item) => item.id === Number(manageForm.appointment_id));
  const activeManageableAppointments = snapshot.appointments.filter(
    (item) => !["canceled_by_client", "canceled_by_admin"].includes(item.status)
  );
  const recentAppointments = snapshot.appointments.slice(0, 8);
  const recentClients = snapshot.clients.slice(0, 8);
  const recentSchedules = snapshot.schedules.slice(0, 8);
  const recentNotifications = snapshot.notifications.slice(0, 10);

  const clientLabel = (appointment: Appointment) =>
    appointment.client_name ? `${appointment.client_name} · VK ID ${appointment.client_vk_user_id}` : `VK ID ${appointment.client_vk_user_id}`;
  const serviceName = (serviceId: number) => snapshot.services.find((item) => item.id === serviceId)?.name || `Услуга №${serviceId}`;
  const masterName = (masterId: number) => snapshot.masters.find((item) => item.id === masterId)?.full_name || `Мастер №${masterId}`;
  const categoryName = (categoryId: number) =>
    snapshot.categories.find((item) => item.id === categoryId)?.name || `Категория №${categoryId}`;

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
            уведомлениями для пользователей VK без длинной прокрутки.
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
                <div className="mini-panel"><h3>Ближайшие записи</h3><ul className="list">{recentAppointments.map((appointment) => <li key={appointment.id}><strong>№{appointment.id} · {serviceName(appointment.service_id)}</strong><span>{clientLabel(appointment)} · {masterName(appointment.master_id)}</span><span>{formatDateTime(appointment.appointment_date, appointment.start_time)} · {appointmentStatusLabel(appointment.status)}</span></li>)}</ul></div>
                <div className="mini-panel"><h3>Последние уведомления</h3><ul className="list">{recentNotifications.slice(0, 6).map((notification) => <li key={notification.id}><strong>{notificationTypeLabel(notification.type)}</strong><span>{notificationStatusLabel(notification.status)} · №{notification.appointment_id}</span></li>)}</ul></div>
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
                  setError("Укажите VK ID клиента для записи.");
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
                <label><span>VK ID клиента</span><input type="number" value={appointmentForm.vk_user_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, vk_user_id: event.target.value }))} required /></label>
                <label><span>Услуга</span><select value={appointmentForm.service_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, service_id: event.target.value }))}><option value="">Выберите услугу</option>{snapshot.services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
                <label><span>Мастер</span><select value={appointmentForm.master_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, master_id: event.target.value }))}><option value="">Любой свободный мастер</option>{snapshot.masters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}</select></label>
                <label><span>Дата</span><input type="date" value={appointmentForm.appointment_date} onChange={(event) => setAppointmentForm((current) => ({ ...current, appointment_date: event.target.value }))} /></label>
                <label><span>Время</span><input type="time" value={appointmentForm.start_time.slice(0, 5)} onChange={(event) => setAppointmentForm((current) => ({ ...current, start_time: `${event.target.value}:00` }))} /></label>
                <label className="full-width"><span>Комментарий</span><input value={appointmentForm.comment} onChange={(event) => setAppointmentForm((current) => ({ ...current, comment: event.target.value }))} /></label>
                <button className="button primary full-width" type="submit">Создать запись</button>
              </form>
              <div className="slot-preview"><h3>Свободные окна</h3>{slotPreview.length === 0 ? <p>Пока пусто. Выберите услугу и дату, затем нажмите кнопку просмотра.</p> : <ul>{slotPreview.slice(0, 8).map((slot) => <li key={`${slot.work_date}-${slot.start_time}`}><strong>{slot.start_time.slice(0, 5)}-{slot.end_time.slice(0, 5)}</strong><span>Мастера: {slot.master_ids.join(", ")}</span></li>)}</ul>}</div>
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
          <SectionPanel title="Каталог" subtitle="Категории, услуги и мастера, которые видит клиент во VK.">
            <div className="catalog-grid">
              <div className="catalog-forms">
                <form className="form-grid compact catalog-form" onSubmit={(event) => { event.preventDefault(); void runAction(() => api.createCategory({ name: categoryForm.name, description: categoryForm.description || undefined }), "Категория создана."); }}>
                  <h3>Новая категория</h3>
                  <label><span>Название</span><input value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} /></label>
                  <label className="full-width"><span>Описание</span><input value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} /></label>
                  <button className="button primary full-width" type="submit">Добавить категорию</button>
                </form>
                <form className="form-grid compact catalog-form" onSubmit={(event) => { event.preventDefault(); void runAction(() => api.createService({ category_id: Number(serviceForm.category_id), name: serviceForm.name, description: serviceForm.description || undefined, duration_minutes: Number(serviceForm.duration_minutes), price: serviceForm.price }), "Услуга создана."); }}>
                  <h3>Новая услуга</h3>
                  <label><span>Категория</span><select value={serviceForm.category_id} onChange={(event) => setServiceForm((current) => ({ ...current, category_id: event.target.value }))}><option value="">Выберите категорию</option>{snapshot.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label>
                  <label><span>Название</span><input value={serviceForm.name} onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))} /></label>
                  <label><span>Длительность</span><input type="number" value={serviceForm.duration_minutes} onChange={(event) => setServiceForm((current) => ({ ...current, duration_minutes: event.target.value }))} /></label>
                  <label><span>Цена</span><input value={serviceForm.price} onChange={(event) => setServiceForm((current) => ({ ...current, price: event.target.value }))} /></label>
                  <button className="button primary full-width" type="submit">Добавить услугу</button>
                </form>
                <form className="form-grid compact catalog-form" onSubmit={(event) => { event.preventDefault(); void runAction(() => api.createMaster({ full_name: masterForm.full_name, specialization: masterForm.specialization || undefined, phone: masterForm.phone || undefined, experience_years: Number(masterForm.experience_years), service_ids: masterForm.service_ids }), "Мастер добавлен."); }}>
                  <h3>Новый мастер</h3>
                  <label><span>ФИО</span><input value={masterForm.full_name} onChange={(event) => setMasterForm((current) => ({ ...current, full_name: event.target.value }))} /></label>
                  <label><span>Специализация</span><input value={masterForm.specialization} onChange={(event) => setMasterForm((current) => ({ ...current, specialization: event.target.value }))} /></label>
                  <label className="full-width"><span>Услуги мастера</span><select multiple value={masterForm.service_ids.map(String)} onChange={(event) => setMasterForm((current) => ({ ...current, service_ids: Array.from(event.target.selectedOptions).map((option) => Number(option.value)) }))}>{snapshot.services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}</select></label>
                  <button className="button primary full-width" type="submit">Добавить мастера</button>
                </form>
              </div>

              <div className="catalog-lists">
                <div className="mini-panel">
                  <h3>Категории</h3>
                  <ul className="list entity-list">
                    {snapshot.categories.map((category) => (
                      <li key={category.id}>
                        <div>
                          <strong>{category.name}</strong>
                          <span>{category.description || "Без описания"}</span>
                        </div>
                        <button
                          className="button subtle"
                          onClick={() =>
                            void runAction(
                              () => api.updateCategory(category.id, { is_active: !category.is_active }),
                              category.is_active
                                ? `Категория «${category.name}» скрыта.`
                                : `Категория «${category.name}» снова активна.`
                            )
                          }
                        >
                          {category.is_active ? "Скрыть" : "Показать"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mini-panel">
                  <h3>Услуги</h3>
                  <ul className="list entity-list">
                    {snapshot.services.map((service) => (
                      <li key={service.id}>
                        <div>
                          <strong>{service.name}</strong>
                          <span>{categoryName(service.category_id)} · {service.duration_minutes} мин · {service.price} ₽</span>
                        </div>
                        <button
                          className="button subtle"
                          onClick={() =>
                            void runAction(
                              () => api.updateService(service.id, { is_active: !service.is_active }),
                              service.is_active
                                ? `Услуга «${service.name}» скрыта.`
                                : `Услуга «${service.name}» снова активна.`
                            )
                          }
                        >
                          {service.is_active ? "Скрыть" : "Показать"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mini-panel">
                  <h3>Мастера</h3>
                  <ul className="list entity-list">
                    {snapshot.masters.map((master) => (
                      <li key={master.id}>
                        <div>
                          <strong>{master.full_name}</strong>
                          <span>{master.specialization || "Специализация не указана"}</span>
                        </div>
                        <button
                          className="button subtle"
                          onClick={() =>
                            void runAction(
                              () => api.updateMaster(master.id, { is_active: !master.is_active }),
                              master.is_active
                                ? `Мастер «${master.full_name}» скрыт.`
                                : `Мастер «${master.full_name}» снова активен.`
                            )
                          }
                        >
                          {master.is_active ? "Скрыть" : "Показать"}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </SectionPanel>
        </div>
      ) : null}

      {activeSection === "clients" ? (
        <div className="dashboard-grid">
          <SectionPanel title="Клиенты и график" subtitle="Ведение базы клиентов и расписания команды.">
            <div className="two-column">
              <form className="form-grid compact" onSubmit={(event) => { event.preventDefault(); void runAction(() => api.createClient({ vk_user_id: Number(clientForm.vk_user_id), full_name: clientForm.full_name || undefined, phone: clientForm.phone || undefined }), "Клиент добавлен."); }}>
                <h3>Клиент</h3>
                <label><span>VK ID</span><input type="number" value={clientForm.vk_user_id} onChange={(event) => setClientForm((current) => ({ ...current, vk_user_id: event.target.value }))} /></label>
                <label><span>Имя</span><input value={clientForm.full_name} onChange={(event) => setClientForm((current) => ({ ...current, full_name: event.target.value }))} /></label>
                <label><span>Телефон</span><input value={clientForm.phone} onChange={(event) => setClientForm((current) => ({ ...current, phone: event.target.value }))} /></label>
                <button className="button primary" type="submit">Добавить клиента</button>
              </form>
              <form className="form-grid compact" onSubmit={(event) => { event.preventDefault(); void runAction(() => api.createSchedule({ master_id: Number(scheduleForm.master_id), work_date: scheduleForm.work_date, start_time: scheduleForm.start_time, end_time: scheduleForm.end_time }), "График мастера добавлен."); }}>
                <h3>Рабочий день</h3>
                <label><span>Мастер</span><select value={scheduleForm.master_id} onChange={(event) => setScheduleForm((current) => ({ ...current, master_id: event.target.value }))}><option value="">Выберите мастера</option>{snapshot.masters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}</select></label>
                <label><span>Дата</span><input type="date" value={scheduleForm.work_date} onChange={(event) => setScheduleForm((current) => ({ ...current, work_date: event.target.value }))} /></label>
                <label><span>Начало</span><input type="time" value={scheduleForm.start_time.slice(0, 5)} onChange={(event) => setScheduleForm((current) => ({ ...current, start_time: `${event.target.value}:00` }))} /></label>
                <label><span>Конец</span><input type="time" value={scheduleForm.end_time.slice(0, 5)} onChange={(event) => setScheduleForm((current) => ({ ...current, end_time: `${event.target.value}:00` }))} /></label>
                <button className="button primary" type="submit">Добавить график</button>
              </form>
            </div>
            <div className="mini-grid">
              <div className="mini-panel"><h3>Последние клиенты</h3><ul className="list">{recentClients.map((client) => <li key={client.id}><strong>{client.full_name || `VK ID ${client.vk_user_id}`}</strong><span>{client.phone || "Телефон не указан"}</span></li>)}</ul></div>
              <div className="mini-panel"><h3>Ближайшие рабочие дни</h3><ul className="list">{recentSchedules.map((schedule) => <li key={schedule.id}><strong>{masterName(schedule.master_id)}</strong><span>{schedule.work_date} · {schedule.start_time.slice(0, 5)}-{schedule.end_time.slice(0, 5)}</span></li>)}</ul></div>
            </div>
          </SectionPanel>
        </div>
      ) : null}

      {activeSection === "notifications" ? (
        <div className="dashboard-grid">
          <SectionPanel title="Уведомления" subtitle="Клиент получает сообщения при создании записи, переносе, отмене и смене статуса." aside={<button className="button ghost" onClick={() => void processNotificationQueue()}>Обработать очередь</button>}>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Время</th><th>Тип</th><th>Статус</th><th>Запись</th><th>Сообщение</th></tr></thead>
                <tbody>{recentNotifications.map((notification) => <tr key={notification.id}><td>{new Date(notification.send_at).toLocaleString()}</td><td>{notificationTypeLabel(notification.type)}</td><td><span className={`status-chip status-${notification.status}`}>{notificationStatusLabel(notification.status)}</span></td><td>№{notification.appointment_id}</td><td>{notification.message || "Текст сообщения будет сформирован при отправке."}</td></tr>)}</tbody>
              </table>
            </div>
          </SectionPanel>
        </div>
      ) : null}
    </main>
  );
}
