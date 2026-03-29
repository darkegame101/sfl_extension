# --- CẤU HÌNH ---
$FIREBASE_URL = "https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/"
$ADMIN_SECRET = "TRUM-BOT-SFL-2024" # <--- Phải khớp với Firebase Rules
$PREFIX = "G0LD"
$OWNER = "boss"
$MONTHS_VALID = 12

# --- HÀM TẠO KEY NGẪU NHIÊN ---
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

Write-Host "`n🚀 Đang tạo License Key cho: $OWNER..." -ForegroundColor Cyan

$key = New-RandomKey
$expiration = (Get-Date).AddMonths($MONTHS_VALID).ToString("yyyy-MM-dd")

$dataObj = @{
    admin_secret = $ADMIN_SECRET
    owner        = $OWNER
    hwid         = ""
    expiration   = $expiration
    status       = "active"
    created_at   = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssZ")
}
$dataJson = $dataObj | ConvertTo-Json

try {
    $url = "$($FIREBASE_URL)licenses/$($key).json"
    $response = Invoke-RestMethod -Uri $url -Method Put -Body $dataJson -ContentType "application/json"
    
    Write-Host "`n✅ KẾT QUẢ THÀNH CÔNG!" -ForegroundColor Green
    Write-Host "🔑 KEY MỚI: $key" -ForegroundColor Yellow
    Write-Host "📅 HẠN DÙNG: $expiration"
    Write-Host "👤 CHỦ SỞ HỮU: $OWNER"
    
    # Lưu vào file để lưu trữ
    $detail = "Key: $key | Owner: $OWNER | Exp: $expiration`n"
    Add-Content -Path "keys.txt" -Value $detail
    
    Write-Host "`n✨ Đã lưu thông tin vào file keys.txt" -ForegroundColor Gray
} catch {
    Write-Host "`n❌ LỖI KHI TẠO KEY: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`nNhấn Enter để kết thúc."
Read-Host