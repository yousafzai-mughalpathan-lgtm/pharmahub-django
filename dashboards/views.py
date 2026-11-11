import json
import io
import pandas as pd
import requests
from datetime import timedelta
import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
from django.db.models import Sum, Count
from django.core.mail import send_mail
from calendar import month_abbr
from decimal import Decimal

from authentication.decorators import role_required, verification_required
from pages.views import get_base_template
from pages import views as pages_views
from orders import views as orders_views

from customers_d.models import Prescription, QuoteItem, CustomerNotification
from orders.models import Order, OrderItem
from admin_panel.models import Notification
from dashboards.models import PharmacyNotification

from .models import Pharmacy, Medicine
from .forms import MedicineForm
from dashboards.utils import send_customer_notification, geocode_address

logger = logging.getLogger(__name__)


def _get_order_customer_user(order: Order):
    """Return the customer user for an Order instance safely."""
    # Prefer customer attribute if present, else fallback to user.
    if hasattr(order, "customer") and getattr(order, "customer") is not None:
        customer_obj = getattr(order, "customer")
        # customer_obj might be a Customer model or directly a user
        if hasattr(customer_obj, "user"):
            return customer_obj.user
        return customer_obj
    if hasattr(order, "user"):
        return getattr(order, "user")
    return None


# ===================================================================
# 1. MAIN PHARMACY DASHBOARD VIEW
# ===================================================================
@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def pharmacy_dashboard(request):
    # Avoid creating Pharmacy row with invalid blanks in required fields.
    # Keep defaults minimal and safe.
    pharmacy, created = Pharmacy.objects.get_or_create(
        user=request.user,
        defaults={
            "email": request.user.email,
            "is_verified": False,
            # other non-null fields are expected to be filled via profile update
        },
    )

    # --- Profile Update Logic (Ajax)
    if request.method == "POST" and request.headers.get("X-Requested-With") == "XMLHttpRequest":
        try:
            pharmacy.name = request.POST.get("name", pharmacy.name)
            pharmacy.owner_name = request.POST.get("owner_name", pharmacy.owner_name)
            pharmacy.email = request.POST.get("email", pharmacy.email)
            pharmacy.phone = request.POST.get("phone", pharmacy.phone)
            pharmacy.address = request.POST.get("address", pharmacy.address)
            pharmacy.city = request.POST.get("city", pharmacy.city)
            pharmacy.pin_code = request.POST.get("pin_code", pharmacy.pin_code)
            pharmacy.license_number = request.POST.get("license_number", pharmacy.license_number)
            pharmacy.gst_number = request.POST.get("gst_number", pharmacy.gst_number)
            pharmacy.operating_hours = request.POST.get("operating_hours", pharmacy.operating_hours)

            if request.FILES.get("logo"):
                pharmacy.logo = request.FILES["logo"]

            # Address/city save hote hi automatic geocoding (lat/lng) — no manual entry needed
            lat, lng = geocode_address(pharmacy.address, pharmacy.city)
            if lat is not None and lng is not None:
                pharmacy.latitude = lat
                pharmacy.longitude = lng

            pharmacy.save()
            return JsonResponse({"status": "success", "message": "Profile updated successfully"})
        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=400)

    # --- Data Fetching
    prescriptions_list = Prescription.objects.filter(pharmacy=request.user).order_by('-created_at')
    medicines = Medicine.objects.filter(user=request.user, is_banned=False).order_by("-id")
    orders_list = Order.objects.filter(pharmacy=pharmacy)

    # Orders -> JSON for dashboard (used by JS rendering; keeps UI DB-synced)
    # Keep values UI-friendly; status casing may vary in DB so we normalize for display only.
    orders_data = [
        {
            "id": str(o.order_id) if hasattr(o, "order_id") else str(o.id),
            "customer": (getattr(getattr(o, "customer", None), "user", None) and (getattr(o.customer.user, "get_full_name", None)() if hasattr(o.customer.user, "get_full_name") else o.customer.user.username)) or str(getattr(o, "customer", "")),

            "date": o.created_at.strftime('%Y-%m-%d') if getattr(o, "created_at", None) else None,
            "amount": float(getattr(o, "total_amount", 0) or 0),
            "status": o.status or "Pending",
        }
        for o in orders_list
    ]


    # Use logger instead of print.
    logger.debug(
        "MediFlex Dashboard for %s: prescriptions=%s",
        getattr(request.user, "username", "unknown"),
        prescriptions_list.count(),
    )

    # --- Sales & Analytics (live, DB-driven — no static/mock numbers)
    delivered_orders = orders_list.filter(status='Delivered')

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    current_period_orders = delivered_orders.filter(created_at__gte=thirty_days_ago)
    previous_period_orders = delivered_orders.filter(created_at__gte=sixty_days_ago, created_at__lt=thirty_days_ago)

    current_sales = current_period_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    previous_sales = previous_period_orders.aggregate(total=Sum('total_amount'))['total'] or Decimal('0')

    current_orders_count = current_period_orders.count()
    previous_orders_count = previous_period_orders.count()

    def _pct_change(current, previous):
        current = float(current)
        previous = float(previous)
        if previous > 0:
            return round(((current - previous) / previous) * 100, 1)
        return 0.0

    sales_change = _pct_change(current_sales, previous_sales)
    order_change = _pct_change(current_orders_count, previous_orders_count)

    current_aov = (float(current_sales) / current_orders_count) if current_orders_count else 0.0
    previous_aov = (float(previous_sales) / previous_orders_count) if previous_orders_count else 0.0
    aov_change = _pct_change(current_aov, previous_aov)

    # Top category + top selling medicines, based on real order items (last 30 days)
    order_items = OrderItem.objects.filter(order__in=current_period_orders).select_related('product')

    category_sales = {}
    item_sales = {}
    total_item_revenue = Decimal('0')

    for item in order_items:
        revenue = (item.price or Decimal('0')) * item.quantity
        total_item_revenue += revenue

        cat = item.product.category if item.product_id else "Uncategorized"
        category_sales[cat] = category_sales.get(cat, Decimal('0')) + revenue

        key = item.product_id
        if key not in item_sales:
            item_sales[key] = {
                "name": item.product.name if item.product_id else "Unknown",
                "brand": item.product.brand if item.product_id else "",
                "units_sold": 0,
            }
        item_sales[key]["units_sold"] += item.quantity

    top_category = "N/A"
    top_category_sales_pct = 0.0
    if category_sales:
        top_category = max(category_sales, key=category_sales.get)
        if total_item_revenue > 0:
            top_category_sales_pct = round(float(category_sales[top_category]) / float(total_item_revenue) * 100, 1)

    top_selling_items = sorted(item_sales.values(), key=lambda x: x["units_sold"], reverse=True)[:5]

    # Last 6 months trend for the Sales Performance chart
    year, month = now.year, now.month
    month_points = []
    for _ in range(6):
        month_points.append((year, month))
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    month_points.reverse()

    chart_labels, chart_sales, chart_orders = [], [], []
    for (y, m) in month_points:
        month_agg = delivered_orders.filter(created_at__year=y, created_at__month=m).aggregate(
            total=Sum('total_amount'), count=Count('id')
        )
        chart_labels.append(month_abbr[m])
        chart_sales.append(float(month_agg['total'] or 0))
        chart_orders.append(month_agg['count'] or 0)

    analytics_data = {
        "total_sales": f"{current_sales:,.2f}",
        "total_orders": current_orders_count,
        "sales_change": sales_change,
        "order_change": order_change,
        "aov": f"{current_aov:,.2f}",
        "aov_change": aov_change,
        "top_category": top_category,
        "top_category_sales": top_category_sales_pct,
        "top_selling_items": top_selling_items,
        "chart_labels": chart_labels,
        "chart_sales": chart_sales,
        "chart_orders": chart_orders,
    }

    context = {
        "pharmacy": pharmacy,
        "is_verified": pharmacy.is_verified,
        "base_template": get_base_template(request),
        "medicine_form": MedicineForm(),
        "inventory_list": medicines,
        "analytics": analytics_data,
        "analytics_chart": {
            "labels": chart_labels,
            "sales": chart_sales,
            "orders": chart_orders,
        },
        "current_time": now,
        "prescriptions": prescriptions_list,
        "total_requests": prescriptions_list.count(),
        "pending_count": prescriptions_list.filter(status='pending').count(),
        "quoted_count": prescriptions_list.filter(status='approved').count(),
        "rejected_count": prescriptions_list.filter(status='rejected').count(),
        "all_medicines": medicines,
        "orders": orders_list.order_by('-created_at'),
        "orders_data": orders_data,
        "total_orders_count": orders_list.count(),

        "order_pending_count": orders_list.filter(status='Pending').count(),
        "order_approved_count": orders_list.filter(status='Approved').count(),
        "order_ready_count": orders_list.filter(status='Ready').count(),
        "order_delivered_count": orders_list.filter(status='Delivered').count(),
    }

    context.update({
        "total_count": medicines.count(),
        "low_stock_count": medicines.filter(stock_quantity__lt=10, stock_quantity__gt=0).count(),
        "out_of_stock_count": medicines.filter(stock_quantity=0).count(),
        "in_stock_count": medicines.filter(stock_quantity__gte=10).count(),
        "categories_count": medicines.values('category').distinct().count(),
    })

    return render(request, "dashboards/pharmacy_dashboard.html", context)


