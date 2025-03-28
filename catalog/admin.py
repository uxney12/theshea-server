from django.contrib import admin
from .models import Supplier, Category, Material, Inventory, Order, OrderLine, Receipt, ReceiptLine, Issue, ProductCategory, ProductType, Collection, Size, Color, Design, SKU, InventorySKU, QC, Import, ImportLine, Export, ExportLine, Employee, ColorInDesign, SizeInDesign, Progress, Message

admin.site.register(Supplier)
admin.site.register(Category)
admin.site.register(Material)
admin.site.register(Inventory)
admin.site.register(Order)
admin.site.register(OrderLine)
admin.site.register(Receipt)
admin.site.register(ReceiptLine)
admin.site.register(Issue)
admin.site.register(ProductCategory)
admin.site.register(ProductType)
admin.site.register(Collection)
admin.site.register(Size)
admin.site.register(Color)
admin.site.register(Design)
admin.site.register(ColorInDesign)
admin.site.register(SizeInDesign)
admin.site.register(SKU)
admin.site.register(InventorySKU)
admin.site.register(QC)
admin.site.register(Import)
admin.site.register(ImportLine)
admin.site.register(Export)
admin.site.register(ExportLine)
admin.site.register(Employee)
admin.site.register(Progress)
admin.site.register(Message)
