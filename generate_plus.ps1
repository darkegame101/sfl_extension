# Enforce TLS 1.2 for Firebase
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- CONFIGURE ---
$FIREBASE_URL = "https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/"
$ADMIN_SECRET = "TRUM-BOT-SFL-2024" 
$PREFIX = "G0LD"
$OWNER = "test"
$MONTHS_VALID = 12

# --- GENERATOR ---
function New-RandomKey {
    $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    $charsList = $chars.ToCharArray()
    $k = ""
    for ($i=0; $i -lt 3; $i++) {
        $p = ""
        for ($j=0; $j -lt 4; $j++) {
            $p += $charsList[(Get-Random -Maximum $charsList.Count)]
        }
        if ($k -eq "") { $k = $p } else { $k = "$k-$p" }
    }
    return "$PREFIX-$k"
}

Write-Host ""
Write-Host ">>> Starting Key Generation for: $OWNER..." -ForegroundColor Cyan

$key = New-RandomKey
$expiration = (Get-Date).AddMonths($MONTHS_VALID).ToString('yyyy-MM-dd')

$dataObj = @{
    admin_secret = $ADMIN_SECRET
    owner        = $OWNER
    hwid         = ""
    expiration   = $expiration
    status       = "active"
    created_at   = (Get-Date).ToString('yyyy-MM-ddTHH:mm:ssZ')
}
$dataJson = $dataObj | ConvertTo-Json

try {
    $url = "$($FIREBASE_URL)licenses/$($key).json"
    $response = Invoke-RestMethod -Uri $url -Method Put -Body $dataJson -ContentType "application/json"
    
    Write-Host ""
    Write-Host "SUCCESS: Key created successfully!" -ForegroundColor Green
    Write-Host "KEY: $key" -ForegroundColor Yellow
    Write-Host "EXP: $expiration"
    
    # Save to file
    $detail = "Key: $key | Owner: $OWNER | Exp: $expiration" + [System.Environment]::NewLine
    Add-Content -Path "keys.txt" -Value $detail
    
    Write-Host "Data saved to keys.txt" -ForegroundColor Gray
} catch {
    Write-Host ""
    Write-Host "ERROR: Failed to create key." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}

Write-Host ""
Write-Host "Press Enter to exit."
Read-Host