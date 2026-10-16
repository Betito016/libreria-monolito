# Tunel SSH al Redis de la instancia GCP: 127.0.0.1:6379 (laptop) -> 127.0.0.1:6379 (instancia).
# Se reconecta solo si la red se cae. Ctrl+C para detenerlo.
#
#   powershell -ExecutionPolicy Bypass -File tools\dev_local\tunel_redis.ps1
$host.UI.RawUI.WindowTitle = 'TUNEL REDIS 6379 -> GCP'
while ($true) {
    Write-Host "$(Get-Date -Format HH:mm:ss) Abriendo tunel a Redis (instancia integracion)..."
    # --ssh-flag: PowerShell se come el separador "--" al llamar a gcloud.ps1
    gcloud compute ssh integracion --zone=us-central1-c --quiet --ssh-flag="-N" --ssh-flag="-L 6379:127.0.0.1:6379"
    Write-Host "$(Get-Date -Format HH:mm:ss) El tunel se cerro; reintento en 5 s." -ForegroundColor Yellow
    Start-Sleep -Seconds 5
}
