# Compila la app Java y genera libreria-java.jar (requiere JDK 17 o superior).
#
#   powershell -ExecutionPolicy Bypass -File compilar.ps1
#   java -jar libreria-java.jar
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$jdk = if ($env:JAVA_HOME) { $env:JAVA_HOME } else {
    Get-ChildItem 'C:\Program Files\Microsoft', 'C:\Program Files\Java', 'C:\Program Files\Eclipse Adoptium' -Directory -Filter 'jdk*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $jdk) { throw 'No se encontró un JDK. Instala uno: winget install Microsoft.OpenJDK.21' }
Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build | Out-Null
$fuentes = Get-ChildItem src -Recurse -Filter *.java | ForEach-Object FullName
& "$jdk\bin\javac.exe" -encoding UTF-8 -d build @fuentes
if ($LASTEXITCODE -ne 0) { throw 'Error de compilación' }
& "$jdk\bin\jar.exe" --create --file libreria-java.jar --main-class library.java.LibreriaJavaApp -C build .
Write-Host "Listo: $PSScriptRoot\libreria-java.jar  ->  `"$jdk\bin\java.exe`" -jar libreria-java.jar"
