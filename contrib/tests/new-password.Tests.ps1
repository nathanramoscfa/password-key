#Requires -Module @{ ModuleName = 'Pester'; ModuleVersion = '5.0.0' }
<#
    Tests for contrib/new-password.ps1.

    This script is a second, independent credential generator. It gets
    the same scrutiny as the Python one - charset containment, absence
    of modulo bias, no shell-hostile characters - because "the code
    looks right" is not a reason for anyone to trust a password
    generator.

    Run locally:  Invoke-Pester contrib/tests
#>

BeforeAll {
    $sut = Join-Path $PSScriptRoot '..' | Join-Path -ChildPath 'new-password.ps1'
    $script:ScriptPath = (Resolve-Path $sut).Path
    # Dot-sourcing loads the charsets and New-RandomPassword without
    # running the script body. See the guard in new-password.ps1.
    . $script:ScriptPath
    $script:UrlSafe = $SetUrlSafe
    $script:Full = $SetFull
}

Describe 'new-password.ps1 (script hygiene)' {
    It 'parses without syntax errors' {
        $errors = $null
        [System.Management.Automation.Language.Parser]::ParseFile(
            $script:ScriptPath, [ref]$null, [ref]$errors) | Out-Null
        $errors | Should -BeNullOrEmpty
    }

    It 'defines the generator when dot-sourced, without generating anything' {
        Get-Command New-RandomPassword -CommandType Function |
            Should -Not -BeNullOrEmpty
    }

    It 'rejects a length below the safe minimum' {
        { & $script:ScriptPath -Length 4 } | Should -Throw
    }

    It 'rejects a length above the maximum' {
        { & $script:ScriptPath -Length 512 } | Should -Throw
    }
}

Describe 'Charsets' {
    It 'URL-safe set is exactly the RFC 3986 unreserved characters' {
        $expected = (
            'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
        ).ToCharArray() | Sort-Object
        ($script:UrlSafe.ToCharArray() | Sort-Object) -join '' |
            Should -BeExactly ($expected -join '')
    }

    It 'has no duplicate characters in <Name>' -ForEach @(
        @{ Name = 'the URL-safe set'; Set = { $script:UrlSafe } }
        @{ Name = 'the full set'; Set = { $script:Full } }
    ) {
        $chars = (& $Set).ToCharArray()
        # A repeated character would make it likelier than the others -
        # a bias that no amount of correct rejection sampling undoes.
        ($chars | Select-Object -Unique).Count | Should -Be $chars.Count
    }

    It 'excludes shell- and SQL-hostile characters from <Name>' -ForEach @(
        @{ Name = 'the URL-safe set'; Set = { $script:UrlSafe } }
        @{ Name = 'the full set'; Set = { $script:Full } }
    ) {
        foreach ($bad in @('"', "'", '\', '`', ' ', '/')) {
            (& $Set).Contains($bad) | Should -BeFalse -Because "'$bad' escapes badly"
        }
    }

    It 'full set is a strict superset of the URL-safe alphanumerics' {
        $alnum = $script:UrlSafe.ToCharArray() | Where-Object { $_ -match '[A-Za-z0-9]' }
        foreach ($ch in $alnum) {
            $script:Full.Contains($ch) | Should -BeTrue
        }
        $script:Full.Length | Should -BeGreaterThan $script:UrlSafe.Length
    }
}

Describe 'New-RandomPassword' {
    It 'returns exactly <Count> characters' -ForEach @(
        @{ Count = 8 }, @{ Count = 32 }, @{ Count = 64 }, @{ Count = 256 }
    ) {
        (New-RandomPassword -Charset $script:UrlSafe -Count $Count).Length |
            Should -Be $Count
    }

    It 'draws only from the given charset (<Name>)' -ForEach @(
        @{ Name = 'URL-safe'; Set = { $script:UrlSafe } }
        @{ Name = 'full'; Set = { $script:Full } }
    ) {
        $charset = & $Set
        $password = New-RandomPassword -Charset $charset -Count 2000
        foreach ($ch in $password.ToCharArray()) {
            $charset.Contains($ch) | Should -BeTrue -Because "'$ch' is not in the set"
        }
    }

    It 'does not repeat itself across calls' {
        $seen = 1..25 | ForEach-Object {
            New-RandomPassword -Charset $script:UrlSafe -Count 32
        }
        ($seen | Select-Object -Unique).Count | Should -Be 25
    }

    It 'is unbiased across the URL-safe set (chi-squared)' {
        $n = $script:UrlSafe.Length
        # 256 % 66 = 58, so a naive (byte % n) would make the first 58
        # characters measurably likelier. That is the bug this test
        # exists to catch, so assert the premise still holds.
        (256 % $n) | Should -Not -Be 0

        $perChar = 500
        $draws = $n * $perChar
        $counts = @{}
        foreach ($ch in $script:UrlSafe.ToCharArray()) { $counts[$ch] = 0 }
        foreach ($ch in (New-RandomPassword -Charset $script:UrlSafe -Count $draws).ToCharArray()) {
            $counts[$ch]++
        }

        # df = 65. The 0.0001 critical value is ~118, so a correct
        # implementation trips this about once in ten thousand runs.
        $chi2 = 0.0
        foreach ($ch in $script:UrlSafe.ToCharArray()) {
            $chi2 += [Math]::Pow($counts[$ch] - $perChar, 2) / $perChar
        }
        $chi2 | Should -BeLessThan 120 -Because "chi-squared $chi2 suggests biased sampling"
    }
}

Describe 'Parity with the Python implementation' {
    BeforeAll {
        $script:Python = (Get-Command python -ErrorAction SilentlyContinue)
        $script:PySets = $null
        if ($script:Python) {
            $code = 'from password_key.generator import URL_SAFE, FULL; print(URL_SAFE); print(FULL)'
            $out = & $script:Python.Source '-c' $code 2>$null
            if ($LASTEXITCODE -eq 0 -and $out.Count -ge 2) {
                $script:PySets = @{ UrlSafe = $out[0]; Full = $out[1] }
            }
        }
    }

    # Two implementations of the same tool drifting apart silently is
    # exactly how one of them ends up weaker than its documentation.
    It 'URL-safe set matches password_key.generator.URL_SAFE' {
        if (-not $script:PySets) { Set-ItResult -Skipped -Because 'password_key is not importable' }
        ($script:PySets.UrlSafe.ToCharArray() | Sort-Object) -join '' |
            Should -BeExactly (($script:UrlSafe.ToCharArray() | Sort-Object) -join '')
    }

    It 'full set matches password_key.generator.FULL' {
        if (-not $script:PySets) { Set-ItResult -Skipped -Because 'password_key is not importable' }
        ($script:PySets.Full.ToCharArray() | Sort-Object) -join '' |
            Should -BeExactly (($script:Full.ToCharArray() | Sort-Object) -join '')
    }
}
