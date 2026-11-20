# Evidencias finales que requieren red hacia la instancia (correr desde una red que NO
# bloquee la IP, p. ej. compartiendo internet del celular):
#   1. Respuestas del gateway con curl         -> evidencias\respuestas_gateway_curl.txt
#   2. Pruebas funcionales en :80 y :8080      -> evidencias\pruebas_funcionales.txt
#   3. Pruebas de falla                        -> evidencias\pruebas_falla_<fecha>.txt
#   4. Capturas de la app Java                 -> evidencias\capturas_app_java\
#
#   $env:GATEWAY_EMAIL = 'admin@libreria.test'; $env:GATEWAY_PASSWORD = Read-Host 'Contraseña'
#   powershell -ExecutionPolicy Bypass -File gateway\completar_evidencias.ps1
$ErrorActionPreference = 'Continue'
Set-Location $PSScriptRoot
$py = Resolve-Path '..\locust_tests\venv\Scripts\python.exe'
$ev = "$PSScriptRoot\evidencias"

$prueba = curl.exe -s --max-time 15 http://34.135.84.31/health
if ($prueba -notmatch '"estado"') { throw 'La red actual no llega al gateway (¿filtro de la red escolar?). Cambia de red.' }

Write-Host '== 1. respuestas con curl'
$out = @("Respuestas del gateway obtenidas con curl $(Get-Date -Format s)", '')
foreach ($u in 'http://34.135.84.31/health', 'http://34.135.84.31/api/books/books?format=json&page_size=1',
               'http://34.135.84.31/api/autores/authors?format=json&page_size=1', 'http://34.135.84.31/api/users/users?format=json',
               'http://34.135.84.31/api/noexiste/x', 'http://34.135.84.31/library/login', 'http://34.135.84.31:8080/health') {
    $out += "==== GET $u"; $out += (curl.exe -s -i --max-time 15 $u | Select-Object -First 25); $out += ''
}
$out += '==== GET http://34.135.84.31/  (monolito, primeras líneas)'
$out += (curl.exe -s -i --max-time 15 http://34.135.84.31/ | Select-Object -First 12)
$out | Set-Content -Encoding utf8 "$ev\respuestas_gateway_curl.txt"

Write-Host '== 2. pruebas funcionales'
$res = foreach ($gw in 'http://34.135.84.31', 'http://34.135.84.31:8080') {
    $env:GATEWAY_URL = $gw
    "==== GATEWAY_URL=$gw"
    & $py -m pytest -v tests\test_gateway.py 2>&1 | Select-String 'PASSED|FAILED|passed|failed' |
        ForEach-Object { $_.Line -replace '^tests/test_gateway.py::', '' }
}
Remove-Item Env:GATEWAY_URL -ErrorAction SilentlyContinue
$res | Set-Content -Encoding utf8 "$ev\pruebas_funcionales.txt"; $res | Select-String 'passed|failed'

Write-Host '== 3. pruebas de falla'
powershell -NoProfile -ExecutionPolicy Bypass -File .\pruebas_falla.ps1 -Gw 'http://34.135.84.31' | Select-String '^====|^HTTP' | ForEach-Object { $_.Line.Substring(0, [Math]::Min(120, $_.Line.Length)) }

Write-Host '== 4. capturas de la app Java'
& $py C:\integracion\entrega\demo_gateway\capturas_java.py