# ===================================================================
# 2. CHANGE ORDER STATUS CONTROLLER
# ===================================================================
@login_required
@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def change_order_status(request, order_id, action):
    try:
        pharmacy = request.user.pharmacy
        order = get_object_or_404(Order, order_id=order_id, pharmacy=pharmacy)

        if action == 'approve':
            order.status = 'Approved'
            msg_content = f"Your PharmaHub Order ({order.order_id}) has been Approved by the pharmacy!"
        elif action == 'reject':
            order.status = 'Rejected'
            msg_content = f"We are sorry. Your PharmaHub Order ({order.order_id}) has been Rejected by the pharmacy."

            # ✅ Stock restore on reject (important for order flow correctness)
            # Restore each item's quantity back to inventory.
            for item in order.items.all():
                med = item.product
                med.stock_quantity = (med.stock_quantity or 0) + item.quantity
                med.save()

            # Mark payment as failed (payment wasn't delivered)
            try:
                if hasattr(order, 'payment') and order.payment:
                    order.payment.status = 'failed'
                    order.payment.save()
            except Exception:
                pass

            # Also update order-level payment_status if field exists
            if hasattr(order, 'payment_status'):
                order.payment_status = 'failed'


        elif action == 'ready':
            order.status = 'Ready'
            msg_content = f"Good news! Your Order ({order.order_id}) is Ready for pickup/delivery."
        elif action == 'deliver':
            order.status = 'Delivered'
            msg_content = f"Thank you! Your Order ({order.order_id}) has been successfully Delivered."

            # ✅ COD delivered -> payment_status should become paid (DB may store 'Cash on Delivery' or 'COD')
            try:
                p_method = str(getattr(order, 'payment_method', '') or '').lower().strip()
                is_cod = ('cash on delivery' in p_method) or (p_method == 'cod') or (p_method.startswith('cod'))

                if is_cod and getattr(order, 'payment_status', None) != 'paid':
                    order.payment_status = 'paid'
                    order.save(update_fields=['payment_status'])
            except Exception as e:
                logger.error(f"Failed to update order.payment_status for deliver: {e}")

            # ✅ Also sync Payment row status if it exists
            try:
                if hasattr(order, 'payment') and order.payment:
                    p_method = str(getattr(order, 'payment_method', '') or '').lower().strip()
                    is_cod = ('cash on delivery' in p_method) or (p_method == 'cod') or (p_method.startswith('cod'))

                    if is_cod and getattr(order.payment, 'status', None) != 'success':
                        order.payment.status = 'success'
                        order.payment.save(update_fields=['status'])
            except Exception as e:
                logger.error(f"Failed to sync order.payment.status for deliver: {e}")


        else:
            messages.error(request, "Invalid action.")
            from django.urls import reverse
            referer = request.META.get('HTTP_REFERER')
            fallback = reverse('dashboards:pharmacy_dashboard') + '#orders'
            return redirect(referer or fallback)

        order.save()

        customer_user = _get_order_customer_user(order)
        if customer_user:
            send_customer_notification(
                customer_user=customer_user,
                message=msg_content,
                order=order,
            )

        messages.success(request, f"Order {order.order_id} status successfully transitioned to '{order.status}'!")
    except Exception as e:
        logger.exception("change_order_status failed")
        messages.error(request, f"Error routing order control: {str(e)}")

    from django.urls import reverse
    referer = request.META.get('HTTP_REFERER')
    fallback = reverse('dashboards:pharmacy_dashboard') + '#orders'
    return redirect(referer or fallback)



