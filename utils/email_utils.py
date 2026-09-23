# utils/email_utils.py
"""
أدوات إرسال الإيميلات
"""
from flask import current_app
from flask_mail import Mail, Message
from datetime import datetime


mail = Mail()


def init_mail(app):
    """تهيئة الإيميل مع التطبيق"""
    mail.init_app(app)


def send_email(to, subject, body_html, body_text=None):
    """إرسال إيميل عام"""
    try:
        if not to:
            return False
        
        msg = Message(
            subject=subject,
            recipients=[to] if isinstance(to, str) else to,
            html=body_html,
            body=body_text or body_html
        )
        mail.send(msg)
        print(f"✅ تم إرسال إيميل إلى {to}")
        return True
    except Exception as e:
        print(f"⚠️ فشل إرسال إيميل إلى {to}: {e}")
        return False


def email_base_template(title, content_html, cta_text=None, cta_url=None):
    """قالب الإيميل الأساسي"""
    from config import Config
    
    cta_html = ''
    if cta_text and cta_url:
        cta_html = f'''
        <tr>
            <td style="padding: 20px 0;">
                <a href="{cta_url}" 
                   style="background: #2563EB; color: #fff; padding: 12px 30px; 
                          text-decoration: none; border-radius: 8px; 
                          font-weight: 600; display: inline-block;">
                    {cta_text}
                </a>
            </td>
        </tr>
        '''
    
    return f'''
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background: #F8FAFC; 
                 font-family: Tajawal, Arial, sans-serif; direction: rtl;">
        <table width="100%" cellpadding="0" cellspacing="0" 
               style="background: #F8FAFC; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" 
                           style="background: #ffffff; border-radius: 16px; 
                                  box-shadow: 0 4px 20px rgba(0,0,0,0.08); 
                                  overflow: hidden;">
                        <tr>
                            <td style="background: linear-gradient(135deg, #1a237e, #0d47a1); 
                                       padding: 30px; text-align: center;">
                                <h1 style="color: #fff; margin: 0; font-size: 24px;">
                                    {Config.COMPANY_NAME}
                                </h1>
                                <p style="color: rgba(255,255,255,0.8); margin: 8px 0 0; 
                                          font-size: 14px;">
                                    منصة متابعة إنجاز المهام
                                </p>
                            </td>
                        </tr>
                        
                        <tr>
                            <td style="padding: 40px 30px;">
                                <h2 style="color: #1a237e; margin: 0 0 20px; 
                                           font-size: 20px;">
                                    {title}
                                </h2>
                                {content_html}
                                {cta_html}
                            </td>
                        </tr>
                        
                        <tr>
                            <td style="background: #0F172A; padding: 20px 30px; 
                                       text-align: center;">
                                <p style="color: #94a3b8; margin: 0; font-size: 12px;">
                                    © {datetime.now().year} {Config.COMPANY_NAME}
                                    <br>
                                    {Config.COMPANY_PHONE} | {Config.COMPANY_ADDRESS}
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    '''


# ============================================================
# ===== دوال الإشعارات =====
# ============================================================

