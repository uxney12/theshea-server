from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static

app_name = 'catalog'

urlpatterns = [
    path('', views.index, name='index'),
    
    ###############################################################################
    path('supplier/', views.list_supplier, name='list_supplier'),
    path('upload_supplier/', views.upload_supplier, name='upload_supplier'),
    path('create_supplier/', views.create_supplier, name='create_supplier'),
    path('delete_supplier/<str:supplier_code>/', views.delete_supplier, name='delete_supplier'),
    path('update_supplier/<str:supplier_code>/', views.update_supplier, name='update_supplier'),
    ###############################################################################
    path('material/', views.list_material, name='list_material'),
    path('upload_material/', views.upload_material, name='upload_material'),
    path('create_material/', views.create_material, name='create_material'),
    path('delete_material/<str:material_code>/', views.delete_material, name='delete_material'),
    path('update_material/<str:material_code>/', views.update_material, name='update_material'),
    ###############################################################################
    path('category/', views.list_category, name='list_category'),
    path('upload_category/', views.upload_category, name='upload_category'),
    path('create_category/', views.create_category, name='create_category'),
    path('delete_category/<str:category_code>/', views.delete_category, name='delete_category'),
    path('update_category/<str:category_code>/', views.update_category, name='update_category'),
    ###############################################################################
    path('inventory/', views.list_inventory, name='list_inventory'),
    ###############################################################################
    path('order/', views.list_order, name='list_order'),
    path('get-materials/', views.get_materials_by_supplier, name='get_materials_by_supplier'),
    path('upload_order/', views.upload_order, name='upload_order'),
    path('create_order/', views.create_order, name='create_order'),
    path('delete_order/<str:order_code>/', views.delete_order, name='delete_order'),
    path('update_order/<str:order_code>/', views.update_order, name='update_order'),
    ###############################################################################
    path('receipt/', views.list_receipt, name='list_receipt'),
    path('get-orderlines/', views.get_orderlines, name='get_orderlines'),
    path('get-order-details/', views.get_order_details, name='get_order_details'),
    path('upload_receipt/', views.upload_receipt, name='upload_receipt'),
    path('create_receipt/', views.create_receipt, name='create_receipt'),
    path('delete_receipt/<str:receipt_code>/', views.delete_receipt, name='delete_receipt'),
    path('update_receipt/<str:receipt_code>/', views.update_receipt, name='update_receipt'),
    ###############################################################################
    path('issue/', views.list_issue, name='list_issue'),
    path('upload_issue/', views.upload_issue, name='upload_issue'),
    path('get_skus/', views.get_skus, name='get_skus'),
    path('get_sku_details/', views.get_sku_details, name='get_sku_details'),
    path('create_issue/', views.create_issue, name='create_issue'),
    path('cancel_issue/<str:issue_code>/', views.cancel_issue, name='cancel_issue'),
    path('update_issue/<str:issue_code>/', views.update_issue, name='update_issue'),
    ###############################################################################
    path('collection/', views.list_collection, name='list_collection'),
    path('upload_collection/', views.upload_collection, name='upload_collection'),
    path('create_collection/', views.create_collection, name='create_collection'),
    path('update_collection/<str:collection_code>/', views.update_collection, name='update_collection'),
    ###############################################################################
    path('design/', views.list_design, name='list_design'),
    path('upload_design/', views.upload_design, name='upload_design'),
    path('create_design/', views.create_design, name='create_design'),
    path('detail_design/<str:design_code>/', views.detail_design, name='detail_design'),
    path('delete_design/<str:design_code>/', views.delete_design, name='delete_design'),
    path('update_design/<str:design_code>/', views.update_design, name='update_design'),
    ###############################################################################
    path('inventory_sku/', views.list_sku_inventory, name='list_sku_inventory'),
    ###############################################################################
    path('sku/', views.list_sku, name='list_sku'),
    ###############################################################################
    path('qc/', views.list_qc, name='list_qc'),
    path('create_qc/', views.create_qc, name='create_qc'),
    path('upload_qc/', views.upload_qc, name='upload_qc'),
    path('cancel_qc/<str:qc_code>/', views.cancel_qc, name='cancel_qc'),
    path('update_qc/<str:qc_code>/', views.update_qc, name='update_qc'),
    ###############################################################################
    path('import/', views.list_import, name='list_import'),
    path('create_import/', views.create_import, name='create_import'),
    path('upload_import/', views.upload_import, name='upload_import'),
    path('cancel_import/<str:import_code>/', views.cancel_import, name='cancel_import'),
    path('update_import/<str:import_code>/', views.update_import, name='update_import'),
    ###############################################################################
    path('export/', views.list_export, name='list_export'),
    path('create_export/', views.create_export, name='create_export'),
    path('upload_export/', views.upload_export, name='upload_export'),
    path('cancel_export/<str:export_code>/', views.cancel_export, name='cancel_export'),
    path('update_export/<str:export_code>/', views.update_export, name='update_export'),
    ###############################################################################
    path('employee/', views.list_employee, name='list_employee'),
    path('create_employee/', views.create_employee, name='create_employee'),
    path('upload_employee/', views.upload_employee, name='upload_employee'),
    path('delete_employee/<str:employee_code>/', views.delete_employee, name='delete_employee'),
    path('update_employee/<str:employee_code>/', views.update_employee, name='update_employee'),
    ###############################################################################
    path('progress/', views.list_progress, name='list_progress'),
    path('create_progress/', views.create_progress, name='create_progress'),
    path('upload_progress/', views.upload_progress, name='upload_progress'),
    path('delete_progress/<str:progress_code>/', views.delete_progress, name='delete_progress'),
    path('update_progress/<str:progress_code>/', views.update_progress, name='update_progress'),
    ###############################################################################
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    ###############################################################################
    path("chatwithgemini/", views.chat_with_gemini, name="chat_with_gemini"),
    ###############################################################################
    #urls.py
    path('chat/', views.chat, name='chat'),
    path('chat/<str:room_name>/', views.room, name='room'),
    path('private_chat/<str:user1>/<str:user2>/', views.private_chat, name='private_chat'),
    path('chatbot/', views.chatbot_private_chat, name='chatbot_private_chat'),
    ###############################################################################
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)