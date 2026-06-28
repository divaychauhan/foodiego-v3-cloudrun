# FoodieGo v3 - Production Style Cloud Run Food Delivery App

Features included:
- Customer register/login/logout
- JWT token auth for separate frontend/backend support
- Restaurant admin login
- Admin order management
- Admin restaurant creation
- Admin menu item creation
- Mock payment gateway for UPI/Card/COD learning flow
- Real-time style order tracking using polling API
- Address validation with pincode rules
- Order cancellation rules: only customer, only PLACED/ACCEPTED, within 10 minutes
- Flask-Migrate database migration support
- Cloud SQL ready
- Google Cloud Run ready
- Optional separate frontend folder

Demo users:
- Customer: customer@foodiego.com / Customer@123
- Admin: admin@foodiego.com / Admin@123

## Local run

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8080

## Docker run

```bash
docker build -t foodiego-v3 .
docker run -p 8080:8080 foodiego-v3
```

## Database migrations

For first migration setup:

```bash
export FLASK_APP=app.py
flask db init
flask db migrate -m "Initial production schema"
flask db upgrade
```

For future model changes:

```bash
flask db migrate -m "Describe change"
flask db upgrade
```

For Cloud Run production, set `AUTO_CREATE_DB=false` and run migrations as a Cloud Run Job before sending traffic to a new revision.

## Separate frontend/backend deployment

Current root app is a single Cloud Run service for fast learning.
For production split:

1. Deploy backend using root Dockerfile to Cloud Run.
2. Copy backend URL.
3. Open `frontend/index.html` and replace:
   `https://YOUR-BACKEND-CLOUD-RUN-URL`
   with your backend Cloud Run URL.
4. Deploy `frontend/` as a separate static container, Firebase Hosting, or Cloud Storage static website.

Because this app uses JWT Bearer tokens, the separate frontend can call the backend API.

## GCP Secret Manager

Create a Flask secret key in GCP Secret Manager before GitHub Actions deploys:

```bash
openssl rand -hex 32 | gcloud secrets create foodiego-secret-key --data-file=-

gcloud secrets add-iam-policy-binding foodiego-secret-key \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

Your existing DB password secret should still be named `foodie-db-pass`.

## Payment gateway note

This project uses a mock payment gateway. It creates a payment record, confirms payment, stores a mock transaction ID, and updates order status. Replace `/api/payments/<payment_id>/confirm` with Razorpay/Stripe/other gateway verification for real money collection.
