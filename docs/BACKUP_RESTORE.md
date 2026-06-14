# Резервное копирование и восстановление SQLite

## Назначение

Инструкция по резервному копированию и восстановлению базы данных Typical Infrastructure на VPS с Docker Compose. Автоматизация (cron/systemd) **не входит** в scope этого документа — ниже только ручные команды и рекомендуемое расписание для настройки администратором.

См. также: [STAGING_DEPLOYMENT.md](runbook/STAGING_DEPLOYMENT.md), [PRODUCTION_LIKE_DEPLOYMENT.md](runbook/PRODUCTION_LIKE_DEPLOYMENT.md).

---

## Архитектура хранения данных

| Параметр | Значение |
|----------|----------|
| Сервис Compose | `app` |
| Путь к SQLite **внутри контейнера** | `/app/data/app.db` |
| Переменная окружения | `SQLITE_PATH=/app/data/app.db` (задаётся в `docker-compose.yml` и `Dockerfile`) |
| Точка монтирования volume | `/app/data` |
| Именованный volume Compose | `app_data` |
| Имя volume на хосте | `{compose_project}_app_data` (например `10typical_infrastructure_app_data`) |

Приложение (ядро, skill_assessment, psychological_testing) использует **один** файл SQLite по пути из `SQLITE_PATH`. Данные переживают пересборку образа и перезапуск контейнера, пока volume не удалён (`docker compose down -v`).

Проверить путь и наличие файла:

```bash
cd /path/to/typical_infrastructure   # каталог с docker-compose.yml на VPS

docker compose exec app printenv SQLITE_PATH
# ожидается: /app/data/app.db

docker compose exec app ls -lh /app/data/app.db
```

Узнать физический путь volume на хосте:

```bash
docker volume inspect "$(docker compose ps -q app | xargs -I{} docker inspect --format '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' {})" \
  --format '{{ .Mountpoint }}'
```

Или проще — по имени из `docker volume ls | grep app_data`.

---

## Схема ежедневного backup на VPS

Рекомендуемая схема для production-like стенда:

```
┌─────────────────────────────────────────────────────────────┐
│  VPS                                                        │
│  ┌──────────────┐    sqlite .backup     ┌─────────────────┐ │
│  │ app container│ ────────────────────► │ /var/backups/   │ │
│  │ /app/data/   │    (через python)     │ typical-infra/  │ │
│  │   app.db     │                       │  YYYY-MM-DD/    │ │
│  └──────────────┘                       └────────┬────────┘ │
│         ▲                                        │          │
│    volume app_data                               ▼          │
│                                          rsync/scp (опц.)   │
│                                          off-site копия     │
└─────────────────────────────────────────────────────────────┘
```

**Принципы:**

1. **Онлайн-backup** — через API SQLite `.backup()` (в образе есть Python + модуль `sqlite3`; отдельный `sqlite3` CLI не требуется). Копия согласована даже при работающем приложении.
2. **Каталог на хосте** — например `/var/backups/typical-infrastructure/` (создать заранее, права только для администратора).
3. **Именование** — `app-YYYY-MM-DD.db` или подкаталог `YYYY-MM-DD/app.db`.
4. **Ротация** — хранить последние 7 ежедневных копий; старше 30 дней удалять вручную или отдельным скриптом (не входит в этот документ).
5. **Off-site** — периодически копировать архив на другой сервер или object storage (S3, Backblaze и т.п.).
6. **Проверка** — после backup выполнять `PRAGMA integrity_check` (см. раздел «Проверка наличия backup»).

**Не использовать** простой `docker cp app:/app/data/app.db` как основной метод: при активной записи файл может оказаться в промежуточном состоянии. Метод `.backup()` безопаснее.

---

## Backup вручную

Выполнять из каталога проекта на VPS (где лежит `docker-compose.yml`).

### 1. Подготовить каталог на хосте

```bash
sudo mkdir -p /var/backups/typical-infrastructure
sudo chown "$USER:$USER" /var/backups/typical-infrastructure
BACKUP_DIR="/var/backups/typical-infrastructure"
DATE="$(date +%Y-%m-%d)"
mkdir -p "$BACKUP_DIR/$DATE"
```

### 2. Создать согласованную копию через Python в контейнере

```bash
docker compose exec -T app python - <<'PY'
import sqlite3
from pathlib import Path

src_path = Path("/app/data/app.db")
tmp_path = Path("/app/data/app.db.backup.tmp")

if not src_path.is_file():
    raise SystemExit(f"source not found: {src_path}")

src = sqlite3.connect(f"file:{src_path}?mode=ro", uri=True)
dst = sqlite3.connect(tmp_path)
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()

print(tmp_path)
PY
```

### 3. Скопировать файл на хост и удалить временный файл в контейнере

