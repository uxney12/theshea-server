from django.shortcuts import render, get_object_or_404
from .models import Supplier, Category, Material, Inventory, Order, OrderLine, Receipt, ReceiptLine, Issue, ProductCategory, ProductType, Collection, Size, Color, Design, SKU, InventorySKU, QC, Import, ImportLine, Export, ExportLine, Employee, ColorInDesign, SizeInDesign, Progress, Message
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import pandas as pd 
import requests
from django.http import JsonResponse
import io
from django.db.models import Prefetch
from collections import defaultdict
from django.utils import timezone
from datetime import datetime
from .chatbot import get_gemini_response
from django.db.models import IntegerField, Value
from django.db.models.functions import Cast
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserRegistrationForm
from django.db.models import F, Value
from django.db.models.functions import Coalesce
import re
from django.utils.timezone import now
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required



def index(request):

    num_suppliers = Supplier.objects.all().count()
    num_categorys = Category.objects.all().count()
    num_materials = Material.objects.all().count()
    num_orders = Order.objects.all().count()
    num_receipts = Receipt.objects.all().count()
    # num_production_rooms = ProductionRoom.objects.all().count()
    # num_delivery = Delivery.objects.all().count()

    context = {
        'num_suppliers': num_suppliers,
        'num_categorys': num_categorys,
        'num_materials': num_materials,
        'num_orders': num_orders,
        'num_receipts': num_receipts,
        # 'num_production_rooms': num_production_rooms,
        # 'num_delivery': num_delivery,
    }
    return render(request, 'index.html', context)

