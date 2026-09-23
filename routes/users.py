# routes/users.py
from flask import render_template, request, redirect, url_for, session, flash
import sqlite3
from models import get_db, hash_password, get_user_permissions, has_permission, add_permission_to_user, remove_permission_from_user
from routes import users_bp
from utils import check_role, log_activity


@users_bp.route('/users')
def users():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    users_list = conn.execute('''
        SELECT * FROM users ORDER BY created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('users.html', users=users_list)


@users_bp.route('/add_user', methods=['GET', 'POST'])
def add_user():
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username'].strip()
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']
        
        # ✅ التحقق من المدخلات
        if not username or not name or not email or not password:
            flash('❌ جميع الحقول مطلوبة', 'danger')
            return redirect(url_for('users.users'))
        
        if len(password) < 4:
            flash('❌ كلمة المرور يجب أن تكون 4 أحرف على الأقل', 'danger')
            return redirect(url_for('users.users'))
        
        conn = get_db()
        
        try:
            # ✅ التحقق من وجود username
            existing_user = conn.execute(
                'SELECT id FROM users WHERE LOWER(username) = LOWER(?)', 
                (username,)
            ).fetchone()
            
            if existing_user:
                flash(f'❌ اسم المستخدم "{username}" موجود مسبقاً', 'danger')
                conn.close()
                return redirect(url_for('users.users'))
            
            # ✅ التحقق من وجود email
            existing_email = conn.execute(
                'SELECT id FROM users WHERE LOWER(email) = LOWER(?)', 
                (email,)
            ).fetchone()
            
            if existing_email:
                flash(f'❌ البريد الإلكتروني "{email}" موجود مسبقاً', 'danger')
                conn.close()
                return redirect(url_for('users.users'))
            
            # ✅ إضافة المستخدم
            conn.execute(
                '''INSERT INTO users (username, name, email, password, role) 
                   VALUES (?, ?, ?, ?, ?)''',
                (username, name, email, hash_password(password), role)
            )
            conn.commit()
            
            flash('✅ تم إضافة المستخدم بنجاح', 'success')
            log_activity(session['user_id'], 'إضافة مستخدم', f'أضاف {username}')
            
            # ✅ إرسال إيميل ترحيبي
            try:
                from utils import send_welcome_email
                send_welcome_email(email, name, username)
            except Exception as email_error:
                print(f"⚠️ فشل إرسال إيميل ترحيبي: {email_error}")
            
        except sqlite3.IntegrityError as e:
            # في حالة حدوث تكرار (حماية إضافية)
            print(f"⚠️ IntegrityError: {e}")
            if 'username' in str(e).lower():
                flash('❌ اسم المستخدم موجود مسبقاً', 'danger')
            elif 'email' in str(e).lower():
                flash('❌ البريد الإلكتروني موجود مسبقاً', 'danger')
            else:
                flash('❌ خطأ في إضافة المستخدم', 'danger')
        
        except Exception as e:
            print(f"❌ خطأ في add_user: {e}")
            import traceback
            traceback.print_exc()
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')
        
        finally:
            conn.close()
        
        return redirect(url_for('users.users'))
    
    return render_template('add_user.html')


@users_bp.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if session['user_role'] != 'مدير':
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('users.users'))
    
    if user_id == session['user_id']:
        flash('❌ لا يمكنك حذف حسابك الخاص', 'danger')
        return redirect(url_for('users.users'))
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        flash('❌ المستخدم غير موجود', 'danger')
        conn.close()
        return redirect(url_for('users.users'))
    
    try:
        # ✅ حذف الصلاحيات الإضافية أولاً
        conn.execute('DELETE FROM user_permissions WHERE user_id = ?', (user_id,))
        
        # ✅ حذف المستخدم
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        
        flash('✅ تم حذف المستخدم بنجاح', 'success')
        log_activity(session['user_id'], 'حذف مستخدم', f'حذف {user["username"]}')
    except Exception as e:
        print(f"❌ خطأ في delete_user: {e}")
        flash(f'❌ خطأ في الحذف: {str(e)}', 'danger')
    finally:
        conn.close()
    
    return redirect(url_for('users.users'))


# ===== إدارة صلاحيات المستخدم =====
@users_bp.route('/user_permissions/<int:user_id>')
def user_permissions(user_id):
    """عرض صلاحيات المستخدم"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        flash('❌ المستخدم غير موجود', 'danger')
        conn.close()
        return redirect(url_for('users.users'))
    
    # جلب جميع الصلاحيات
    all_permissions = conn.execute(
        'SELECT * FROM permissions ORDER BY resource, action'
    ).fetchall()
    
    # جلب صلاحيات المستخدم الكلية (من الدور + الإضافية)
    user_perms = get_user_permissions(user_id)
    
    # جلب صلاحيات الدور فقط
    role_perms = set()
    cursor = conn.execute("""
        SELECT p.name 
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON r.id = rp.role_id
        JOIN users u ON u.role = r.name
        WHERE u.id = ?
    """, (user_id,))
    for row in cursor.fetchall():
        role_perms.add(row['name'] if isinstance(row, dict) else row[0])
    
    # جلب الصلاحيات الإضافية فقط
    extra_perms = set()
    cursor = conn.execute("""
        SELECT p.name 
        FROM permissions p
        JOIN user_permissions up ON p.id = up.permission_id
        WHERE up.user_id = ?
    """, (user_id,))
    for row in cursor.fetchall():
        extra_perms.add(row['name'] if isinstance(row, dict) else row[0])
    
    conn.close()
    
    # تنظيم الصلاحيات حسب المصدر
    grouped_permissions = {}
    for perm in all_permissions:
        # دعم dict و tuple
        if isinstance(perm, dict):
            perm_name = perm['name']
            perm_id = perm['id']
            perm_resource = perm['resource']
            perm_action = perm['action']
            perm_description = perm['description']
        else:
            perm_id = perm[0]
            perm_name = perm[1]
            perm_resource = perm[2]
            perm_action = perm[3]
            perm_description = perm[4]
        
        resource = perm_resource
        if resource not in grouped_permissions:
            grouped_permissions[resource] = []
        
        is_role = perm_name in role_perms
        is_extra = perm_name in extra_perms
        is_active = perm_name in user_perms
        
        grouped_permissions[resource].append({
            'id': perm_id,
            'name': perm_name,
            'action': perm_action,
            'description': perm_description,
            'has_permission': is_active,
            'from_role': is_role,
            'from_extra': is_extra
        })
    
    return render_template('user_permissions.html', 
                         user=user, 
                         grouped_permissions=grouped_permissions)


@users_bp.route('/toggle_permission/<int:user_id>/<int:permission_id>', methods=['POST'])
def toggle_permission(user_id, permission_id):
    """تفعيل/إلغاء صلاحية للمستخدم"""
    if not check_role(['مدير']):
        flash('⛔ غير مصرح لك', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db()
    permission = conn.execute(
        'SELECT name FROM permissions WHERE id = ?', 
        (permission_id,)
    ).fetchone()
    
    if not permission:
        flash('❌ الصلاحية غير موجودة', 'danger')
        conn.close()
        return redirect(url_for('users.user_permissions', user_id=user_id))
    
    perm_name = permission['name'] if isinstance(permission, dict) else permission[0]
    
    # التحقق من وجود الصلاحية
    if has_permission(user_id, perm_name):
        remove_permission_from_user(user_id, perm_name)
        flash('✅ تم إلغاء الصلاحية', 'success')
    else:
        add_permission_to_user(user_id, perm_name)
        flash('✅ تم إضافة الصلاحية', 'success')
    
    conn.close()
    return redirect(url_for('users.user_permissions', user_id=user_id))