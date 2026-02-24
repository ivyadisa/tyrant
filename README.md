 # 🏠 Tyrant – Rental & Property Management System

**A comprehensive Django-based REST API for managing rental properties, bookings, and payments with role-based access control.**

Tyrant is a backend rental and property management system that enables tenants to discover and book apartments while empowering landlords to list, manage, and monetize their properties. Built with Django REST Framework, it features secure authentication, wallet-based payments (M-Pesa), real-time occupancy tracking, and admin oversight.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [System Requirements](#system-requirements)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Payment Integration](#payment-integration)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)
- [Support](#support)

---

## Features

### User Management
- User registration with email OTP verification
-   Role-based access control (Tenant, Landlord, Admin)
-   User verification workflow with admin oversight
-   Secure password reset via email OTP
-   User profile management

### Property Management
-   Complete apartment/unit CRUD operations
-   Apartment listing approval workflow (Admin verification)
-   Amenities and facility management
-   Real-time occupancy status tracking
-   Landlord filtering and property statistics

### Bookings & Reservations
-   Create, view, and manage bookings
-   Booking confirmation workflow
-   Automatic unit status updates
-   Tenant and landlord booking history

### Payment System
-   M-Pesa mobile money integration via payment aggregator
-   Secure payment processing with 10% platform commission
-   Automatic 90% landlord payment distribution
-   Wallet balance management and transaction history
-   Commission tracking and admin revenue analytics

### Wallet & Transactions
-   User wallet balance management
-   Deposit and withdrawal operations
-   Transaction history with detailed logs
-   Bank account information storage

### Admin Features
-   User suspension/unsuspension
-   Apartment approval/rejection workflow
-   Commission and revenue tracking
-   Analytics dashboard with key metrics

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.10+, Django 4.0+ |
| **API Framework** | Django REST Framework (DRF) |
| **Database** | PostgreSQL 12+ |
| **Authentication** | Token-based (DRF TokenAuth) |
| **Payment** | M-Pesa via Payment Aggregator (Pesapal/Intasend/Flutterwave) |
| **Deployment** | Docker, Heroku (Procfile included) |
| **Email** | Django Mail Backend |

---

##  System Requirements

| Requirement | Version |
|------------|---------|
| **Python** | 3.10+ |
| **PostgreSQL** | 12+ |
| **RAM** | 2GB minimum |
| **Disk Space** | 1GB minimum |
| **OS** | Linux, macOS, Windows |

---

## Prerequisites

Before installation, ensure you have:

- **Python 3.10+** installed and in PATH
- **PostgreSQL 12+** installed and running
- **pip** (Python package manager)
- **Virtual environment support** (venv or virtualenv)
- **Git** for cloning the repository
- **Payment Aggregator Account** (Pesapal/Intasend/Flutterwave) for M-Pesa integration

---

##  Installation

### 1. Clone the Repository

```bash
git clone https://github.com/flow-pie/tyrant.git
cd tyrant
```

### 2. Create Virtual Environment

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Database

Create a PostgreSQL database:

```sql
CREATE DATABASE tyrant_db;
CREATE USER tyrant_user WITH PASSWORD 'secure_password';
ALTER ROLE tyrant_user SET client_encoding TO 'utf8';
ALTER ROLE tyrant_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE tyrant_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE tyrant_db TO tyrant_user;
```

Update `tyrent_backend/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tyrant_db',
        'USER': 'tyrant_user',
        'PASSWORD': 'secure_password',
        'HOST': 'localhost',
        'PORT': 5432,
    }
}
```

### 5. Run Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. Create Superuser (Admin Account)

```bash
python manage.py createsuperuser
```

Follow the prompts to create an admin account.

### 7. Start Development Server

```bash
python manage.py runserver
```

Server will run at `http://localhost:8000`

---

##  Quick Start

### Example: User Registration & Login

**Register a new user:**
```bash
curl -X POST http://localhost:8000/api/users/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tenant@example.com",
    "password": "SecurePass123",
    "first_name": "Test",
    "last_name": "User"
  }'
```

**Response:**
```json
{
  "id": 1,
  "email": "tenant@example.com",
  "first_name": "John",
  "role": "tenant",
  "message": "User registered successfully. OTP sent to email."
}
```

**Verify email with OTP:**
```bash
curl -X POST http://localhost:8000/api/auth/verify-email/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tenant@example.com",
    "otp": "123456"
  }'
```

**Login:**
```bash
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tenant@example.com",
    "password": "SecurePass123"
  }'
```

**Response:**
```json
{
  "token": "abc123def456...",
  "user": {
    "id": 1,
    "email": "tenant@example.com",
    "role": "tenant"
  }
}
```

Use the token in subsequent requests:
```bash
curl -X GET http://localhost:8000/api/users/profile/ \
  -H "Authorization: Token abc123def456..."
```

### Example: Browse Apartments (Tenant)

```bash
curl -X GET http://localhost:8000/api/properties/apartments/ \
  -H "Authorization: Token your_token"
```

### Example: Create Booking

```bash
curl -X POST http://localhost:8000/api/bookings/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Token your_token" \
  -d '{
    "unit": 1,
    "check_in_date": "2026-03-01",
    "check_out_date": "2026-04-01"
  }'
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Database
DB_ENGINE=django.db.backends.postgresql
DB_NAME=tyrant_db
DB_USER=tyrant_user
DB_PASSWORD=secure_password
DB_HOST=localhost
DB_PORT=5432

# Django
SECRET_KEY=your_secret_key
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,domain.com

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=email@gmail.com
EMAIL_HOST_PASSWORD=your_email_password

# Payment Aggregator (M-Pesa)
PAYMENT_AGGREGATOR=pesapal  # or intasend, flutterwave
PAYMENT_API_KEY=your_api_key
PAYMENT_API_SECRET=your_api_secret
PAYMENT_CALLBACK_URL=https://yourdomain.com/api/bookings/payment-webhook/

# Commission Settings
PLATFORM_COMMISSION_PERCENTAGE=10  # 10% platform commission
```

Load variables in `settings.py`:
```python
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'your_default-secret-key')
DEBUG = os.getenv('DEBUG', False) == 'True'
```

---

##  Project Structure

```
tyrant/
├── bookings/                  # Booking app
│   ├── models.py             # Booking models
│   ├── views.py              # Booking views/endpoints
│   ├── serializers.py        # Booking serializers
│   └── urls.py               # Booking URL routes
│
├── properties/               # Properties app
│   ├── models.py             # Apartment, Unit, Amenity models
│   ├── views.py              # Property views/endpoints
│   ├── serializers.py        # Property serializers
│   └── urls.py               # Property URL routes
│
├── users/                    # User management app
│   ├── models.py             # User, Profile models
│   ├── views.py              # Auth endpoints, user views
│   ├── serializers.py        # User serializers
│   └── urls.py               # User URL routes
│
├── wallet/                   # Wallet/Payment app
│   ├── models.py             # Wallet, Transaction models
│   ├── views.py              # Wallet views/endpoints
│   ├── serializers.py        # Wallet serializers
│   └── urls.py               # Wallet URL routes
│
├── verification/             # Verification app
│   ├── models.py             # Verification models
│   ├── views.py              # Verification views
│   └── urls.py               # Verification URL routes
│
├── tyrent_backend/           # Django project config
│   ├── settings.py           # Project settings
│   ├── urls.py               # Root URL config
│   ├── wsgi.py               # WSGI application
│   └── asgi.py               # ASGI application
│
├── manage.py                 # Django management command
├── requirements.txt          # Python dependencies
├── runtime.txt               # Python version for Heroku
├── Procfile                  # Deployment configuration
├── README.md                 # This file
└── issues.md                 # Known issues and roadmap
```

---

##  API Documentation

### Authentication Endpoints
- `POST /api/auth/register/` - Register new user
- `POST /api/auth/login/` - Login user
- `POST /api/auth/verify-email/` - Verify email with OTP
- `POST /api/auth/resend-otp/` - Resend verification OTP
- `POST /api/auth/password-reset/` - Initiate password reset
- `POST /api/auth/confirm-password-reset/` - Confirm password reset with OTP

### User Endpoints
- `GET /api/users/profile/` - Get user profile
- `PATCH /api/users/profile/` - Update user profile
- `GET /api/users/dashboard/` - Get role-specific dashboard
- `GET /api/users/analytics/` (Admin only) - Platform analytics

### Property Endpoints
- `GET /api/properties/apartments/` - List apartments (filtered for tenants)
- `POST /api/properties/apartments/` - Create apartment (Landlord)
- `GET /api/properties/apartments/{id}/` - Get apartment details
- `PATCH /api/properties/apartments/{id}/` - Update apartment (Landlord)
- `DELETE /api/properties/apartments/{id}/` - Delete apartment (Landlord)
- `GET /api/properties/apartments/search/` - Search with filters
- `POST /api/properties/apartments/{id}/verify/` (Admin) - Approve apartment
- `POST /api/properties/apartments/{id}/reject/` (Admin) - Reject apartment

### Booking Endpoints
- `POST /api/bookings/` - Create booking
- `GET /api/bookings/` - List user bookings
- `GET /api/bookings/{id}/` - Get booking details
- `PATCH /api/bookings/{id}/` - Update booking
- `POST /api/bookings/{id}/cancel/` - Cancel booking
- `POST /api/bookings/{id}/initiate-payment/` - Start M-Pesa payment
- `POST /api/bookings/{id}/confirm-payment/` - Confirm payment
- `GET /api/bookings/{id}/payment-status/` - Check payment status

### Wallet Endpoints
- `GET /api/wallet/balance/` - Get wallet balance
- `POST /api/wallet/deposit/` - Deposit funds (M-Pesa)
- `POST /api/wallet/withdraw/` - Request withdrawal
- `GET /api/wallet/transactions/` - Transaction history
- `POST /api/wallet/payout-request/` (Landlord) - Request payout
- `GET /api/wallet/payouts/` - Payout history

For complete API documentation, see `/api/docs/` (if Swagger/ReDoc enabled).

---

## Payment Integration

### M-Pesa Payment Flow

1. **Tenant initiates payment:**
   ```bash
   POST /api/bookings/{id}/initiate-payment/
   {
     "phone_number": "+254712345678",
     "amount": 50000  # Amount in cents
   }
   ```

2. **M-Pesa prompt sent to tenant's phone**

3. **Tenant enters M-Pesa PIN**

4. **Payment aggregator sends webhook:**
   ```
   POST /api/bookings/payment-webhook/
   {
     "booking_id": 123,
     "status": "completed",
     "amount": 50000,
     "transaction_id": "tx_123456"
   }
   ```

5. **Automatic fund distribution:**
   - Platform keeps: 10% (5,000)
   - Landlord receives: 90% (45,000)

6. **Webhook response:**
   ```json
   {
     "booking_id": 123,
     "payment_status": "completed",
     "landlord_amount": 45000,
     "platform_commission": 5000
   }
   ```

### Setting Up Payment Aggregator

**For Pesapal:**
1. Create account at [pesapal.com](https://pesapal.com)
2. Get API Key and Secret
3. Update `.env` with credentials
4. Test using their sandbox environment

**For Intasend:**
1. Create account at [intasend.com](https://intasend.com)
2. Get API Key and Secret
3. Update `.env` with credentials
4. Use their testing mode first

---

## Troubleshooting

### Database Connection Error
```
django.db.utils.OperationalError: could not translate host name "localhost" to address
```
**Solution:** Ensure PostgreSQL is running:
```bash
# macOS
brew services start postgresql

# Linux
sudo systemctl start postgresql

# Windows
# Use PostgreSQL Service Manager
```

### ModuleNotFoundError: No module named 'django'
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
```

### Port 8000 Already in Use
```bash
# Use a different port
python manage.py runserver 8001

# Or kill the process using port 8000
# Linux/macOS:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### OTP Not Received
- Check email configuration in `settings.py`
- Ensure EMAIL_HOST_USER and EMAIL_HOST_PASSWORD are correct
- Check spam/junk folder
- Verify email backend is set to SMTP

### Payment Gateway Not Working
- Verify API keys in `.env` file
- Check payment aggregator sandbox vs. production mode
- Review webhook callback URL configuration
- Check server logs for detailed error messages

### Migration Errors
```bash
# Reset migrations (development only!)
python manage.py migrate users zero
python manage.py migrate

# Or if specific app:
python manage.py migrate bookings zero
python manage.py migrate bookings
```

---

## Contributing

We welcome contributions! Follow these steps:

1. **Fork the repository**
   ```bash
   git clone https://github.com/flow-pie/tyrant.git
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/feature-name
   ```

3. **Make your changes**
   - Write clean, readable code
   - Add comments for complex logic
   - Follow Django best practices

4. **Test your changes**
   ```bash
   python manage.py test
   ```

5. **Commit with clear messages**
   ```bash
   git commit -m "Add: Description of your changes"
   ```

6. **Push to your fork**
   ```bash
   git push origin feature/feature-name
   ```

7. **Create a Pull Request**
   - Provide a clear description
   - Reference any related issues
   - Wait for review and approval

### Code Standards
- Use PEP 8 style guide
- Add docstrings to functions/classes
- Keep functions small and focused
- Write tests for new features

---

##  Roadmap

### Phase 1 - MVP (Current)
-    User authentication and roles
-    Property listing management
-    Booking system
-    Basic wallet functionality
-    Email verification workflow
-    M-Pesa payment integration
-    Apartment approval workflow
-    Verification system

### Phase 2 - Q2 2026
-    Advanced search and filtering
-    User reviews and ratings
-    Lease agreement management
-    Admin dashboard enhancements
-    Rate limiting and security hardening
-    File upload validation

### Phase 3 - Q3 2026
-    Mobile app (React Native/Flutter)
-    Amenity distance calculation
-    Virtual property tours
-    SMS notifications
-    Push notifications
-    Refund workflow

### Phase 4 - Q4 2026
-    AI-powered property recommendations
-    Advanced analytics
-    Multi-currency support
-    Additional payment methods
-    Dispute resolution system

See [issues.md](./issues.md) for detailed technical requirements and implementation status.

---

##  Support

### Getting Help
- **Documentation:** Check [issues.md](./issues.md) for known issues and features
- **Discussions:** Create a GitHub issue for bugs or feature requests
- **Email:** Contact maintainers at : 

### Reporting Issues
When reporting issues, please include:
- Steps to reproduce
- Expected vs. actual behavior
- Python version and OS
- Relevant error logs
- Attempts to fix it

---

##  Credits & Maintainers

**Original Developer:** [ivyadisa](https://github.com/ivyadisa)

**Current Maintainers:**
- [flow-pie](https://github.com/flow-pie) (Backend Development)
- [ivyadisa](https://github.com/ivyadisa) (Backend Development)
- [mosesomo](https://github.com/mosesomo) (Frontend Development)

**Contributors:**
- Community contributions welcome! See [CONTRIBUTING.md](./CONTRIBUTING.md)

---

##  Compatibility

| Component | Version |
|-----------|---------|
| Python | 3.10, 3.11, 3.12 |
| Django | 4.0, 4.1, 4.2 |
| PostgreSQL | 12, 13, 14, 15 |
| DRF | 3.13+ |

---

## Changelog

### v1.0.0 (Current - In Development)
- Initial project setup with core features
- User authentication with email OTP
- Property and booking management
- Wallet system foundation
- M-Pesa payment integration (planned)
- Admin oversight capabilities

For full changelog, see [CHANGELOG.md](./CHANGELOG.md)

---

**Last Updated:** February 2026
**Status:** Active Development 