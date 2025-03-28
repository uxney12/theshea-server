from django.db.models import F
from .models import Material, InventorySKU, SKU

def low_stock_alert(request):
    low_stock_count = Material.objects.filter(
        inventory__quantity__lt=F('stock_min')
    ).count()
    
    low_stock_sku_count = InventorySKU.objects.filter(
        quantity__lt=2
    ).count()
    
    return {
        'low_stock_count': low_stock_count,
        'low_stock_sku_count': low_stock_sku_count
    }
