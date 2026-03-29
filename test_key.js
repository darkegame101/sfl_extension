const https = require('https');
const url = require('url');

const FIREBASE_URL = "https://sfl-d26a3-default-rtdb.asia-southeast1.firebasedatabase.app/";
const key = "G0LD-9999-8888-7777";
const data = {
    owner: "Administrator",
    hwid: "",
    expiration: "2026-12-31",
    status: "active",
    created_at: new Date().toISOString()
};

function post() {
    return new Promise((resolve, reject) => {
        const dbUrl = new url.URL(`${FIREBASE_URL}licenses/${key}.json`);
        const options = {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' }
        };
        console.log(`📡 Sending to: ${dbUrl.href}`);
        const req = https.request(dbUrl, options, (res) => {
            console.log(`✅ Status: ${res.statusCode}`);
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => resolve(body));
        });
        req.on('error', (e) => {
            console.error(`❌ Request Error: ${e.message}`);
            reject(e);
        });
        req.write(JSON.stringify(data));
        req.end();
    });
}

post().then(r => console.log("DONE:", r)).catch(e => console.error("FAIL:", e));
