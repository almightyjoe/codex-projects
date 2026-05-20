#!/usr/bin/env bash
set -euo pipefail

APP_NAME="JJOES PRIVATES NETWORK"
WG_INTERFACE="jjpn0"
WG_DIR="/etc/wireguard"
CLIENT_DIR="${WG_DIR}/jjpn-clients"
SERVER_ADDRESS="10.44.0.1/24"
CLIENT_DNS="1.1.1.1, 9.9.9.9"
PORT="51820"
ENDPOINT=""
CLIENT_NAME="iphone"
ROUTE_ALL_TRAFFIC="true"

usage() {
  cat <<USAGE
${APP_NAME} Raspberry Pi installer

Usage:
  sudo ./install-server.sh --endpoint vpn.example.com [options]

Options:
  --endpoint VALUE       Public DNS name or IP clients use to reach this Pi.
  --port VALUE           WireGuard UDP port. Default: ${PORT}
  --client-name VALUE    First client profile name. Default: ${CLIENT_NAME}
  --split-tunnel         Only route VPN subnet traffic through the tunnel.
  --help                 Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="${2:-}"
      shift 2
      ;;
    --port)
      PORT="${2:-}"
      shift 2
      ;;
    --client-name)
      CLIENT_NAME="${2:-}"
      shift 2
      ;;
    --split-tunnel)
      ROUTE_ALL_TRAFFIC="false"
      shift
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

if [[ -z "${ENDPOINT}" ]]; then
  ENDPOINT="$(curl -fsS https://api.ipify.org || true)"
fi

if [[ -z "${ENDPOINT}" ]]; then
  echo "Could not determine public endpoint. Re-run with --endpoint vpn.example.com" >&2
  exit 1
fi

umask 077

echo "Installing ${APP_NAME} server dependencies..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y wireguard wireguard-tools qrencode iptables iptables-persistent curl

mkdir -p "${WG_DIR}" "${CLIENT_DIR}"
chmod 700 "${WG_DIR}" "${CLIENT_DIR}"

WAN_INTERFACE="$(ip route list default | awk '{print $5; exit}')"
if [[ -z "${WAN_INTERFACE}" ]]; then
  echo "Could not detect default network interface." >&2
  exit 1
fi

SERVER_PRIVATE_KEY_FILE="${WG_DIR}/${WG_INTERFACE}.server.key"
SERVER_PUBLIC_KEY_FILE="${WG_DIR}/${WG_INTERFACE}.server.pub"

if [[ ! -f "${SERVER_PRIVATE_KEY_FILE}" ]]; then
  wg genkey | tee "${SERVER_PRIVATE_KEY_FILE}" | wg pubkey > "${SERVER_PUBLIC_KEY_FILE}"
fi

SERVER_PRIVATE_KEY="$(cat "${SERVER_PRIVATE_KEY_FILE}")"
SERVER_PUBLIC_KEY="$(cat "${SERVER_PUBLIC_KEY_FILE}")"

cat > "/etc/sysctl.d/99-jjpn.conf" <<SYSCTL
net.ipv4.ip_forward=1
SYSCTL
sysctl --system >/dev/null

cat > "${WG_DIR}/${WG_INTERFACE}.conf" <<WGCONF
[Interface]
Address = ${SERVER_ADDRESS}
ListenPort = ${PORT}
PrivateKey = ${SERVER_PRIVATE_KEY}
PostUp = iptables -A FORWARD -i ${WG_INTERFACE} -j ACCEPT; iptables -A FORWARD -o ${WG_INTERFACE} -j ACCEPT; iptables -t nat -A POSTROUTING -o ${WAN_INTERFACE} -j MASQUERADE
PostDown = iptables -D FORWARD -i ${WG_INTERFACE} -j ACCEPT; iptables -D FORWARD -o ${WG_INTERFACE} -j ACCEPT; iptables -t nat -D POSTROUTING -o ${WAN_INTERFACE} -j MASQUERADE
WGCONF

chmod 600 "${WG_DIR}/${WG_INTERFACE}.conf"

cat > /usr/local/sbin/jjpn-add-client <<'HELPER'
#!/usr/bin/env bash
set -euo pipefail

