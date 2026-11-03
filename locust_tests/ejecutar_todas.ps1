# Corre las 12 pruebas (6 perfiles x 2 sistemas) en secuencia, alternando sistemas,
# con una pausa de 30 s entre corridas para que la instancia se estabilice.
# Por cada corrida guarda, ademas del CSV y el HTML de Locust:
#   evidencias\red_<perfil>_<sistema>.txt     latencia base de la red (5 x GET /health) antes de la prueba
#   evidencias\vmstat_<perfil>_<sistema>.txt  CPU/memoria de la instancia cada 5 s durante la prueba
#
#   .\ejecutar_todas.ps1                      (pide las credenciales si no estan en el entorno)
#   .\ejecutar_todas.ps1 -Perfiles load,spike (solo algunos perfiles)
param(
    [string[]]$Perfiles = @('smoke', 'load', 'stress', 'spike', 'soak', 'quiebre'),
    [string[]]$Sistemas = @('monolito', 'microservicios'),
    [string]$Ip = '34.135.84.31',
    [string]$Zona = 'us-central1-c'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$duracion = @{ smoke = 30; load = 120; stress = 180; spike = 120; soak = 240; quiebre = 240; exploratoria100 = 280 }
$puertoSalud = @{ monolito = 3000; microservicios = 5001 }
$rutaSalud = @{ monolito = '/'; microservicios = '/health?format=json' }
New-Item -ItemType Directory -Force evidencias | Out-Null

foreach ($perfil in $Perfiles) {
    foreach ($sistema in $Sistemas) {
        $nombre = "${perfil}_$sistema"
        # 1) Latencia base de la red hacia la instancia (sin carga).
        $url = "http://${Ip}:$($puertoSalud[$sistema])$($rutaSalud[$sistema])"
        $red = 1..5 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code} %{time_total}\n" --max-time 20 $url }
        "Latencia base sin carga (codigo HTTP, segundos) $(Get-Date -Format s) -> $url`n$($red -join "`n")" |
            Set-Content -Encoding utf8 "evidencias\red_$nombre.txt"

        # 2) vmstat en la instancia durante la prueba (en segundo plano).
        $muestras = [int]($duracion[$perfil] / 5) + 6
        $vm = Start-Job -ScriptBlock {
            param($zona, $n)
            gcloud compute ssh integracion --zone=$zona --quiet --command="vmstat -t 5 $n" 2>&1
        } -ArgumentList $Zona, $muestras

        # 3) La prueba.
        & "$PSScriptRoot\ejecutar_prueba.ps1" -Perfil $perfil -Sistema $sistema -Ip $Ip

        Wait-Job $vm -Timeout 120 | Out-Null
        Receive-Job $vm | Set-Content -Encoding utf8 "evidencias\vmstat_$nombre.txt"
        Remove-Job $vm -Force
        Start-Sleep -Seconds 30
    }
}
Write-Host "Listo: evidencias en $PSScriptRoot\evidencias"
