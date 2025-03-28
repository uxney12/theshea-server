from django.db import models

class Category(models.Model):
    category_code = models.CharField(max_length=255)
    category_name = models.CharField(max_length=1000, null=True, blank=True)
    description = models.CharField(max_length=10000, null=True, blank=True)

    def __str__(self):
        return f'{self.category_code} - {self.category_name}'


class Supplier(models.Model):
    supplier_code = models.CharField(max_length=255)
    supplier_name = models.CharField(max_length=1000, null=True, blank=True)
    category = models.ForeignKey('Category', on_delete=models.RESTRICT, null=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    facebook =  models.CharField(max_length=255, null=True, blank=True)
    website =  models.CharField(max_length=255, null=True, blank=True)
    address = models.CharField(max_length=10000, null=True, blank=True)
    notes = models.CharField(max_length=10000, null=True, blank=True)

    def __str__(self):
        return f'{self.supplier_code} - {self.supplier_name}'


class Material(models.Model):
    material_code = models.CharField(max_length=255)
    material_name = models.CharField(max_length=1000, null=True, blank=True)
    image = models.ImageField(upload_to='material_images/', null=True, blank=True)
    types = models.CharField(max_length=255, null=True, blank=True)
    color = models.CharField(max_length=255, null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.RESTRICT, null=True)
    notes = models.CharField(max_length=10000, null=True, blank=True)
    stock_min = models.PositiveIntegerField(default=0) 
    stock_max = models.PositiveIntegerField(default=0)  

    def __str__(self):
        return f'{self.material_code} - {self.material_name}'



class Inventory(models.Model):
    material = models.ForeignKey('Material', on_delete=models.RESTRICT, null=True)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.material} - {self.quantity}"


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    order_code = models.CharField(max_length=255)
    order_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.RESTRICT, null=True)
    expected_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=255, null=True, blank=True)
    total_quantity = models.IntegerField(null=True, blank=True)
    total_amount = models.FloatField(null=True, blank=True)
    prepaid = models.FloatField(null=True, blank=True)  
    note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='completed')

    def __str__(self):
        return f'{self.order_code} - {self.total_amount}'



class OrderLine(models.Model):
    order = models.ForeignKey('Order', on_delete=models.RESTRICT, null=True)
    order_line_code = models.CharField(max_length=255, null=True)
    material = models.ForeignKey('Material', on_delete=models.RESTRICT, null=True)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)
    unit_of_measure = models.CharField(max_length=255)
    total = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f'{self.order.order_code} - {self.order_line_code} - {self.material.material_code}'


class Receipt(models.Model):
    RECEIPT_STATUS_CHOICES = [
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    receipt_code = models.CharField(max_length=255) 
    receipt_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey('Supplier', on_delete=models.RESTRICT, null=True) 
    order = models.ForeignKey('Order', on_delete=models.RESTRICT, null=True, blank=True) 
    subtotal = models.FloatField(null=True, blank=True)  
    shipping_fee = models.FloatField(null=True, blank=True)  
    vat_fee = models.FloatField(null=True, blank=True)  
    total_quantity = models.IntegerField(null=True, blank=True)
    total_amount = models.FloatField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=RECEIPT_STATUS_CHOICES, default='completed')

    def __str__(self):
        return f'{self.receipt_code} - {self.total_amount}'


class ReceiptLine(models.Model):
    receipt = models.ForeignKey('Receipt', on_delete=models.RESTRICT, null=True)  
    receipt_line_code = models.CharField(max_length=255, null=True)
    material = models.ForeignKey('Material', on_delete=models.RESTRICT, null=True)
    quantity = models.IntegerField(null=True, blank=True)
    price = models.IntegerField(null=True, blank=True)
    unit_of_measure = models.CharField(max_length=255)
    total = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f'{self.receipt.receipt_code} - {self.receipt_line_code} - {self.material.material_code}'


