from django.shortcuts import render
from pages.views import get_base_template  # Pages app se function mangwa lain

def index(request):
    return render(request, 'pharmacy/index.html', {
        "base_template": get_base_template(request)
    })

# Baaki views (about, medicines, etc.) yahan se delete kar dein 
# Kyunke wo ab Pages app handle kar rahi hai!