# dashboards/utils.py
import requests
from django.core.mail import send_mail
from django.conf import settings
from dashboards.models import PharmacyNotification
from customers_d.models import CustomerNotification


def _nominatim_lookup(query):
    """Single Nominatim lookup. Returns (lat, lng) or (None, None)."""
    query = (query or "").strip()
    if not query:
        return None, None

    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 1},
            # Nominatim usage policy requires an identifying User-Agent —
            # generic ones get silently rate-limited/blocked.
            headers={"User-Agent": "PharmaHub-FYP-App/1.0 (contact: support@pharmahub.local)"},
            timeout=6,
        )
        response.raise_for_status()
        results = response.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed for '{query}': {e}")

    return None, None


def geocode_address(address, city="", country="Pakistan"):
    """
    Address ko lat/lng mein convert karta hai OpenStreetMap ki free
    Nominatim API se (koi API key nahi chahiye).

    Nominatim ek galat/incomplete street address par POORI query fail kar
    deta hai (e.g. "Farooq Brothers, <messy street>" jaisi entries), chahe
    city sahi ho. Isliye agar full address+city+country query fail ho,
    to progressively kam-specific queries try karte hain (city+country,
    phir sirf city) taake kam se kam ek approximate/city-level pin mil
    jaye — poora "manually enter coordinates" pe bhejne se behtar hai.
    """
    address = (address or "").strip()
    city = (city or "").strip()
    country = (country or "").strip()

    candidate_queries = []
    full = ", ".join(part for part in [address, city, country] if part)
    if full:
        candidate_queries.append(full)

    city_level = ", ".join(part for part in [city, country] if part)
    if city_level and city_level not in candidate_queries:
        candidate_queries.append(city_level)

    if not candidate_queries:
        return None, None

    for query in candidate_queries:
        lat, lng = _nominatim_lookup(query)
        if lat is not None and lng is not None:
            return lat, lng

    return None, None

def send_pharmacy_notification(pharmacy_user, message, prescription=None, order=None):
    """
    Pharmacy user ko dashboard notification aur automatic email bhejna.
    """
    # 1. Database mein notification save karna
    PharmacyNotification.objects.create(
        user=pharmacy_user,
        message=message,
        prescription=prescription,
        order=order
    )
    
    # 2. Email Notification bhejna
    subject = "PharmaHub: New Dashboard Alert"
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[pharmacy_user.email],
            fail_silently=True
        )
        print(f"Notification Email sent successfully to Pharmacy: {pharmacy_user.email}")
    except Exception as e:
        print(f"Email sending failed for Pharmacy: {e}")


def send_customer_notification(customer_user, message, prescription=None, order=None):
    """
    Customer user ko dashboard notification aur automatic email bhejna.
    """
    # 1. Database mein notification save karna
    CustomerNotification.objects.create(
        user=customer_user,
        message=message,
        prescription=prescription,
        # Agar aap ne CustomerNotification mein order ki field add ki hui hai, to isko uncomment kar lein:
        # order=order 
    )
    
    # 2. Email Notification bhejna
    subject = "PharmaHub: Order & Prescription Update"
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_user.email],
            fail_silently=True
        )
        print(f"Notification Email sent successfully to Customer: {customer_user.email}")
    except Exception as e:
        print(f"Email sending failed for Customer: {e}")