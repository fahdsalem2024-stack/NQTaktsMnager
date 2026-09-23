# utils/email_utils.py
"""
أدوات إرسال الإيميلات - Non-Blocking + Multi-Port Fallback
"""
import threading
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


def _send_via_smtp(smtp_server, port, username, password, use_tls, use_ssl, 
                   to_email, subject, body_html):
    """إرسال إيميل عبر SMTP مباشرة"""
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = username
    msg['To'] = to_email
    
    # Plain text + HTML
    part_text = MIMEText(body_html, 'plain', 'utf-8')
    part_html = MIMEText(body_html, 'html', 'utf-8')
    msg.attach(part_text)
    msg.attach(part_html)
    
    # ✅ محاولة الاتصال
    if use_ssl:
        # SSL مباشرة (بورت 465)
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_server, port, context=context, timeout=10) as server:
            server.login(username, password)
            server.send_message(msg)
    else:
        # STARTTLS (بورت 587)
        with smtplib.SMTP(smtp_server, port, timeout=10) as server:
            server.ehlo()
            if use_tls:
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            server.login(username, password)
            server.send_message(msg)
    
    return True


def _send_email_worker(app, to, subject, body_html):
    """Worker بيشتغل في Thread منفصل"""
    try:
        with app.app_context():
            smtp_server = app.config['MAIL_SERVER']
            username = app.config['MAIL_USERNAME']
            password = app.config['MAIL_PASSWORD']
            
            # ✅ قائمة ports للتجربة
            ports_to_try = [
                (587, True, False),   # STARTTLS
                (465, False, True),   # SSL
                (2525, True, False),  # بديل (SendGrid, Mailgun)
                (25, False, False),   # Plain
            ]
            
            last_error = None
            
            for port, use_tls, use_ssl in ports_to_try:
                try:
                    print(f"📤 محاولة إرسال عبر {smtp_server}:{port}...")
                    _send_via_smtp(
                        smtp_server, port, username, password,
                        use_tls, use_ssl, to, subject, body_html
                    )
                    print(f"✅ تم إرسال إيميل إلى {to} عبر البورت {port}")
                    return True
                except Exception as e:
                    print(f"⚠️ فشل البورت {port}: {e}")
                    last_error = e
                    continue
            
            print(f"❌ فشل إرسال إيميل إلى {to} على كل البورتات: {last_error}")
            return False
            
    except Exception as e:
        print(f"❌ خطأ عام في _send_email_worker: {e}")
        return False


def send_email(to, subject, body_html, body_text=None):
    """إرسال إيميل (في Thread منفصل — Non-Blocking)"""
    try:
        if not to:
            return False
        
        from flask import current_app
        app = current_app._get_current_object()
        
        # ✅ تحقق من وجود إعدادات
        if not app.config.get('MAIL_USERNAME'):
            print(f"⚠️ MAIL_USERNAME غير موجود — تخطي الإيميل")
            return False
        
        if app.config.get('MAIL_SUPPRESS_SEND'):
            print(f"⚠️ الإيميل معطل — تخطي")
            return False
        
        # ✅ إرسال في Thread منفصل
        thread = threading.Thread(
            target=_send_email_worker,
            args=(app, to, subject, body_html),
            daemon=True
        )
        thread.start()
        
        print(f"📤 جاري إرسال إيميل إلى {to} في الخلفية")
        return True
    except Exception as e:
        print(f"⚠️ فشل بدء إرسال إيميل: {e}")
        return False


def email_base_template(title, content_html, cta_text=None, cta_url=None):
    """قالب الإيميل الأساسي"""
    from config import Config
    
    cta_html = ''
    if cta_text and cta_url:
        cta_html = f'''
        <div style="text-align: center; margin-top: 25px;">
            <a href="{cta_url}" 
               style="background: #2563EB; color: #fff; padding: 12px 30px; 
                      text-decoration: none; border-radius: 8px; 
                      font-weight: 600; display: inline-block;">
                {cta_text}
            </a>
        </div>
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
            <strong>من:</strong> {old_status}
        </p>
        <p style="margin: 5px 0; color: #475569;">
            <strong>إلى:</strong> {new_status}
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
    
    html = email_base_template('✅ تم استلام دفعتكم', content)
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
    
    html = email_base_template('📄 عقد جديد', content)
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
    '''
    
    html = email_base_template('⚠️ تذكير بدفعة مستحقة', content)
    return send_email(to_email, f'⚠️ تذكير: دفعة مستحقة على العقد {contract_number}', html)