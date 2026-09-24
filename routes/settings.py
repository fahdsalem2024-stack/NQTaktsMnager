# routes/settings.py
from flask import render_template, request, redirect, url_for, session, flash, send_file
import os
import shutil
import sqlite3
from datetime import datetime
from werkzeug.utils import secure_filename
from models import get_db
from routes import settings_bp
from utils import check_role, log_activity, get_company_settings
from config import Config


@settings_bp.route('/company_settings', methods=['GET', 'POST'])
def company_settings():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    conn = get_db()
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        name_en = request.form['name_en']
        phone = request.form['phone']
        address = request.form['address']
        email = request.form['email']
        website = request.form['website']
        
        conn.execute('''
            UPDATE company_settings SET 
                name = ?, name_en = ?, phone = ?, address = ?, email = ?, website = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (name, name_en, phone, address, email, website, settings['id']))
        conn.commit()
        conn.close()
        
        flash('✅ تم تحديث إعدادات الشركة بنجاح', 'success')
        log_activity(session['user_id'], 'تحديث إعدادات الشركة', '')
        return redirect(url_for('settings.company_settings'))
    
    conn.close()
    return render_template('company_settings.html', settings=settings)


@settings_bp.route('/upload_logo', methods=['POST'])
def upload_logo():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    if 'logo' not in request.files:
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    file = request.files['logo']
    if file.filename == '':
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
        filename = f"logo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        file_path = os.path.join('static', filename)
        file.save(file_path)
        
        conn = get_db()
        conn.execute('UPDATE company_settings SET logo_path = ?', (filename,))
        conn.commit()
        conn.close()
        
        flash('✅ تم رفع الشعار بنجاح', 'success')
        log_activity(session['user_id'], 'رفع شعار', f'رفع {filename}')
    
    return redirect(url_for('settings.company_settings'))


@settings_bp.route('/upload_favicon', methods=['POST'])
def upload_favicon():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    if 'favicon' not in request.files:
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    file = request.files['favicon']
    if file.filename == '':
        flash('❌ لم يتم اختيار صورة', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    if file:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
        filename = f"favicon.{ext}"
        file_path = os.path.join('static', filename)
        file.save(file_path)
        
        conn = get_db()
        conn.execute('UPDATE company_settings SET favicon_path = ?', (filename,))
        conn.commit()
        conn.close()
        
        flash('✅ تم رفع أيقونة الموقع بنجاح', 'success')
        log_activity(session['user_id'], 'رفع أيقونة موقع', f'رفع {filename}')
    
    return redirect(url_for('settings.company_settings'))


@settings_bp.route('/reset_sequence', methods=['POST'])
def reset_sequence():
    """إعادة ضبط الترقيم - يبدأ من 1"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    try:
        conn = get_db()
        
        tables = [
            'users', 'clients', 'trainers', 'tasks',
            'client_contracts', 'client_payments', 'contract_payments',
            'contract_attachments', 'client_modules', 'meetings',
            'notifications', 'activity_log', 'login_attempts',
            'module_types', 'contract_types',
        ]
        
        reset_count = 0
        
        for table in tables:
            try:
                result = conn.execute(
                    "UPDATE sqlite_sequence SET seq = 0 WHERE name = ?",
                    (table,)
                )
                
                if result.rowcount > 0:
                    reset_count += 1
                    print(f"✅ تم تصفير ترقيم: {table}")
                else:
                    try:
                        conn.execute(
                            "INSERT INTO sqlite_sequence (name, seq) VALUES (?, 0)",
                            (table,)
                        )
                        reset_count += 1
                        print(f"✅ تم إضافة وتصفير: {table}")
                    except:
                        print(f"ℹ️ الجدول {table} غير موجود في sqlite_sequence")
                        
            except Exception as e:
                print(f"⚠️ فشل في {table}: {e}")
        
        conn.commit()
        conn.close()
        
        flash(f'✅ تم إعادة ضبط الترقيم لـ {reset_count} جدول بنجاح! الترقيم الجديد سيبدأ من 1', 'success')
        log_activity(session['user_id'], 'إعادة ضبط الترقيم', f'تم تصفير {reset_count} جدول')
        
    except Exception as e:
        flash(f'❌ خطأ: {str(e)}', 'danger')
        print(f"❌ خطأ: {e}")
    
    return redirect(url_for('settings.company_settings'))


# ✅ إصلاح: ترتيب الحذف من الأبناء للأباء + استخدام Exception
@settings_bp.route('/delete_all_data', methods=['POST'])
def delete_all_data():
    """حذف جميع البيانات من النظام (للمدير فقط)"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    confirm_text = request.form.get('confirm_text', '').strip()
    
    if confirm_text not in ['تأكيد', 'Confirm', 'confirm']:
        flash('❌ لم تقم بتأكيد الحذف بشكل صحيح', 'danger')
        return redirect(url_for('settings.company_settings'))
    
    try:
        conn = get_db()
        
        # ✅ ترتيب الحذف من الأبناء للأباء (مهم جداً!)
        tables = [
            # 1. الأبناء الأعمق
            'task_updates',
            'contract_modules',
            'contract_attachments',
            'payment_installments',
            'meeting_reminders',
            
            # 2. المهام (بتشاور على contract_payments + clients + meetings)
            'tasks',
            
            # 3. بقية الأبناء
            'contract_payments',
            'client_payments',
            'client_modules',
            'client_contracts',
            'meetings',
            
            # 4. العلاقات
            'client_trainers',
            
            # 5. الأباء
            'clients',
            'trainers',
            
            # 6. السجلات
            'notifications',
            'activity_log',
            'login_attempts',
        ]
        
        deleted_count = 0
        for table in tables:
            try:
                conn.execute(f"DELETE FROM {table}")
                deleted_count += 1
                print(f"✅ تم مسح جدول: {table}")
            except Exception as e:
                print(f"⚠️ خطأ في {table}: {e}")
        
        conn.commit()
        conn.close()
        
        flash(f'✅ تم مسح جميع البيانات بنجاح! ({deleted_count} جدول)', 'success')
        log_activity(session['user_id'], 'مسح جميع البيانات', f'تم مسح {deleted_count} جدول')
        
    except Exception as e:
        flash(f'❌ خطأ أثناء مسح البيانات: {str(e)}', 'danger')
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
    
    return redirect(url_for('settings.company_settings'))