# Run as Administrator once. LAN-only inbound rules, including Public hotspot profiles.
$ErrorActionPreference = 'Stop'
foreach ($rule in @(@{Name='VHBridge-UDP-LAN';Port=39570},@{Name='VHBridge-mDNS-LAN';Port=5353})) {
    if (-not (Get-NetFirewallRule -Name $rule.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -Name $rule.Name -DisplayName $rule.Name -Direction Inbound -Action Allow -Protocol UDP -LocalPort $rule.Port -RemoteAddress LocalSubnet -Profile Any | Out-Null
    }
}
Write-Host 'Bridge UDP39570 and Bonjour UDP5353 allowed from local subnets on all profiles.'
