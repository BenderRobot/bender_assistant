[CmdletBinding()]
param(
    [string]$RemoteHost = '192.168.1.41',
    [string]$RemoteUser = 'bender',
    [string]$RemoteDirectory = 'applications/bender_assistant',
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\bender_deploy_ed25519",
    [ValidateRange(1024,65535)][int]$Port = 1455,
    [switch]$NewAccount
)
$ErrorActionPreference = 'Stop'
if ($RemoteHost -notmatch '^[a-zA-Z0-9.-]+$' -or $RemoteUser -notmatch '^[a-z_][a-z0-9_-]*$' -or
    $RemoteDirectory -notmatch '^[a-zA-Z0-9_/-]+$' -or $RemoteDirectory.Contains('..') -or $RemoteDirectory.StartsWith('/')) {
    throw 'Adresse ou chemin distant invalide.'
}
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) { throw 'OpenSSH Windows est requis.' }
if (-not (Test-Path -LiteralPath $IdentityFile)) { throw 'Cle SSH absente. Executer MAJ_BENDER.ps1 -SetupSsh une fois.' }
$target = "$RemoteUser@$RemoteHost"
$forward = "127.0.0.1:${Port}:127.0.0.1:${Port}"
$command = "cd ~/$RemoteDirectory && .venv/bin/python -m bender_brain login --no-browser --port $Port"
if ($NewAccount) { $command += ' --new-account' }
Write-Host 'Connexion officielle de Bender a ton compte ChatGPT.'
Write-Host 'Garde ce terminal ouvert, puis ouvre le lien HTTPS affiche et autorise Bender Jarvis.'
Write-Host 'La connexion revient sur 127.0.0.1 par le tunnel SSH. Ne change pas cette adresse.'
Write-Host 'Si le port est occupe, relance ce script avec -Port 1456.'
$previousPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & ssh -F NUL -i $IdentityFile -o IdentitiesOnly=yes -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -t -L $forward $target $command
    $result = $LASTEXITCODE
} finally { $ErrorActionPreference = $previousPreference }
if ($result -ne 0) { throw "Connexion interrompue (code $result). Verifier la mise a jour du Debian, le port et les messages ci-dessus." }
Write-Host 'Retourne dans Cerveau GPT, puis Actualiser le statut. Tu peux tester une reponse texte.'