class Issue(models.Model):
    RECEIPT_STATUS_CHOICES = [
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    issue_code = models.CharField(max_length=50, unique=True)
    issue_date = models.DateField(null=True, blank=True)
    tailor = models.ForeignKey('Employee', on_delete=models.RESTRICT, null=True)  
    design_code = models.ForeignKey('Design', on_delete=models.RESTRICT, null=True)  
    sku_code = models.CharField(max_length=255, null=True, blank=True) 
    sku_name = models.ForeignKey('SKU', on_delete=models.RESTRICT, null=True)  
    color = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=20, null=True, blank=True)
    sewing_type = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    main_fabric = models.ForeignKey('Material', on_delete=models.RESTRICT, null=True, related_name='main_fabric_set')  
    lining_fabric = models.ForeignKey('Material', on_delete=models.RESTRICT, null=True, related_name='lining_fabric_set')  
    main_fabric_meters = models.FloatField(null=True, blank=True)
    lining_fabric_meters = models.FloatField(null=True, blank=True)
    status =  models.CharField(max_length=10, choices=RECEIPT_STATUS_CHOICES, default='completed')
    
    def __str__(self):
        return f"{self.issue_code} - {self.sku_code}"


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


class ProductCategory(models.Model): 
    category_code = models.CharField(max_length=10)  
    category_name = models.CharField(max_length=255) 

    def __str__(self):
        return f'{self.category_code} - {self.category_name}'


class ProductType(models.Model):  
    type_code = models.CharField(max_length=10) 
    type_name = models.CharField(max_length=255) 

    def __str__(self):
        return f'{self.type_code} - {self.type_name}'


class Collection(models.Model): 
    collection_code = models.CharField(max_length=10)  
    collection_name = models.CharField(max_length=255) 
    style = models.CharField(max_length=255, null=True, blank=True) 
    description = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f'{self.collection_code} - {self.collection_name}'


class Color(models.Model):
    color_code = models.CharField(max_length=10)  
    ordering_color = models.CharField(max_length=10)  
    color_name = models.CharField(max_length=100)

    def __str__(self):
        return f'{self.color_code} - {self.ordering_color} - {self.color_name}'


class Size(models.Model):  
    size_code = models.CharField(max_length=10) 
    size_name = models.CharField(max_length=10)  

    def __str__(self):
        return f'{self.size_code} - {self.size_name}'


class Design(models.Model):
    design_code = models.CharField(max_length=10)  
    design_name = models.CharField(max_length=255)
    employee = models.ForeignKey('Employee', on_delete=models.RESTRICT,null=True, blank=True)  
    product_type = models.ForeignKey('ProductType', on_delete=models.RESTRICT, null=True, blank=True)  
    product_category = models.ForeignKey('ProductCategory', on_delete=models.RESTRICT, null=True, blank=True)  
    collection = models.ForeignKey('Collection', on_delete=models.RESTRICT, null=True, blank=True)
    is_set = models.BooleanField(default=False, null=True, blank=True)
    image = models.ImageField(upload_to='design_images/', blank=True, null=True)
    description = models.CharField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return f'{self.design_code} - {self.design_name}'


class ColorInDesign(models.Model):
    color = models.ForeignKey('Color', on_delete=models.RESTRICT, null=True)  
    design = models.ForeignKey('Design', on_delete=models.RESTRICT, null=True)  

    def __str__(self):
        return f'{self.color.color_name} - {self.design.design_name}'

class SizeInDesign(models.Model):
    size = models.ForeignKey('Size', on_delete=models.RESTRICT, null=True)  
    design = models.ForeignKey('Design', on_delete=models.RESTRICT, null=True)  

    def __str__(self):
        return f'{self.size.size_name} - {self.design.design_name}'


class SKU(models.Model):
    sku_code = models.CharField(max_length=10)  
    sku_name = models.CharField(max_length=255)
    design = models.ForeignKey('Design', on_delete=models.RESTRICT)  
    color = models.ForeignKey('Color', on_delete=models.RESTRICT)  
    size = models.ForeignKey('Size', on_delete=models.RESTRICT)  
    image = models.ImageField(upload_to='sku_images/', blank=True, null=True)

    def __str__(self):
        return f'{self.sku_code} - {self.sku_name}'


