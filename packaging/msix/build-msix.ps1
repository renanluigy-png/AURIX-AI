param(
    [string]$ExecutablePath = "dist\AURIX-AI.exe",
    [string]$OutputPath = "dist-msix\AURIX-AI.msix",
    [string]$Version = "0.4.0.0"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$identityName = $env:AURIX_MSIX_IDENTITY_NAME
$publisher = $env:AURIX_MSIX_PUBLISHER
$publisherDisplayName = $env:AURIX_MSIX_PUBLISHER_DISPLAY_NAME
$identityConfigured = -not [string]::IsNullOrWhiteSpace($identityName) -and -not [string]::IsNullOrWhiteSpace($publisher)

if ([string]::IsNullOrWhiteSpace($identityName)) { $identityName = "AURIXAI.PublisherIdentityRequired" }
if ([string]::IsNullOrWhiteSpace($publisher)) { $publisher = "CN=AURIX-PUBLISHER-IDENTITY-REQUIRED" }
if ([string]::IsNullOrWhiteSpace($publisherDisplayName)) { $publisherDisplayName = "Luigy Renan" }

if ($identityName -notmatch '^[A-Za-z0-9.-]{3,50}$') {
    throw "AURIX_MSIX_IDENTITY_NAME inválido. Use o Package/Identity Name reservado no Partner Center."
}
if ($publisher -notmatch '^CN=.+') {
    throw "AURIX_MSIX_PUBLISHER deve ser o Publisher completo do Partner Center, começando com CN=."
}
if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw "Versão MSIX inválida: $Version. Use quatro números, por exemplo 0.4.0.0."
}

$ExecutablePath = (Resolve-Path $ExecutablePath).Path
$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $OutputPath
$stage = Join-Path $env:RUNNER_TEMP "aurix-msix-stage"
$verify = Join-Path $env:RUNNER_TEMP "aurix-msix-verify"
$certificateFile = Join-Path $env:RUNNER_TEMP "aurix-msix-signing.pfx"
$certificatePasswordText = [Guid]::NewGuid().ToString("N")
$certificatePassword = ConvertTo-SecureString $certificatePasswordText -AsPlainText -Force
$certificate = $null

Remove-Item $stage, $verify -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage, $outputDirectory | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "Assets") | Out-Null
Copy-Item $ExecutablePath (Join-Path $stage "AURIX-AI.exe") -Force

$manifestTemplatePath = Join-Path $PSScriptRoot "AppxManifest.xml.template"
if (-not (Test-Path $manifestTemplatePath)) { throw "Template de manifesto não encontrado: $manifestTemplatePath" }
$manifestText = Get-Content $manifestTemplatePath -Raw -Encoding UTF8
$manifestText = $manifestText.Replace("__IDENTITY_NAME__", [System.Security.SecurityElement]::Escape($identityName))
$manifestText = $manifestText.Replace("__PUBLISHER__", [System.Security.SecurityElement]::Escape($publisher))
$manifestText = $manifestText.Replace("__PUBLISHER_DISPLAY_NAME__", [System.Security.SecurityElement]::Escape($publisherDisplayName))
$manifestText = $manifestText.Replace("__VERSION__", $Version)
[xml]$null = $manifestText
[System.IO.File]::WriteAllText((Join-Path $stage "AppxManifest.xml"), $manifestText, [System.Text.UTF8Encoding]::new($false))

python (Join-Path $PSScriptRoot "generate_assets.py") $stage
if ($LASTEXITCODE -ne 0) { throw "Não foi possível gerar os ícones do pacote MSIX." }

$windowsKits = Join-Path ${env:ProgramFiles(x86)} "Windows Kits\10\bin"
$makeAppx = Get-ChildItem -Path $windowsKits -Filter "MakeAppx.exe" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1
$signTool = Get-ChildItem -Path $windowsKits -Filter "SignTool.exe" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -match '\\x64\\SignTool\.exe$' } |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeAppx) { throw "MakeAppx.exe não foi encontrado no Windows SDK." }
if (-not $signTool) { throw "SignTool.exe não foi encontrado no Windows SDK." }

Remove-Item $OutputPath -Force -ErrorAction SilentlyContinue
& $makeAppx.FullName pack /d $stage /p $OutputPath /o
if ($LASTEXITCODE -ne 0) { throw "MakeAppx falhou ao criar o pacote MSIX." }

# A temporary self-signed certificate validates package signing only. It is NOT trusted by Windows.
# Microsoft Store replaces this signature after the package passes certification.
try {
    $certificate = New-SelfSignedCertificate -Type Custom -Subject $publisher -KeyAlgorithm RSA -KeyLength 3072 -HashAlgorithm SHA256 -KeyExportPolicy Exportable -CertStoreLocation "Cert:\CurrentUser\My" -NotAfter (Get-Date).AddDays(3) -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}")
    Export-PfxCertificate -Cert $certificate -FilePath $certificateFile -Password $certificatePassword | Out-Null
    & $signTool.FullName sign /fd SHA256 /f $certificateFile /p $certificatePasswordText $OutputPath
    if ($LASTEXITCODE -ne 0) { throw "SignTool falhou ao assinar o pacote de validação." }

    & $makeAppx.FullName unpack /p $OutputPath /d $verify
    if ($LASTEXITCODE -ne 0) { throw "MakeAppx não conseguiu validar/abrir o pacote MSIX." }
    if (-not (Test-Path (Join-Path $verify "AURIX-AI.exe"))) { throw "O executável não foi encontrado dentro do pacote MSIX." }
} finally {
    if ($certificate) { Remove-Item ("Cert:\CurrentUser\My\" + $certificate.Thumbprint) -Force -ErrorAction SilentlyContinue }
    Remove-Item $certificateFile -Force -ErrorAction SilentlyContinue
    Remove-Item $verify -Recurse -Force -ErrorAction SilentlyContinue
}

if ($identityConfigured) {
    Write-Host "MSIX criado com a identidade configurada no Partner Center: $identityName"
} else {
    Write-Warning "MSIX criado com identidade provisória. Configure AURIX_MSIX_IDENTITY_NAME e AURIX_MSIX_PUBLISHER no GitHub antes de enviar ao Partner Center."
}
Write-Host "Pacote MSIX: $OutputPath"
Get-FileHash $OutputPath -Algorithm SHA256 | Format-List