WG_INTERFACE="jjpn0"
WG_DIR="/etc/wireguard"
CLIENT_DIR="${WG_DIR}/jjpn-clients"
SERVER_PUBLIC_KEY_FILE="${WG_DIR}/${WG_INTERFACE}.server.pub"
PORT="${JJPN_PORT:-51820}"
ENDPOINT="${JJPN_ENDPOINT:-}"
CLIENT_DNS="${JJPN_DNS:-1.1.1.1, 9.9.9.9}"
ROUTE_ALL_TRAFFIC="${JJPN_ROUTE_ALL_TRAFFIC:-true}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run with sudo." >&2
  exit 1
fi

CLIENT_NAME="${1:-}"
if [[ -z "${CLIENT_NAME}" ]]; then
  echo "Usage: sudo JJPN_ENDPOINT=vpn.example.com jjpn-add-client device-name" >&2
  exit 1
fi

if [[ -z "${ENDPOINT}" ]]; then
  ENDPOINT="$(curl -fsS https://api.ipify.org || true)"
fi

mkdir -p "${CLIENT_DIR}"
chmod 700 "${CLIENT_DIR}"

NEXT_HOST="$(grep -h '^AllowedIPs = 10\.44\.0\.' "${WG_DIR}/${WG_INTERFACE}.conf" 2>/dev/null | sed -E 's/.*10\.44\.0\.([0-9]+).*/\1/' | sort -n | tail -1)"
if [[ -z "${NEXT_HOST}" ]]; then
  NEXT_HOST=2
else
  NEXT_HOST=$((NEXT_HOST + 1))
fi

if [[ "${NEXT_HOST}" -gt 254 ]]; then
  echo "No available client addresses remain in 10.44.0.0/24." >&2
  exit 1
fi

CLIENT_ADDRESS="10.44.0.${NEXT_HOST}/32"
CLIENT_PRIVATE_KEY="$(wg genkey)"
CLIENT_PUBLIC_KEY="$(printf '%s' "${CLIENT_PRIVATE_KEY}" | wg pubkey)"
SERVER_PUBLIC_KEY="$(cat "${SERVER_PUBLIC_KEY_FILE}")"
ALLOWED_IPS="0.0.0.0/0, ::/0"

if [[ "${ROUTE_ALL_TRAFFIC}" != "true" ]]; then
  ALLOWED_IPS="10.44.0.0/24"
fi

CLIENT_FILE="${CLIENT_DIR}/${CLIENT_NAME}.conf"

cat > "${CLIENT_FILE}" <<CLIENTCONF
[Interface]
PrivateKey = ${CLIENT_PRIVATE_KEY}
Address = ${CLIENT_ADDRESS}
DNS = ${CLIENT_DNS}

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
Endpoint = ${ENDPOINT}:${PORT}
AllowedIPs = ${ALLOWED_IPS}
PersistentKeepalive = 25
CLIENTCONF

cat >> "${WG_DIR}/${WG_INTERFACE}.conf" <<PEER

# ${CLIENT_NAME}
[Peer]
PublicKey = ${CLIENT_PUBLIC_KEY}
AllowedIPs = ${CLIENT_ADDRESS}
PEER

chmod 600 "${CLIENT_FILE}" "${WG_DIR}/${WG_INTERFACE}.conf"
systemctl restart "wg-quick@${WG_INTERFACE}"

echo "Created ${CLIENT_FILE}"
echo
qrencode -t ansiutf8 < "${CLIENT_FILE}" || true
HELPER

chmod 700 /usr/local/sbin/jjpn-add-client

systemctl enable "wg-quick@${WG_INTERFACE}"
systemctl restart "wg-quick@${WG_INTERFACE}"

JJPN_ENDPOINT="${ENDPOINT}" JJPN_PORT="${PORT}" JJPN_DNS="${CLIENT_DNS}" JJPN_ROUTE_ALL_TRAFFIC="${ROUTE_ALL_TRAFFIC}" \
  /usr/local/sbin/jjpn-add-client "${CLIENT_NAME}"

cat <<DONE

${APP_NAME} server is running.

Server public key:
  ${SERVER_PUBLIC_KEY}

Client profiles:
  ${CLIENT_DIR}

Add another device:
  sudo JJPN_ENDPOINT=${ENDPOINT} JJPN_PORT=${PORT} jjpn-add-client device-name

Router/firewall reminder:
  Forward UDP ${PORT} from your router to this Raspberry Pi.
DONE