def validate_date(date_str):
    if isinstance(date_str, pd.Timestamp):
        date_str = date_str.strftime('%Y-%m-%d')

    date_pattern_ymd = r"^\d{4}-\d{2}-\d{2}$"
    if re.match(date_pattern_ymd, date_str):
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    
    date_pattern_dmy = r"^\d{2}/\d{2}/\d{4}$"
    if re.match(date_pattern_dmy, date_str):
        return datetime.strptime(date_str, '%d/%m/%Y').date()

    return None


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def list_supplier(request):
    valid_sort_fields = ['supplier_code', 'supplier_name', 'category__category_name', 'phone_number', 'facebook', 'website']
    
    sort_field = request.GET.get('sort_field', 'supplier_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'supplier_code'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    all_supplier = Supplier.objects.select_related('category')
    if search_query:
        all_supplier = all_supplier.filter(
            Q(supplier_code__icontains=search_query) |
            Q(supplier_name__icontains=search_query) |
            Q(category__category_name__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(facebook__icontains=search_query) |
            Q(website__icontains=search_query)
        )

    all_supplier = all_supplier.order_by(sort_field)
    paginator = Paginator(all_supplier, 10) 
    page_number = request.GET.get('page')
    suppliers_page = paginator.get_page(page_number)

    category = Category.objects.all()

    suppliers = Supplier.objects.filter(supplier_code__regex=r'^SUV\d+$')\
        .annotate(numeric_code=Cast(F('supplier_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    last_supplier_index = suppliers.first().numeric_code if suppliers.exists() else 0
    new_supplier_code = f'SUV{last_supplier_index + 1:03d}'

    categorys = Category.objects.filter(category_code__regex=r'^CT\d+$')\
        .annotate(numeric_code=Cast(F('category_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    last_category_index = categorys.first().numeric_code if categorys.exists() else 0
    new_category_code = f'CT{last_category_index + 1:03d}'

    context = {
        'all_supplier': all_supplier,
        'suppliers_page': suppliers_page,
        'new_supplier_code': new_supplier_code,
        'new_category_code': new_category_code,
        'current_sort_field': sort_field.replace('-', ''),  
        'current_sort_order': sort_order,
        'category': category,
        'search_query': search_query,
    }

    return render(request, 'catalog/list_supplier.html', context)

@csrf_exempt
def upload_supplier(request):
    categorys = Category.objects.filter(category_code__regex=r'^CT\d+$').annotate(numeric_code=Cast(F('category_code')[3:], IntegerField())).order_by('-numeric_code')
    if categorys.exists():
        last_category_index = categorys.first().numeric_code  
    else:
        last_category_index = 0
    new_category_code = f'CT{last_category_index + 1:03d}' 

    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['ID NCC Vải', 'Tên NCC Vải', 'Phân loại', 'SĐT', 'Facebook', 'Website', 'Địa chỉ', "Ghi chú"]

        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/supplier')
        
        df = df.fillna('')

        for index, row in df.iterrows():
            category = None

            if row['Phân loại']:
                category, created = Category.objects.get_or_create(category_code=new_category_code,category_name=row['Phân loại'])

            Supplier.objects.create(
                supplier_code=row['ID NCC Vải'],
                supplier_name=row['Tên NCC Vải'],
                category=category,
                phone_number=row['SĐT'],
                facebook=row['Facebook'],
                website=row['Website'],
                address=row['Địa chỉ'],
                notes=row['Ghi chú']
            )

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'})
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def create_supplier(request):
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        supplier_code = request.POST.get('supplier_code') or body.get('supplier_code')
        supplier_name = request.POST.get('supplier_name') or body.get('supplier_name')
        category_value = request.POST.get('category') or body.get('category')
        category = category_value.split('-')[0].strip() if category_value else None
        phone_number = request.POST.get('phone_number') or body.get('phone_number')
        facebook = request.POST.get('facebook') or body.get('facebook')
        website = request.POST.get('website') or body.get('website')
        address = request.POST.get('address') or body.get('address')
        notes = request.POST.get('notes') or body.get('notes')
        Supplier.objects.create(
            supplier_code=supplier_code,
            supplier_name=supplier_name,
            category=Category.objects.filter(category_code=category).last(),
            phone_number=phone_number,
            facebook=facebook,
            website=website,
            address=address,
            notes=notes
        )
        return JsonResponse({'message': 'Nhà cung cấp đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)  

@csrf_exempt 
def delete_supplier(request, supplier_code):
    if request.method == 'POST':
        supplier = get_object_or_404(Supplier, supplier_code=supplier_code)
        supplier.delete()

        return JsonResponse({'message': 'Nhà cung cấp đã được xóa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)
    
@csrf_exempt
def update_supplier(request, supplier_code):
    if request.method == "POST":
        supplier = get_object_or_404(Supplier, supplier_code=supplier_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        supplier_name = request.POST.get('supplier_name') or body.get('supplier_name')
        category_value = request.POST.get('category') or body.get('category')
        category = category_value.split('-')[0].strip() if category_value else None
        phone_number = request.POST.get('phone_number') or body.get('phone_number')
        facebook = request.POST.get('facebook') or body.get('facebook')
        website = request.POST.get('website') or body.get('website')
        address = request.POST.get('address') or body.get('address')
        notes = request.POST.get('notes') or body.get('notes')

        if supplier_name:
            supplier.supplier_name = supplier_name
        if category_value:
            category_code = category_value.split('-')[0].strip()
            category = Category.objects.get(category_code=category_code)
            supplier.category = category
        if phone_number:
            supplier.phone_number = phone_number
        if facebook:
            supplier.facebook = facebook
        if website:
            supplier.website = website
        if address:
            supplier.address = address
        if notes:
            supplier.notes = notes
        supplier.save()

        return JsonResponse({'message': 'Nhà cung cấp đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


@csrf_exempt
def list_material(request):
    valid_sort_fields = ['material_code', 'material_name', 'color', 'types', 'supplier__supplier_name']
    
    sort_field = request.GET.get('sort_field', 'material_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'material_code'
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    all_material = Material.objects.all().order_by(sort_field)

    supplier_filter = request.GET.get('supplier', '')
    color_filter = request.GET.get('color', '')
    type_filter = request.GET.get('type', '')

    materials = Material.objects.select_related('supplier').order_by(sort_field)

    if supplier_filter:
        materials = materials.filter(supplier__supplier_code=supplier_filter)
    
    if color_filter:
        materials = materials.filter(color=color_filter)
    
    if type_filter:
        materials = materials.filter(types=type_filter)
    
    if search_query:
        materials = materials.filter(
            Q(material_code__icontains=search_query) |
            Q(material_name__icontains=search_query) |
            Q(color__icontains=search_query) |
            Q(types__icontains=search_query) |
            Q(supplier__supplier_name__icontains=search_query)
        )

    paginator = Paginator(materials, 10)
    page_number = request.GET.get('page')
    materials_page = paginator.get_page(page_number)

    material_objects = Material.objects.filter(material_code__regex=r'^MAV\d+$')\
        .annotate(numeric_code=Cast(F('material_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    last_material_index = material_objects.first().numeric_code if material_objects.exists() else 0
    new_material_code = f'MAV{last_material_index + 1:03d}'

    supplier_objects = Supplier.objects.filter(supplier_code__regex=r'^SUV\d+$')\
        .annotate(numeric_code=Cast(F('supplier_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    last_supplier_index = supplier_objects.first().numeric_code if supplier_objects.exists() else 0
    new_supplier_code = f'SUV{last_supplier_index + 1:03d}'

    context = {
        'all_material': all_material,
        'materials_page': materials_page, 
        'new_material_code': new_material_code,
        'new_supplier_code': new_supplier_code,
        'current_sort_field': sort_field.replace('-', ''), 
        'current_sort_order': sort_order,
        'search_query': search_query,
        'suppliers': Supplier.objects.all(),
        'colors': Material.objects.values('color').distinct(),
        'types': Material.objects.values('types').distinct(),
    }

    return render(request, 'catalog/list_material.html', context)

@csrf_exempt
def upload_material(request):
    suppliers = Supplier.objects.filter(supplier_code__regex=r'^SUV\d+$').annotate(
        numeric_code=Cast(F('supplier_code')[3:], IntegerField())
    ).order_by('-numeric_code')

    if suppliers.exists():
        last_supplier_index = suppliers.first().numeric_code  
    else:
        last_supplier_index = 0
    new_supplier_code = f'SUV{last_supplier_index + 1:03d}' 

    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã nguyên vật liệu', 'Tên nguyên vật liệu', 'Nhà cung cấp', 
                            'Hình ảnh', 'Loại', 'Màu', 'Ghi chú', 'Tồn kho tối thiểu', 'Tồn kho tối đa']

        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/material')

        df = df.fillna('')
        for index, row in df.iterrows():
            supplier = None
            if row['Nhà cung cấp']:
                supplier = Supplier.objects.filter(supplier_name=row['Nhà cung cấp']).first()
                
                if not supplier:
                    supplier = Supplier.objects.create(
                        supplier_code=new_supplier_code,
                        supplier_name=row['Nhà cung cấp']
                    )

            image_file = None
            image_link = row['Hình ảnh']
            if image_link and image_link.startswith('http'):
                image_response = requests.get(image_link)
                if image_response.status_code == 200:
                    image_name = image_link.split('/')[-1]
                    image_file = ContentFile(image_response.content, name=image_name)

            stock_min = int(row['Tồn kho tối thiểu']) if str(row['Tồn kho tối thiểu']).isdigit() else 0
            stock_max = int(row['Tồn kho tối đa']) if str(row['Tồn kho tối đa']).isdigit() else 0
            print(stock_min)
            print(stock_max)
            Material.objects.create(
                material_code=row['Mã nguyên vật liệu'],
                material_name=row['Tên nguyên vật liệu'],
                supplier=supplier,
                image=image_file,
                types=row['Loại'],
                color=row['Màu'],
                notes=row['Ghi chú'],
                stock_min=stock_min,
                stock_max=stock_max
            )

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'})
    return JsonResponse({'error': 'Bad request'}, status=400)

def create_material(request):
    if request.method == "POST":
        if request.content_type.startswith('multipart'):
            material_code = request.POST.get('material_code')
            material_name = request.POST.get('material_name')
            supplier_value = request.POST.get('supplier')
            supplier_code = supplier_value.split('-')[0].strip() if supplier_value else None
            types = request.POST.get('types')
            color = request.POST.get('color')
            notes = request.POST.get('notes')
            stock_min = request.POST.get('stock_min', 0)
            stock_max = request.POST.get('stock_max', 0)
            image = request.FILES.get('image')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            material_code = body.get('material_code')
            material_name = body.get('material_name')
            supplier_value = body.get('supplier')
            supplier_code = supplier_value.split('-')[0].strip() if supplier_value else None
            types = body.get('types')
            color = body.get('color')
            notes = body.get('notes')
            stock_min = body.get('stock_min', 0)
            stock_max = body.get('stock_max', 0)
            image = None  

        stock_min = int(stock_min) if str(stock_min).isdigit() else 0
        stock_max = int(stock_max) if str(stock_max).isdigit() else 0

        Material.objects.create(
            material_code=material_code,
            material_name=material_name,
            supplier=Supplier.objects.filter(supplier_code=supplier_code).last(),
            image=image,
            types=types,
            color=color,
            notes=notes,
            stock_min=stock_min,
            stock_max=stock_max
        )
        return JsonResponse({'message': 'Nguyên vật liệu đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt 
def delete_material(request, material_code):
    if request.method == 'POST':
        material = get_object_or_404(Material, material_code=material_code)
        material.delete()

        return JsonResponse({'message': 'Nguyên vật liệu đã được xóa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def update_material(request, material_code):
    if request.method == "POST":
        material = get_object_or_404(Material, material_code=material_code)

        if request.content_type.startswith('multipart'):
            material_name = request.POST.get('material_name')
            supplier_value = request.POST.get('supplier')
            supplier_code = supplier_value.split('-')[0].strip() if supplier_value else None
            types = request.POST.get('types')
            color = request.POST.get('color')
            notes = request.POST.get('notes')
            stock_min = request.POST.get('stock_min')
            stock_max = request.POST.get('stock_max')
            image = request.FILES.get('image')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            material_name = body.get('material_name')
            supplier_value = body.get('supplier')
            supplier_code = supplier_value.split('-')[0].strip() if supplier_value else None
            types = body.get('types')
            color = body.get('color')
            notes = body.get('notes')
            stock_min = body.get('stock_min')
            stock_max = body.get('stock_max')
            image = None  

        if material_name:
            material.material_name = material_name
        if supplier_value:
            supplier = Supplier.objects.filter(supplier_code=supplier_code).last()
            if supplier:
                material.supplier = supplier
        if image:
            material.image = image
        if types:
            material.types = types
        if color:
            material.color = color
        if notes:
            material.notes = notes
        if stock_min and str(stock_min).isdigit():
            material.stock_min = int(stock_min)
        if stock_max and str(stock_max).isdigit():
            material.stock_max = int(stock_max)

        material.save()

        return JsonResponse({'message': 'Nguyên vật liệu đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def list_category(request):
    valid_sort_fields = ['category_code', 'category_name', 'description']
    
    sort_field = request.GET.get('sort_field', 'category_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'category_code'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    all_category = Category.objects.all()
    if search_query:
        all_category = all_category.filter(
            Q(category_code__icontains=search_query) |
            Q(category_name__icontains=search_query) |
            Q(description__icontains=search_query) 
        )

    all_category = all_category.order_by(sort_field)
    paginator = Paginator(all_category, 10) 
    page_number = request.GET.get('page')
    categories_page = paginator.get_page(page_number)

    categorys = Category.objects.filter(category_code__regex=r'^CT\d+$')\
        .annotate(numeric_code=Cast(F('category_code')[2:], IntegerField()))\
        .order_by('-numeric_code')
    last_category_index = categorys.first().numeric_code if categorys.exists() else 0
    new_category_code = f'CT{last_category_index + 1:03d}'

    context = {
        'categories_page': categories_page,
        'new_category_code': new_category_code,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }

    return render(request, 'catalog/list_category.html', context)

@csrf_exempt
def upload_category(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã loại nguyên vật liệu', 'Tên loại nguyên vật liệu', 'Mô tả']

        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/category')

        df = df.fillna('')
        for index, row in df.iterrows():

            Category.objects.create(
                category_code=row['Mã loại nguyên vật liệu'],
                category_name=row['Tên loại nguyên vật liệu'],
                description=row['Mô tả'],
            )

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'})
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def create_category(request):
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        category_code = request.POST.get('category_code') or body.get('category_code')
        category_name = request.POST.get('category_name') or body.get('category_name')
        description = request.POST.get('description') or body.get('description')
        Category.objects.create(
            category_code=category_code,
            category_name=category_name,
            description=description,
        )
        return JsonResponse({'message': 'Loại nguyên vật liệu đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400) 

@csrf_exempt 
def delete_category(request, category_code):
    if request.method == 'POST':
        category = get_object_or_404(Category, category_code=category_code)
        category.delete()

        return JsonResponse({'message': 'Loại nguyên vật liệu đã được xóa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def update_category(request, category_code):
    if request.method == "POST":
        category = get_object_or_404(Category, category_code=category_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        category_code = request.POST.get('category_code') or body.get('category_code')
        category_name = request.POST.get('category_name') or body.get('category_name')
        description = request.POST.get('description') or body.get('description')

        if category_code:
            category.category_code = category_code
        if category_name:
            category.category_name = category_name
        if description:
            category.description = description

        category.save()

        return JsonResponse({'message': 'Loại nguyên vật liệu đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def list_inventory(request):  
    valid_sort_fields = ['material_code', 'material_name', 'quantity']
    
    sort_field = request.GET.get('sort_field', 'material_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'material_code'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    materials_without_inventory = Material.objects.filter(inventory__isnull=True)
    for material in materials_without_inventory:
        Inventory.objects.create(material=material, quantity=0)

    inventory_list = Material.objects.annotate(
        quantity=Coalesce(F('inventory__quantity'), Value(0))
    )
    
    if search_query:
        inventory_list = inventory_list.filter(
            Q(material_code__icontains=search_query) |
            Q(material_name__icontains=search_query)
        )

    inventory_list = inventory_list.order_by(sort_field)
    paginator = Paginator(inventory_list, 10)
    page_number = request.GET.get('page')
    inventory_page = paginator.get_page(page_number)

    context = {
        'inventory_page': inventory_page, 
        'current_sort_field': sort_field.replace('-', ''),  
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
  
    return render(request, 'catalog/list_inventory.html', context)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def list_order(request):
    valid_sort_fields = ['order_code', 'supplier__supplier_name', 'material__material_name', 'order_date', 'total_amount', 'total_quantity', 'status']
    sort_field = request.GET.get('sort_field', 'order_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'order_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_order = Order.objects.all()
    
    if search_query:
        all_order = all_order.filter(
            Q(order_code__icontains=search_query) |
            Q(supplier__supplier_name__icontains=search_query) 
        )
    
    all_order = all_order.order_by(sort_field)
    paginator = Paginator(all_order, 10)
    page_number = request.GET.get('page')
    order_page = paginator.get_page(page_number)


    orders = Order.objects.filter(order_code__regex=r'^POV\d+$').annotate(numeric_code=Cast(F('order_code')[3:], IntegerField())).order_by('-numeric_code')
    if orders.exists():
        last_order_index = orders.first().numeric_code  
    else:
        last_order_index = 0
    new_order_code = f'POV{last_order_index + 1:05d}'


    suppliers = Supplier.objects.filter(supplier_code__regex=r'^SUV\d+$').annotate(numeric_code=Cast(F('supplier_code')[3:], IntegerField())).order_by('-numeric_code')
    if suppliers.exists():
        last_supplier_index = suppliers.first().numeric_code  
    else:
        last_supplier_index = 0
    new_supplier_code = f'SUV{last_supplier_index + 1:03d}' 


    materials = Material.objects.filter(material_code__regex=r'^MAV\d+$').annotate(numeric_code=Cast(F('material_code')[3:], IntegerField())).order_by('-numeric_code')
    if materials.exists():
        last_material_index = materials.first().numeric_code  
    else:
        last_material_index = 0
    new_material_code = f'MAV{last_material_index + 1:03d}'


    current_time = timezone.now() 
    supplier = Supplier.objects.all()
    material = Material.objects.all()
    orders = Order.objects.all()
    for order in orders:
        order.orderline_set.all()


    context = {
        'order_page': order_page,
        'new_order_code': new_order_code,
        'new_supplier_code': new_supplier_code,
        'new_material_code':new_material_code,
        'current_sort_field': request.GET.get('sort_field', ''),
        'current_sort_order': request.GET.get('sort_order', ''),
        'current_time': current_time,
        'supplier': supplier,
        'material': material,
        'order': Order.objects.prefetch_related('orderline_set').first()
        }
  
    return render(request, 'catalog/list_order.html', context)

def get_materials_by_supplier(request):
    supplier_code = request.GET.get('supplier_code', None)
    if supplier_code:
        materials = Material.objects.filter(supplier__supplier_code=supplier_code).values('material_code', 'material_name')
    else:
        materials = Material.objects.all().values('material_code', 'material_name')
    
    return JsonResponse(list(materials), safe=False)

@csrf_exempt
def upload_order(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ["Mã đặt hàng", "Ngày đặt hàng", "Nhà cung cấp", "Ngày dự kiến nhận hàng", "Tổng số lượng đặt", "Giá trị đơn hàng", "Phương thức thanh toán", "Trả trước", "Ghi chú", "STT", "Nguyên vật liệu", "Số lượng", "Đơn giá", "Đơn vị tính", "Tổng tiền"]

        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/order')

        order_dict = defaultdict(list)

        df = df.fillna('')
        for _, row in df.iterrows():
            order_dict[row['Mã đặt hàng']].append(row)

        for order_code, rows in order_dict.items():
            first_row = rows[0]

            order_date_str = first_row['Ngày đặt hàng']
            order_date = validate_date(order_date_str) if order_date_str else None

            expected_date_str = first_row['Ngày dự kiến nhận hàng']
            expected_date = validate_date(expected_date_str) if expected_date_str else None

            
            supplier = Supplier.objects.filter(supplier_name=first_row['Nhà cung cấp']).first()
            if not supplier:
                suppliers = Supplier.objects.filter(supplier_code__regex=r'^SUV\d+$').annotate(numeric_code=Cast(F('supplier_code')[3:], IntegerField())).order_by('-numeric_code')
                if suppliers.exists():
                    last_supplier_index = suppliers.first().numeric_code  
                else:
                    last_supplier_index = 0
                new_supplier_code = f'SUV{last_supplier_index + 1:03d}' 
                supplier = Supplier.objects.create(supplier_code=new_supplier_code, supplier_name=first_row['Nhà cung cấp'])
            
            order = Order.objects.create(
                order_code=first_row['Mã đặt hàng'],
                order_date=order_date,    
                supplier=supplier, 
                expected_date=expected_date,
                total_quantity=row['Tổng số lượng đặt'] if pd.notna(row['Tổng số lượng đặt']) else 0,
                total_amount=row['Giá trị đơn hàng'] if pd.notna(row['Giá trị đơn hàng']) else 0,
                payment_method=first_row['Phương thức thanh toán'],
                prepaid=first_row['Trả trước'],
                note=first_row['Ghi chú'],
                status='completed',
            )

            for row in rows:
                material = Material.objects.filter(material_name=row['Nguyên vật liệu']).first()
                if not material:
                    materials = Material.objects.filter(material_code__regex=r'^MAV\d+$').annotate(numeric_code=Cast(F('material_code')[3:], IntegerField())).order_by('-numeric_code')
                    if materials.exists():
                        last_material_index = materials.first().numeric_code  
                    else:
                        last_material_index = 0
                    new_material_code = f'MAV{last_material_index + 1:03d}'
                    material = Material.objects.create(material_code=new_material_code, material_name=row['Nguyên vật liệu'])

                OrderLine.objects.create(
                    order=order,
                    order_line_code=row['STT'],
                    material=material,
                    quantity=row['Số lượng'] if pd.notna(row['Số lượng']) else 0,
                    price=row['Đơn giá'] if pd.notna(row['Đơn giá']) else 0,
                    unit_of_measure=row['Đơn vị tính'],
                    total=row['Tổng tiền'] if pd.notna(row['Tổng tiền']) else 0,
                )

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def create_order(request):
    form_values = request.POST.copy()
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        order_code = request.POST.get('order_code') or body.get('order_code')
        order_date = request.POST.get('order_date') or body.get('order_date')
        print(order_date)
        order_date = validate_date(order_date)
        print(order_date)
        supplier_value = request.POST.get('supplier') or body.get('supplier')
        supplier = supplier_value.split('-')[0].strip() if supplier_value else None
        expected_date = request.POST.get('expected_date') or body.get('expected_date')
        expected_date = validate_date(expected_date)
        total_quantity = request.POST.get('total_quantity') or body.get('total_quantity')
        total_amount  = request.POST.get('total_amount') or body.get('total_amount')
        payment_method = request.POST.get('payment_method') or body.get('payment_method')
        prepaid = request.POST.get('prepaid') or body.get('prepaid')
        note = request.POST.get('note') or body.get('note')
        order = Order.objects.create(
            order_code=order_code,
            order_date=order_date,
            supplier=Supplier.objects.filter(supplier_code=supplier).last(),
            expected_date=expected_date,
            total_quantity=total_quantity,
            total_amount=total_amount,
            payment_method=payment_method,
            prepaid=prepaid,
            status='completed',
            note=note
        )
        order_lines = body.get('order_lines', [])
        
        order_line_codes = []
        materials = []
        quantities = []
        prices = []
        unit_of_measures = []
        totals = []

        for line in order_lines:
            order_line_codes.append(line.get('order_line_code', ''))
            materials.append(line.get('material', ''))
            quantities.append(line.get('quantity', ''))
            prices.append(line.get('price', ''))
            unit_of_measures.append(line.get('unit_of_measure', ''))
            totals.append(line.get('total', ''))

        if not order_lines:
            order_line_codes = form_values.getlist('order_line_code', [])
            materials = form_values.getlist('material', [])
            quantities = form_values.getlist('quantity', [])
            prices = form_values.getlist('price', [])
            unit_of_measures = form_values.getlist('unit_of_measure', [])
            total = form_values.getlist('total', [])

        for order_line_code, material, quantity, price, unit_of_measure, total in zip(order_line_codes, materials, quantities, prices, unit_of_measures, totals):
            material_code = material.split('-')[0].strip()
            material_flt = Material.objects.filter(material_code=material_code).last()
            price = float(price) if price else 0.0  
            OrderLine.objects.create(
                order=order,
                order_line_code=order_line_code,
                material=material_flt,
                quantity=quantity,
                price=price,
                unit_of_measure=unit_of_measure,
                total=total
            )

        return JsonResponse({'message': 'Đơn hàng đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400) 

@csrf_exempt 
def delete_order(request, order_code):
    if request.method == 'POST':
        order = get_object_or_404(Order, order_code=order_code)
        order.status = "cancelled"
        order.save()

        return JsonResponse({'message': 'Phiếu đặt hàng đã được hủy thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def update_order(request, order_code):
    if request.method == "POST":
        order = get_object_or_404(Order, order_code=order_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        order_code = request.POST.get('order_code') or body.get('order_code')
        order_date = request.POST.get('order_date') or body.get('order_date')
        order_date = validate_date(order_date)
        supplier_value = request.POST.get('supplier') or body.get('supplier')
        supplier = supplier_value.split('-')[0].strip() if supplier_value else None
        expected_date = request.POST.get('expected_date') or body.get('expected_date')
        expected_date = validate_date(expected_date)
        total_quantity = request.POST.get('total_quantity') or body.get('total_quantity')
        total_amount = request.POST.get('total_amount') or body.get('total_amount')
        payment_method = request.POST.get('payment_method') or body.get('payment_method')
        prepaid = request.POST.get('prepaid') or body.get('prepaid')
        note = request.POST.get('note') or body.get('note')

        if order_code:
            order.order_code = order_code
        if order_date:
            order.order_date = order_date
        if supplier:
            supplier = Supplier.objects.get(supplier_code=supplier)
            order.supplier = supplier
        if expected_date:
            order.expected_date = expected_date
        if payment_method:
            order.payment_method = payment_method
        if total_quantity:
            order.total_quantity = total_quantity
        if total_amount:
            order.total_amount = total_amount 
        if prepaid:
            order.prepaid = prepaid
        if note:
            order.note = note

        order.status='completed'
        order.save()
        order_lines = body.get('orderlines_update', [])
        existing_order_lines = {ol.order_line_code: ol for ol in OrderLine.objects.filter(order=order)}

        for line in order_lines:
            order_line_code = line.get('order_line_code')
            material_code = line.get('material').split('-')[0].strip()
            material = Material.objects.filter(material_code=material_code).last()
            quantity = line.get('quantity')
            price = float(line.get('price', 0.0))
            unit_of_measure = line.get('unit_of_measure')
            total = line.get('total')

            if order_line_code in existing_order_lines:
                order_line = existing_order_lines[order_line_code]
                order_line.material = material
                order_line.quantity = quantity
                order_line.price = price
                order_line.unit_of_measure = unit_of_measure
                order_line.total = total
                order_line.save()
            else:
                OrderLine.objects.create(
                    order=order,
                    order_line_code=order_line_code,
                    material=material,
                    quantity=quantity,
                    price=price,
                    unit_of_measure=unit_of_measure,
                    total=total
                )


        return JsonResponse({'message': 'Phiếu đặt hàng đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


@csrf_exempt 
def list_receipt(request):
    valid_sort_fields = ['receipt_code', 'supplier__supplier_name', 'order__order_code','receipt_date', 'total_amount', 'status']
    sort_field = request.GET.get('sort_field', 'receipt_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'receipt_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_receipt = Receipt.objects.all()
    
    if search_query:
        all_receipt = all_receipt.filter(
            Q(receipt_code__icontains=search_query) |
            Q(supplier__supplier_name__icontains=search_query)|
            Q(order__order_code__icontains=search_query)
        )
    
    all_receipt = all_receipt.order_by(sort_field)
    paginator = Paginator(all_receipt, 10)
    page_number = request.GET.get('page')
    receipt_page = paginator.get_page(page_number)
    
    receipts = Receipt.objects.filter(receipt_code__regex=r'^PIV\d+$').annotate(
        numeric_code=Cast(F('receipt_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    
    last_receipt_index = receipts.first().numeric_code if receipts.exists() else 0
    new_receipt_code = f'PIV{last_receipt_index + 1:05d}'
    current_time = timezone.now()
    suppliers = Supplier.objects.all()
    
    context = {
        'receipt_page': receipt_page,
        'new_receipt_code': new_receipt_code,
        'current_time': current_time,
        'suppliers': suppliers,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_receipt.html', context)

def get_orderlines(request):
    order_code = request.GET.get('order_code')
    print("Order Code:", order_code) 
    order = Order.objects.prefetch_related('orderline_set').filter(order_code=order_code).first()
    
    if order:
        orderlines = order.orderline_set.all().values(
            'order_line_code', 
            'material__material_code', 
            'material__material_name', 
            'quantity', 
            'price', 
            'unit_of_measure', 
            'total'
        )
        print("Orderlines:", list(orderlines))
        return JsonResponse(list(orderlines), safe=False)
    else:
        print("No order found") 
        return JsonResponse([], safe=False)

def get_order_details(request):
    order_code = request.GET.get('order_code')
    order = get_object_or_404(Order, order_code=order_code)
    total_quantity = order.total_quantity
    data = {
        'supplier_code': order.supplier.supplier_code,
        'total_quantity': order.total_quantity,
        'subtotal': order.total_amount 
    }
    return JsonResponse(data)

@csrf_exempt
def upload_receipt(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ["Mã nhập hàng", "Ngày nhập hàng", "Mã đặt hàng", "Nhà cung cấp", "Tổng số lượng nhập",
                            "Tổng tiền hàng", "Phí vận chuyển", "Phí VAT", "Tổng tiền", "Ghi chú", 
                            "STT", "Nguyên vật liệu", "Số lượng", "Đơn giá", "Đơn vị tính", "Thành tiền"]

        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/receipt')

        receipt_dict = defaultdict(list)

        df = df.fillna('')  
        for _, row in df.iterrows():
            receipt_dict[row['Mã nhập hàng']].append(row)

        for receipt_code, rows in receipt_dict.items():
            first_row = rows[0]

            receipt_date_str = first_row['Ngày nhập hàng']
            receipt_date = validate_date(receipt_date_str) if receipt_date_str else None

            supplier = Supplier.objects.filter(supplier_name=first_row['Nhà cung cấp']).first()
            order = Order.objects.filter(order_code=first_row['Mã đặt hàng']).first()

            receipt = Receipt.objects.create(
                receipt_code=first_row['Mã nhập hàng'],
                receipt_date=receipt_date,    
                supplier=supplier,
                order=order,
                total_quantity=first_row['Tổng số lượng nhập'] if pd.notna(first_row['Tổng số lượng nhập']) else 0,
                subtotal=first_row['Tổng tiền hàng'] if pd.notna(first_row['Tổng tiền hàng']) else 0,
                shipping_fee=first_row['Phí vận chuyển'] if pd.notna(first_row['Phí vận chuyển']) else 0,
                vat_fee=first_row['Phí VAT'] if pd.notna(first_row['Phí VAT']) else 0,
                total_amount=first_row['Tổng tiền'] if pd.notna(first_row['Tổng tiền']) else 0,
                note=first_row['Ghi chú'],
                status='completed',
            )

            for row in rows:
                material = Material.objects.filter(material_name=row['Nguyên vật liệu']).first()
                if not material:
                    continue 

                quantity = int(row['Số lượng']) if pd.notna(row['Số lượng']) else 0
                price = float(row['Đơn giá']) if pd.notna(row['Đơn giá']) else 0
                total = float(row['Thành tiền']) if pd.notna(row['Thành tiền']) else 0
                unit_of_measure = row['Đơn vị tính']

                ReceiptLine.objects.create(
                    receipt=receipt,
                    receipt_line_code=row['STT'],
                    material=material,
                    quantity=quantity,
                    price=price,
                    unit_of_measure=unit_of_measure,
                    total=total,
                )

                inventory, created = Inventory.objects.get_or_create(material=material, defaults={'quantity': 0})
                inventory.quantity += quantity
                inventory.save()

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

def create_receipt(request):
    form_values = request.POST.copy()
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        receipt_code = request.POST.get('receipt_code') or body.get('receipt_code')
        receipt_date = request.POST.get('receipt_date') or body.get('receipt_date')
        receipt_date = validate_date(receipt_date)
        supplier_value = request.POST.get('supplier') or body.get('supplier')
        supplier = supplier_value.split('-')[0].strip() if supplier_value else None
        order_value = request.POST.get('order') or body.get('order')
        order = order_value.split('-')[0].strip() if order_value else None
        total_quantity = request.POST.get('total_quantity') or body.get('total_quantity')
        subtotal = request.POST.get('subtotal') or body.get('subtotal')
        shipping_fee = request.POST.get('shipping_fee') or body.get('shipping_fee')
        vat_fee = request.POST.get('vat_fee') or body.get('vat_fee')
        total_amount = request.POST.get('total_amount') or body.get('total_amount')

        receipt = Receipt.objects.create(
            receipt_code=receipt_code,
            receipt_date=receipt_date,
            supplier=Supplier.objects.filter(supplier_code=supplier).last(),
            order=Order.objects.filter(order_code=order).last(),
            total_quantity=total_quantity,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            vat_fee=vat_fee,
            total_amount=total_amount,
            status='completed',
        )

        receipt_lines = body.get('receipt_lines', [])

        for line in receipt_lines:
            receipt_line_code = line.get('receipt_line_code', '')
            material_code = line.get('material', '').split('-')[0].strip()
            quantity = int(line.get('quantity', 0))
            price = float(line.get('price', 0))
            unit_of_measure = line.get('unit_of_measure', '')
            total = float(line.get('total', 0))

            material = Material.objects.filter(material_code=material_code).last()

            if not material:
                continue 

            ReceiptLine.objects.create(
                receipt=receipt,
                receipt_line_code=receipt_line_code,
                material=material,
                quantity=quantity,
                price=price,
                unit_of_measure=unit_of_measure,
                total=total
            )

            inventory, created = Inventory.objects.get_or_create(material=material, defaults={'quantity': 0})
            inventory.quantity += quantity
            inventory.save()

        return JsonResponse({'message': 'Biên nhận đã được tạo thành công!'})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def delete_receipt(request, receipt_code):
    if request.method == 'POST':
        receipt = get_object_or_404(Receipt, receipt_code=receipt_code)
        receipt_lines = ReceiptLine.objects.filter(receipt=receipt)

        for line in receipt_lines:
            inventory = Inventory.objects.filter(material=line.material).first()
            if inventory:
                inventory.quantity -= line.quantity
                inventory.save()

        receipt.status = "cancelled"
        receipt.save() 

        return JsonResponse({'message': 'Phiếu nhập hàng đã được xóa thành công!'}, status=200)

    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def update_receipt(request, receipt_code):
    if request.method == "POST":
        receipt = get_object_or_404(Receipt, receipt_code=receipt_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        receipt_code = request.POST.get('receipt_code') or body.get('receipt_code')
        receipt_date = request.POST.get('receipt_date') or body.get('receipt_date')
        supplier_value = request.POST.get('supplier') or body.get('supplier')
        supplier = supplier_value.split('-')[0].strip() if supplier_value else None
        order_value = request.POST.get('order') or body.get('order')
        order = order_value.split('-')[0].strip() if order_value else None
        total_quantity = request.POST.get('total_quantity') or body.get('total_quantity')
        subtotal = request.POST.get('subtotal') or body.get('subtotal')
        shipping_fee = request.POST.get('shipping_fee') or body.get('shipping_fee')
        vat_fee = request.POST.get('vat_fee') or body.get('vat_fee')
        total_amount = request.POST.get('total_amount') or body.get('total_amount')

        if receipt_code:
            receipt.receipt_code = receipt_code
        if receipt_date:
            receipt.receipt_date = validate_date(receipt_date)
        if supplier:
            supplier = Supplier.objects.get(supplier_code=supplier)
            receipt.supplier = supplier
        if order:
            order = Order.objects.get(order_code=order)
            receipt.order = order 
        if total_quantity:
            receipt.total_quantity = total_quantity
        if subtotal:
            receipt.subtotal = subtotal
        if shipping_fee:
            receipt.shipping_fee = shipping_fee
        if vat_fee:
            receipt.vat_fee = vat_fee
        if total_amount:
            receipt.total_amount = total_amount

        receipt.status='completed'
        receipt.save()

        receipt_lines = body.get('receiptlines_update', [])
        existing_receipt_lines = {rl.receipt_line_code: rl for rl in ReceiptLine.objects.filter(receipt=receipt)}

        for line in receipt_lines:
            receipt_line_code = line.get('receipt_line_code')
            material_code = line.get('material').split('-')[0].strip()
            material = Material.objects.filter(material_code=material_code).last()
            quantity = int(line.get('quantity', 0))
            price = float(line.get('price', 0.0))
            unit_of_measure = line.get('unit_of_measure')
            total = line.get('total')

            if receipt_line_code in existing_receipt_lines:
                receipt_line = existing_receipt_lines[receipt_line_code]
                old_quantity = receipt_line.quantity

                inventory = Inventory.objects.filter(material=receipt_line.material).first()
                if inventory:
                    inventory.quantity -= old_quantity  
                    inventory.save()

                receipt_line.material = material
                receipt_line.quantity = quantity
                receipt_line.price = price
                receipt_line.unit_of_measure = unit_of_measure
                receipt_line.total = total
                receipt_line.save()

            else:
                receipt_line = ReceiptLine.objects.create(
                    receipt=receipt,
                    receipt_line_code=receipt_line_code,
                    material=material,
                    quantity=quantity,
                    price=price,
                    unit_of_measure=unit_of_measure,
                    total=total
                )

            inventory, created = Inventory.objects.get_or_create(material=material, defaults={'quantity': 0})
            inventory.quantity += quantity
            inventory.save()

        return JsonResponse({'message': 'Biên nhận đã được cập nhật thành công!'}, status=200)

    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def list_collection(request):
    valid_sort_fields = ['collection_code', 'collection_name', 'style', 'date']
    
    sort_field = request.GET.get('sort_field', 'collection_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'collection_code'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    all_collections = Collection.objects.all()
    
    if search_query:
        all_collections = all_collections.filter(
            Q(collection_code__icontains=search_query) |
            Q(collection_name__icontains=search_query) |
            Q(style__icontains=search_query)
        )
    
    all_collections = all_collections.order_by(sort_field)
    paginator = Paginator(all_collections, 10)
    page_number = request.GET.get('page')
    collections_page = paginator.get_page(page_number)

    collections = Collection.objects.filter(collection_code__regex=r'^BST\d+$')\
        .annotate(numeric_code=Cast(F('collection_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    last_collection_index = collections.first().numeric_code if collections.exists() else 0
    new_collection_code = f'BST{last_collection_index + 1:03d}'

    context = {
        'collections_page': collections_page,
        'new_collection_code': new_collection_code,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }

    return render(request, 'catalog/list_collection.html', context)

def upload_collection(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã bộ sưu tập', 'Tên bộ sưu tập', 'Phong cách', 'Mô tả', 'Ngày']
        if not all(col in df.columns for col in required_columns):
            return JsonResponse({'error': 'Thiếu các cột bắt buộc trong tệp.'}, status=400)

        df = df.fillna('')
        for index, row in df.iterrows():
            Collection.objects.create(
                collection_code=row['Mã bộ sưu tập'],
                collection_name=row['Tên bộ sưu tập'],
                style=row['Phong cách'],
                description=row['Mô tả'],
                date=row['Ngày'] if row['Ngày'] else None,
            )

        return JsonResponse({'message': 'Dữ liệu đã được tải lên thành công!'}, status=200)
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def create_collection(request):
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        collection_code = request.POST.get('collection_code') or body.get('collection_code')
        collection_name = request.POST.get('collection_name') or body.get('collection_name')
        style = request.POST.get('style') or body.get('style')
        description = request.POST.get('description') or body.get('description')
        date = request.POST.get('date') or body.get('date')
        Collection.objects.create(
            collection_code=collection_code,
            collection_name=collection_name,
            style=style,
            description=description,
            date=date
        )
        return JsonResponse({'message': 'Loại nguyên vật liệu đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400) 

@csrf_exempt
def update_collection(request, collection_code):
    if request.method == "POST":
        collection = get_object_or_404(Collection, collection_code=collection_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        collection_code = request.POST.get('collection_code') or body.get('collection_code')
        collection_name = request.POST.get('collection_name') or body.get('collection_name')
        style = request.POST.get('style') or body.get('style')
        description = request.POST.get('description') or body.get('description')
        date = request.POST.get('date') or body.get('date')

        if collection_code:
            collection.collection_code = collection_code
        if collection_name:
            collection.collection_name = collection_name
        if description:
            collection.description = description
        if style:
            collection.style = style
        if date:
            collection.date = date

        collection.save()

        return JsonResponse({'message': 'Loại nguyên vật liệu đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

@csrf_exempt
def list_design(request):
    valid_sort_fields = ['design_code', 'design_name', 'product_type__type_name', 'product_category__category_name', 'collection__collection_name']
    
    sort_field = request.GET.get('sort_field', 'design_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()

    if sort_field not in valid_sort_fields:
        sort_field = 'design_code'

    if sort_order == 'desc':
        sort_field = f'-{sort_field}'

    all_designs = Design.objects.prefetch_related(
        Prefetch('colorindesign_set', queryset=ColorInDesign.objects.select_related('color')),
        Prefetch('sizeindesign_set', queryset=SizeInDesign.objects.select_related('size'))
    )
    
    if search_query:
        all_designs = all_designs.filter(
            Q(design_code__icontains=search_query) |
            Q(design_name__icontains=search_query) |
            Q(product_type__type_name__icontains=search_query) |
            Q(product_category__category_name__icontains=search_query) |
            Q(collection__collection_name__icontains=search_query) |
            Q(sizeindesign__size__size_name__icontains=search_query) |
            Q(colorindesign__color__color_name__icontains=search_query) |
            Q(description__icontains=search_query)
        ).distinct()

    all_designs = all_designs.order_by(sort_field)
    paginator = Paginator(all_designs, 10)
    page_number = request.GET.get('page')
    designs_page = paginator.get_page(page_number)
    
    current_date = now()
    year = current_date.strftime("%y")  
    month = current_date.strftime("%m") 
    last_design = Design.objects.filter(design_code__startswith=f"{year}{month}").order_by('-design_code').first()
    
    if last_design:
        last_sequence = int(last_design.design_code[-3:])  
        new_sequence = last_sequence + 1
    else:
        new_sequence = 1
    
    new_design_code = f"{year}{month}{new_sequence:03d}"
    
    context = {
        'designs_page': designs_page,
        'new_design_code': new_design_code,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_design.html', context)

@csrf_exempt
def upload_design(request):

    employees = Employee.objects.filter(employee_code__regex=r'^NV\d{3}$').annotate(
        numeric_code=Cast(F('employee_code')[2:], IntegerField())
    ).order_by('-numeric_code')
    if employees.exists():
        last_employee_index = employees.first().numeric_code
    else:
        last_employee_index = 0
    new_employee_code = f'NV{last_employee_index + 1:03d}'


    product_types = ProductType.objects.filter(type_code__regex=r'^DSP\d{2}$').annotate(
        numeric_code=Cast(F('type_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    if product_types.exists():
        last_type_index = product_types.first().numeric_code
    else:
        last_type_index = 0
    new_type_code = f'DSP{last_type_index + 1:02d}'


    product_categories = ProductCategory.objects.filter(category_code__regex=r'^CL\d{2}$').annotate(
        numeric_code=Cast(F('category_code')[2:], IntegerField())
    ).order_by('-numeric_code')
    if product_categories.exists():
        last_category_index = product_categories.first().numeric_code
    else:
        last_category_index = 0
    new_category_code = f'CL{last_category_index + 1:02d}'


    collections = Collection.objects.filter(collection_code__regex=r'^BST\d{3}$').annotate(
        numeric_code=Cast(F('collection_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    if collections.exists():
        last_collection_index = collections.first().numeric_code
    else:
        last_collection_index = 0
    new_collection_code = f'BST{last_collection_index + 1:03d}'


    def generate_new_color_code():
        colors = Color.objects.filter(color_code__regex=r'^RC\d{5}$').annotate(
            numeric_code=Cast(F('color_code')[2:], IntegerField())
        ).order_by('-numeric_code')
        if colors.exists():
            last_color_index = colors.first().numeric_code
        else:
            last_color_index = 0
        return f'RC{last_color_index + 1:05d}'


    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = [
            'Mã mẫu thiết kế', 'Tên mẫu thiết kế', 'Nhân viên', 'Dòng sản phẩm', 'Chủng loại sản phẩm', 
            'Bộ sưu tập', 'Full bộ', 'Hình ảnh', 'Màu sắc', 'Kích thước', 'Mô tả'
        ]

        if not all(col in df.columns for col in required_columns):
            return JsonResponse({'error': 'Missing required columns in the file.'}, status=400)

        df = df.fillna('')


        for index, row in df.iterrows():
            employee = None
            if row['Nhân viên']:
                employee = Employee.objects.filter(employee_name=row['Nhân viên']).first()
                if not employee:
                    employee = Employee.objects.create(
                        employee_code=new_employee_code,
                        employee_name=row['Nhân viên']
                    )

            product_type = None
            if row['Dòng sản phẩm']:
                product_type = ProductType.objects.filter(type_name=row['Dòng sản phẩm']).first()
                if not product_type:
                    product_type = ProductType.objects.create(
                        type_code=new_type_code,
                        type_name=row['Dòng sản phẩm']
                    )

            product_category = None
            if row['Chủng loại sản phẩm']:
                product_category = ProductCategory.objects.filter(category_name=row['Chủng loại sản phẩm']).first()
                if not product_category:
                    product_category = ProductCategory.objects.create(
                        category_code=new_category_code,
                        category_name=row['Chủng loại sản phẩm']
                    )

            collection = None
            if row['Bộ sưu tập']:
                collection = Collection.objects.filter(collection_name=row['Bộ sưu tập']).first()
                if not collection:
                    collection = Collection.objects.create(
                        collection_code=new_collection_code,
                        collection_name=row['Bộ sưu tập']
                    )
                
            image_file = None
            image_link = row['Hình ảnh']
            if image_link and image_link.startswith('http'):
                image_response = requests.get(image_link)
                if image_response.status_code == 200:
                    image_name = image_link.split('/')[-1]
                    image_file = ContentFile(image_response.content, name=image_name)

            design = Design.objects.create(
                design_code=row['Mã mẫu thiết kế'],
                design_name=row['Tên mẫu thiết kế'],
                employee=employee,
                product_type=product_type,
                product_category=product_category,
                collection=collection,
                is_set=row['Full bộ'],
                description=row['Mô tả'],
                image=image_file,
            )

            colors = row['Màu sắc'].split(',')
            ordering_color = 1

            color_objects = []
            for color_name in colors:
                color_name = color_name.strip()
                if color_name:
                    new_color_code = generate_new_color_code()
                    color = Color.objects.create(
                        color_name=color_name,
                        color_code=new_color_code,
                        ordering_color=f"{ordering_color:02d}",
                    )
                    ColorInDesign.objects.create(design=design, color=color)
                    color_objects.append(color)
                    ordering_color += 1

            sizes = row['Kích thước'].split(',')
            size_objects = []
            for size_name in sizes:
                size_name = size_name.strip()
                if size_name:
                    size, _ = Size.objects.get_or_create(size_name=size_name)
                    SizeInDesign.objects.create(design=design, size=size)
                    size_objects.append(size)

            for color in color_objects:
                for size in size_objects:
                    sku_code = f"{design.design_code}{color.ordering_color}{size.size_code}"
                    SKU.objects.create(
                        sku_code=sku_code,
                        sku_name=f"{design.design_name} ({color.color_name} - {size.size_name})",
                        design=design,
                        color=color,
                        size=size
                    )

        return JsonResponse({'message': 'Design templates uploaded successfully!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def delete_design(request, design_code):
    if request.method == 'POST':
        design = get_object_or_404(Design, design_code=design_code)

        
        SKU.objects.filter(design=design).delete()
        SizeInDesign.objects.filter(design=design).delete()
        color_in_designs = ColorInDesign.objects.filter(design=design)
        colors_to_check = [color_in_design.color for color_in_design in color_in_designs]

        color_in_designs.delete()

        for color in colors_to_check:
            if not ColorInDesign.objects.filter(color=color).exists():
                color.delete()

        design.delete()

        return JsonResponse({'message': 'Thiết kế đã được xóa thành công!'}, status=200)

    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def create_design(request):
    all_design = Design.objects.prefetch_related(
            Prefetch('colorindesign_set', queryset=ColorInDesign.objects.select_related('color')),
            Prefetch('sizeindesign_set', queryset=SizeInDesign.objects.select_related('size'))
        )

    current_date = now()
    year = current_date.strftime("%y")  
    month = current_date.strftime("%m") 
    last_design = Design.objects.filter(design_code__startswith=f"{year}{month}").order_by('-design_code').first()
    if last_design:
        last_sequence = int(last_design.design_code[-3:])  
        new_sequence = last_sequence + 1
    else:
        new_sequence = 1
    new_design_code = f"{year}{month}{new_sequence:03d}"

    def generate_new_color_code():
        colors = Color.objects.filter(color_code__regex=r'^RC\d{5}$').annotate(
            numeric_code=Cast(F('color_code')[2:], IntegerField())
        ).order_by('-numeric_code')
        if colors.exists():
            last_color_index = colors.first().numeric_code
        else:
            last_color_index = 0
        return f'RC{last_color_index + 1:05d}'

    def str_to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes']
        return False

    if request.method == "POST":
        if request.content_type.startswith('multipart'):
            design_code = new_design_code
            design_name = request.POST.get('design_name')

            employee_value = request.POST.get('employee')
            employee_code = employee_value.split('-')[0].strip() if employee_value else None

            type_value = request.POST.get('product_type')
            type_code = type_value.split('-')[0].strip() if type_value else None

            category_value = request.POST.get('product_category')
            category_code = category_value.split('-')[0].strip() if category_value else None

            collection_value = request.POST.get('collection')
            collection_code = collection_value.split('-')[0].strip() if collection_value else None
            
            is_set = str_to_bool(request.POST.get('is_set'))
            description = request.POST.get('description')
            image = request.FILES.get('image')

            colors = request.POST.getlist('color') 
            sizes= request.POST.getlist('size')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            design_code = new_design_code
            design_name = body.get('design_name')
            
            employee_value = body.get('employee')
            employee_code = employee_value.split('-')[0].strip() if employee_value else None

            type_value = body.get('product_type')
            type_code = type_value.split('-')[0].strip() if type_value else None

            category_value = body.get('product_category')
            category_code = category_value.split('-')[0].strip() if category_value else None

            collection_value = body.get('collection')
            collection_code = collection_value.split('-')[0].strip() if collection_value else None

            is_set = str_to_bool(body.get('is_set'))
            description = body.get('description')
            colors = body.getlist('color') 
            sizes= body.getlist('size')
            image = None 

        design = Design.objects.create(
            design_code=design_code,
            design_name=design_name,
            employee=Employee.objects.filter(employee_code=employee_code).last(),
            product_type=ProductType.objects.filter(type_code=type_code).last(),
            product_category=ProductCategory.objects.filter(category_code=category_code).last(),
            collection=Collection.objects.filter(collection_code=collection_code).last(),
            image=image,
            description=description,
            is_set=is_set,
        )

        color_objects = []
        ordering_color = 1
        for index, color_name in enumerate(colors, start=1):
            new_color_code = generate_new_color_code()
            color=Color.objects.create(
                color_code=new_color_code,
                ordering_color=f"{ordering_color:02d}",  
                color_name=color_name.strip()
            )
            ColorInDesign.objects.create(design=design, color=color)
            color_objects.append(color)
            ordering_color += 1

        size_objects = []
        for index, size_name in enumerate(sizes, start=1):
                size, _ = Size.objects.get_or_create(size_name=size_name)
                SizeInDesign.objects.create(design=design, size=size)
                size_objects.append(size)

        for color in color_objects:
            for size in size_objects:
                sku_code = f"{design.design_code}{color.ordering_color}{size.size_code}"
                SKU.objects.create(
                    sku_code=sku_code,
                    sku_name=f"{design.design_name} ({color.color_name} - {size.size_name})",
                    design=design,
                    color=color,
                    size=size
                )
        

    supplier = Supplier.objects.all()
    employee = Employee.objects.all()
    material = Material.objects.all()
    product_category = ProductCategory.objects.all()
    product_type = ProductType.objects.all()
    collection = Collection.objects.all()
    color = ColorInDesign.objects.all()
    size = SizeInDesign.objects.all()

    context = {
        'all_design': all_design,
        'new_design_code': new_design_code,
        'supplier': supplier,
        'product_category': product_category,
        'product_type': product_type,
        'collection': collection,
        'color': color,
        'size': size,
        'employee': employee,
        'material': material,
        }
    return render(request, 'catalog/create_design.html', context)

@csrf_exempt
def detail_design(request, design_code):
    design = get_object_or_404(Design, design_code=design_code)
    colors = ColorInDesign.objects.filter(design=design)
    sizes = SizeInDesign.objects.filter(design=design)
    skus = SKU.objects.filter(design=design)
    color_sku_map = {color.color: skus.filter(color=color.color) for color in colors}

    if request.method == 'POST':
        image = request.FILES.get('image')
        sku_ids = request.POST.get('sku_ids')

        if not image or not sku_ids:
            return JsonResponse({'success': False, 'message': 'Thiếu hình ảnh hoặc danh sách SKU.'})

        sku_ids = [int(id) for id in sku_ids.split(',') if id]

        for sku_id in sku_ids:
            sku = get_object_or_404(SKU, id=sku_id)
            sku.image = image
            sku.save()

        return JsonResponse({'success': True})


    context = {
        'design': design,
        'colors': colors,
        'sizes': sizes,
        'skus': skus,
        'color_sku_map': color_sku_map,
    }

    return render(request, 'catalog/detail_design.html', context)

@csrf_exempt
def update_design(request, design_code):
    design = get_object_or_404(Design, design_code=design_code)
    employee = Employee.objects.all()
    product_category = ProductCategory.objects.all()
    product_type = ProductType.objects.all()
    collection = Collection.objects.all()
    colors = ColorInDesign.objects.filter(design=design).select_related('color').values_list('color__color_name', flat=True)
    sizes_in_design = SizeInDesign.objects.filter(design=design).select_related('size').values_list('size__size_name', flat=True)

    size_list = ["3XS", "2XS", "XS", "S", "M", "L", "XL", "2XL", "3XL", "Free size"]

    def generate_new_color_code():
        colors = Color.objects.filter(color_code__regex=r'^RC\d{5}$').annotate(
            numeric_code=Cast(F('color_code')[2:], IntegerField())
        ).order_by('-numeric_code')
        if colors.exists():
            last_color_index = colors.first().numeric_code
        else:
            last_color_index = 0
        return f'RC{last_color_index + 1:05d}'

    def str_to_bool(value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes']
        return False
        
    if request.method == "POST":
        design = get_object_or_404(Design, design_code=design_code)

        if request.content_type.startswith('multipart'):
            design_name = request.POST.get('design_name')

            employee_value = request.POST.get('employee')
            employee_code = employee_value.split('-')[0].strip() if employee_value else None

            type_value = request.POST.get('product_type')
            type_code = type_value.split('-')[0].strip() if type_value else None

            category_value = request.POST.get('product_category')
            category_code = category_value.split('-')[0].strip() if category_value else None

            collection_value = request.POST.get('collection')
            collection_code = collection_value.split('-')[0].strip() if collection_value else None
            
            is_set = str_to_bool(request.POST.get('is_set'))
            description = request.POST.get('description')
            image = request.FILES.get('image')

            colors = request.POST.getlist('color')
            sizes = request.POST.getlist('size')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            design_name = body.get('design_name')
            
            employee_value = body.get('employee')
            employee_code = employee_value.split('-')[0].strip() if employee_value else None

            type_value = body.get('product_type')
            type_code = type_value.split('-')[0].strip() if type_value else None

            category_value = body.get('product_category')
            category_code = category_value.split('-')[0].strip() if category_value else None

            collection_value = body.get('collection')
            collection_code = collection_value.split('-')[0].strip() if collection_value else None

            is_set = str_to_bool(body.get('is_set'))
            description = body.get('description')
            colors = body.get('color', [])
            sizes = body.get('size', [])
            image = None

        if design_name:
            design.design_name = design_name
        if employee_code:
            design.employee = Employee.objects.filter(employee_code=employee_code).last()
        if type_code:
            design.product_type = ProductType.objects.filter(type_code=type_code).last()
        if category_code:
            design.product_category = ProductCategory.objects.filter(category_code=category_code).last()
        if collection_code:
            design.collection = Collection.objects.filter(collection_code=collection_code).last()
        if image:
            design.image = image
        if description:
            design.description = description
        design.is_set = is_set

        design.save()

        SKU.objects.filter(design=design).delete()
        SizeInDesign.objects.filter(design=design).delete()
        color_in_designs = ColorInDesign.objects.filter(design=design)
        colors_to_check = [color_in_design.color for color_in_design in color_in_designs]

        color_in_designs.delete()

        for color in colors_to_check:
            if not ColorInDesign.objects.filter(color=color).exists():
                color.delete()


        color_objects = []
        ordering_color = 1
        for color_name in colors:
            new_color_code = generate_new_color_code()
            color = Color.objects.create(
                color_code=new_color_code,
                ordering_color=f"{ordering_color:02d}",
                color_name=color_name.strip()
            )
            ColorInDesign.objects.create(design=design, color=color)
            color_objects.append(color)
            ordering_color += 1

        size_objects = []
        for size_name in sizes:
            size, _ = Size.objects.get_or_create(size_name=size_name)
            SizeInDesign.objects.create(design=design, size=size)
            size_objects.append(size)

        for color in color_objects:
            for size in size_objects:
                sku_code = f"{design.design_code}{color.ordering_color}{size.size_code}"
                SKU.objects.create(
                    sku_code=sku_code,
                    sku_name=f"{design.design_name} ({color.color_name} - {size.size_name})",
                    design=design,
                    color=color,
                    size=size
                )
    
    context = {
        'design': design,
        'product_category': product_category,
        'product_type': product_type,
        'collection': collection,
        'employee': employee,
        'colors': list(colors), 
        'sizes_in_design': list(sizes_in_design), 
        'size_list': size_list,
        'color_count': len(colors),  
        'color_range': range(1, 11),
    }
    return render(request, 'catalog/update_design.html', context)



#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

@csrf_exempt
def list_sku(request):
    valid_sort_fields = ['sku_code', 'sku_name', 'design__collection__collection_name', 'design__collection__style', 'color__color_name', 'size__size_name']
    
    sort_field = request.GET.get('sort_field', 'sku_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'sku_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_sku = SKU.objects.select_related('design', 'color', 'size')
    
    if search_query:
        all_sku = all_sku.filter(
            Q(sku_code__icontains=search_query) |
            Q(sku_name__icontains=search_query) |
            Q(design__collection__collection_name__icontains=search_query) |
            Q(design__collection__style__icontains=search_query) |
            Q(color__color_name__icontains=search_query) |
            Q(size__size_name__icontains=search_query)
        )
    
    all_sku = all_sku.order_by(sort_field)
    
    paginator = Paginator(all_sku, 10) 
    page_number = request.GET.get('page')
    sku_page = paginator.get_page(page_number)
    
    designs = Design.objects.all()
    colors = Color.objects.all()
    sizes = Size.objects.all()
    
    context = {
        'sku_page': sku_page,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
        'designs': designs,
        'colors': colors,
        'sizes': sizes,
    }
    
    return render(request, 'catalog/list_sku.html', context)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

def list_sku_inventory(request):
    sort_field = request.GET.get('sort_field', 'sku_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    skus = SKU.objects.filter(inventorysku__isnull=True)
    for sku in skus:
        InventorySKU.objects.create(sku=sku, quantity=0)
    
    inventory = SKU.objects.annotate(
        quantity=Coalesce(F('inventorysku__quantity'), Value(0))
    )
    
    if search_query:
        inventory = inventory.filter(
            Q(sku_code__icontains=search_query) |
            Q(sku_name__icontains=search_query) 
        )
    
    inventory = inventory.order_by(sort_field)
    paginator = Paginator(inventory, 10)  
    page_number = request.GET.get('page')
    inventory_page = paginator.get_page(page_number)
    
    context = {
        'inventory_page': inventory_page,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_sku_inventory.html', context)

#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


@csrf_exempt
def list_qc(request):
    valid_sort_fields = ['qc_code', 'employee__employee_name', 'sku__sku_name', 'qc_date', 'status', 'order_status', 'quantity']
    sort_field = request.GET.get('sort_field', 'qc_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'qc_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_qc = QC.objects.all()
    
    if search_query:
        all_qc = all_qc.filter(
            Q(qc_code__icontains=search_query) |
            Q(employee__employee_name__icontains=search_query) |
            Q(status__icontains=search_query) |
            Q(order_status__icontains=search_query) |
            Q(sku__sku_name__icontains=search_query)
        )
    
    all_qc = all_qc.order_by(sort_field)
    paginator = Paginator(all_qc, 10)
    page_number = request.GET.get('page')
    qc_page = paginator.get_page(page_number)
    
    qcs = QC.objects.filter(qc_code__regex=r'^QC\d+$').annotate(
        numeric_code=Cast(F('qc_code')[2:], IntegerField())
    ).order_by('-numeric_code')

    last_qc_index = qcs.first().numeric_code if qcs.exists() else 0
    new_qc_code = f'QC{last_qc_index + 1:04d}'
    current_time = timezone.now() 
    employees = Employee.objects.all()
    skus = SKU.objects.all()
    
    context = {
        'qc_page': qc_page,
        'new_qc_code': new_qc_code,
        'current_time': current_time,
        'employees': employees,
        'skus': skus,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
  
    return render(request, 'catalog/list_qc.html', context)

@csrf_exempt
def create_qc(request):
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        qc_code = request.POST.get('qc_code') or body.get('qc_code')
        qc_date = request.POST.get('qc_date') or body.get('qc_date')
        qc_date = validate_date(qc_date)
        employee_value = request.POST.get('employee') or body.get('employee')
        employee = employee_value.split('-')[0].strip() if employee_value else None
        sku_value = request.POST.get('sku') or body.get('sku')
        sku = sku_value.split('-')[0].strip() if sku_value else None
        quantity = request.POST.get('quantity') or body.get('quantity')
        status = request.POST.get('status') or body.get('status')
        note = request.POST.get('note') or body.get('note')
        QC.objects.create(
            qc_code=qc_code,
            qc_date=qc_date,
            employee=Employee.objects.filter(employee_code=employee).last(),
            sku=SKU.objects.filter(sku_code=sku).last(),
            quantity=quantity,
            status=status,
            order_status='completed',
            note=note,
        )
        return JsonResponse({'message': 'Phiếu QC đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400) 

@csrf_exempt
def upload_qc(request):
    employees = Employee.objects.filter(employee_code__regex=r'^TSH\d+$').annotate(
        numeric_code=Cast(F('employee_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    
    if employees.exists():
        last_employee_index = employees.first().numeric_code  
    else:
        last_employee_index = 0
    
    new_employee_code = f'TSH{last_employee_index + 1:03d}' 
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã phiếu QC', 'Ngày QC', 'Nhân viên', 'Mã SKU', 'Số lượng', 'Trạng thái', 'Ghi chú']

        if not all(col in df.columns for col in required_columns):
            return JsonResponse({'error': 'Missing required columns in the file.'}, status=400)
        
        df = df.fillna('')

        for index, row in df.iterrows():
            
            employee = None
            if row['Nhân viên']:
                employee = Employee.objects.filter(employee_name=row['Nhân viên']).first()
                if not employee:
                    employee = Employee.objects.create(
                        employee_code=new_employee_code,
                        employee_name=row['Nhân viên']
                    )

            sku = None
            if row['Mã SKU']:
                sku = SKU.objects.filter(sku_name=row['Mã SKU']).first()
            
            QC.objects.create(
                qc_code=row['Mã phiếu QC'],
                qc_date=row['Ngày QC'],
                employee=employee,
                sku=sku,
                quantity=row['Số lượng'],
                status=row['Trạng thái'],
                order_status='completed',
                note=row['Ghi chú']
            )
        
        return JsonResponse({'message': 'QC data uploaded successfully!'})
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def update_qc(request, qc_code):
    if request.method == "POST":
        qc = get_object_or_404(QC, qc_code=qc_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        qc_code = request.POST.get('qc_code') or body.get('qc_code')
        qc_date = request.POST.get('qc_date') or body.get('qc_date')
        qc_date = validate_date(qc_date)
        employee_value = request.POST.get('employee') or body.get('employee')
        employee = employee_value.split('-')[0].strip() if employee_value else None
        sku_value = request.POST.get('sku') or body.get('sku')
        sku = sku_value.split('-')[0].strip() if sku_value else None
        quantity = request.POST.get('quantity') or body.get('quantity')
        status = request.POST.get('status') or body.get('status')
        note = request.POST.get('note') or body.get('note')

        if qc_code:
            qc.qc_code = qc_code
        if qc_date:
            qc.qc_date = qc_date
        if employee:
            qc.employee = Employee.objects.filter(employee_code=employee).last()
        if sku:
            qc.sku = SKU.objects.filter(sku_code=sku).last()
        if quantity:
            qc.quantity = quantity
        if status:
            qc.status = status
        if note:
            qc.note = note

        qc.order_status='completed'
        qc.save()

        return JsonResponse({'message': 'Loại nguyên vật liệu đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def cancel_qc(request, qc_code):
    if request.method == "POST":
        qc = get_object_or_404(QC, qc_code=qc_code)
        print(qc)
        qc.order_status = "cancelled"
        qc.save()
        return JsonResponse({'message': 'Phiếu QC đã được hủy thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

@csrf_exempt
def list_import(request):
    valid_sort_fields = ['import_code', 'import_date', 'total', 'status']
    sort_field = request.GET.get('sort_field', 'import_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'import_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_imports = Import.objects.all()
    
    if search_query:
        all_imports = all_imports.filter(
            Q(import_code__icontains=search_query) |
            Q(status__icontains=search_query)
        )
    
    all_imports = all_imports.order_by(sort_field)
    paginator = Paginator(all_imports, 10)
    page_number = request.GET.get('page')
    import_page = paginator.get_page(page_number)
    
    imports = Import.objects.filter(import_code__regex=r'^IM\d+$').annotate(
        numeric_code=Cast(F('import_code')[2:], IntegerField())
    ).order_by('-numeric_code')
    
    last_import_index = imports.first().numeric_code if imports.exists() else 0
    new_import_code = f'IM{last_import_index + 1:04d}'
    current_time = timezone.now()
    skus = SKU.objects.all()
    
    context = {
        'import_page': import_page,
        'new_import_code': new_import_code,
        'current_time': current_time,
        'skus': skus,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_import.html', context)

@csrf_exempt
def create_import(request):
    form_values = request.POST.copy()
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        import_code = request.POST.get('import_code') or body.get('import_code')
        import_date = request.POST.get('import_date') or body.get('import_date')
        import_date = validate_date(import_date)
        total = request.POST.get('total') or body.get('total')
        note = request.POST.get('note') or body.get('note')

        import_obj = Import.objects.create(
            import_code=import_code,
            import_date=import_date,
            total=total,
            status='completed',
            note=note
        )
        import_lines = body.get('import_lines', [])

        import_line_codes = []
        skus = []
        quantities = []

        for line in import_lines:
            import_line_codes.append(line.get('import_line_code', ''))
            skus.append(line.get('sku', ''))
            quantities.append(int(line.get('quantity', 0))) 

        if not import_lines:
            import_line_codes = form_values.getlist('import_line_code', [])
            skus = form_values.getlist('sku', [])
            quantities = [int(q) for q in form_values.getlist('quantity', [])]  

        for import_line_code, sku, quantity in zip(import_line_codes, skus, quantities):
            sku_code = sku.split('-')[0].strip()
            sku_flt = SKU.objects.filter(sku_code=sku_code).last()

            if sku_flt:
                ImportLine.objects.create(
                    import_obj=import_obj,
                    import_line_code=import_line_code,
                    sku=sku_flt,
                    quantity=quantity,
                )

                inventory, created = InventorySKU.objects.get_or_create(sku=sku_flt)
                inventory.quantity += quantity
                inventory.save()

        return JsonResponse({'message': 'Đơn hàng đã được tạo thành công!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def upload_import(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ["Mã nhập kho", "Ngày nhập", "Tổng số lượng", "Ghi chú", "STT", "SKU", "Số lượng"]
        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/import')

        import_dict = defaultdict(list)
        df = df.fillna('')  
        for _, row in df.iterrows():
            import_dict[row['Mã nhập kho']].append(row)

        for import_code, rows in import_dict.items():
            first_row = rows[0]
            import_date = pd.to_datetime(first_row['Ngày nhập'], errors='coerce').date() if first_row['Ngày nhập'] else None
            total_quantity = first_row['Tổng số lượng'] if pd.notna(first_row['Tổng số lượng']) else 0
            note = first_row['Ghi chú']

            import_obj = Import.objects.create(
                import_code=import_code,
                import_date=import_date,
                total=total_quantity,
                note=note,
                status='completed'
            )

            for row in rows:
                sku = SKU.objects.filter(sku_name=row['SKU']).first()
                if not sku:
                    continue 

                quantity = int(row['Số lượng']) if pd.notna(row['Số lượng']) else 0
                
                ImportLine.objects.create(
                    import_obj=import_obj,
                    import_line_code=row['STT'],
                    sku=sku,
                    quantity=quantity,
                )

                inventory_sku, created = InventorySKU.objects.get_or_create(sku=sku, defaults={'quantity': 0})
                inventory_sku.quantity += quantity
                inventory_sku.save()

        return JsonResponse({'message': 'Dữ liệu nhập kho đã được tải lên thành công!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def cancel_import(request, import_code):
    if request.method == "POST":
        import_obj = get_object_or_404(Import, import_code=import_code)

        if import_obj.status == "cancelled":
            return JsonResponse({'error': 'Phiếu nhập đã bị hủy trước đó!'}, status=400)
        import_lines = import_obj.importline_set.all()

        for line in import_lines:
            sku_flt = line.sku
            if sku_flt:
                inventory = InventorySKU.objects.filter(sku=sku_flt).first()
                if inventory:
                    inventory.quantity = max(0, inventory.quantity - line.quantity)
                    inventory.save()

        import_obj.status = "cancelled"
        import_obj.save()

        return JsonResponse({'message': 'Phiếu nhập kho đã được hủy thành công và số lượng đã được cập nhật!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def update_import(request, import_code):
    if request.method == "POST":
        import_obj = get_object_or_404(Import, import_code=import_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        import_code = request.POST.get('import_code') or body.get('import_code')
        import_date = request.POST.get('import_date') or body.get('import_date')
        import_date = validate_date(import_date)
        total = request.POST.get('total') or body.get('total')
        status = request.POST.get('status') or body.get('status')
        note = request.POST.get('note') or body.get('note')

        if import_code:
            import_obj.import_code = import_code
        if import_date:
            import_obj.import_date = import_date
        if total:
            import_obj.total = total
        if status:
            import_obj.status = status
        if note:
            import_obj.note = note

        import_obj.status = 'completed'
        import_obj.save()

        existing_import_lines = {il.import_line_code: il for il in ImportLine.objects.filter(import_obj=import_obj)}
        import_lines = body.get('importlines_update', [])
        updated_import_lines = set()

        for line in import_lines:
            import_line_code = line.get('import_line_code')
            sku_code = line.get('sku').split('-')[0].strip()
            sku = SKU.objects.filter(sku_code=sku_code).last()
            quantity = int(line.get('quantity', 0))  # Đảm bảo là số nguyên

            if import_line_code in existing_import_lines:
                import_line = existing_import_lines[import_line_code]
                
                inventory = InventorySKU.objects.filter(sku=import_line.sku).first()
                if inventory:
                    inventory.quantity = max(0, inventory.quantity - import_line.quantity)
                    inventory.save()
                
                import_line.sku = sku
                import_line.quantity = quantity
                import_line.save()

            else:
                import_line = ImportLine.objects.create(
                    import_obj=import_obj,
                    import_line_code=import_line_code,
                    sku=sku,
                    quantity=quantity
                )

            inventory, created = InventorySKU.objects.get_or_create(sku=sku)
            inventory.quantity += quantity
            inventory.save()

            updated_import_lines.add(import_line_code)

        for import_line_code, import_line in existing_import_lines.items():
            if import_line_code not in updated_import_lines:
                inventory = InventorySKU.objects.filter(sku=import_line.sku).first()
                if inventory:
                    inventory.quantity = max(0, inventory.quantity - import_line.quantity)
                    inventory.save()

                import_line.delete()

        return JsonResponse({'message': 'Phiếu nhập kho đã được cập nhật thành công!'}, status=200)

    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

@csrf_exempt
def list_export(request):
    valid_sort_fields = ['export_code', 'export_date', 'total', 'status']
    sort_field = request.GET.get('sort_field', 'export_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'export_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_exports = Export.objects.all()
    
    if search_query:
        all_exports = all_exports.filter(
            Q(export_code__icontains=search_query) |
            Q(status__icontains=search_query)
        )
    
    all_exports = all_exports.order_by(sort_field)
    paginator = Paginator(all_exports, 10)
    page_number = request.GET.get('page')
    export_page = paginator.get_page(page_number)
    
    exports = Export.objects.filter(export_code__regex=r'^EX\d+$').annotate(
        numeric_code=Cast(F('export_code')[2:], IntegerField())
    ).order_by('-numeric_code')
    
    last_export_index = exports.first().numeric_code if exports.exists() else 0
    new_export_code = f'EX{last_export_index + 1:04d}'
    current_time = timezone.now()
    skus = SKU.objects.all()
    
    context = {
        'export_page': export_page,
        'new_export_code': new_export_code,
        'current_time': current_time,
        'skus': skus,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_export.html', context)

@csrf_exempt
def create_export(request):
    form_values = request.POST.copy()
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        export_code = request.POST.get('export_code') or body.get('export_code')
        export_date = request.POST.get('export_date') or body.get('export_date')
        export_date = validate_date(export_date)
        total = request.POST.get('total') or body.get('total')
        note = request.POST.get('note') or body.get('note')

        export_obj = Export.objects.create(
            export_code=export_code,
            export_date=export_date,
            total=total,
            status='completed',
            note=note
        )
        export_lines = body.get('export_lines', [])

        export_line_codes = []
        skus = []
        quantities = []

        for line in export_lines:
            export_line_codes.append(line.get('export_line_code', ''))
            skus.append(line.get('sku', ''))
            quantities.append(int(line.get('quantity', 0)))

        if not export_lines:
            export_line_codes = form_values.getlist('export_line_code', [])
            skus = form_values.getlist('sku', [])
            quantities = [int(q) for q in form_values.getlist('quantity', [])]

        for export_line_code, sku, quantity in zip(export_line_codes, skus, quantities):
            sku_code = sku.split('-')[0].strip()
            sku_flt = SKU.objects.filter(sku_code=sku_code).last()

            if sku_flt:
                ExportLine.objects.create(
                    export_obj=export_obj,
                    export_line_code=export_line_code,
                    sku=sku_flt,
                    quantity=quantity,
                )

                inventory, created = InventorySKU.objects.get_or_create(sku=sku_flt)
                if inventory.quantity >= quantity:
                    inventory.quantity -= quantity
                    inventory.save()
                else:
                    return JsonResponse({'error': f'Số lượng tồn kho không đủ cho SKU {sku_code}'}, status=400)

        return JsonResponse({'message': 'Đơn hàng xuất đã được tạo thành công!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def upload_export(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ["Mã xuất kho", "Ngày xuất", "Tổng số lượng", "Ghi chú", "STT", "SKU", "Số lượng"]
        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/export')

        export_dict = defaultdict(list)
        df = df.fillna('')  
        for _, row in df.iterrows():
            export_dict[row['Mã xuất kho']].append(row)

        for export_code, rows in export_dict.items():
            first_row = rows[0]
            export_date = pd.to_datetime(first_row['Ngày xuất'], errors='coerce').date() if first_row['Ngày xuất'] else None
            total_quantity = first_row['Tổng số lượng'] if pd.notna(first_row['Tổng số lượng']) else 0
            note = first_row['Ghi chú']

            export_obj = Export.objects.create(
                export_code=export_code,
                export_date=export_date,
                total=total_quantity,
                note=note,
                status='completed'
            )

            for row in rows:
                sku = SKU.objects.filter(sku_name=row['SKU']).first()
                if not sku:
                    continue 

                quantity = int(row['Số lượng']) if pd.notna(row['Số lượng']) else 0
                
                ExportLine.objects.create(
                    export_obj=export_obj,
                    export_line_code=row['STT'],
                    sku=sku,
                    quantity=quantity,
                )

                inventory_sku = InventorySKU.objects.filter(sku=sku).first()
                if inventory_sku and inventory_sku.quantity >= quantity:
                    inventory_sku.quantity -= quantity
                    inventory_sku.save()
                else:
                    return JsonResponse({'error': f'Không đủ tồn kho cho SKU {sku.sku_name}'}, status=400)

        return JsonResponse({'message': 'Dữ liệu xuất kho đã được tải lên thành công!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def cancel_export(request, export_code):
    if request.method == "POST":
        export_obj = get_object_or_404(Export, export_code=export_code)

        if export_obj.status == "cancelled":
            return JsonResponse({'error': 'Phiếu xuất đã bị hủy trước đó!'}, status=400)
        
        export_lines = export_obj.exportline_set.all()

        for line in export_lines:
            sku_flt = line.sku
            if sku_flt:
                inventory = InventorySKU.objects.filter(sku=sku_flt).first()
                if inventory:
                    inventory.quantity += line.quantity
                    inventory.save()

        export_obj.status = "cancelled"
        export_obj.save()

        return JsonResponse({'message': 'Phiếu xuất kho đã được hủy thành công và số lượng đã được cập nhật!'})

    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def update_export(request, export_code):
    if request.method == "POST":
        export_obj = get_object_or_404(Export, export_code=export_code)
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        export_code = request.POST.get('export_code') or body.get('export_code')
        export_date = request.POST.get('export_date') or body.get('export_date')
        export_date = validate_date(export_date)
        total = request.POST.get('total') or body.get('total')
        status = request.POST.get('status') or body.get('status')
        note = request.POST.get('note') or body.get('note')

        if export_code:
            export_obj.export_code = export_code
        if export_date:
            export_obj.export_date = export_date
        if total:
            export_obj.total = total
        if status:
            export_obj.status = status
        if note:
            export_obj.note = note

        export_obj.status = 'completed'
        export_obj.save()

        existing_export_lines = {el.export_line_code: el for el in ExportLine.objects.filter(export_obj=export_obj)}
        export_lines = body.get('exportlines_update', [])
        updated_export_lines = set()

        for line in export_lines:
            export_line_code = line.get('export_line_code')
            sku_code = line.get('sku').split('-')[0].strip()
            sku = SKU.objects.filter(sku_code=sku_code).last()
            quantity = int(line.get('quantity', 0)) 

            if export_line_code in existing_export_lines:
                export_line = existing_export_lines[export_line_code]
                
                inventory = InventorySKU.objects.filter(sku=export_line.sku).first()
                if inventory:
                    inventory.quantity += export_line.quantity
                    inventory.save()
                
                export_line.sku = sku
                export_line.quantity = quantity
                export_line.save()

            else:
                export_line = ExportLine.objects.create(
                    export_obj=export_obj,
                    export_line_code=export_line_code,
                    sku=sku,
                    quantity=quantity
                )

            inventory, created = InventorySKU.objects.get_or_create(sku=sku)
            inventory.quantity = max(0, inventory.quantity - quantity)
            inventory.save()

            updated_export_lines.add(export_line_code)

        for export_line_code, export_line in existing_export_lines.items():
            if export_line_code not in updated_export_lines:
                inventory = InventorySKU.objects.filter(sku=export_line.sku).first()
                if inventory:
                    inventory.quantity += export_line.quantity
                    inventory.save()

                export_line.delete()

        return JsonResponse({'message': 'Phiếu xuất kho đã được cập nhật thành công!'}, status=200)

    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


@csrf_exempt
def list_employee(request):
    valid_sort_fields = ['employee_code', 'employee_name', 'position', 'gender', 'date_of_birth', 'department', 'employment_status']
    sort_field = request.GET.get('sort_field', 'employee_code')
    sort_order = request.GET.get('sort_order', 'asc')  
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'employee_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_employees = Employee.objects.all()
    
    if search_query:
        all_employees = all_employees.filter(
            Q(employee_code__icontains=search_query) |
            Q(employee_name__icontains=search_query) |
            Q(position__icontains=search_query)
        )
    
    all_employees = all_employees.order_by(sort_field)
    paginator = Paginator(all_employees, 10)
    page_number = request.GET.get('page')
    employee_page = paginator.get_page(page_number)
    
    context = {
        'employee_page': employee_page,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_employee.html', context)

@csrf_exempt
def create_employee(request):
    employees = Employee.objects.filter(employee_code__regex=r'^TSH\d+$').annotate(
        numeric_code=Cast(F('employee_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    
    if employees.exists():
        last_employee_index = employees.first().numeric_code  
    else:
        last_employee_index = 0
    
    new_employee_code = f'TSH{last_employee_index + 1:03d}' 

    if request.method == "POST":
        if request.content_type.startswith('multipart'):
            employee_name = request.POST.get('employee_name')
            position = request.POST.get('position')
            department = request.POST.get('department')
            phone_number = request.POST.get('phone_number')
            gender = request.POST.get('gender')
            date_of_birth = request.POST.get('date_of_birth')
            address = request.POST.get('address')
            employment_status = request.POST.get('employment_status')
            image = request.FILES.get('image')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            employee_name = body.get('employee_name')
            position = body.get('position')
            department = body.get('department')
            phone_number = body.get('phone_number')
            gender = body.get('gender')
            date_of_birth = body.get('date_of_birth')
            address = body.get('address')
            employment_status = body.get('employment_status')
            image = None  
        
        Employee.objects.create(
            employee_code=new_employee_code,
            employee_name=employee_name,
            position=position,
            department=department,
            phone_number=phone_number,
            gender=gender,
            date_of_birth=date_of_birth,
            address=address,
            employment_status=employment_status,
            image=image,
        )
        return JsonResponse({'message': 'Nhân viên đã được tạo thành công!'})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def upload_employee(request):
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã nhân viên', 'Tên nhân viên', 'Chức vụ', 'Phòng ban', 'Số điện thoại', 'Giới tính', 'Ngày sinh', 'Địa chỉ']
        
        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/employee')

        df = df.fillna('')
        for index, row in df.iterrows():
            Employee.objects.create(
                employee_code=row['Mã nhân viên'],
                employee_name=row['Tên nhân viên'],
                position=row['Chức vụ'],
                department=row['Phòng ban'],
                phone_number=row['Số điện thoại'],
                gender=row['Giới tính'],
                date_of_birth=row['Ngày sinh'],
                address=row['Địa chỉ'],
                employment_status='active',
            )

        return JsonResponse({'message': 'Dữ liệu nhân viên đã được tải lên thành công!'}, status=200)
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt 
def delete_employee(request, employee_code):
    if request.method == 'POST':
        employee = get_object_or_404(Employee, employee_code=employee_code)
        employee.delete()

        return JsonResponse({'message': 'Nhân viên đã được xóa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt
def update_employee(request, employee_code):
    if request.method == "POST":
        employee = get_object_or_404(Employee, employee_code=employee_code)

        if request.content_type.startswith('multipart'):
            employee_name = request.POST.get('employee_name')
            position = request.POST.get('position')
            department = request.POST.get('department')
            phone_number = request.POST.get('phone_number')
            gender = request.POST.get('gender')
            date_of_birth = request.POST.get('date_of_birth')
            address = request.POST.get('address')
            employment_status = request.POST.get('employment_status')
            image = request.FILES.get('image')
        else:
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode)
            employee_name = body.get('employee_name')
            position = body.get('position')
            department = body.get('department')
            phone_number = body.get('phone_number')
            gender = body.get('gender')
            date_of_birth = body.get('date_of_birth')
            address = body.get('address')
            employment_status = body.get('employment_status')
            image = None  
        
        if employee_name:
            employee.employee_name = employee_name
        if position:
            employee.position = position
        if department:
            employee.department = department
        if phone_number:
            employee.phone_number = phone_number
        if gender:
            employee.gender = gender
        if date_of_birth:
            employee.date_of_birth = date_of_birth
        if address:
            employee.address = address
        if employment_status:
            employee.employment_status = employment_status
        if image:
            employee.image = image
        
        employee.save()

        return JsonResponse({'message': 'Nhân viên đã được chỉnh sửa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

def list_progress(request):
    valid_sort_fields = ['progress_code', 'work_date', 'status', 'tailor__employee_name', 'design__design_name', 'task_name', 'start_time', 'end_time', 'main_fabric_meters']
    sort_field = request.GET.get('sort_field', 'progress_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()
    page_number = request.GET.get('page', 1)
    
    if sort_field not in valid_sort_fields:
        sort_field = 'progress_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_progress = Progress.objects.all()
    
    if search_query:
        all_progress = all_progress.filter(
            Q(progress_code__icontains=search_query) |
            Q(work_date__icontains=search_query) |
            Q(tailor__employee_name__icontains=search_query) |
            Q(design__design_name__icontains=search_query) |
            Q(task_name__icontains=search_query) |
            Q(status__icontains=search_query)
        )
    
    all_progress = all_progress.order_by(sort_field)
    
    paginator = Paginator(all_progress, 10)  
    progress_page = paginator.get_page(page_number)
    
    progress_entries = Progress.objects.filter(progress_code__regex=r'^PG\d+$')\
        .annotate(numeric_code=Cast(F('progress_code')[2:], IntegerField()))\
        .order_by('-numeric_code')
    
    last_progress_index = progress_entries.first().numeric_code if progress_entries.exists() else 0
    new_progress_code = f'PG{last_progress_index + 1:07d}'
    
    for progress in progress_page:
        if progress.tailor:
            parts = progress.tailor.employee_name.split()
            progress.tailor.short_name = f"C.{parts[-1]}" if len(parts) > 1 else f"C.{parts[0]}"
    
    current_time = timezone.now()
    current_hour_minute = current_time.strftime('%H:%M')
    employees = Employee.objects.all()
    
    designs = Design.objects.all().prefetch_related('colorindesign_set__color', 'sizeindesign_set__size')
    design_data = [{
        'design': design,
        'colors': [cid.color.color_name for cid in design.colorindesign_set.all()],
        'sizes': [sid.size.size_name for sid in design.sizeindesign_set.all()]
    } for design in designs]
    
    context = {
        'progress_page': progress_page,
        'new_progress_code': new_progress_code,
        'current_time': current_time,
        'employees': employees,
        'designs': design_data,
        'current_hour_minute': current_hour_minute,
        'current_sort_field': sort_field,
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_progress.html', context)

@csrf_exempt
def create_progress(request):
    if request.method == "POST":
        if request.content_type == "application/json":
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode) if body_unicode else {}
        else:
            body = {}

        progress_code = request.POST.get('progress_code') or body.get('progress_code')
        work_date = request.POST.get('work_date') or body.get('work_date')
        tailor_value = request.POST.get('tailor') or body.get('tailor')
        tailor = tailor_value.split('-')[0].strip() if tailor_value else None
        design_value = request.POST.get('design') or body.get('design')
        design = design_value.split('-')[0].strip() if design_value else None
        color = request.POST.get('color') or body.get('color')
        size = request.POST.get('size') or body.get('size')
        design_name = request.POST.get('design_name') or body.get('design_name')
        task_name = request.POST.get('task_name') or body.get('task_name')
        main_fabric_meters = request.POST.get('main_fabric_meters') or body.get('main_fabric_meters')
        lining_fabric_meters = request.POST.get('lining_fabric_meters') or body.get('lining_fabric_meters')
        start_time = request.POST.get('start_time') or body.get('start_time')
        end_time = request.POST.get('end_time') or body.get('end_time')
        status = request.POST.get('status') or body.get('status')
        notes = request.POST.get('notes') or body.get('notes')
        
        Progress.objects.create(
            progress_code=progress_code,
            work_date=work_date,
            tailor=Employee.objects.filter(employee_code=tailor).last(),
            design=Design.objects.filter(design_code=design).last(),
            color=color,
            size=size,
            design_name=design_name,
            task_name=task_name,
            main_fabric_meters=main_fabric_meters,
            lining_fabric_meters=lining_fabric_meters,
            start_time=start_time,
            end_time=end_time,
            status=status,
            notes=notes,
        )
        
        return JsonResponse({'message': 'Phiếu tiến độ đã được tạo thành công!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def upload_progress(request):
    employees = Employee.objects.filter(employee_code__regex=r'^TSH\d+$').annotate(
        numeric_code=Cast(F('employee_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    
    if employees.exists():
        last_employee_index = employees.first().numeric_code  
    else:
        last_employee_index = 0
    
    new_employee_code = f'TSH{last_employee_index + 1:03d}' 

    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã phiếu', 'Ngày làm việc', 'Nhân viên', 'Mẫu thiết kế', 'Màu sắc', 'Kích thước', 'Tên thiết kế', 'Tên công việc', 'Số mét vải chính', 'Số mét vải lót', 'Giờ bắt đầu', 'Giờ kết thúc', 'Trạng thái', 'Ghi chú']
        
        if not all(col in df.columns for col in required_columns):
            messages.error(request, 'Thiếu các cột bắt buộc trong tệp.')
            return redirect('/progress')

        df = df.fillna('')
        for index, row in df.iterrows():
            tailor = None
            if row['Nhân viên']:
                tailor = Employee.objects.filter(employee_name=row['Nhân viên']).first()
                if not tailor:
                    tailor = Employee.objects.create(
                        employee_code=new_employee_code,
                        employee_name=row['Nhân viên']
                    )

            design = None
            if row['Mẫu thiết kế']:
                design = Design.objects.filter(design_name=row['Mẫu thiết kế']).first()

            Progress.objects.create(
                progress_code=row['Mã phiếu'],
                work_date=row['Ngày làm việc'],
                tailor=tailor,
                design=design,
                color=row['Màu sắc'],
                size=row['Kích thước'],
                design_name=row['Tên thiết kế'],
                task_name=row['Tên công việc'],
                main_fabric_meters=row['Số mét vải chính'] if row['Số mét vải chính'] else 0,
                lining_fabric_meters=row['Số mét vải lót'] if row['Số mét vải lót'] else 0,
                start_time=row['Giờ bắt đầu'],
                end_time=row['Giờ kết thúc'],
                status=row['Trạng thái'],
                notes=row['Ghi chú'],
            )

        return JsonResponse({'message': 'Dữ liệu tiến độ đã được tải lên thành công!'}, status=200)
    return JsonResponse({'error': 'Bad request'}, status=400)

@csrf_exempt
def update_progress(request, progress_code):
    if request.method == "POST":
        progress = get_object_or_404(Progress, progress_code=progress_code)
        
        if request.content_type == "application/json":
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode) if body_unicode else {}
        else:
            body = {}

        work_date = request.POST.get('work_date') or body.get('work_date')
        tailor_value = request.POST.get('tailor') or body.get('tailor')
        tailor = tailor_value.split('-')[0].strip() if tailor_value else None
        design_value = request.POST.get('design') or body.get('design')
        design = design_value.split('-')[0].strip() if design_value else None
        color = request.POST.get('color') or body.get('color')
        size = request.POST.get('size') or body.get('size')
        design_name = request.POST.get('design_name') or body.get('design_name')
        
        task_name = request.POST.get('task_name') or body.get('task_name')
        main_fabric_meters = request.POST.get('main_fabric_meters') or body.get('main_fabric_meters')
        lining_fabric_meters = request.POST.get('lining_fabric_meters') or body.get('lining_fabric_meters')
        start_time = request.POST.get('start_time') or body.get('start_time')
        end_time = request.POST.get('end_time') or body.get('end_time')
        status = request.POST.get('status') or body.get('status')
        notes = request.POST.get('notes') or body.get('notes')

        if work_date:
            progress.work_date = work_date
        if tailor:
            tailor = Employee.objects.get(employee_code=tailor)
            progress.tailor = tailor
        if design:
            design = Design.objects.get(design_code=design)
            progress.design = design
        if color:
            progress.color = color
        if size:
            progress.size = size
        if design_name:
            progress.design_name = design_name

        if task_name:
            progress.task_name = task_name
        if main_fabric_meters:
            progress.main_fabric_meters = float(main_fabric_meters)  
        if lining_fabric_meters:
            progress.lining_fabric_meters = float(lining_fabric_meters) 
        if start_time:
            progress.start_time = start_time
        if end_time:
            progress.end_time = end_time
        if status:
            progress.status = status
        if notes:
            progress.notes = notes

        progress.save()

        return JsonResponse({'message': 'Progress đã được cập nhật thành công!'}, status=200)
    
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

@csrf_exempt 
def delete_progress(request, progress_code):
    if request.method == 'POST':
        progress = get_object_or_404(Progress, progress_code=progress_code)
        progress.delete()

        return JsonResponse({'message': 'Phiếu tiến độ đã được xóa thành công!'}, status=200)
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)

#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


def reduce_inventory(material_name, quantity):
    if material_name:
        material = Material.objects.filter(material_name=material_name).last()
        if material:
            inventory, created = Inventory.objects.get_or_create(material=material, defaults={'quantity': 0})
            if inventory.quantity >= quantity:
                inventory.quantity -= quantity
                inventory.save()
            else:
                return JsonResponse({'error': f'Không đủ {material_name} trong kho'}, status=400)

@csrf_exempt
def upload_issue(request):
    employees = Employee.objects.filter(employee_code__regex=r'^TSH\d+$').annotate(
        numeric_code=Cast(F('employee_code')[3:], IntegerField())
    ).order_by('-numeric_code')
    
    if employees.exists():
        last_employee_index = employees.first().numeric_code  
    else:
        last_employee_index = 0
    
    new_employee_code = f'TSH{last_employee_index + 1:03d}' 
    
    if request.method == 'POST':
        if request.FILES.get('file'):
            uploaded_file = request.FILES['file']
            df = pd.read_excel(uploaded_file)
        elif request.POST.get('sheetUrl'):
            sheet_url = request.POST.get('sheetUrl')
            if not sheet_url.startswith('https://docs.google.com/spreadsheets/d/'):
                return JsonResponse({'error': 'Invalid Google Sheets URL'}, status=400)

            sheet_id = sheet_url.split('/d/')[1].split('/')[0]
            sheet_url = f'https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx'
            response = requests.get(sheet_url)
            if response.status_code != 200:
                return JsonResponse({'error': 'Failed to fetch Google Sheets data'}, status=400)

            df = pd.read_excel(io.BytesIO(response.content))
        else:
            return JsonResponse({'error': 'No file or URL provided'}, status=400)

        required_columns = ['Mã phiếu xuất', 'Ngày xuất', 'Thợ may', 'Mẫu thiết kế', 'Mã SKU', 'Tên SKU', 'Màu', 'Size', 'Loại may', 'Ghi chú', 'Vải chính', 'Vải lót', 'Số mét vải chính', 'Số mét vải lót']
        
        if not all(col in df.columns for col in required_columns):
            return JsonResponse({'error': 'Missing required columns in the file.'}, status=400)
        
        df = df.fillna('')

        for index, row in df.iterrows():
            tailor = None
            if row['Thợ may']:
                tailor = Employee.objects.filter(employee_name=row['Thợ may']).first()
                if not tailor:
                    tailor = Employee.objects.create(
                        employee_code=new_employee_code,
                        employee_name=row['Thợ may']
                    )
            
            design = Design.objects.filter(design_name=row['Mẫu thiết kế']).first()
            sku = SKU.objects.filter(sku_name=row['Tên SKU']).first()
            main_fabric = Material.objects.filter(material_name=row['Vải chính']).first()
            lining_fabric = Material.objects.filter(material_name=row['Vải lót']).first()
            
            issue = Issue.objects.create(
                issue_code=row['Mã phiếu xuất'],
                issue_date=row['Ngày xuất'],
                tailor=tailor,
                design_code=design,
                sku_code=row['Mã SKU'],
                sku_name=sku,
                color=row['Màu'],
                size=row['Size'],
                sewing_type=row['Loại may'],
                notes=row['Ghi chú'],
                main_fabric=main_fabric,
                lining_fabric=lining_fabric,
                main_fabric_meters=row['Số mét vải chính'],
                lining_fabric_meters=row['Số mét vải lót'],
                status='completed'
            )
            
            if row['Số mét vải chính'] > 0:
                response = reduce_inventory(row['Vải chính'], row['Số mét vải chính'])
                if response:
                    return response
            
            if row['Số mét vải lót'] > 0:
                response = reduce_inventory(row['Vải lót'], row['Số mét vải lót'])
                if response:
                    return response
        
        return JsonResponse({'message': 'Issue data uploaded successfully!'})
    
    return JsonResponse({'error': 'Bad request'}, status=400)

def get_skus(request):
    print(request.GET)  
    design_code = request.GET.get("design_code")

    if not design_code:
        return JsonResponse({"error": "Missing design_code"}, status=400)

    skus = SKU.objects.filter(design__design_code=design_code).values("sku_code", "sku_name")
    return JsonResponse(list(skus), safe=False)

def get_sku_details(request):
    sku_code = request.GET.get("sku_code")
    sku = get_object_or_404(SKU, sku_code=sku_code)
    data = {
        "sku_code": sku.sku_code,
        "color": sku.color.color_name, 
        "size": sku.size.size_name,  
    }
    return JsonResponse(data)

@csrf_exempt
def list_issue(request):
    valid_sort_fields = ['issue_code', 'issue_date', 'tailor__employee_name', 'sku_name__sku_name', 'main_fabric__material_name', 'main_fabric_meters', 'sewing_type', 'status']
    sort_field = request.GET.get('sort_field', 'issue_code')
    sort_order = request.GET.get('sort_order', 'asc')
    search_query = request.GET.get('search', '').strip()
    
    if sort_field not in valid_sort_fields:
        sort_field = 'issue_code'
    
    if sort_order == 'desc':
        sort_field = f'-{sort_field}'
    
    all_issues = Issue.objects.all()
    
    if search_query:
        all_issues = all_issues.filter(
            Q(issue_code__icontains=search_query) |
            Q(tailor__employee_name__icontains=search_query) |
            Q(sku_name__sku_name__icontains=search_query) |
            Q(main_fabric__material_name__icontains=search_query) |
            Q(lining_fabric__material_name__icontains=search_query) |
            Q(sewing_type__icontains=search_query) |
            Q(status__icontains=search_query)
        )
    
    all_issues = all_issues.order_by(sort_field)
    paginator = Paginator(all_issues, 5)
    page_number = request.GET.get('page')
    issues_page = paginator.get_page(page_number)
    
    for issue in issues_page:
        if issue.tailor:
            parts = issue.tailor.employee_name.split()
            if len(parts) > 1:
                issue.tailor.short_name = f"C.{parts[-1]}"
            else:
                issue.tailor.short_name = f"C.{parts[0]}"
    
    issue_entries = Issue.objects.filter(issue_code__regex=r'^PEV\d+$')\
        .annotate(numeric_code=Cast(F('issue_code')[3:], IntegerField()))\
        .order_by('-numeric_code')
    
    last_issue_index = issue_entries.first().numeric_code if issue_entries.exists() else 0
    new_issue_code = f'PEV{last_issue_index + 1:05d}'
    
    current_time = timezone.now()
    employees = Employee.objects.all()
    designs = Design.objects.all()
    materials = Material.objects.all()
    
    context = {
        'issues_page': issues_page,
        'new_issue_code': new_issue_code,
        'current_time': current_time,
        'employees': employees,
        'designs': designs,
        'materials': materials,
        'current_sort_field': sort_field.replace('-', ''),
        'current_sort_order': sort_order,
        'search_query': search_query,
    }
    
    return render(request, 'catalog/list_issue.html', context)

@csrf_exempt
def create_issue(request):
    if request.method == "POST":
        body_unicode = request.body.decode('utf-8')
        body = json.loads(body_unicode)

        issue_code = request.POST.get('issue_code') or body.get('issue_code')
        issue_date = request.POST.get('issue_date') or body.get('issue_date')
        issue_date = validate_date(issue_date)
        tailor_value = request.POST.get('tailor') or body.get('tailor')
        tailor = tailor_value.split('-')[0].strip() if tailor_value else None
        design_code = request.POST.get('design_code') or body.get('design_code')
        sku_code = request.POST.get('sku_code') or body.get('sku_code')
        sku_name = request.POST.get('sku_name') or body.get('sku_name')
        color = request.POST.get('color') or body.get('color')
        size = request.POST.get('size') or body.get('size')
        sewing_type = request.POST.get('sewing_type') or body.get('sewing_type')
        notes = request.POST.get('notes') or body.get('notes')
        main_fabric_value = request.POST.get('main_fabric') or body.get('main_fabric')
        main_fabric = main_fabric_value.split('-')[0].strip() if main_fabric_value else None
        lining_fabric_value = request.POST.get('lining_fabric') or body.get('lining_fabric')
        lining_fabric = lining_fabric_value.split('-')[0].strip() if lining_fabric_value else None
        main_fabric_meters = float(request.POST.get('main_fabric_meters') or body.get('main_fabric_meters') or 0)
        lining_fabric_meters = float(request.POST.get('lining_fabric_meters') or body.get('lining_fabric_meters') or 0)
        status = request.POST.get('status') or body.get('status')

        issue = Issue.objects.create(
            issue_code=issue_code,
            issue_date=issue_date,
            tailor=Employee.objects.filter(employee_code=tailor).last(),
            design_code=Design.objects.filter(design_code=design_code).last(),
            sku_code=sku_code,
            sku_name=SKU.objects.filter(sku_code=sku_name).last(),
            color=color,
            size=size,
            sewing_type=sewing_type,
            notes=notes,
            main_fabric=Material.objects.filter(material_code=main_fabric).last(),
            lining_fabric=Material.objects.filter(material_code=lining_fabric).last(),
            main_fabric_meters=main_fabric_meters,
            lining_fabric_meters=lining_fabric_meters,
            status='completed'
        )

        def reduce_inventory(material_code, quantity):
            if material_code:
                material = Material.objects.filter(material_code=material_code).last()
                if material:
                    inventory, created = Inventory.objects.get_or_create(material=material, defaults={'quantity': 0})
                    if inventory.quantity >= quantity:
                        inventory.quantity -= quantity
                        inventory.save()
                    else:
                        return JsonResponse({'error': f'Không đủ {material_code} trong kho'}, status=400)

        if main_fabric_meters > 0:
            response = reduce_inventory(main_fabric, main_fabric_meters)
            if response:
                return response
        if lining_fabric_meters > 0:
            response = reduce_inventory(lining_fabric, lining_fabric_meters)
            if response:
                return response

        return JsonResponse({'message': 'Issue đã được tạo thành công!', 'issue_id': issue.id})
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def cancel_issue(request, issue_code):
    if request.method == "POST":
        issue = get_object_or_404(Issue, issue_code=issue_code)

        if issue.status == "cancelled":
            return JsonResponse({'error': 'Phiếu xuất đã bị hủy trước đó!'}, status=400)

        if issue.main_fabric and issue.main_fabric_meters:
            main_fabric = issue.main_fabric
            inventory, created = Inventory.objects.get_or_create(material=main_fabric, defaults={'quantity': 0})
            inventory.quantity += issue.main_fabric_meters
            inventory.save()

        if issue.lining_fabric and issue.lining_fabric_meters:
            lining_fabric = issue.lining_fabric
            inventory, created = Inventory.objects.get_or_create(material=lining_fabric, defaults={'quantity': 0})
            inventory.quantity += issue.lining_fabric_meters
            inventory.save()

        issue.status = "cancelled"
        issue.save()

        return JsonResponse({'message': 'Phiếu xuất kho đã được hủy thành công và số lượng đã được cập nhật!'})
    return JsonResponse({'error': 'Invalid request method'}, status=400)

@csrf_exempt
def update_issue(request, issue_code):
    if request.method == "POST":
        issue = get_object_or_404(Issue, issue_code=issue_code)
        
        if request.content_type == "application/json":
            body_unicode = request.body.decode('utf-8')
            body = json.loads(body_unicode) if body_unicode else {}
        else:
            body = {}

        issue_date = request.POST.get('issue_date') or body.get('issue_date')
        tailor_value = request.POST.get('tailor') or body.get('tailor')
        tailor = tailor_value.split('-')[0].strip() if tailor_value else None
        design_code = request.POST.get('design_code') or body.get('design_code')
        sku_code = request.POST.get('sku_code') or body.get('sku_code')
        sku_name = request.POST.get('sku_name') or body.get('sku_name')
        color = request.POST.get('color') or body.get('color')
        size = request.POST.get('size') or body.get('size')
        sewing_type = request.POST.get('sewing_type') or body.get('sewing_type')
        notes = request.POST.get('notes') or body.get('notes')
        main_fabric_value = request.POST.get('main_fabric') or body.get('main_fabric')
        main_fabric = main_fabric_value.split('-')[0].strip() if main_fabric_value else None
        lining_fabric_value = request.POST.get('lining_fabric') or body.get('lining_fabric')
        lining_fabric = lining_fabric_value.split('-')[0].strip() if lining_fabric_value else None
        main_fabric_meters = request.POST.get('main_fabric_meters') or body.get('main_fabric_meters')
        lining_fabric_meters = request.POST.get('lining_fabric_meters') or body.get('lining_fabric_meters')

        old_main_fabric = issue.main_fabric
        old_lining_fabric = issue.lining_fabric
        old_main_fabric_meters = issue.main_fabric_meters
        old_lining_fabric_meters = issue.lining_fabric_meters

        if issue_date:
            issue.issue_date = issue_date
        if tailor:
            tailor = Employee.objects.get(employee_code=tailor)
            issue.tailor = tailor
        if design_code:
            design = Design.objects.get(design_code=design_code)
            issue.design_code = design
        if sku_code:
            issue.sku_code = sku_code
        if sku_name:
            sku = SKU.objects.get(sku_code=sku_name)
            issue.sku_name = sku
        if color:
            issue.color = color
        if size:
            issue.size = size
        if sewing_type:
            issue.sewing_type = sewing_type
        if notes:
            issue.notes = notes
        if main_fabric:
            issue.main_fabric = Material.objects.get(material_code=main_fabric)
        if lining_fabric:
            issue.lining_fabric = Material.objects.get(material_code=lining_fabric)
        if main_fabric_meters:
            issue.main_fabric_meters = float(main_fabric_meters)
        if lining_fabric_meters:
            issue.lining_fabric_meters = float(lining_fabric_meters)
        
        issue.status = 'Completed'
        issue.save()

        if old_main_fabric and old_main_fabric != issue.main_fabric:
            inventory_old_main = Inventory.objects.filter(material=old_main_fabric).first()
            if inventory_old_main:
                inventory_old_main.quantity += old_main_fabric_meters
                inventory_old_main.save()
        
        if old_lining_fabric and old_lining_fabric != issue.lining_fabric:
            inventory_old_lining = Inventory.objects.filter(material=old_lining_fabric).first()
            if inventory_old_lining:
                inventory_old_lining.quantity += old_lining_fabric_meters
                inventory_old_lining.save()
        
        inventory_main = Inventory.objects.filter(material=issue.main_fabric).first()
        if inventory_main:
            inventory_main.quantity -= issue.main_fabric_meters
            inventory_main.save()
        
        inventory_lining = Inventory.objects.filter(material=issue.lining_fabric).first()
        if inventory_lining:
            inventory_lining.quantity -= issue.lining_fabric_meters
            inventory_lining.save()

        return JsonResponse({'message': 'Issue và tồn kho đã được cập nhật thành công!'}, status=200)
    
    return JsonResponse({'error': 'Request method must be POST.'}, status=400)



#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

def signup_view(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tài khoản đã được tạo thành công. Bạn có thể đăng nhập!')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    return render(request, 'registration/signup.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')
            else:
                messages.error(request, 'Tên đăng nhập hoặc mật khẩu không chính xác.')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################


@csrf_exempt
def chat_with_gemini(request):
    if request.method == "POST":
        data = json.loads(request.body)
        user_message = data.get("message", "")

        if user_message:
            bot_response = get_gemini_response(user_message)
            return JsonResponse({"response": bot_response})

    return JsonResponse({"error": "Invalid request"}, status=400)


#########################################################
#########################################################
#########################################################
#########################################################
#########################################################

#views.py 

def chat(request):
    rooms = set(Message.objects.values_list('room', flat=True))
    room_data = []

    for room in rooms:
        latest_message = Message.objects.filter(room=room).order_by('-date_added').first()
        if latest_message:
            room_data.append({
                'room': room,
                'latest_message': latest_message.content,
                'last_sender': latest_message.username
            })

    users = User.objects.all()
    print(users)

    context = {
        'rooms': room_data,
        'users': users, 
    }
    return render(request, 'chat/chat_list.html', context)

def room(request, room_name):
    username = request.GET.get('username', 'Anonymous')
    is_bot = request.GET.get('bot', 'false') == 'true'

    websocket_url = f"/ws/chat/{room_name}/" if not is_bot else f"/ws/bot/{room_name}/"

    messages = Message.objects.filter(room=room_name).order_by('date_added')[:50]

    return render(request, 'chat/room.html', {
        'room_name': room_name,
        'username': username,
        'websocket_url': websocket_url,
        'messages': messages
    })

def private_chat(request, user1, user2):
    room = f'private_{min(user1, user2)}_{max(user1, user2)}'
    messages = Message.objects.filter(room=room).order_by('date_added')[:50]
    
    websocket_url = f"/ws/private/{user1}/{user2}/"

    return render(request, 'chat/private_chat.html', { 
        'user1': user1,
        'user2': user2,
        'websocket_url': websocket_url,
        'messages': messages
    })

@login_required
def chatbot_private_chat(request):
    user = request.user.username
    room = f'private_chatbot_{user}'
    messages = Message.objects.filter(room=room).order_by('date_added')[:50]
    
    websocket_url = f"/ws/chatbot/{user}/"

    return render(request, 'chat/private_chatbot.html', { 
        'user': user,
        'websocket_url': websocket_url,
        'messages': messages
    })