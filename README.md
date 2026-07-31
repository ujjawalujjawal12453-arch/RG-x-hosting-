# UM MODE OFF — Hosting Bot + Free Trial Website (ONE project)

Ye bot aur website **ab wapas ek hi project** mein hain — sirf isliye alag
kiye the taaki dekha ja sake, par usse database mismatch ho raha tha (do
alag `bot.db` files ban rahi thi). Ab dono **ek hi `config.py` aur
`database.py`** use karte hain — matlab ek hi `data/bot.db` file, kabhi
mismatch nahi ho sakta, structurally hi possible nahi hai.

---

## File Map — kya kahan hai, line-wise

```
telegram-hosting-bot/
│
├── main.py                  ← RENDER/normal use ke liye ye chalao — bot + website DONO ek sath
├── bot.py                  ← Sirf bot chalana ho to isko chalao: python3 bot.py
├── config.py                ← SAB settings yahan (.env se load hoti hain). BOT_TOKEN, ADMIN_ID, saare rates/limits
├── database.py               ← Database ka poora logic. Bot aur website DONO isi file ko use karte hain — isiliye ab mismatch nahi hoga
├── process_manager.py        ← User ke uploaded bots/APIs ko real mein chalata/rokta hai
├── keyboards.py               ← Telegram ke buttons/menus
├── jobs.py                    ← Background checks (expiry, renewal reminders)
├── rules.py                   ← Violation/strike/ban system
├── scanner.py                  ← Uploaded files ka quick-scan (risky code detect karta hai)
├── ui_utils.py                  ← Chhota helper (photo/text message edit karne ke liye)
├── requirements.txt              ← Saari Python libraries jo install karni hain
├── .env.example                   ← Iski copy banao `.env` naam se, phir values bharo
├── Procfile                        ← Render deployment ke liye (website chalane ka command)
│
├── handlers/
│   ├── user.py                      ← User ke saare buttons/messages (key activate, upload, trial, referral)
│   └── admin.py                      ← Admin panel (key generate, approve/reject, stats, ban/unban)
│
├── data/
│   ├── bot.db                         ← ASLI DATABASE — bot aur website dono isi file ko padhte/likhte hain
│   ├── qr/payment_qr.png               ← Tumhara payment QR
│   ├── branding/logo.png                ← Tumhara "UM Mode Off" logo
│   └── user_files/                       ← Users ne jo files upload ki, wahan save hoti hain
│
└── website/
    ├── app.py                          ← WEBSITE ka main entry point. Isko chalao: python3 website/app.py
    ├── linklocker.py                    ← GPLinks (ya jo bhi) API ka connection
    └── templates/
        ├── index.html                    ← Free-trial claim page ka design
        └── message.html                   ← Error/expired-link page
```

**Sabse zaroori baat:** `website/app.py` `config.py` aur `database.py` ko
seedha `bot.py` wale folder se import karta hai (upar wale folder se) —
isiliye ab dono files **hamesha** same `data/bot.db` ko dekhenge. Ye
`website/` ko `telegram-hosting-bot/` ke ANDAR hi rakhna zaroori banata hai
— bahar mat nikaalna, warna wahi purani mismatch wapas aa jaayegi.

---

## Setup — line by line

```bash
cd telegram-hosting-bot
pip install -r requirements.txt --break-system-packages
cp .env.example .env
```

`.env` kholo, ye bharo:
- `BOT_TOKEN` — @BotFather se
- `ADMIN_ID` — apna Telegram numeric ID (bot start karke `/whoami` se milega)
- `LINKLOCKER_API_KEY` — GPLinks (ya jo use karna hai) ka key
- `PUBLIC_BASE_URL` — website jahan live hogi uska address (local test ke
  liye `http://localhost:5000` chalega)

## Chalana — Termux/VPS par (dono ek sath, ek hi command se)

```bash
cd telegram-hosting-bot
python3 main.py
```

Bas itna — `main.py` bot aur website **dono ek hi process mein** chala deta
hai (website background mein, bot foreground mein). Alag-alag terminal
kholne ki zaroorat nahi.

*(Agar kabhi sirf ek hi chalana ho testing ke liye: `python3 bot.py` ya
`python3 website/app.py` bhi alag-alag chal sakte hain — par normal use
ke liye `main.py` hi chalao.)*

## Render par deploy karna hai to (EK hi Web Service — bas)

Poora `telegram-hosting-bot` folder GitHub par push karo (jaisa
`deploy_helper.py` se pehle kiya). Render par:

1. **New → Web Service** → apna GitHub repo connect karo
2. Build command: `pip install -r requirements.txt`
3. Start command: khud-ba-khud `Procfile` se le lega (`python3 main.py`)
4. Environment variables Render ke **Environment tab** mein daalo — wahi
   sab jo `.env` mein hain (`BOT_TOKEN`, `ADMIN_ID`, `LINKLOCKER_API_KEY`, etc.)
5. **Sabse zaroori:** `PUBLIC_BASE_URL` ko apne Render URL par set karo
   (deploy hone ke baad Render jo URL dega, jaise
   `https://tumhara-app.onrender.com`) — agar ye galat/localhost raha to
   free-trial ka link kabhi kaam nahi karega. `main.py` startup par isko
   khud check karke warning bhi dega agar galat lage.

Render ko **do alag services banane ki zaroorat nahi** — ek hi Web Service
`main.py` ke through dono cheezein (bot polling + website) sambhal leta hai.

⚠️ Render ka free-tier disk ephemeral hai (restart par `data/bot.db` reset
ho sakta hai) — jaisa pehle discuss kiya tha, abhi ke liye theek hai.

---

## Features (sab wahi hain jo pehle the)

- 🤖 3 categories: Bot / API / Website hosting, alag pricing
- ⭐ Priority aur 👑 VIP tiers (extra charge, extra resource/queue-priority)
- 🎁 Free Trial — website se, GPLinks task-lock + Telegram PIN verify,
  16-digit trial key (paid keys 8-digit)
- 👥 Referral bonus, 🔁 Renewal discount
- 📋 Waitlist — server full hone par bhi request khoti nahi
- 🚫 Rules & violations — risky upload / bruteforce / spam par strike,
  3 strikes = auto-ban
- 📢 Broadcast, 📊 Stats (aaj ka + all-time revenue)
- 💳 QR payment, 📸 screenshot turant admin ko, quick-scan on every upload
