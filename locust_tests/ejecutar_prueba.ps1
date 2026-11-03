# Ejecuta UNA prueba de Locust (un perfil contra un sistema) sin interfaz y guarda
# las evidencias: CSV (--csv) y reporte HTML (--html) en evidencias\.
#
#   .\ejecutar_prueba.ps1 -Perfil load -Sistema monolito
#   .\ejecutar_prueba.ps1 -Perfil load -Sistema microservicios
#
# Perfiles: smoke, load, stress, spike, soak, quiebre (definidos en locustfile.py).
# Las credenciales se piden si no estan en LOCUST_EMAIL / LOCUST_PASSWORD y no se guardan.
#
# -Gui: en lugar de --headless abre la interfaz en http://localhost:8089, la prueba arranca
#       sola (--autostart) y Locust se cierra solo al terminar (--autoquit), escribiendo el
#       CSV y el HTML completos. Sirve para VER la prueba en vivo sin arriesgar las evidencias.
param(
    [Parameter(Mandatory)][ValidateSet('smoke', 'load', 'stress', 'spike', 'soak', 'quiebre', 'exploratoria100')][string]$Perfil,
    [Parameter(Mandatory)][ValidateSet('monolito', 'microservicios')][string]$Sistema,
    [string]$Ip = '34.135.84.31',
    [switch]$Gui
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not $env:LOCUST_EMAIL) { $env:LOCUST_EMAIL = Read-Host 'Correo del administrador' }
if (-not $env:LOCUST_PASSWORD) {
    $seguro = Read-Host 'Contrasena (no se muestra ni se guarda)' -AsSecureString
    $env:LOCUST_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
}

$clase = @{ monolito = 'MonolitoUser'; microservicios = 'MicroserviciosUser' }[$Sistema]
$nombre = "${Perfil}_$Sistema"
New-Item -ItemType Directory -Force evidencias | Out-Null
$env:PERFIL = $Perfil
$env:LOCUST_SISTEMA = $Sistema

Write-Host "== $nombre  ->  http://${Ip}  ($clase)  inicio $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
# Locust escribe su resumen en stderr: en PowerShell 5.1 eso no debe detener el script.
$ErrorActionPreference = 'Continue'
$modo = if ($Gui) { @('--autostart', '--autoquit', '10') } else { @('--headless', '--only-summary') }
if ($Gui) { Start-Process 'http://localhost:8089' }
& .\venv\Scripts\locust -f locustfile.py @modo --host "http://$Ip" `
    --csv "evidencias\$nombre" --csv-full-history --html "evidencias\$nombre.html" `
    --loglevel WARNING $clase 2>&1 | ForEach-Object { "$_" } |
    Tee-Object -FilePath "evidencias\consola_$nombre.txt"
$ErrorActionPreference = 'Stop'
Write-Host "== fin $(Get-Date -Format 'HH:mm:ss')  ->  evidencias\${nombre}_stats.csv, evidencias\$nombre.html"