def send_welcome_email(user_email, user_name, username):
    """إيميل ترحيب لمستخدم جديد"""
    from config import Config
    
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        مرحباً <strong>{user_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم إنشاء حسابك بنجاح في نظام <strong>{Config.COMPANY_NAME}</strong>.
    </p>
    <div style="background: #F1F5F9; padding: 20px; border-radius: 12px; 
                margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #1a237e; font-weight: 600;">
            بيانات الدخول:
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>اسم المستخدم:</strong> {username}
        </p>
    </div>
    <p style="color: #94a3b8; font-size: 13px;">
        يُنصح بتغيير كلمة المرور بعد أول تسجيل دخول.
    </p>
    '''
    
    html = email_base_template(
        'مرحباً بك في النظام! 🎉',
        content,
        'تسجيل الدخول',
        'https://nqsup.railway.app/login'
    )
    
    return send_email(user_email, f'مرحباً بك في {Config.COMPANY_NAME}', html)


def send_task_assigned_email(to_email, user_name, task_title, client_name, due_date):
    """إيميل إشعار بتكليف مهمة جديدة"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        مرحباً <strong>{user_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم تكليفك بمهمة جديدة:
    </p>
    <div style="background: #EFF6FF; padding: 20px; border-radius: 12px; 
                border-right: 4px solid #2563EB; margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #1a237e; font-weight: 700; 
                  font-size: 17px;">
            📋 {task_title}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>العميل:</strong> {client_name}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>تاريخ الاستحقاق:</strong> {due_date}
        </p>
    </div>
    '''
    
    html = email_base_template(
        '📋 مهمة جديدة',
        content,
        'عرض المهمة',
        'https://nqsup.railway.app/tasks'
    )
    
    return send_email(to_email, f'📋 مهمة جديدة: {task_title}', html)


def send_task_status_update_email(to_email, user_name, task_title, old_status, new_status):
    """إيميل تحديث حالة مهمة"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        مرحباً <strong>{user_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم تحديث حالة المهمة:
    </p>
    <div style="background: #F1F5F9; padding: 20px; border-radius: 12px; 
                margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #1a237e; font-weight: 700;">
            {task_title}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>من:</strong> <span style="background: #e2e8f0; 
            padding: 3px 10px; border-radius: 12px;">{old_status}</span>
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>إلى:</strong> <span style="background: #d4edda; color: #155724; 
            padding: 3px 10px; border-radius: 12px;">{new_status}</span>
        </p>
    </div>
    '''
    
    html = email_base_template(
        '🔄 تحديث حالة مهمة',
        content,
        'عرض التفاصيل',
        'https://nqsup.railway.app/tasks'
    )
    
    return send_email(to_email, f'🔄 تحديث: {task_title}', html)


def send_payment_received_email(to_email, client_name, amount, invoice_number, payment_date):
    """إيميل إشعار باستلام دفعة"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        عزيزي <strong>{client_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم استلام دفعتكم بنجاح. شكراً لتعاملكم معنا.
    </p>
    <div style="background: #F0FDF4; padding: 20px; border-radius: 12px; 
                border-right: 4px solid #22c55e; margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #166534; font-weight: 700;">
            💰 تفاصيل الدفعة:
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>المبلغ:</strong> {amount} ر.س
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>رقم الفاتورة:</strong> {invoice_number}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>تاريخ الدفع:</strong> {payment_date}
        </p>
    </div>
    '''
    
    html = email_base_template(
        '✅ تم استلام دفعتكم',
        content
    )
    
    return send_email(to_email, '✅ تم استلام دفعتكم', html)


def send_contract_created_email(to_email, client_name, contract_number, contract_title, contract_value):
    """إيميل إشعار بعقد جديد"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        عزيزي <strong>{client_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم إصدار عقد جديد لكم:
    </p>
    <div style="background: #FEFCE8; padding: 20px; border-radius: 12px; 
                border-right: 4px solid #f59e0b; margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #92400e; font-weight: 700;">
            📄 عقد رقم: {contract_number}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>العنوان:</strong> {contract_title}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>القيمة:</strong> {contract_value} ر.س
        </p>
    </div>
    '''
    
    html = email_base_template(
        '📄 عقد جديد',
        content
    )
    
    return send_email(to_email, f'📄 عقد جديد: {contract_number}', html)


def send_password_reset_email(to_email, user_name, new_password):
    """إيميل إعادة تعيين كلمة المرور"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        مرحباً <strong>{user_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        تم إعادة تعيين كلمة المرور الخاصة بك.
    </p>
    <div style="background: #FEF2F2; padding: 20px; border-radius: 12px; 
                border-right: 4px solid #ef4444; margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #991b1b; font-weight: 700;">
            🔑 كلمة المرور الجديدة:
        </p>
        <p style="margin: 10px 0; color: #1a237e; font-size: 20px; 
                  font-weight: 700; letter-spacing: 2px; text-align: center; 
                  background: #fff; padding: 15px; border-radius: 8px;">
            {new_password}
        </p>
    </div>
    <p style="color: #94a3b8; font-size: 13px;">
        ⚠️ يجب تغيير كلمة المرور بعد أول تسجيل دخول.
    </p>
    '''
    
    html = email_base_template(
        '🔑 إعادة تعيين كلمة المرور',
        content,
        'تسجيل الدخول',
        'https://nqsup.railway.app/login'
    )
    
    return send_email(to_email, '🔑 إعادة تعيين كلمة المرور', html)


def send_overdue_payment_reminder(to_email, client_name, contract_number, amount, due_date):
    """إيميل تذكير بدفعة متأخرة"""
    content = f'''
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        عزيزي <strong>{client_name}</strong>،
    </p>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        نود تذكيركم بوجود دفعة مستحقة:
    </p>
    <div style="background: #FEF2F2; padding: 20px; border-radius: 12px; 
                border-right: 4px solid #ef4444; margin: 20px 0;">
        <p style="margin: 0 0 10px; color: #991b1b; font-weight: 700;">
            ⚠️ دفعة مستحقة
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>رقم العقد:</strong> {contract_number}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>المبلغ:</strong> {amount} ر.س
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>تاريخ الاستحقاق:</strong> {due_date}
        </p>
    </div>
    <p style="color: #475569; line-height: 1.8; font-size: 15px;">
        يرجى التكرم بسداد المبلغ في أقرب وقت.
    </p>
    '''
    
    html = email_base_template(
        '⚠️ تذكير بدفعة مستحقة',
        content
    )
    
    return send_email(to_email, f'⚠️ تذكير: دفعة مستحقة على العقد {contract_number}', html)