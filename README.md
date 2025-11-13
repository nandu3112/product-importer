# **Acme Product Importer & Management Web App**

A scalable web application designed to **import large product datasets (up to 500,000 records)** from CSV files into a PostgreSQL database, with a clean UI for product management and webhook configuration.

---

## **✨ Features**

### ✅ **CSV File Upload**
- Upload large CSV files (up to **500,000 products**).
- **Duplicate handling**: Automatically overwrite based on **SKU** (case-insensitive).
- SKU uniqueness enforced across all records.
- Optimized for **large file handling** while keeping the UI responsive.

### ✅ **Upload Progress Visibility**
- Dynamic progress updates during parsing, validation, and import.
- Clear error messages and **retry option** on failure.
- Implemented using **SSE/WebSockets** for real-time feedback.

### ✅ **Product Management UI**
- View, create, update, and delete products from a web interface.
- **Filtering** by SKU, name, active status, or description.
- **Pagination** for large datasets.
- Inline editing or modal forms for quick updates.
- Confirmation dialogs for deletion.

### ✅ **Bulk Delete**
- Delete **all products** with a single action.
- Protected with confirmation dialogs.
- Visual feedback and success/failure notifications.

### ✅ **Webhook Configuration**
- Add, edit, test, and delete multiple webhooks.
- Manage webhook URLs, event types, and enable/disable status.
- Test triggers with **response code & response time** feedback.

---

## **🛠 Tech Stack**

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
- **Frontend**: HTML, CSS, JavaScript (minimalist design)
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Async Task Queue**: Celery with Redis
- **Deployment**: [Render](https://render.com/) (Publicly accessible)
- **Real-time Updates**: WebSockets / Server-Sent Events (SSE)

---

## **📂 Project Structure**

```
.
├── db.sqlite3
├── manage.py
├── Procfile
├── product_importer
│   ├── asgi.py
│   ├── celery.py
│   ├── __init__.py
│   ├── __pycache__
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── products
│   ├── admin.py
│   ├── apps.py
│   ├── forms.py
│   ├── __init__.py
│   ├── migrations
│   ├── models.py
│   ├── __pycache__
│   ├── services.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
├── README.md
├── requirements.txt
├── static
├── staticfiles
├── templates
│   ├── base.html
│   ├── products
│   ├── uploads
│   └── webhooks
├── uploads
│   ├── admin.py
│   ├── apps.py
│   ├── bulk_services.py
│   ├── consumers.py
│   ├── __init__.py
│   ├── migrations
│   ├── models.py
│   ├── __pycache__
│   ├── routing.py
│   ├── services.py
│   ├── task_services.py
│   ├── tasks.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
└── webhooks
    ├── admin.py
    ├── apps.py
    ├── forms.py
    ├── __init__.py
    ├── migrations
    ├── models.py
    ├── __pycache__
    ├── services.py
    ├── tests.py
    ├── urls.py
    └── views.py
```

---

## **🚀 Deployment**

1. **Clone the repository**
   ```bash
   git clone https://github.com/nandu3112/product-importer.git
   cd product-importer
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export REDIS_URL=redis://localhost:6379/0
   ```

4. **Run migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the app**
   ```bash
   uvicorn app.main:app --reload
   ```

6. **Start Celery worker**
   ```bash
   celery -A app.tasks worker --loglevel=info
   ```

---

## **📊 Performance Highlights**
- Handles **500,000+ records** efficiently using **streaming CSV parsing**.
- Asynchronous background processing for heavy tasks.
- Optimized database operations with bulk inserts and upserts.

---

## **✅ Live Demo**
[**Click here to access the deployed app**](https://acme-product-importer.onrender.com)

---

## **📧 Contact**
For any queries, reach out at **toramnandhitha@example.com**.
