# Развертывание Glamour в облаке

## Что понадобится

- VPS или облачный сервер с Ubuntu 22.04/24.04
- домен, например `bot.example.ru`
- открытые порты `80` и `443`
- Docker и Docker Compose Plugin
- данные VK-сообщества: `VK_CALLBACK_SECRET`, `VK_CONFIRMATION_TOKEN`, `VK_ACCESS_TOKEN`

## 1. Подготовка сервера

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable docker
sudo systemctl start docker
```

## 2. Загрузка проекта

Скопируйте проект на сервер в любую папку, например `/opt/glamour`.

```bash
cd /opt/glamour
cp .env.production.example .env.production
```

Заполните `.env.production`:

- `APP_DOMAIN` укажите вашим доменом
- `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`, `AUTH_SECRET` замените на безопасные значения
- если меняете `POSTGRES_DB`, `POSTGRES_USER` или `POSTGRES_PASSWORD`, сразу обновите и `DATABASE_URL`
- `VK_CALLBACK_SECRET`, `VK_CONFIRMATION_TOKEN`, `VK_ACCESS_TOKEN` заполните значениями из VK
- `ALLOW_CORS_ORIGINS` укажите как `https://ваш-домен`

## 3. Запуск в production

```bash
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
docker compose --env-file .env.production -f docker-compose.production.yml exec app python -m app.scripts.seed_demo --reset
```

После запуска будут доступны:

- админка: `https://ваш-домен/admin`
- API: `https://ваш-домен/docs`
- healthcheck: `https://ваш-домен/healthz`

## 4. Подключение в VK

В настройках Callback API сообщества VK:

- URL: `https://ваш-домен/api/v1/vk/events`
- Секретный ключ: такой же, как `VK_CALLBACK_SECRET`
- Строка подтверждения: такая же, как `VK_CONFIRMATION_TOKEN`

После этого VK сможет отправлять события в облачный Glamour.

## 5. Полезные команды

```bash
docker compose --env-file .env.production -f docker-compose.production.yml logs -f app
docker compose --env-file .env.production -f docker-compose.production.yml logs -f caddy
docker compose --env-file .env.production -f docker-compose.production.yml restart app
docker compose --env-file .env.production -f docker-compose.production.yml exec app python -m app.scripts.process_notifications
```

## Что проверить перед подключением VK

- домен уже смотрит на IP сервера
- `https://ваш-домен/healthz` открывается
- `https://ваш-домен/admin` открывается
- в `.env.production` заполнены `VK_CALLBACK_SECRET`, `VK_CONFIRMATION_TOKEN`, `VK_ACCESS_TOKEN`
- в админку можно войти под production-логином
