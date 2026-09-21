# utils/excel_export.py
"""
أدوات تصدير البيانات إلى Excel
"""
from io import BytesIO
from datetime import datetime
import pandas as pd


def export_to_excel(data, sheet_name='Sheet1', columns_map=None):
    """
    تصدير البيانات إلى Excel
    
    Args:
        data: list of dicts
        sheet_name: اسم الورقة
        columns_map: dict لتحويل أسماء الأعمدة
    
    Returns:
        BytesIO object
    """
    df = pd.DataFrame(data)
    
    if columns_map:
        df = df.rename(columns=columns_map)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    
    output.seek(0)
    return output


def export_contracts_to_excel(contracts):
    """تصدير العقود إلى Excel"""
    data = []
    for c in contracts:
        data.append({
            'رقم العقد': c['contract_number'],
            'العميل': c['client_name'],
            'الشركة': c['company_name'] or '',
            'العنوان': c['title'],
            'نوع العقد': c['contract_type_name'] or '',
            'تاريخ البداية': c['start_date'],
            'تاريخ النهاية': c['end_date'],
            'قيمة العقد': c['contract_value'],
            'المبلغ الإجمالي': c['total_amount'],
            'المدفوع': c['paid_amount'],
            'حالة الدفع': c['payment_status'],
            'الحالة': c['status'],
        })
    
    return export_to_excel(data, 'العقود')


def export_payments_to_excel(payments):
    """تصدير المدفوعات إلى Excel"""
    data = []
    for p in payments:
        data.append({
            'العميل': p['client_name'],
            'الشركة': p['company_name'] or '',
            'المديول': p['module_name'] or '',
            'المبلغ': p['amount'],
            'تاريخ الدفع': p['payment_date'],
            'تاريخ الاستحقاق': p['due_date'] or '',
            'طريقة الدفع': p['payment_method'],
            'الحالة': p['status'],
            'رقم الفاتورة': p['invoice_number'] or '',
        })
    
    return export_to_excel(data, 'المدفوعات')


def export_tasks_to_excel(tasks):
    """تصدير المهام إلى Excel"""
    data = []
    for t in tasks:
        data.append({
            'العنوان': t['title'],
            'العميل': t['client_name'],
            'المدرب': t['trainer_name'] or '',
            'المستخدم': t['assigned_user_name'] or '',
            'الحالة': t['status'],
            'الأولوية': t['priority'],
            'تاريخ الاستحقاق': t['due_date'],
            'نسبة الإنجاز': f"{t['completion_percentage']}%",
        })
    
    return export_to_excel(data, 'المهام')


def export_clients_to_excel(clients):
    """تصدير العملاء إلى Excel"""
    data = []
    for c in clients:
        data.append({
            'الاسم': c['name'],
            'الشركة': c['company_name'] or '',
            'الهاتف': c['phone'] or '',
            'البريد': c['email'] or '',
            'العنوان': c['address'] or '',
            'ملاحظات': c['notes'] or '',
        })
    
    return export_to_excel(data, 'العملاء')


def export_full_report(conn):
    """تصدير تقرير شامل بعدة أوراق"""
    contracts = conn.execute('''
        SELECT client_contracts.*, clients.name as client_name, clients.company_name
        FROM client_contracts
        JOIN clients ON client_contracts.client_id = clients.id
        ORDER BY client_contracts.created_at DESC
    ''').fetchall()
    
    payments = conn.execute('''
        SELECT client_payments.*, clients.name as client_name, clients.company_name
        FROM client_payments
        LEFT JOIN clients ON client_payments.client_id = clients.id
        ORDER BY client_payments.created_at DESC
    ''').fetchall()
    
    tasks = conn.execute('''
        SELECT tasks.*, clients.name as client_name
        FROM tasks
        JOIN clients ON tasks.client_id = clients.id
        ORDER BY tasks.created_at DESC
    ''').fetchall()
    
    clients_data = conn.execute('SELECT * FROM clients ORDER BY name').fetchall()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ورقة العقود
        contracts_data = [{
            'رقم العقد': c['contract_number'],
            'العميل': c['client_name'],
            'الشركة': c['company_name'] or '',
            'العنوان': c['title'],
            'قيمة العقد': c['contract_value'],
            'المدفوع': c['paid_amount'],
            'حالة الدفع': c['payment_status'],
            'الحالة': c['status'],
        } for c in contracts]
        pd.DataFrame(contracts_data).to_excel(writer, index=False, sheet_name='العقود')
        
        # ورقة المدفوعات
        payments_data = [{
            'العميل': p['client_name'],
            'الشركة': p['company_name'] or '',
            'المبلغ': p['amount'],
            'تاريخ الدفع': p['payment_date'],
            'الحالة': p['status'],
            'طريقة الدفع': p['payment_method'],
        } for p in payments]
        pd.DataFrame(payments_data).to_excel(writer, index=False, sheet_name='المدفوعات')
        
        # ورقة المهام
        tasks_data = [{
            'العنوان': t['title'],
            'العميل': t['client_name'],
            'الحالة': t['status'],
            'الأولوية': t['priority'],
            'تاريخ الاستحقاق': t['due_date'],
        } for t in tasks]
        pd.DataFrame(tasks_data).to_excel(writer, index=False, sheet_name='المهام')
        
        # ورقة العملاء
        clients_list = [{
            'الاسم': c['name'],
            'الشركة': c['company_name'] or '',
            'الهاتف': c['phone'] or '',
            'البريد': c['email'] or '',
        } for c in clients_data]
        pd.DataFrame(clients_list).to_excel(writer, index=False, sheet_name='العملاء')
    
    output.seek(0)
    return output