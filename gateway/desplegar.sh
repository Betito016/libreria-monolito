#!/bin/bash
# Instala o actualiza el Library API Gateway en la instancia (ejecutar como root,
# desde la carpeta gateway/ copiada al servidor). Es idempotente.
#
#   sudo bash desplegar.sh
set -euo pipefail
cd "$(dirname "$0")"

echo "== configuración (/etc/library-gateway) y código de salud (/opt/library-gateway)"
install -d -m 755 /etc/library-gateway /opt/library-gateway/salud
install -m 644 config/gateway.env config/books-2.env /etc/library-gateway/
install -m 644 salud/salud_gateway.py /opt/library-gateway/salud/
restorecon -R /etc/library-gateway /opt/library-gateway

echo "== systemd: segunda instancia de libros (:6001) y salud agregada (:8090)"
install -m 644 systemd/library-books-2.service systemd/library-gateway-salud.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable -q library-books-2 library-gateway-salud
systemctl restart library-books-2 library-gateway-salud
sleep 4
for u in library-books library-books-2 library-gateway-salud; do printf '%-24s %s\n' "$u" "$(systemctl is-active $u)"; done

echo "== nginx: gateway (:8080), web + API (:80) y rutas comunes"
install -d -m 755 /etc/nginx/library-gateway
install -m 644 nginx/rutas-api.conf /etc/nginx/library-gateway/rutas-api.conf
install -m 644 nginx/library-gateway.conf /etc/nginx/conf.d/library-gateway.conf
install -m 644 nginx/library-web.conf /etc/nginx/conf.d/library-web.conf
# El antiguo servidor del puerto 80 (monolito en /library/) se guarda, no se borra.
if [ -f /etc/nginx/conf.d/libreria.conf ]; then
    install -d -m 700 /etc/nginx/respaldo
    mv /etc/nginx/conf.d/libreria.conf /etc/nginx/respaldo/libreria.conf.$(date +%Y%m%d%H%M)
    echo "libreria.conf movido a /etc/nginx/respaldo/"
fi
restorecon -R /etc/nginx/library-gateway /etc/nginx/conf.d
nginx -t
systemctl reload nginx

echo "== firewalld: puerto 8080"
firewall-cmd -q --permanent --add-port=8080/tcp
firewall-cmd -q --reload
firewall-cmd --list-ports