class InventorySKU(models.Model):
    sku = models.ForeignKey('SKU', on_delete=models.RESTRICT, null=True)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.sku} - {self.quantity}"


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

class QC(models.Model):
    ORDER_STATUS_CHOICES = [
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    qc_code = models.CharField(max_length=10)  
    qc_date = models.DateField(null=True, blank=True)
    employee = models.ForeignKey('Employee', on_delete=models.RESTRICT, null=True, blank=True)  
    sku = models.ForeignKey('SKU', on_delete=models.RESTRICT, null=True, blank=True)  
    quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=255, null=True, blank=True) 
    order_status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='completed') 
    note = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return f'{self.qc_code} - {self.qc_date}'


class Import(models.Model):
    ORDER_STATUS_CHOICES = [
    ('completed', 'Hoàn thành'),
    ('cancelled', 'Đã hủy'),
    ]

    import_code = models.CharField(max_length=10)  
    import_date = models.DateField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='completed') 
    note = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return f'{self.import_code} - {self.import_date}'


class ImportLine(models.Model):
    import_obj = models.ForeignKey('Import', on_delete=models.RESTRICT, null=True)  
    import_line_code = models.CharField(max_length=10)  
    sku = models.ForeignKey('SKU', on_delete=models.RESTRICT, null=True)  
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.import_obj.import_code} - {self.import_line_code} - {self.sku.sku_code}'


class Export(models.Model):
    ORDER_STATUS_CHOICES = [
        ('completed', 'Hoàn thành'),
        ('cancelled', 'Đã hủy'),
    ]

    export_code = models.CharField(max_length=10)
    export_date = models.DateField(null=True, blank=True)
    total = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='completed')
    note = models.CharField(max_length=1000, null=True, blank=True)

    def __str__(self):
        return f'{self.export_code} - {self.export_date}'


class ExportLine(models.Model):
    export_obj = models.ForeignKey('Export', on_delete=models.RESTRICT, null=True)
    export_line_code = models.CharField(max_length=10)
    sku = models.ForeignKey('SKU', on_delete=models.RESTRICT, null=True)
    quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f'{self.export_obj.export_code} - {self.export_line_code} - {self.sku.sku_code}'


class Employee(models.Model):
    STATUS_CHOICES = [
        ('active', 'Đang làm việc'),
        ('inactive', 'Đã nghỉ việc'),
    ]

    employee_code = models.CharField(max_length=10, unique=True)
    employee_name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, null=True, blank=True)
    department = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    employment_status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    image = models.ImageField(upload_to='employee_images/', null=True, blank=True) 
    
    
    def __str__(self):
        return f'{self.employee_code} - {self.employee_name}'


class Progress(models.Model):
    progress_code = models.CharField(max_length=50, unique=True)
    work_date = models.DateField(null=True, blank=True)
    tailor = models.ForeignKey(Employee, on_delete=models.RESTRICT, null=True)
    design = models.ForeignKey(Design, on_delete=models.RESTRICT, null=True)
    color = models.CharField(max_length=50, null=True, blank=True)
    size = models.CharField(max_length=10, null=True, blank=True)
    design_name = models.CharField(max_length=255, null=True, blank=True)
    
    task_name = models.CharField(max_length=10, null=True, blank=True)
    main_fabric_meters = models.FloatField(null=True, blank=True)
    lining_fabric_meters = models.FloatField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=50, choices=[('In Progress', 'Dở dang'), ('Completed', 'Hoàn thành')], null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.progress_code} - {self.design.design_name} ({self.task_name})"


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


class Message(models.Model):
    username = models.CharField(max_length=255)
    room = models.CharField(max_length=255)
    content = models.TextField()
    date_added = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ('date_added',)
    def __str__(self):
        return f'{self.room} - {self.username} - {self.content}'


