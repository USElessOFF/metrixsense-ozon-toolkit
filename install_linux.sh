#!/usr/bin/env bash
# =============================================================
#  MetrixSense — Linux installer (Docker)
#
#  One-liner:
#    curl -fsSL https://raw.githubusercontent.com/USElessOFF/metrixsense-ozon-toolkit/main/install_linux.sh | bash
#
#  Known issues / troubleshooting:
#   - Docker daemon permission denied -> log out/in (docker group) or use sudo
#   - First build downloads ~1 GB and takes 5-10 minutes
#   - Ports 8000/8080 busy -> stop the other app or edit docker-compose.yml
# =============================================================
set -euo pipefail

REPO_ZIP_URL="${REPO_ZIP_URL:-https://github.com/USElessOFF/metrixsense-ozon-toolkit/archive/refs/heads/main.zip}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/metrixsense}"

Cyan='\033[0;36m'; Green='\033[0;32m'; Yellow='\033[0;33m'; Red='\033[0;31m'; NC='\033[0m'
step() { echo -e "${Cyan}==> $1${NC}"; }
ok()   { echo -e "    ${Green}[OK] $1${NC}"; }
warn() { echo -e "    ${Yellow}[!] $1${NC}"; }
die()  { echo -e "    ${Red}[X] $1${NC}"; exit 1; }

echo "============================================="
echo "  MetrixSense — установка (Linux, Docker)"
echo "============================================="

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; else warn "sudo не найден — команды Docker выполнятся от текущего пользователя"; fi
fi

# --- 1. Docker ---------------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  step "Docker не найден — устанавливаю (get.docker.com)..."
  curl -fsSL https://get.docker.com | $SUDO sh
  if [ -n "$SUDO" ]; then
    $SUDO usermod -aG docker "$USER" 2>/dev/null || true
    warn "Пользователь добавлен в группу docker. Перелогиньтесь, чтобы права применились."
  fi
fi
docker info >/dev/null 2>&1 || warn "Docker daemon недоступен: 'permission denied'? Перелогиньтесь или используйте sudo."

# --- 2. Docker Compose -------------------------------------------------------
if docker compose version >/dev/null 2>&1; then
  COMPOSE="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE="docker-compose"
else
  step "Устанавливаю Docker Compose v2 (плагин)..."
  mkdir -p ~/.docker/cli-plugins
  curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
    -o ~/.docker/cli-plugins/docker-compose
  chmod +x ~/.docker/cli-plugins/docker-compose
  COMPOSE="docker compose"
fi
ok "Compose: $COMPOSE"

# --- 3. Проект ---------------------------------------------------------------
if [ ! -f "$INSTALL_DIR/backend/requirements.txt" ]; then
  step "Скачиваю проект..."
  TMP="$(mktemp -d)"
  curl -fsSL "$REPO_ZIP_URL" -o "$TMP/repo.zip"
  if command -v unzip >/dev/null 2>&1; then
    unzip -q "$TMP/repo.zip" -d "$TMP/x"
  else
    warn "unzip не найден — распаковываю через python3"
    python3 -m zipfile -e "$TMP/repo.zip" "$TMP/x"
  fi
  rm -rf "$INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"
  cp -a "$TMP"/x/*/. "$INSTALL_DIR/"
  rm -rf "$TMP"
else
  warn "$INSTALL_DIR уже содержит проект — использую его (удалите папку для чистой установки)"
fi
cd "$INSTALL_DIR"
mkdir -p backend/data backend/files backend/logs
ok "Проект: $INSTALL_DIR"

# --- 4. Запуск ---------------------------------------------------------------
step "Собираю и запускаю контейнеры (первая сборка 5–10 минут)..."
$SUDO $COMPOSE up -d --build

step "Ожидаю готовность backend (/health)..."
READY=0
for i in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then READY=1; break; fi
  sleep 2
done
if [ "$READY" -eq 1 ]; then ok "Backend готов"; else warn "Backend ещё поднимается — логи: $SUDO $COMPOSE logs -f"; fi

(command -v xdg-open >/dev/null 2>&1 && xdg-open http://localhost:8080 >/dev/null 2>&1) || true

echo ""
echo -e "${Green}=== Установка завершена! ===${NC}"
echo -e "Веб-интерфейс:    ${Green}http://localhost:8080${NC}"
echo -e "API-документация: http://localhost:8080/docs"
echo -e "Данные:           $INSTALL_DIR/backend/data"
echo -e "Логи:             $SUDO $COMPOSE logs -f"
echo ""
echo -e "${Yellow}Возможные проблемы:${NC}"
echo " - permission denied у Docker -> перелогиньтесь (группа docker) или используйте sudo"
echo " - порты 8000/8080 заняты     -> освободите их или измените в docker-compose.yml"
echo " - пароль по умолчанию публичный -> смените DEFAULT_PASSWORD в backend/.env"