# ===================================================================
# 3. PHARMACY NOTIFICATIONS VIEWS
# ===================================================================
@login_required
@role_required('pharmacy', 'pharmacist')
def pharmacy_notifications(request):

    notifications_qs = PharmacyNotification.objects.filter(user=request.user).order_by('-created_at')

    # Evaluate queryset before marking read (avoid template mismatch)
    notifications_list = list(notifications_qs)

    PharmacyNotification.objects.filter(user=request.user, is_read=False).update(is_read=True)

    context = {
        'notifications': notifications_list,
        'base_template': get_base_template(request),
    }

    return render(request, 'dashboards/pharmacy_notifications.html', context)


@login_required
@require_POST
def clear_all_notifications_api(request):
    try:
        deleted_count, _ = PharmacyNotification.objects.filter(user=request.user).delete()
        logger.info("Deleted %s pharmacy notifications for %s", deleted_count, request.user)
        return JsonResponse({
            'success': True,
            'message': 'All pharmacy notifications cleared successfully!',
        })
    except Exception as e:
        logger.exception("clear_all_notifications_api failed")
        return JsonResponse({
            'success': False,
            'message': str(e),
        }, status=500)


# ===================================================================
# 4. INVENTORY MANAGEMENT (ADD/EDIT/DELETE/BULK UPLOAD)
# ===================================================================
@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
@require_http_methods(["POST"])
def add_edit_medicine(request):
    if not request.user.pharmacy.is_verified:
        return redirect("/pharmacy_dashboard/?tab=profile")

    medicine_id = request.POST.get("medicine_id")
    if medicine_id:
        medicine = get_object_or_404(Medicine, id=medicine_id, user=request.user)
    else:
        medicine = Medicine(user=request.user, pharmacy=request.user.pharmacy)

    medicine.pharmacy = request.user.pharmacy

    form = MedicineForm(request.POST, request.FILES, instance=medicine)
    if form.is_valid():
        form.save()
        messages.success(request, "Medicine saved successfully.")
    else:
        messages.error(request, f"Invalid medicine data: {form.errors}")

    return redirect("/pharmacy_dashboard/?tab=inventory")


