# Run as Administrator once. LAN-only inbound rules, including Public hotspot profiles.
$ErrorActionPreference = 'Stop'
foreach ($rule in @(@{Name='VRidge2-UDP-LAN';Port=39580},@{Name='VRidge2-mDNS-LAN';Port=5353})) {
    if (-not (Get-NetFirewallRule -Name $rule.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $rule.Name -DisplayName $rule.Name -Direction Inbound -Action Allow -Protocol UDP -LocalPort $rule.Port -RemoteAddress LocalSubnet -Profile Any | Out-Null
    }
}
Write-Host 'Bridge UDP39580 and Bonjour UDP5353 allowed from local subnets on all profiles.'
