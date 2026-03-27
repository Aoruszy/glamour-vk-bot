type LoginScreenProps = {
  username: string;
  password: string;
  loading: boolean;
  error: string;
  onUsernameChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: () => void;
};

export function LoginScreen({
  username,
  password,
  loading,
  error,
  onUsernameChange,
  onPasswordChange,
  onSubmit
}: LoginScreenProps) {
  return (
    <main className="login-shell">
      <div className="ambient ambient-left" />
      <div className="ambient ambient-right" />

      <section className="login-card">
        <p className="eyebrow">Админ-панель Glamour</p>
        <h1>Вход в рабочее место салона.</h1>
        <p>
          Используйте логин и пароль администратора, чтобы открыть записи, каталог услуг, команду,
          клиентов и контур уведомлений VK.
        </p>

        <form
          className="form-grid login-form"
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
        >
          <label className="full-width">
            <span>Логин</span>
            <input
              autoComplete="username"
              value={username}
              onChange={(event) => onUsernameChange(event.target.value)}
            />
          </label>
          <label className="full-width">
            <span>Пароль</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => onPasswordChange(event.target.value)}
            />
          </label>
          <button className="button primary full-width" type="submit">
            {loading ? "Входим..." : "Войти"}
          </button>
        </form>

        {error ? <div className="banner banner-error inline-banner">{error}</div> : null}
      </section>
    </main>
  );
}
