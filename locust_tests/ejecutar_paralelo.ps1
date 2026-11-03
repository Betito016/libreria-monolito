# Corre cada perfil contra el monolito y contra los microservicios AL MISMO TIEMPO
# (dos procesos de Locust), para reducir el tiempo total. Ambos sistemas comparten la
# misma VM durante la prueba: la condicion es igual para los dos y el vmstat de la
# instancia (uno por perfil) muestra si la CPU se saturo. Ver RESULTADOS.md.
#
#   .\ejecutar_paralelo.ps1 -Perfiles stress,spike,soak,quiebre
param(
    [string[]]$Perfiles = @('stress', 'spike', 'soak', 'quiebre'),
    [string]$Ip = '34.135.84.31',
    [string]$Zona = 'us-central1-c'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$duracion = @{ smoke = 30; load = 120; stress = 90; spike = 120; soak = 240; quiebre = 140; exploratoria100 = 280 }
New-Item -ItemType Directory -Force evidencias | Out-Null

foreach ($perfil in $Perfiles) {
    # 1) Latencia base de la red (sin carga) hacia cada sistema.
    foreach ($par in @(@('monolito', "http://${Ip}:3000/"), @('microservicios', "http://${Ip}:5001/health?format=json"))) {
        $red = 1..5 | ForEach-Object { curl.exe -s -o NUL -w "%{http_code} %{time_total}\n" --max-time 20 $par[1] }
        "Latencia base sin carga (codigo HTTP, segundos) $(Get-Date -Format s) -> $($par[1])`n$($red -join "`n")" |
            Set-Content -Encoding utf8 "evidencias\red_${perfil}_$($par[0]).txt"
    }
    # 2) vmstat de la instancia durante el perfil (cubre a los dos sistemas).
    $n = [int]($duracion[$perfil] / 5) + 6
    $vm = Start-Job { param($z, $n) gcloud compute ssh integracion --zone=$z --quiet --command="vmstat -t 5 $n" 2>&1 } -ArgumentList $Zona, $n
    # 3) Las dos pruebas en paralelo.
    Write-Host "== $perfil (monolito + microservicios en paralelo) inicio $(Get-Date -Format 'HH:mm:ss')"
    $pruebas = foreach ($sistema in 'monolito', 'microservicios') {
        Start-Job -ScriptBlock { param($dir, $p, $s, $ip) Set-Location $dir; & .\ejecutar_prueba.ps1 -Perfil $p -Sistema $s -Ip $ip *>&1 | Out-Null } `
            -ArgumentList $PSScriptRoot, $perfil, $sistema, $Ip
    }
    $pruebas | Wait-Job | Out-Null
    $pruebas | Remove-Job -Force
    foreach ($sistema in 'monolito', 'microservicios') {
        $agg = Import-Csv "evidencias\${perfil}_${sistema}_stats.csv" | Where-Object Name -eq 'Aggregated'
        Write-Host ("   {0,-15} peticiones={1} fallas={2} p95={3} ms rps={4}" -f $sistema, $agg.'Request Count', $agg.'Failure Count', $agg.'95%', [math]::Round([double]$agg.'Requests/s', 2))
    }
    Wait-Job $vm -Timeout 120 | Out-Null
    $salida = Receive-Job $vm
    foreach ($sistema in 'monolito', 'microservicios') {
        @("vmstat de la instancia durante $perfil (monolito y microservicios corriendo en paralelo)") + $salida |
            Set-Content -Encoding utf8 "evidencias\vmstat_${perfil}_$sistema.txt"
    }
    Remove-Job $vm -Force
    Start-Sleep -Seconds 15
}
Write-Host "Listo $(Get-Date -Format 'HH:mm:ss')"
