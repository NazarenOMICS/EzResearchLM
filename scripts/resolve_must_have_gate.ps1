function Resolve-EzMustHaveGate {
    param(
        [bool]$ExplicitlySet,
        [bool]$RequestedValue,
        [string]$StatePath
    )
    if ($ExplicitlySet) { return $RequestedValue }
    if (-not $StatePath -or -not (Test-Path -LiteralPath $StatePath)) { return $false }
    $prior = Get-Content -LiteralPath $StatePath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($prior.must_have_gate_version -eq 2) {
        if (-not ($prior.PSObject.Properties.Name -contains 'stop_if_missing_must_have')) {
            throw 'Version 2 run state is missing stop_if_missing_must_have'
        }
        return [bool]$prior.stop_if_missing_must_have
    }
    if ($prior.must_have_gate_version) { throw 'Unsupported must-have gate version' }
    # Before v2, false was recorded but the implementation always blocked.
    return $true
}
