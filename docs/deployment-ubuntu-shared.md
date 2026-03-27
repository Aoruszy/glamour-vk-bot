# Развертывание Glamour на Ubuntu-сервере с другим проектом

Этот сценарий подходит, если на одном VPS уже работает другой сайт и вы хотите аккуратно добавить Glamour на отдельный поддомен, без Docker.

## Схема

- существующий проект остается как есть
- Glamour работает на `127.0.0.1:8010`
- nginx проксирует `bot.example.ru` на `127.0.0.1:8010`
- для Glamour используется отдельная база PostgreSQL

## 1. Подготовка сервера

Подключитесь по SSH и установите зависимости:

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib nginx git nodejs npm
```

Если `nodejs` в репозитории слишком старый, установите актуальную LTS-версию любым привычным вам способом, затем проверьте:

```bash
node -v
npm -v
```

## 2. Заберите проект с GitHub

```bash
sudo mkdir -p /var/www
cd /var/www
sudo git clone https://github.com/USERNAME/REPO.git glamour
sudo chown -R $USER:$USER /var/www/glamour
cd /var/www/glamour
```

## 3. Создайте базу PostgreSQL

```bash
sudo -u postgres psql
```

Внутри `psql`:

```sql
CREATE DATABASE glamour;
CREATE USER glamour_user WITH ENCRYPTED PASSWORD 'CHANGE_ME_DB_PASSWORD';
GRANT ALL PRIVILEGES ON DATABASE glamour TO glamour_user;
\q
```

## 4. Подготовьте backend

```bash
cd /var/www/glamour/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Создайте production-файл:

```bash
cp .env.example .env.production
nano .env.production
```

Пример:

```env
APP_NAME=Glamour API
APP_ENV=production
APP_HOST=127.0.0.1
APP_PORT=8010
API_PREFIX=/api/v1

DATABASE_URL=postgresql+psycopg://glamour_user:CHANGE_ME_DB_PASSWORD@127.0.0.1:5432/glamour

ALLOW_CORS_ORIGINS=https://bot.example.ru

ADMIN_USERNAME=admin
ADMIN_PASSWORD=CHANGE_ME_ADMIN_PASSWORD
AUTH_SECRET=CHANGE_ME_LONG_RANDOM_SECRET
AUTH_ACCESS_TOKEN_TTL_MINUTES=480

VK_GROUP_ID=237104538
VK_CALLBACK_SECRET=CHANGE_ME_VK_CALLBACK_SECRET
VK_CONFIRMATION_TOKEN=CHANGE_ME_VK_CONFIRMATION_TOKEN
VK_ACCESS_TOKEN=CHANGE_ME_VK_ACCESS_TOKEN
VK_API_VERSION=5.199

SALON_NAME=Glamour
SALON_ADDRESS=Калининград, адрес салона
SALON_PHONE=+7 (900) 000-00-00
SALON_WORKING_HOURS=10:00-20:00
SALON_MAP_URL=
SALON_WEBSITE_URL=https://bot.example.ru/admin
```

## 5. Соберите frontend

```bash
cd /var/www/glamour/frontend
npm install
npm run build
```

Frontend соберется в `frontend/dist`, а FastAPI сам отдаст его по `/admin`.

## 6. Создайте systemd-сервис

Скопируйте шаблон:

```bash
sudo cp /var/www/glamour/deploy/systemd/glamour.service /etc/systemd/system/glamour.service
```

Если нужно, поправьте путь в сервисе:

- `WorkingDirectory=/var/www/glamour/backend`
- `EnvironmentFile=/var/www/glamour/backend/.env.production`
- `ExecStart=/var/www/glamour/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010`

Затем:

```bash
sudo systemctl daemon-reload
sudo systemctl enable glamour
sudo systemctl start glamour
sudo systemctl status glamour
```

## 7. Настройте nginx

Скопируйте шаблон:

```bash
sudo cp /var/www/glamour/deploy/nginx/glamour.conf /etc/nginx/sites-available/glamour
```

Откройте файл и замените:

- `server_name bot.example.ru;` на ваш поддомен

Включите сайт:

```bash
sudo ln -s /etc/nginx/sites-available/glamour /etc/nginx/sites-enabled/glamour
sudo nginx -t
sudo systemctl reload nginx
```

## 8. Выпустите SSL

Если вы уже используете certbot на сервере:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d bot.example.ru
```

После этого проверьте:

- `https://bot.example.ru/healthz`
- `https://bot.example.ru/admin`

## 9. Заполните данные и создайте демо при необходимости

Если хотите тестовые данные:

```bash
cd /var/www/glamour/backend
source .venv/bin/activate
python -m app.scripts.seed_demo --reset
```

## 10. Подключите VK

В настройках сообщества VK:

- адрес callback: `https://bot.example.ru/api/v1/vk/events`
- секретный ключ: как `VK_CALLBACK_SECRET`
- строка подтверждения: как `VK_CONFIRMATION_TOKEN`
- тип события: включить `message_new`

## 11. Обновление проекта

```bash
cd /var/www/glamour
git pull

cd /var/www/glamour/frontend
npm install
npm run build

cd /var/www/glamour/backend
source .venv/bin/activate
pip install -e .

sudo systemctl restart glamour
```

## 12. Полезные проверки

```bash
sudo systemctl status glamour
journalctl -u glamour -n 100 --no-pager
sudo nginx -t
curl http://127.0.0.1:8010/healthz
curl https://bot.example.ru/healthz
```