```bash
docker compose cp "app:/app/data/app.db.backup.tmp" "$BACKUP_DIR/$DATE/app.db"
docker compose exec app rm -f /app/data/app.db.backup.tmp

ls -lh "$BACKUP_DIR/$DATE/app.db"
```

### 4. (Опционально) сжать архив

```bash
gzip -k "$BACKUP_DIR/$DATE/app.db"
# получится app.db.gz рядом с app.db
```

---

## Restore вручную

**Внимание:** restore **перезаписывает** текущую базу. Перед операцией сделайте backup текущего состояния.

### 1. Остановить приложение

```bash
docker compose stop app
```

Остановка снимает блокировку SQLite с файла `app.db`.

### 2. Сохранить текущую БД (на всякий случай)

```bash
BACKUP_DIR="/var/backups/typical-infrastructure"
DATE="$(date +%Y-%m-%d-%H%M%S)"
mkdir -p "$BACKUP_DIR/pre-restore"
docker compose cp "app:/app/data/app.db" "$BACKUP_DIR/pre-restore/app-before-restore-$DATE.db" 2>/dev/null || true
```

### 3. Восстановить файл из backup

Подставьте путь к нужной копии, например `/var/backups/typical-infrastructure/2026-06-13/app.db`:

```bash
RESTORE_FILE="/var/backups/typical-infrastructure/2026-06-13/app.db"

# если backup сжат:
# gunzip -c "$RESTORE_FILE.gz" > /tmp/app.db.restore
# RESTORE_FILE=/tmp/app.db.restore

docker compose cp "$RESTORE_FILE" "app:/app/data/app.db"
```

### 4. Запустить приложение и проверить

```bash
docker compose start app
docker compose ps
curl -sf "http://127.0.0.1:${APP_PORT:-8100}/health/ready"
```

Ожидается HTTP 200. При ошибках — логи: `docker compose logs --tail=50 app`.

---

## Проверка наличия backup

### Список backup на хосте

```bash
BACKUP_DIR="/var/backups/typical-infrastructure"
find "$BACKUP_DIR" -type f \( -name 'app.db' -o -name 'app.db.gz' \) -printf '%T@ %p\n' | sort -n
```

Или по датам:

```bash
ls -la "$BACKUP_DIR"
```

### Проверка целостности SQLite в backup-файле

На хосте (нужен `sqlite3` CLI **на VPS**, не обязательно в контейнере):

```bash
BACKUP_FILE="/var/backups/typical-infrastructure/2026-06-13/app.db"
sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;"
# ожидается одна строка: ok
```

Если `sqlite3` на хосте нет — проверка через одноразовый контейнер:

```bash
docker run --rm -v "$BACKUP_FILE:/backup.db:ro" python:3.11-slim \
  python -c "import sqlite3; c=sqlite3.connect('/backup.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0])"
```

### Проверка, что backup не пустой

```bash
BACKUP_FILE="/var/backups/typical-infrastructure/2026-06-13/app.db"
test -s "$BACKUP_FILE" && echo "OK: file exists and non-empty" || echo "FAIL: missing or empty"
stat --format='%s bytes, modified %y' "$BACKUP_FILE"
```

Разумный минимальный размер для MVP с seed-данными — десятки килобайт и выше; нулевой размер означает сбой backup.

---

## Рекомендуемое расписание

| Параметр | Рекомендация |
|----------|--------------|
| Частота | **Ежедневно**, в окне минимальной нагрузки |
| Время | **03:00** по локальному времени VPS (после возможных ночных деплоев) |
| Хранение на VPS | 7 последних ежедневных копий |
| Off-site | 1 раз в неделю — копия на внешнее хранилище |
| Перед деплоем | Ручной backup (раздел «Backup вручную») |
| После restore | Smoke: `curl …/health/ready` и выборочная проверка API |

**Пример записи cron** (настраивает администратор; **не** добавляется репозиторием автоматически):

```cron
# /etc/cron.d/typical-infrastructure-backup
0 3 * * * root cd /path/to/typical_infrastructure && /usr/local/bin/backup-typical-infra.sh >> /var/log/typical-infra-backup.log 2>&1
```

Скрипт `backup-typical-infra.sh` должен повторять шаги из раздела «Backup вручную». Его размещение и права — на усмотрение администратора VPS.

**Альтернатива:** systemd timer с тем же скриптом — эквивалентно по смыслу, выбор между cron и timer не влияет на приложение.

---

## Чеклист перед production-like эксплуатацией

- [ ] Подтверждён путь `/app/data/app.db` в работающем контейнере
- [ ] Выполнен хотя бы один ручной backup и проверен `PRAGMA integrity_check`
- [ ] Выполнен тестовый restore на staging (или в отдельном volume) и проверен `/health/ready`
- [ ] Настроено расписание и ротация на VPS администратором
- [ ] Настроена off-site копия (желательно)