@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
@require_http_methods(["POST"])
def delete_medicine(request, pk):
    if not request.user.pharmacy.is_verified:
        return redirect("/pharmacy_dashboard/?tab=profile")

    medicine = get_object_or_404(Medicine, pk=pk, user=request.user)
    medicine.delete()
    messages.success(request, "Medicine deleted.")
    return redirect("/pharmacy_dashboard/?tab=inventory")


@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
@require_http_methods(["POST"])
def delete_all_medicines(request):
    """Bulk-delete every medicine belonging to the logged-in pharmacy user
    in one click. Same ownership scoping as delete_medicine (user=request.user)
    so a pharmacy can only ever wipe its own inventory, never another
    pharmacy's. Deleting here removes the rows from the one live Medicine
    table, so the customer search/cart pages and the admin Medicine Control
    panel (which both read from this same table/API) drop the items too --
    nothing extra to sync."""
    if not request.user.pharmacy.is_verified:
        return redirect("/pharmacy_dashboard/?tab=profile")

    deleted_count, _ = Medicine.objects.filter(user=request.user).delete()
    if deleted_count:
        messages.success(request, f"Deleted {deleted_count} medicine(s) from your inventory.")
    else:
        messages.info(request, "Your inventory was already empty.")
    return redirect("/pharmacy_dashboard/?tab=inventory")


