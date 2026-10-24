[CmdletBinding(SupportsShouldProcess=$true)]
param()
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
if (Test-Path -LiteralPath (Join-Path $repo 'bulletin_api.py')) {
    Write-Host 'Cette version inclut les voix hybrides : utilisation de la mise a jour complete pour garder les modules coherents.'
    & (Join-Path (Split-Path $repo -Parent) 'MAJ_BENDER.ps1') -Message 'Mise a jour voix hybrides Bender' -WhatIf:$WhatIfPreference
    return
}
$identity = Join-Path $env:USERPROFILE '.ssh\bender_deploy_ed25519'
$target = 'bender@192.168.1.41'
$files = @('media_api.py','bender_voice/config.py','bender_voice/service.py','bender_voice/references.py','static/media.js','templates/index.html','scripts/repair-reference-ui.sh')
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $file))) { throw "Fichier local manquant : $file" }
}
foreach ($program in @('tar','ssh','scp')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) { throw "Programme manquant : $program" }
}
if (-not $PSCmdlet.ShouldProcess($target, 'Sauvegarder et reparer le bouton et l API Chatterbox, puis verifier le serveur')) { return }
if (-not (Test-Path -LiteralPath $identity)) { throw 'Cle SSH Bender introuvable.' }
function Native([string]$Program,[string[]]$Arguments) {
    $previous = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Program @Arguments
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previous }
    if ($code -ne 0) { throw "$Program a echoue (code $code). Lire le message ci-dessus." }
}
$suffix = [guid]::NewGuid().ToString('N')
$archive = Join-Path (Split-Path $repo -Parent) ('.bender-reference-repair-' + $suffix + '.tar.gz')
$stage = '.bender-reference-repair-' + $suffix
$options = @('-F','NUL','-i',$identity,'-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes')
try {
    Native tar (@('-czf',$archive,'-C',$repo) + $files)
    Native ssh ($options + @($target,"mkdir -m 700 ~/$stage"))
    Native scp ($options + @($archive,"${target}:$stage/payload.tar.gz"))
    # A single interactive sudo session; keep stdin attached to the console.
    $command = "tar -xzf ~/$stage/payload.tar.gz -C ~/$stage && bash ~/$stage/scripts/repair-reference-ui.sh"
    Native ssh ($options + @('-t',$target,$command))
    Write-Host 'Reparation terminee et verifiee : http://192.168.1.41:8000/?v=reference-repair#samples'
} finally {
    if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
}
