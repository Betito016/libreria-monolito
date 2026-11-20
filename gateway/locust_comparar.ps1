# Locust: MISMO escenario de microservicios (locust_tests/locustfile.py, MicroserviciosUser)
# llamando DIRECTO a cada puerto y A TRAVÉS del gateway (:8080), uno después del otro
# (nunca a la vez: comparten la misma VM). Guarda CSV + HTML en evidencias\locust\.
#
#   .\locust_comparar.ps1                          # perfiles load y stress
#   .\locust_comparar.ps1 -Perfiles load,stress,spike
param(
    [string[]]$Perfiles = @('load', 'stress'),
    [string]$Ip = '34.135.84.31'
)
$ErrorActionPreference = 'Continue'
$locust = Resolve-Path "$PSScriptRoot\..\locust_tests"
$salida = "$PSScriptRoot\evidencias\locust"
New-Item -ItemType Directory -Force $salida | Out-Null
if (-not $env:LOCUST_EMAIL) { $env:LOCUST_EMAIL = Read-Host 'Correo del administrador' }
if (-not $env:LOCUST_PASSWORD) {
    $s = Read-Host 'Contrasena (no se muestra ni se guarda)' -AsSecureString
    $env:LOCUST_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
}

foreach ($perfil in $Perfiles) {
    foreach ($via in 'directo', 'gateway') {
        $nombre = "${perfil}_$via"
        $env:PERFIL = $perfil; $env:LOCUST_VIA = $via; $env:LOCUST_SISTEMA = $nombre
        Write-Host "== $nombre  inicio $(Get-Date -Format 'HH:mm:ss')"
        Push-Location $locust
        & .\venv\Scripts\locust -f locustfile.py --headless --host "http://$Ip" `
            --csv "$salida\$nombre" --csv-full-history --html "$salida\$nombre.html" `
            --only-summary --loglevel WARNING MicroserviciosUser 2>&1 | ForEach-Object { "$_" } |
            Set-Content -Encoding utf8 "$salida\consola_$nombre.txt"
        Pop-Location
        $agg = Import-Csv "$salida\${nombre}_stats.csv" | Where-Object Name -eq 'Aggregated'
        Write-Host ("   peticiones={0} fallas={1} p50={2} ms p95={3} ms rps={4}" -f $agg.'Request Count', $agg.'Failure Count', `
            $agg.'50%', $agg.'95%', [math]::Round([double]$agg.'Requests/s', 2))
        Start-Sleep -Seconds 20
    }
}
Remove-Item Env:LOCUST_VIA, Env:PERFIL, Env:LOCUST_SISTEMA -ErrorAction SilentlyContinue