@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def bulk_upload_medicine(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        file = request.FILES['excel_file']
        try:
            df = pd.read_excel(file) if not file.name.endswith('.csv') else pd.read_csv(file)
            df.columns = [str(c).strip() for c in df.columns]
            df = df.fillna("")

            success_count = 0
            for index, row in df.iterrows():
                try:
                    name = row.get('Name')
                    if not name or str(name).strip() == "":
                        continue

                    raw_date = row.get('Expiry')
                    clean_date = None
                    if raw_date:
                        if isinstance(raw_date, pd.Timestamp):
                            clean_date = raw_date.date()
                        else:
                            try:
                                clean_date = pd.to_datetime(raw_date).date()
                            except Exception:
                                clean_date = None

                    # Medicine.expiry_date is non-nullable in models; skip row if date missing
                    if clean_date is None:
                        logger.warning("Skipping row %s due to invalid expiry_date", index)
                        continue

                    medicine = Medicine(
                        user=request.user,
                        pharmacy=request.user.pharmacy,
                        name=str(name).strip(),
                        brand=str(row.get('Brand', "")).strip(),
                        category=str(row.get('Category', "General Items")).strip(),
                        price=float(row.get('Price')) if row.get('Price') not in ("", None) else 0,
                        stock_quantity=int(row.get('Stock')) if row.get('Stock') not in ("", None) else 0,
                        expiry_date=clean_date,
                    )

                    img_url = row.get('Image_URL')
                    if img_url and str(img_url).startswith('http'):
                        try:
                            res = requests.get(img_url, timeout=5)
                            if res.status_code == 200:
                                f_name = f"med_{index}_{request.user.id}.jpg"
                                medicine.image.save(f_name, ContentFile(res.content), save=False)
                        except Exception as img_e:
                            logger.info("Image download failed at row %s: %s", index, img_e)

                    medicine.save()
                    success_count += 1

                except Exception as row_e:
                    logger.exception("bulk_upload_medicine row error index=%s", index)
                    continue

            if success_count > 0:
                messages.success(request, f"Successfully uploaded {success_count} medicines to your inventory.")
            else:
                messages.warning(
                    request,
                    "No valid data found in the file. Please check your column headers and data format.",
                )

        except Exception as e:
            logger.exception("bulk_upload_medicine failed")
            messages.error(request, f"An error occurred while processing the file: {str(e)}")

    return redirect("/pharmacy_dashboard/?tab=inventory")


@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def get_medicine_data(request, pk):
    medicine = get_object_or_404(Medicine, pk=pk, user=request.user)
    data = {
        "id": medicine.id,
        "name": medicine.name,
        "brand": medicine.brand,
        "category": medicine.category,
        "price": str(medicine.price),
        "stock_quantity": medicine.stock_quantity,
        "expiry_date": medicine.expiry_date.strftime("%Y-%m-%d") if medicine.expiry_date else "",
        "batch_number": medicine.batch_number or "",
        "description": medicine.description or "",
        "image_url": medicine.image.url if medicine.image else None,
    }
    return JsonResponse(data)


@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def download_inventory_template(request):
    headers = ['Name', 'Brand', 'Category', 'Price', 'Stock', 'Expiry', 'Image_URL']
    df = pd.DataFrame(columns=headers)
    df.loc[0] = ['Panadol', 'GSK', 'Painkillers', '50.00', '100', '2026-12-31', 'https://example.com/image.jpg']

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template')

    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=pharmacy_inventory_template.xlsx'
    return response


# ===================================================================
# 5. PRESCRIPTION REVIEWS & VERIFICATION PROCEDURES
# ===================================================================
@role_required('pharmacy', 'pharmacist')
@verification_required
def medicine_list(request):
    # Provide a real response instead of pass.
    prescriptions = Prescription.objects.filter(pharmacy=request.user).order_by('-created_at')
    context = {
        'prescriptions': prescriptions,
        'base_template': get_base_template(request),
    }
    return render(request, "dashboards/pharmacy_prescription_list.html", context)


@role_required('pharmacy', 'pharmacist')
@login_required
@verification_required
def review_prescription(request, pk):
    prescription = get_object_or_404(Prescription, id=pk, pharmacy=request.user)

    if request.method == "POST":
        medicines_json = request.POST.get('medicines_json')
        if medicines_json:
            prescription.quote_items.all().delete()
            selected_data = json.loads(medicines_json)

            for item in selected_data:
                med_obj = get_object_or_404(Medicine, id=item['id'])
                QuoteItem.objects.create(
                    prescription=prescription,
                    medicine=med_obj,
                    price_at_quote=med_obj.price,
                    quantity=1,
                )

            prescription.status = 'approved'
            prescription.save()

            msg_content = (
                f"Good news! The pharmacy has approved your prescription PRX-{prescription.id} and sent a price quote. "
                "Please review it on your dashboard."
            )
            customer_user = prescription.customer
            if hasattr(customer_user, 'user'):
                customer_user = customer_user.user

            send_customer_notification(
                customer_user=customer_user,
                message=msg_content,
                prescription=prescription,
            )

            CustomerNotification.objects.create(
                user=prescription.customer,
                prescription=prescription,
                message=f"Good news! Pharmacy has approved PRX-{prescription.id} and sent a quote.",
            )

            messages.success(request, f"Quote successfully sent to {prescription.customer.username}")
            return redirect('dashboards:pharmacy_dashboard')

    all_medicines = Medicine.objects.filter(user=request.user, is_banned=False).order_by('-id')
    context = {
        'p': prescription,
        'all_medicines': all_medicines,
    }
    return render(request, "dashboards/review_prescription.html", context)


@role_required('pharmacy', 'pharmacist')
def reject_prescription(request, pk):
    prescription = get_object_or_404(Prescription, id=pk, pharmacy=request.user)

    if request.method == "POST":
        reason = request.POST.get('rejection_reason')
        custom_msg = request.POST.get('custom_rejection_msg')
        final_reason = (custom_msg if reason == "Other" else reason) or "No reason provided"

        prescription.status = 'rejected'
        prescription.rejection_reason = final_reason
        prescription.save()

        msg_content = f"Your prescription PRX-{prescription.id} was rejected by the pharmacy. Reason: {final_reason}"
        customer_user = prescription.customer
        if hasattr(customer_user, 'user'):
            customer_user = customer_user.user

        send_customer_notification(
            customer_user=customer_user,
            message=msg_content,
            prescription=prescription,
        )

        CustomerNotification.objects.create(
            user=prescription.customer,
            prescription=prescription,
            message=f"Prescription PRX-{prescription.id} was rejected. Reason: {final_reason}",
        )

        messages.error(request, f"Prescription #{pk} has been rejected.")

    return redirect('dashboards:pharmacy_dashboard')


@login_required
def submit_verification(request):
    if request.method == 'POST':
        try:
            pharmacy = request.user.pharmacy
            license_no = request.POST.get('license_number')
            gst_no = request.POST.get('gst_number')
            license_file = request.FILES.get('license_document')

            if license_no and license_file:
                pharmacy.license_number = license_no
                pharmacy.gst_number = gst_no
                pharmacy.license_document = license_file
                pharmacy.verification_status = 'pending'
                pharmacy.submitted_at = timezone.now()
                pharmacy.is_verified = False
                pharmacy.save()

                messages.success(request, "Documents submitted! Admin will notify you soon.")
            else:
                messages.error(request, "Please fill required fields and upload document.")

        except Exception:
            messages.error(request, "Pharmacy profile not found.")

    return redirect('dashboards:pharmacy_dashboard')


@role_required('pharmacy', 'pharmacist')
def pharmacy_home(request):
    return render(request, "dashboards/pharmacy_home.html")


# ===================================================================
# 6. CUSTOMER-FACING WRAPPERS
# ===================================================================
def customer_medicine(request):
    return pages_views.medicine(request)


def customer_about(request):
    return pages_views.about(request)


def customer_pharmacies(request):
    return pages_views.pharmacies(request)


def customer_contact(request):
    return pages_views.contact(request)


# ===================================================================
# PHARMACY ORDER DETAILS MODAL API (used by pharmacy_dashboard.html)
# ===================================================================
@login_required
@role_required('pharmacy', 'pharmacist', 'admin', 'super_admin')
def get_order_details_api(request, order_id):
    """Serialize pharmacy-owned order details + items for modal rendering."""
    try:
        pharmacy = request.user.pharmacy
        order = get_object_or_404(Order, order_id=order_id, pharmacy=pharmacy)

        items_data = []
        # order.items is expected related name (OrderItem)
        for item in order.items.all():
            product = getattr(item, 'product', None)
            items_data.append({
                'name': getattr(product, 'name', '') or '',
                'brand': getattr(product, 'brand', 'Generic') or 'Generic',
                'quantity': getattr(item, 'quantity', 0) or 0,
                'price': float(getattr(item, 'price', 0) or 0),
                'total': float((getattr(item, 'price', 0) or 0) * (getattr(item, 'quantity', 0) or 0)),
            })

        created_at = getattr(order, 'created_at', None)
        created_at_str = created_at.strftime('%Y-%m-%d %I:%M %p') if created_at else ''

        data = {
            'success': True,
            'order_id': order.order_id,
            'customer_name': getattr(order, 'full_name', '') or '',
            'phone': getattr(order, 'phone', '') or '',
            'address': getattr(order, 'address', '') or '',
            'notes': getattr(order, 'notes', '') or 'No special instructions provided by customer.',
            'total_amount': float(getattr(order, 'total_amount', 0) or 0),
            'status': getattr(order, 'status', '') or '',
            'payment_method': getattr(order, 'payment_method', '') or '',
            'created_at': created_at_str,
            'items': items_data,
        }
        return JsonResponse(data)
    except Exception as e:
        logger.exception('get_order_details_api failed')
        return JsonResponse({'success': False, 'message': str(e)}, status=400)