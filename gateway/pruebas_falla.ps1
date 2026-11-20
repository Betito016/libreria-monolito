# Pruebas de balanceo y de falla del Library API Gateway (RF3, RF4, RF5, RF6).
# Provoca fallas REALES en la instancia (detiene servicios con systemctl, congela un
# proceso con SIGSTOP) y SIEMPRE los restaura al final. Guarda la salida en
# evidencias\pruebas_falla_<fecha>.txt.
#
#   .\pruebas_falla.ps1                         (requiere gcloud con acceso a la instancia)
param(
    [string]$Gw = 'http://34.135.84.31:8080',
    [string]$Zona = 'us-central1-c'
)
$ErrorActionPreference = 'Continue'
New-Item -ItemType Directory -Force "$PSScriptRoot\evidencias" | Out-Null
$salida = "$PSScriptRoot\evidencias\pruebas_falla_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"
Start-Transcript -Path $salida | Out-Null

function Remoto([string]$cmd) { gcloud compute ssh integracion --zone=$Zona --quiet --command="$cmd" 2>&1 | Out-Null }
function Pedir([string]$ruta) {
    # Devuelve "HTTP <codigo> instancia=<upstream> rid=<request id> <cuerpo corto>"
    $h = "$env:TEMP\gw_h.txt"; $b = "$env:TEMP\gw_b.txt"
    $codigo = curl.exe -s -D $h -o $b -w "%{http_code}" --max-time 30 "$Gw$ruta"
    $cab = Get-Content $h -ErrorAction SilentlyContinue
    $inst = $cab | Select-String '^X-Gateway-Instancia:\s*(.*)$' | ForEach-Object { $_.Matches[0].Groups[1].Value }
    $rid = $cab | Select-String '^X-Request-ID:\s*(.*)$' | ForEach-Object { $_.Matches[0].Groups[1].Value }
    if (-not $inst) { $inst = '(gateway)' }
    $cuerpo = (Get-Content $b -Raw -ErrorAction SilentlyContinue) -replace '\s+', ' '
    "HTTP $codigo instancia=$inst rid=$rid  $($cuerpo.Substring(0, [Math]::Min(170, $cuerpo.Length)))"
}
function Titulo([string]$t) { Write-Host "`n==== $t ====" }

try {
    Titulo '1. Round robin: 6 peticiones seguidas al catálogo (books :5001 y :6001)'
    1..6 | ForEach-Object { Pedir '/api/books/books?format=json&page_size=1' }

    Titulo '2. Salud agregada con todo arriba'
    Pedir '/health'

    Titulo '3. Instancia :5001 caída (systemctl stop library-books): el catálogo sigue respondiendo'
    Remoto 'sudo systemctl stop library-books'
    1..4 | ForEach-Object { Pedir '/api/books/books?format=json&page_size=1' }
    Pedir '/health'
    Remoto 'sudo systemctl start library-books'

    Titulo '4. Servicio pagos caído (una sola instancia): 503 JSON con request_id'
    Remoto 'sudo systemctl stop library-pagos'
    Pedir '/api/pagos/health?format=json'
    Remoto 'sudo systemctl start library-pagos'

    Titulo '5. Timeout: proceso de pagos congelado (SIGSTOP), el gateway corta a los 10 s con 504'
    Remoto 'sudo systemctl kill -s SIGSTOP library-pagos'
    $t = Measure-Command { $r = Pedir '/api/pagos/health?format=json' }
    "$r  (tardó $([math]::Round($t.TotalSeconds, 1)) s)"
    Remoto 'sudo systemctl kill -s SIGCONT library-pagos'

    Titulo '6. Ruta inexistente: 404 JSON del gateway'
    Pedir '/api/inexistente/algo'

    Titulo '7. Recuperación: todo arriba otra vez'
    Start-Sleep -Seconds 5
    Pedir '/health'
}
finally {
    # Pase lo que pase, dejar los servicios como estaban.
    Remoto 'sudo systemctl kill -s SIGCONT library-pagos; sudo systemctl start library-books library-pagos'
    Stop-Transcript | Out-Null
    Write-Host "Evidencia: $salida"
}
