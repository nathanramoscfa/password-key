# new-password.ps1
<#
.SYNOPSIS
    Generate a cryptographically random password onto the clipboard.

.DESCRIPTION
    Uses the OS cryptographic RNG, not Get-Random (which is seeded
    pseudo-randomness and must never be used for a credential).

    The password is copied to the clipboard and NOT printed. That is
    deliberate: a secret should never enter a terminal, and terminal
    scrollback is a file on disk. Use -Show only if you genuinely have
    to read it.

.PARAMETER Full
    Use the full punctuation set instead of the URL-safe default.

    THINK BEFORE USING THIS. The default set is letters, digits and
    - _ . ~ : the characters that carry no special meaning in a URL, in a
    single-quoted SQL literal, or in a shell. The full set adds @ : / ? #
    % and friends, every one of which has to be percent-encoded by hand
    the moment the password goes into a DSN like

        postgresql://user:PASSWORD@host/db

    and each is a silent, hours-later failure when it is not. At 32
    characters the URL-safe set is already ~193 bits of entropy, so the
    restriction buys safety for nothing. -Full exists only for systems
    that mandate a punctuation class.

.PARAMETER Length
    Character count. Default 32.

.PARAMETER Show
    Print the password instead of only copying it.

.EXAMPLE
    .\new-password.ps1
    A 32-character password safe for any DSN, on the clipboard.

.EXAMPLE
    .\new-password.ps1 -Length 48 -Full
    A 48-character password from the full character set.
#>
[CmdletBinding()]
param(
    [ValidateRange(8, 256)]
    [int]$Length = 32,
    [switch]$Full,
    [switch]$Show,
    # Back-compat: -UrlSafe is now the default and this is a no-op. Kept
    # so older notes and runbook copies keep working rather than erroring.
    [switch]$UrlSafe
)

$ErrorActionPreference = 'Stop'

# No quotes, no backslash, no backtick, no space in either set. They cost
# nothing in entropy at this length and they are the characters that turn
# a working password into a confusing escaping bug three steps later.
$SetUrlSafe = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
              'abcdefghijklmnopqrstuvwxyz' +
              '0123456789-_.~'
$SetFull    = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
              'abcdefghijklmnopqrstuvwxyz' +
              '0123456789' +
              '!#$%&()*+,-.:;<=>?@[]^{|}_~'

function New-RandomPassword {
    param(
        [Parameter(Mandatory = $true)][string]$Charset,
        [Parameter(Mandatory = $true)][int]$Count
    )
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $n = $Charset.Length
        # Rejection sampling. Taking (byte % n) directly would make the
        # first (256 % n) characters of the set slightly more likely —
        # a real, measurable bias. Discard bytes at or above the largest
        # exact multiple of n instead.
        $limit = [int]([Math]::Floor(256 / $n) * $n)
        $sb = New-Object System.Text.StringBuilder
        $buf = New-Object byte[] 1
        while ($sb.Length -lt $Count) {
            $rng.GetBytes($buf)
            $v = [int]$buf[0]
            if ($v -lt $limit) {
                [void]$sb.Append($Charset[$v % $n])
            }
        }
        return $sb.ToString()
    }
    finally {
        $rng.Dispose()
    }
}

# URL-safe is the DEFAULT. Getting this backwards costs an hour: a '@'
# in a password silently splits a DSN, and the error surfaces far from
# the cause.
if ($Full) {
    $charset = $SetFull
    $label = 'FULL punctuation - NOT safe in a DSN without encoding'
}
else {
    $charset = $SetUrlSafe
    $label = 'URL-safe (letters, digits, - _ . ~) - safe anywhere'
}

$password = New-RandomPassword -Charset $charset -Count $Length
$bits = [Math]::Floor([Math]::Log($charset.Length, 2) * $Length)

$copied = $false
try {
    Set-Clipboard -Value $password
    $copied = $true
}
catch {
    $copied = $false
}

Write-Host ""
Write-Host "  Length    : $Length characters"
if ($Full) {
    Write-Host "  Charset   : $label" -ForegroundColor Yellow
    Write-Host "  WARNING   : percent-encode this before putting it in a DSN" -ForegroundColor Yellow
}
else {
    Write-Host "  Charset   : $label"
}
Write-Host "  Strength  : ~$bits bits of entropy"
if ($copied) {
    Write-Host "  Clipboard : COPIED" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Paste it into your password manager now, then copy"
    Write-Host "  something harmless to clear the clipboard."
}
else {
    Write-Host "  Clipboard : FAILED - showing it instead" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  $password"
}
if ($Show -and $copied) {
    Write-Host ""
    Write-Host "  $password"
}
Write-Host ""

# Drop it from this session's memory. Not a guarantee against a memory
# dump, but it keeps the value out of $LASTEXITCODE-adjacent inspection
# and out of any later Get-Variable sweep.
$password = $null
Remove-Variable password -ErrorAction SilentlyContinue
