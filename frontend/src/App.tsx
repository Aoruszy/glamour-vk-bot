import { startTransition, useEffect, useState } from "react";

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

function monthBounds() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), 1);
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0);
  return {
    start: start.toISOString().slice(0, 10),
    end: end.toISOString().slice(0, 10)
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
  switch (status) {
    case "new":
      return "Новая";
    case "confirmed":
      return "Подтверждена";
    case "completed":
      return "Выполнена";
    case "canceled_by_client":
      return "Отменена клиентом";
    case "canceled_by_admin":
      return "Отменена администратором";
    case "rescheduled":
      return "Перенесена";
    case "no_show":
      return "Не пришел";
    default:
      return status;
  }
}

function notificationTypeLabel(type: string) {
  switch (type) {
    case "booking_confirmation":
      return "Подтверждение записи";
    case "reminder_24h":
      return "Напоминание за 24 часа";
    case "reminder_2h":
      return "Напоминание за 2 часа";
    case "cancellation":
      return "Отмена";
    case "reschedule":
      return "Перенос";
    default:
      return type;
  }
}

function notificationStatusLabel(status: string) {
  switch (status) {
    case "pending":
      return "Ожидает";
    case "sent":
      return "Отправлено";
    case "skipped":
      return "Пропущено";
    case "failed":
      return "Ошибка";
    default:
      return status;
  }
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
    client_id: "",
    service_id: "",
    master_id: "",
    appointment_date: new Date().toISOString().slice(0, 10),
    start_time: "10:00:00",
    comment: ""
  });
  const [appointmentManageForm, setAppointmentManageForm] = useState({
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
    if (snapshot.appointments.length === 0) {
      return;
    }
    if (appointmentManageForm.appointment_id) {
      return;
    }
    const first = snapshot.appointments[0];
    setAppointmentManageForm((current) => ({
      ...current,
      appointment_id: String(first.id),
      appointment_date: first.appointment_date,
      start_time: first.start_time,
      master_id: String(first.master_id),
      status: first.status,
      comment: first.comment || ""
    }));
  }, [snapshot.appointments, appointmentManageForm.appointment_id]);

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
    setStatusMessage("");
  }

  async function refreshAll(initial = false) {
    if (initial) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }
    setError("");

    try {
      const [stats, clients, categories, services, masters, schedules, appointments, notifications] =
        await Promise.all([
          api.getStats(dateRange.start, dateRange.end),
          api.listClients(),
          api.listCategories(),
          api.listServices(),
          api.listMasters(),
          api.listSchedules(),
          api.listAppointments(),
          api.listNotifications()
        ]);

      startTransition(() => {
        setSnapshot({
          stats,
          clients,
          categories,
          services,
          masters,
          schedules,
          appointments,
          notifications
        });
      });
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
    setStatusMessage("");
    setError("");
    try {
      await action();
      setStatusMessage(message);
      await refreshAll();
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        handleLogout();
        setError("Сессия администратора истекла. Войдите снова.");
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Произошла непредвиденная ошибка.");
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

  async function processNotificationQueue() {
    setStatusMessage("");
    setError("");
    try {
      const result = await api.processNotifications();
      setStatusMessage(
        `Очередь обработана: отправлено ${result.sent}, пропущено ${result.skipped}, ошибок ${result.failed}.`
      );
      await refreshAll();
    } catch (caughtError) {
      if (caughtError instanceof ApiError && caughtError.status === 401) {
        handleLogout();
        setError("Сессия администратора истекла. Войдите снова.");
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Не удалось обработать очередь уведомлений.");
      }
    }
  }

  async function previewSlots() {
    if (!appointmentForm.service_id || !appointmentForm.appointment_date) {
      setError("Выберите услугу и дату перед просмотром свободных слотов.");
      return;
    }

    try {
      const slots = await api.getAvailableSlots(
        Number(appointmentForm.service_id),
        appointmentForm.appointment_date,
        appointmentForm.master_id ? Number(appointmentForm.master_id) : undefined
      );
      setSlotPreview(slots);
      setStatusMessage(`Найдено слотов: ${slots.length}.`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось загрузить свободные слоты.");
    }
  }

  async function previewRescheduleSlots() {
    if (!selectedManagedAppointment) {
      setError("Сначала выберите запись для переноса.");
      return;
    }

    try {
      const slots = await api.getAvailableSlots(
        selectedManagedAppointment.service_id,
        appointmentManageForm.appointment_date,
        appointmentManageForm.master_id
          ? Number(appointmentManageForm.master_id)
          : undefined
      );
      setSlotPreview(slots);
      setStatusMessage(`Найдено слотов для переноса: ${slots.length}.`);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Не удалось подобрать слоты для переноса.");
    }
  }

  function clientName(clientId: number) {
    return snapshot.clients.find((item) => item.id === clientId)?.full_name || `Клиент #${clientId}`;
  }

  function serviceName(serviceId: number) {
    return snapshot.services.find((item) => item.id === serviceId)?.name || `Услуга #${serviceId}`;
  }

  function masterName(masterId: number) {
    return snapshot.masters.find((item) => item.id === masterId)?.full_name || `Мастер #${masterId}`;
  }

  const selectedManagedAppointment = snapshot.appointments.find(
    (item) => item.id === Number(appointmentManageForm.appointment_id)
  );

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
          <p className="eyebrow">Glamour CRM</p>
          <h1>Подготавливаем рабочее место салона.</h1>
          <p>Загружаем расписание, записи и активность VK-бота.</p>
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
          <p className="eyebrow">Glamour CRM</p>
          <h1>Управление салоном в одном окне.</h1>
          <p>
            Вы вошли как <strong>{adminName}</strong>. Здесь собраны записи, мастера,
            услуги, клиенты и рабочий контур VK-бота.
          </p>
        </div>
        <div className="hero-actions">
          <label>
            <span>С</span>
            <input
              type="date"
              value={dateRange.start}
              onChange={(event) =>
                setDateRange((current) => ({ ...current, start: event.target.value }))
              }
            />
          </label>
          <label>
            <span>По</span>
            <input
              type="date"
              value={dateRange.end}
              onChange={(event) =>
                setDateRange((current) => ({ ...current, end: event.target.value }))
              }
            />
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

      <section className="stats-grid">
        <StatCard label="Записи" value={snapshot.stats?.total_appointments ?? 0} note="Все записи за выбранный период." />
        <StatCard label="Отмены" value={snapshot.stats?.canceled_appointments ?? 0} note="Отмены клиентов и администратора вместе." />
        <StatCard label="Новые клиенты" value={snapshot.stats?.new_clients ?? 0} note="Карточки, созданные из VK или админки." />
        <StatCard label="Покрытие команды" value={`${snapshot.stats?.active_masters ?? 0} мастеров / ${snapshot.stats?.active_services ?? 0} услуг`} note="Активные специалисты и каталог услуг." />
      </section>

      <div className="dashboard-grid">
        <SectionPanel title="Управление записями" subtitle="Создавайте записи, просматривайте свободные слоты и контролируйте ближайшие визиты." aside={<button className="button ghost" onClick={() => void previewSlots()}>Показать слоты</button>}>
          <div className="two-column">
            <form className="form-grid" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createAppointment({
                  client_id: Number(appointmentForm.client_id),
                  service_id: Number(appointmentForm.service_id),
                  appointment_date: appointmentForm.appointment_date,
                  start_time: appointmentForm.start_time,
                  master_id: appointmentForm.master_id ? Number(appointmentForm.master_id) : undefined,
                  comment: appointmentForm.comment || undefined,
                  created_by: "admin"
                });
                setAppointmentForm((current) => ({ ...current, comment: "" }));
                setSlotPreview([]);
              }, "Запись успешно создана.");
            }}>
              <label>
                <span>Клиент</span>
                <select value={appointmentForm.client_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, client_id: event.target.value }))}>
                  <option value="">Выберите клиента</option>
                  {snapshot.clients.map((client) => <option key={client.id} value={client.id}>{client.full_name || `Клиент #${client.id}`}</option>)}
                </select>
              </label>
              <label>
                <span>Услуга</span>
                <select value={appointmentForm.service_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, service_id: event.target.value }))}>
                  <option value="">Выберите услугу</option>
                  {snapshot.services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
                </select>
              </label>
              <label>
                <span>Мастер</span>
                <select value={appointmentForm.master_id} onChange={(event) => setAppointmentForm((current) => ({ ...current, master_id: event.target.value }))}>
                  <option value="">Любой свободный мастер</option>
                  {snapshot.masters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}
                </select>
              </label>
              <label>
                <span>Дата</span>
                <input type="date" value={appointmentForm.appointment_date} onChange={(event) => setAppointmentForm((current) => ({ ...current, appointment_date: event.target.value }))} />
              </label>
              <label>
                <span>Время начала</span>
                <input type="time" value={appointmentForm.start_time.slice(0, 5)} onChange={(event) => setAppointmentForm((current) => ({ ...current, start_time: `${event.target.value}:00` }))} />
              </label>
              <label className="full-width">
                <span>Комментарий</span>
                <input type="text" value={appointmentForm.comment} onChange={(event) => setAppointmentForm((current) => ({ ...current, comment: event.target.value }))} placeholder="Необязательная заметка к визиту" />
              </label>
              <button className="button primary full-width" type="submit">Создать запись</button>
            </form>

            <div className="slot-preview">
              <h3>Предпросмотр свободных слотов</h3>
              {slotPreview.length === 0 ? <p>Слоты пока не загружены.</p> : <ul>{slotPreview.slice(0, 8).map((slot) => <li key={`${slot.work_date}-${slot.start_time}`}><strong>{slot.start_time.slice(0, 5)}</strong> - {slot.end_time.slice(0, 5)}, мастера: {slot.master_ids.join(", ")}</li>)}</ul>}
            </div>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Клиент</th>
                  <th>Услуга</th>
                  <th>Мастер</th>
                  <th>Статус</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.appointments.slice(0, 8).map((appointment) => (
                  <tr key={appointment.id}>
                    <td>{appointment.appointment_date} {appointment.start_time.slice(0, 5)}</td>
                    <td>{clientName(appointment.client_id)}</td>
                    <td>{serviceName(appointment.service_id)}</td>
                    <td>{masterName(appointment.master_id)}</td>
                    <td><span className={`status-chip status-${appointment.status}`}>{appointmentStatusLabel(appointment.status)}</span></td>
                    <td><button className="button subtle" onClick={() => void runAction(() => api.cancelAppointment(appointment.id, { actor_role: "admin", reason: "Отменено из панели администратора" }), `Запись #${appointment.id} отменена.`)}>Отменить</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="two-column" style={{ marginTop: "16px" }}>
            <form
              className="form-grid compact"
              onSubmit={(event) => {
                event.preventDefault();
                if (!appointmentManageForm.appointment_id) {
                  setError("Выберите запись для переноса.");
                  return;
                }
                void runAction(
                  async () => {
                    await api.rescheduleAppointment(Number(appointmentManageForm.appointment_id), {
                      appointment_date: appointmentManageForm.appointment_date,
                      start_time: appointmentManageForm.start_time,
                      master_id: appointmentManageForm.master_id
                        ? Number(appointmentManageForm.master_id)
                        : undefined,
                      comment: appointmentManageForm.comment || undefined,
                      actor_role: "admin"
                    });
                  },
                  `Запись #${appointmentManageForm.appointment_id} перенесена.`
                );
              }}
            >
              <h3>Перенос визита</h3>
              <label className="full-width">
                <span>Запись</span>
                <select
                  value={appointmentManageForm.appointment_id}
                  onChange={(event) => {
                    const appointment = snapshot.appointments.find(
                      (item) => item.id === Number(event.target.value)
                    );
                    setAppointmentManageForm((current) => ({
                      ...current,
                      appointment_id: event.target.value,
                      appointment_date: appointment?.appointment_date || current.appointment_date,
                      start_time: appointment?.start_time || current.start_time,
                      master_id: appointment ? String(appointment.master_id) : "",
                      status: appointment?.status || current.status,
                      comment: appointment?.comment || ""
                    }));
                  }}
                >
                  <option value="">Выберите запись</option>
                  {snapshot.appointments.map((appointment) => (
                    <option key={appointment.id} value={appointment.id}>
                      #{appointment.id} · {clientName(appointment.client_id)} ·{" "}
                      {appointment.appointment_date} {appointment.start_time.slice(0, 5)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Новая дата</span>
                <input
                  type="date"
                  value={appointmentManageForm.appointment_date}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      appointment_date: event.target.value
                    }))
                  }
                />
              </label>
              <label>
                <span>Новое время</span>
                <input
                  type="time"
                  value={appointmentManageForm.start_time.slice(0, 5)}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      start_time: `${event.target.value}:00`
                    }))
                  }
                />
              </label>
              <label>
                <span>Мастер</span>
                <select
                  value={appointmentManageForm.master_id}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      master_id: event.target.value
                    }))
                  }
                >
                  <option value="">Сохранить текущего или подобрать автоматически</option>
                  {snapshot.masters.map((master) => (
                    <option key={master.id} value={master.id}>
                      {master.full_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span>Комментарий</span>
                <input
                  value={appointmentManageForm.comment}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      comment: event.target.value
                    }))
                  }
                />
              </label>
              <button
                className="button ghost"
                type="button"
                onClick={() => void previewRescheduleSlots()}
              >
                Показать новые слоты
              </button>
              <button className="button primary" type="submit">
                Сохранить перенос
              </button>
            </form>

            <form
              className="form-grid compact"
              onSubmit={(event) => {
                event.preventDefault();
                if (!appointmentManageForm.appointment_id) {
                  setError("Выберите запись для смены статуса.");
                  return;
                }
                void runAction(
                  async () => {
                    await api.updateAppointmentStatus(Number(appointmentManageForm.appointment_id), {
                      status: appointmentManageForm.status,
                      actor_role: "admin",
                      comment: appointmentManageForm.comment || undefined
                    });
                  },
                  `Статус записи #${appointmentManageForm.appointment_id} обновлен.`
                );
              }}
            >
              <h3>Смена статуса</h3>
              <label className="full-width">
                <span>Выбранная запись</span>
                <div className="slot-preview">
                  {selectedManagedAppointment ? (
                    <p>
                      #{selectedManagedAppointment.id} · {clientName(selectedManagedAppointment.client_id)} ·{" "}
                      {serviceName(selectedManagedAppointment.service_id)} ·{" "}
                      {selectedManagedAppointment.appointment_date}{" "}
                      {selectedManagedAppointment.start_time.slice(0, 5)}
                    </p>
                  ) : (
                    <p>Запись пока не выбрана.</p>
                  )}
                </div>
              </label>
              <label>
                <span>Статус</span>
                <select
                  value={appointmentManageForm.status}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      status: event.target.value
                    }))
                  }
                >
                  <option value="confirmed">Подтверждена</option>
                  <option value="completed">Выполнена</option>
                  <option value="no_show">Не пришел</option>
                  <option value="canceled_by_admin">Отменена администратором</option>
                </select>
              </label>
              <label className="full-width">
                <span>Комментарий к статусу</span>
                <input
                  value={appointmentManageForm.comment}
                  onChange={(event) =>
                    setAppointmentManageForm((current) => ({
                      ...current,
                      comment: event.target.value
                    }))
                  }
                />
              </label>
              <button className="button primary full-width" type="submit">
                Обновить статус
              </button>
            </form>
          </div>
        </SectionPanel>

        <SectionPanel title="Каталог и команда" subtitle="Поддерживайте категории, услуги и профили мастеров, которые используются ботом VK и модулем записи.">
          <div className="three-column">
            <form className="form-grid compact" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createCategory({ name: categoryForm.name, description: categoryForm.description || undefined });
                setCategoryForm({ name: "", description: "" });
              }, "Категория услуг создана.");
            }}>
              <h3>Новая категория</h3>
              <label>
                <span>Название</span>
                <input value={categoryForm.name} onChange={(event) => setCategoryForm((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label>
                <span>Описание</span>
                <input value={categoryForm.description} onChange={(event) => setCategoryForm((current) => ({ ...current, description: event.target.value }))} />
              </label>
              <button className="button primary" type="submit">Добавить категорию</button>
            </form>

            <form className="form-grid compact" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createService({
                  category_id: Number(serviceForm.category_id),
                  name: serviceForm.name,
                  description: serviceForm.description || undefined,
                  duration_minutes: Number(serviceForm.duration_minutes),
                  price: serviceForm.price
                });
                setServiceForm({ category_id: serviceForm.category_id, name: "", description: "", duration_minutes: "60", price: "1500.00" });
              }, "Услуга создана.");
            }}>
              <h3>Новая услуга</h3>
              <label>
                <span>Категория</span>
                <select value={serviceForm.category_id} onChange={(event) => setServiceForm((current) => ({ ...current, category_id: event.target.value }))}>
                  <option value="">Выберите категорию</option>
                  {snapshot.categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
                </select>
              </label>
              <label>
                <span>Название</span>
                <input value={serviceForm.name} onChange={(event) => setServiceForm((current) => ({ ...current, name: event.target.value }))} />
              </label>
              <label>
                <span>Длительность (мин)</span>
                <input type="number" value={serviceForm.duration_minutes} onChange={(event) => setServiceForm((current) => ({ ...current, duration_minutes: event.target.value }))} />
              </label>
              <label>
                <span>Цена</span>
                <input value={serviceForm.price} onChange={(event) => setServiceForm((current) => ({ ...current, price: event.target.value }))} />
              </label>
              <button className="button primary" type="submit">Добавить услугу</button>
            </form>

            <form className="form-grid compact" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createMaster({
                  full_name: masterForm.full_name,
                  specialization: masterForm.specialization || undefined,
                  phone: masterForm.phone || undefined,
                  experience_years: Number(masterForm.experience_years),
                  service_ids: masterForm.service_ids
                });
                setMasterForm({ full_name: "", specialization: "", phone: "", experience_years: "3", service_ids: [] });
              }, "Мастер добавлен.");
            }}>
              <h3>Новый мастер</h3>
              <label>
                <span>ФИО</span>
                <input value={masterForm.full_name} onChange={(event) => setMasterForm((current) => ({ ...current, full_name: event.target.value }))} />
              </label>
              <label>
                <span>Специализация</span>
                <input value={masterForm.specialization} onChange={(event) => setMasterForm((current) => ({ ...current, specialization: event.target.value }))} />
              </label>
              <label>
                <span>Набор услуг</span>
                <select multiple value={masterForm.service_ids.map(String)} onChange={(event) => {
                  const values = Array.from(event.target.selectedOptions).map((option) => Number(option.value));
                  setMasterForm((current) => ({ ...current, service_ids: values }));
                }}>
                  {snapshot.services.map((service) => <option key={service.id} value={service.id}>{service.name}</option>)}
                </select>
              </label>
              <button className="button primary" type="submit">Добавить мастера</button>
            </form>
          </div>
        </SectionPanel>

        <SectionPanel title="Клиенты и график" subtitle="Ведите клиентскую базу и назначайте рабочие дни для каждого мастера.">
          <div className="two-column">
            <form className="form-grid compact" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createClient({
                  vk_user_id: Number(clientForm.vk_user_id),
                  full_name: clientForm.full_name || undefined,
                  phone: clientForm.phone || undefined
                });
                setClientForm({ vk_user_id: "", full_name: "", phone: "" });
              }, "Клиент добавлен.");
            }}>
              <h3>Новый клиент</h3>
              <label>
                <span>ID пользователя VK</span>
                <input type="number" value={clientForm.vk_user_id} onChange={(event) => setClientForm((current) => ({ ...current, vk_user_id: event.target.value }))} />
              </label>
              <label>
                <span>ФИО</span>
                <input value={clientForm.full_name} onChange={(event) => setClientForm((current) => ({ ...current, full_name: event.target.value }))} />
              </label>
              <label>
                <span>Телефон</span>
                <input value={clientForm.phone} onChange={(event) => setClientForm((current) => ({ ...current, phone: event.target.value }))} />
              </label>
              <button className="button primary" type="submit">Добавить клиента</button>
            </form>

            <form className="form-grid compact" onSubmit={(event) => {
              event.preventDefault();
              void runAction(async () => {
                await api.createSchedule({
                  master_id: Number(scheduleForm.master_id),
                  work_date: scheduleForm.work_date,
                  start_time: scheduleForm.start_time,
                  end_time: scheduleForm.end_time
                });
              }, "Рабочий день добавлен.");
            }}>
              <h3>Новый рабочий день</h3>
              <label>
                <span>Мастер</span>
                <select value={scheduleForm.master_id} onChange={(event) => setScheduleForm((current) => ({ ...current, master_id: event.target.value }))}>
                  <option value="">Выберите мастера</option>
                  {snapshot.masters.map((master) => <option key={master.id} value={master.id}>{master.full_name}</option>)}
                </select>
              </label>
              <label>
                <span>Дата</span>
                <input type="date" value={scheduleForm.work_date} onChange={(event) => setScheduleForm((current) => ({ ...current, work_date: event.target.value }))} />
              </label>
              <label>
                <span>Начало</span>
                <input type="time" value={scheduleForm.start_time.slice(0, 5)} onChange={(event) => setScheduleForm((current) => ({ ...current, start_time: `${event.target.value}:00` }))} />
              </label>
              <label>
                <span>Конец</span>
                <input type="time" value={scheduleForm.end_time.slice(0, 5)} onChange={(event) => setScheduleForm((current) => ({ ...current, end_time: `${event.target.value}:00` }))} />
              </label>
              <button className="button primary" type="submit">Добавить рабочий день</button>
            </form>
          </div>

          <div className="mini-grid">
            <div className="mini-panel">
              <h3>Последние клиенты</h3>
              <ul className="list">
                {snapshot.clients.slice(0, 6).map((client) => <li key={client.id}><strong>{client.full_name || `Клиент #${client.id}`}</strong><span>{client.phone || "Телефон пока не указан"}</span></li>)}
              </ul>
            </div>
            <div className="mini-panel">
              <h3>Ближайшие рабочие дни</h3>
              <ul className="list">
                {snapshot.schedules.slice(0, 6).map((schedule) => <li key={schedule.id}><strong>{masterName(schedule.master_id)}</strong><span>{schedule.work_date} - {schedule.start_time.slice(0, 5)}-{schedule.end_time.slice(0, 5)}</span></li>)}
              </ul>
            </div>
          </div>
        </SectionPanel>

        <SectionPanel
          title="Очередь уведомлений"
          subtitle="Следите за подтверждениями записей и напоминаниями, которые формирует система."
          aside={
            <button
              className="button ghost"
              onClick={() => void processNotificationQueue()}
            >
              Обработать очередь
            </button>
          }
        >
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Отправить в</th>
                  <th>Тип</th>
                  <th>Статус</th>
                  <th>Запись</th>
                  <th>Сообщение</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.notifications.slice(0, 8).map((notification) => (
                  <tr key={notification.id}>
                    <td>{new Date(notification.send_at).toLocaleString()}</td>
                    <td>{notificationTypeLabel(notification.type)}</td>
                    <td>{notificationStatusLabel(notification.status)}</td>
                    <td>#{notification.appointment_id}</td>
                    <td>{notification.message || "Текст сообщения отсутствует"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionPanel>
      </div>
    </main>
  );
}
