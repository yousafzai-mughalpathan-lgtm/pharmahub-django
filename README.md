# PharmaHub

PharmaHub is a Django-based, multi-vendor pharmacy marketplace project. It brings customers, pharmacies, and administrators together for medicine discovery, prescription workflows, order management, and pharmacy operations.

> **Academic project notice:** The symptom checker and generated health information are for demonstration and informational purposes only. They are not medical advice, diagnosis, or a substitute for a licensed healthcare professional. Do not use the project to make real treatment decisions.

## Highlights

- Customer, pharmacy, and administrator roles with authentication and role-based access.
- Pharmacy onboarding and verification workflows.
- Medicine catalogue, inventory management, search, and stock-aware listings.
- Shopping cart, checkout, order tracking, and pharmacy-side order management.
- Prescription upload and review workflows.
- Pharmacy dashboards with sales and order analytics.
- REST API built with Django REST Framework and JWT authentication.
- Symptom checker combining a scikit-learn model and optional Gemini-powered explanations.
- Notifications, email integration, and Google sign-in integration (optional configuration).

## Technology

- Python and Django
- Django REST Framework, Simple JWT, Django Channels
- PostgreSQL
- pandas, NumPy, and scikit-learn for the symptom-checker data/model workflow
- Google Gemini API for optional generated health-information responses
- HTML, CSS, JavaScript, and Django templates

## Requirements

- Python 3.10 or later
- PostgreSQL
- Git

Install PostgreSQL separately and create a database and database user for the project. The project dependencies are pinned in `requirements.txt`.

## Local setup

1. Clone the repository and open its project directory.
2. Create and activate a virtual environment.
3. Install dependencies:

	```powershell
	python -m pip install -r requirements.txt
	```

4. Copy `.env.example` to `.env`. Fill in local values; keep `.env` private and never commit it. Generate a new Django secret key for your own environment.
5. Create the PostgreSQL database and user that match the `DB_*` values in `.env`.
6. Apply migrations and create an administrator account:

	```powershell
	python manage.py migrate
	python manage.py createsuperuser
	```

7. Start the development server:

	```powershell
	python manage.py runserver
	```

Open `http://127.0.0.1:8000/` in your browser. The custom admin panel is available at `/admin/`; Django's built-in admin is at `/django-admin/`.

### Environment variables

See `.env.example` for the supported settings. `SECRET_KEY` is required. `DEBUG` defaults to `False` in code; use `DEBUG=True` only for local development. Database, email, Google OAuth, and Gemini settings are environment-based. Features requiring an external integration will need valid credentials configured locally.

## Symptom-checker data

The `ai_model/` directory contains the project datasets and model artifacts used by the symptom-checker workflow. The model is informational only and has not been clinically validated. Any result must be reviewed by a qualified healthcare professional.

## Security and privacy

- Never commit `.env`, private keys, database files, logs, or user-uploaded media. These are excluded by `.gitignore`.
- Use fresh, individually scoped credentials in local and deployed environments. Do not reuse credentials that were ever committed or shared.
- Set `DEBUG=False` and configure `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, HTTPS, database credentials, and provider credentials appropriately before any deployment.
- Do not upload real patient records, prescriptions, pharmacy licenses, or other personal data to this repository.

## Project structure

```text
PharmaHub/
├── PharmaHub/       # Django project configuration and entry points
├── admin_panel/     # Custom admin workflows and APIs
├── ai_model/        # Symptom-checker model, datasets, and training scripts
├── api/             # REST API endpoints
├── authentication/  # Login, signup, roles, and authentication helpers
├── customers_d/     # Customer features, cart, prescriptions, and symptom checker
├── dashboards/      # Pharmacy dashboards and inventory workflows
├── orders/          # Checkout, orders, and payment-related flows
├── pages/           # Public pages and assistant-related views
├── pharmacy/        # Pharmacy application models and pages
├── static/          # Static assets
├── manage.py
└── requirements.txt
```

## Contributors

PharmaHub was developed collaboratively as an academic project.

- **Amna Farooq — Project Lead & Backend Developer:** Led the project and worked on the customer-side theme, header fixes, admin-side header, AI symptom checker, and add-to-cart functionality.
- **Iqra Azam — Pharmacy Frontend Developer:** Built the pharmacy-side frontend.
- **Sonia — Authentication Developer:** Worked on the login and registration flows.
