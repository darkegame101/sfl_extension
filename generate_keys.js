const https = require('https');
const url = require('url');

// --- CẤU HÌNH ---
const FIREBASE_URL = "https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/";
const ADMIN_SECRET = "TRUM-BOT-SFL-2024"; // <--- Đặt mật mã này vào Firebase Rules
const PREFIX = "G0LD"; // Tiền tố cho Key
const COUNT = 1;       // Số lượng Key muốn tạo
const OWNER = "boss"; // Tên khách hàng để dễ quản lý
const MONTHS_VALID = 5; // Thời hạn mặc định (số tháng)

function generateRandomKey() {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    const part = () => Array.from({length: 4}, () => chars[Math.floor(Math.random() * chars.length)]).join('');
    return `${PREFIX}-${part()}-${part()}-${part()}`;
}

function postToFirebase(key, data) {
    return new Promise((resolve, reject) => {
        // --- SỬ DỤNG URL GỐC (Bảo mật bằng CUSTOM SECRET trong JSON) ---
        const dbUrl = new url.URL(`${FIREBASE_URL}licenses/${key}.json`);
        
        const options = {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        };

        const req = https.request(dbUrl, options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => resolve(body));
        });

        req.on('error', reject);
        req.write(JSON.stringify(data));
        req.end();
    });
}

const fs = require('fs');

async function start() {
    console.log(`🚀 Đang tạo ${COUNT} license keys...`);
    
    let keyOutput = "";
    const expiration = new Date();
    expiration.setMonth(expiration.getMonth() + MONTHS_VALID);
    const expStr = expiration.toISOString().split('T')[0];

    for (let i = 0; i < COUNT; i++) {
        const key = generateRandomKey();
        const data = {
            admin_secret: ADMIN_SECRET, // Mật mã để Firebase cho phép ghi
            owner: OWNER,
            hwid: "",
            expiration: expStr,
            status: "active",
            created_at: new Date().toISOString()
        };

        try {
            await postToFirebase(key, data);
            const detail = `🔑 KEY: ${key}\n📅 Hạn dùng: ${expStr}\n👤 Chủ: ${OWNER}\n------------------\n`;
            console.log(detail);
            keyOutput += detail;
        } catch (e) {
            console.error(`❌ Lỗi khi tạo key ${key}: ${e.message}`);
        }
    }
    
    fs.writeFileSync('keys.txt', keyOutput);
    console.log("\n✨ Đã lưu danh sách Key vào file keys.txt!");
}

start().catch(err => {
    console.error("💥 LỖI NGHIÊM TRỌNG:", err);
    fs.writeFileSync('error_log.txt', err.stack);
});
