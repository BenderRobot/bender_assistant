[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [string]$RepoPath = "$env:USERPROFILE\Documents\Bender\bender_assistant",
    [string]$RemoteHost = '192.168.1.41',
    [string]$RemoteUser = 'bender',
    [string]$RemoteDirectory = 'applications/bender_assistant',
    [string]$Message = ('Mise a jour Bender ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')),
    [switch]$PublishOnly,
    [switch]$SetupSsh,
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\bender_deploy_ed25519"
)
$ErrorActionPreference = 'Stop'
function Run([string]$Program, [string[]]$Arguments) {
    # Windows PowerShell wraps native stderr in ErrorRecord objects, even for
    # successful Git progress messages and unittest output. Use the exit code.
    $previousPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        if ($Program -in @('ssh','scp','ssh-keygen')) {
            # Keep OpenSSH attached to the console for password/sudo prompts.
            & $Program @Arguments
        } else {
            & $Program @Arguments 2>&1 | ForEach-Object { Write-Host "$_" }
        }
        $nativeExitCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $previousPreference }
    if ($nativeExitCode -ne 0) { throw "$Program a echoue (code $nativeExitCode)." }
}
foreach ($program in @('git','ssh','scp')) {
    if (-not (Get-Command $program -ErrorAction SilentlyContinue)) { throw "Installer $program avant de continuer." }
}
if ($RemoteHost -notmatch '^[a-zA-Z0-9.-]+$' -or $RemoteUser -notmatch '^[a-z_][a-z0-9_-]*$' -or
    $RemoteDirectory -notmatch '^[a-zA-Z0-9_/-]+$' -or $RemoteDirectory.Contains('..') -or $RemoteDirectory.StartsWith('/')) {
    throw 'Adresse ou chemin distant invalide : utiliser un chemin relatif au dossier personnel.'
}
if (-not $PSCmdlet.ShouldProcess("$RepoPath -> GitHub -> $RemoteUser@$RemoteHost", 'Tester, commit, push et deployer Bender')) { return }
$target = "$RemoteUser@$RemoteHost"
if ($SetupSsh) {
    if (-not (Test-Path -LiteralPath $IdentityFile)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $IdentityFile) | Out-Null
        Write-Host 'Creation de la cle : choisir une phrase secrete (avec ssh-agent), ou Entree deux fois pour une cle sans phrase secrete.'
        Run ssh-keygen @('-t','ed25519','-f',$IdentityFile,'-C','bender-update')
    }
    if (-not (Test-Path -LiteralPath "$IdentityFile.pub")) { throw 'Cle publique .pub manquante.' }
    $publicKey = (Get-Content -LiteralPath "$IdentityFile.pub" -Raw).Trim()
    if ($publicKey -notmatch '^ssh-ed25519 [A-Za-z0-9+/=]+(?: [a-zA-Z0-9@._-]+)?$') { throw 'Format de cle publique inattendu.' }
    $installKey = "umask 077; mkdir -p ~/.ssh; chmod 700 ~/.ssh; touch ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys; grep -qxF '$publicKey' ~/.ssh/authorized_keys || printf '%s\n' '$publicKey' >> ~/.ssh/authorized_keys"
    Run ssh @('-F','NUL',$target,$installKey)
    Run ssh @('-F','NUL','-i',$IdentityFile,'-o','IdentitiesOnly=yes','-o','BatchMode=yes',$target,'true')
    Write-Host 'Cle installee et connexion sans mot de passe verifiee. Relancer sans -SetupSsh pour deployer.'
    return
}
$sshOptions = @('-F','NUL')
if (-not $PublishOnly) {
    if (-not (Test-Path -LiteralPath $IdentityFile)) { throw 'Executer une fois ce script avec -SetupSsh avant de deployer.' }
    $sshOptions += @('-i',$IdentityFile,'-o','IdentitiesOnly=yes','-o','BatchMode=yes')
    Run ssh ($sshOptions + @($target,'true'))
}
if (-not (Test-Path -LiteralPath $RepoPath)) {
    New-Item -ItemType Directory -Force -Path (Split-Path $RepoPath) | Out-Null
    Run git @('-c','http.sslBackend=openssl','clone','https://github.com/BenderRobot/bender_assistant.git',$RepoPath)
}
$RepoPath = (Resolve-Path -LiteralPath $RepoPath).Path
Push-Location $RepoPath
try {
    $origin = (& git remote get-url origin)
    if ($LASTEXITCODE -ne 0 -or $origin -notmatch 'github.com[:/]BenderRobot/bender_assistant(?:\.git)?$') { throw 'Le depot origin ne correspond pas a BenderRobot/bender_assistant.' }
    $branch = (& git branch --show-current)
    if ($branch -ne 'main') { throw 'Se placer sur main avant la publication.' }
    Run git @('-c','http.sslBackend=openssl','fetch','origin','main')
    & git merge-base --is-ancestor origin/main HEAD
    if ($LASTEXITCODE -ne 0) { throw 'GitHub contient des changements absents ici. Integrer origin/main avant de relancer ; aucun ecrasement automatique.' }
    foreach ($private in @('.env','bender_memory.db','voice.json')) {
        $trackedPrivate = @(& git ls-files -- $private)
        if ($LASTEXITCODE -ne 0) { throw 'Impossible de verifier les fichiers prives suivis par Git.' }
        if ($trackedPrivate.Count -gt 0) { Run git @('rm','--cached','--',$private) }
    }
    Run git @('add','--all','--','.')
    $files = @(& git ls-files)
    foreach ($file in $files) {
        if ($file -match '(^|/)(data|models|\.venv[^/]*|\.ssh)(/|$)|(^|/)(\.env|voice\.json|id_rsa|id_ed25519)$|\.(db|sqlite3?|wav|mp3|mp4|pem|key)$') {
            throw "Fichier prive interdit dans Git : $file. Retirer ce fichier du suivi avant de relancer."
        }
        if ($file -eq '.env.example' -and (Select-String -Path $file -Pattern '^\s*\w*(KEY|TOKEN|PASSWORD|SECRET)\w*\s*=\s*\S+' -Quiet)) {
            throw '.env.example contient une valeur sensible : vider les valeurs avant publication.'
        }
    }
    $python = if (Test-Path '.venv\Scripts\python.exe') { '.venv\Scripts\python.exe' } else { 'python' }
    Run $python @('-m','unittest','discover','-s','tests','-v')
    & git diff --cached --quiet
    if ($LASTEXITCODE -eq 1) { Run git @('commit','-m',$Message) }
    elseif ($LASTEXITCODE -ne 0) { throw 'Verification Git impossible.' }
    Run git @('-c','http.sslBackend=openssl','push','origin','main')
    $revision = (& git rev-parse HEAD).Trim()
    if ($PublishOnly) { Write-Host "Publie sur GitHub : $revision"; return }
    $temp = Join-Path ([IO.Path]::GetTempPath()) ('bender-update-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $temp | Out-Null
    try {
        $archive = Join-Path $temp 'release.tar.gz'
        Run git @('archive','--format=tar.gz',"--output=$archive",$revision)
        $remoteStage = ".bender-update-$revision"
        Run scp ($sshOptions + @($archive,"${target}:$remoteStage.tar.gz"))
        $deployCommand = "mkdir -p ~/$remoteStage && mv ~/$remoteStage.tar.gz ~/$remoteStage/release.tar.gz && tar -xOf ~/$remoteStage/release.tar.gz scripts/deploy-debian.sh > ~/$remoteStage/deploy.sh && bash ~/$remoteStage/deploy.sh $RemoteDirectory $revision"
        Run ssh ($sshOptions + @('-t',$target,$deployCommand))
        Write-Host "Bender mis a jour : http://${RemoteHost}:8000 - revision $revision"
    } finally { Remove-Item -LiteralPath $temp -Recurse -Force }
} finally { Pop-Location }
