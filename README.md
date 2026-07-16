# Project structure 

```
Backend modules
Project setup
FastAPI or Django/DRF, PostgreSQL, environment config, authentication setup.
Users & roles
Customer, admin, nutrition manager, delivery manager, driver, finance/admin staff.
Meals module
Meals, meal categories, macros, calories, allergens, dietary tags, meal images.
Meal plans module
Weekly plans, monthly plans, custom plans, family plans, corporate plans.
Subscription module
Subscribe, pause, skip meal/day, upgrade, cancel, renew.
Orders module
Generate orders from subscriptions, order history, order status.
Payments module
Mada/Visa/Mastercard/Apple Pay through Moyasar/HyperPay/PayTabs.
Delivery module
Addresses, drivers, delivery schedules, route assignment, delivery tracking.
Notifications module
Email, SMS, WhatsApp for order confirmation, payment, delivery, renewal.
Admin dashboard APIs
Customer management, subscriptions, meals, revenue, analytics, permissions.
Recommended backend stack

Since you are strong in Python backend, I recommend:

FastAPI + PostgreSQL + SQLAlchemy + Alembic + JWT + Celery + Redis

Use:

FastAPI for APIs
PostgreSQL for database
SQLAlchemy for models
Alembic for migrations
JWT for login/auth
Redis + Celery for background jobs
S3-compatible storage for meal images
Payment gateway webhooks for recurring billing

```
# Folder Structuring

```
nutrio_backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── permissions.py
│   ├── db/
│   │   ├── database.py
│   │   └── base.py
│   ├── modules/
│   │   ├── auth/
│   │   ├── users/
│   │   ├── meals/
│   │   ├── subscriptions/
│   │   ├── orders/
│   │   ├── payments/
│   │   ├── deliveries/
│   │   └── notifications/
│   └── admin/
├── alembic/
├── requirements.txt
└── .env

```

# PHASE 

```
Authentication ✅

↓

Roles & Permissions ✅

↓

Meal Categories

↓

Meals

↓

Meal Plans

↓

Customer Profile

↓

Subscriptions

↓

Orders

↓

Deliveries

↓

Payments

↓

Reports

↓

Notifications

↓

Admin Dashboard

```

```
Phase 1 ✅ (Completed)

Authentication

✅ Register
✅ Email OTP
✅ Login
✅ Forgot Password
✅ Reset Password
✅ Change Password
✅ Roles
✅ Permissions
✅ RBAC
```

# DATA BASE MIGRATIONS

```
nano ~/Downloads/NeuroMeals/Backend/alembic.ini

Replace this 
sqlalchemy.url = driver://user:password@localhost/dbname

with

sqlalchemy.url = postgresql://postgres:password@localhost:5432/nutrio_meals

cd ~/Downloads/NeuroMeals/Backend
alembic revision --autogenerate -m "Add user columns"
alembic upgrade head

cd /root/Backend
alembic stamp head


1: cd /root/Backend
ls -la migrations/versions
alembic heads
alembic history --verbose
alembic current
# or check DB directly:
python -c "import os,urllib.parse; print(os.getenv('DATABASE_URL'))"
psql "$DATABASE_URL" -c "SELECT * FROM alembic_version;"

```

# CHECK LIVE LOGS 

```
sudo journalctl -u nutriomeals-api -f


```

# RESTART 
```
sudo systemctl restart nutriomeals-api

```

Register
↓
Verify email
↓
Login
↓
Frontend shows available plans
GET /plans/?is_active=true
↓
User chooses plan
↓
Create subscription
POST /subscriptions/
↓
Subscription becomes pending_payment
↓
Payment later


"subscription": {
  "id": 1,
  "plan_id": 2,
  "plan_name": "Muscle Gain Monthly Plan",
  "status": "pending_payment",
  "payment_status": "unpaid"
}

# DB QUERY
```
psql "postgresql://postgres:Amron@localhost:5432/nutrio_meals"

```
```
SELECT * FROM subscriptions;
```



```
1. Register Tap sandbox account
2. Obtain test API keys
3. Make Payment model provider-independent
4. Add Tap provider service
5. Replace Stripe create-checkout
6. Add Tap verification endpoint
7. Add Tap webhook
8. Test mada/cards
9. Enable and test Apple Pay
10. Decide whether PayPal is through Tap or separate
11. Obtain live approval and live keys
12. Run one small live SAR transaction

```

# AWS
ssh -i ~/Downloads/adam_katani.pem ubuntu@13.48.55.140

# CHARGES

```
https://os.tap.company/acceptance/charges
```

```
ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'CHEF';
```

psql "$DATABASE_URL" -c "
SELECT enumlabel
FROM pg_enum
JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
WHERE pg_type.typname = 'userrole';
"


alembic revision \
  --autogenerate \
  -m "add plan weekly menu items"