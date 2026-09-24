# routes/auth.py
from flask import render_template, request, redirect, url_for, session, flash
from models import get_db, hash_password, verify_password
from routes import auth_bp
from utils import (
    get_company_settings,
    log_activity,
    check_rate_limit,
    record_login_attempt,
    clear_login_attempts,
)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # ===== الحصول على IP المستخدم =====
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')
        # لو فيه أكثر من IP، خد الأول (الأصلي)
        if ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()
        
        # ===== التحقق من Rate Limit =====
        is_blocked, remaining, minutes_left = check_rate_limit(username, ip_address)
        
        if is_blocked:
            flash(
                f'⛔ تم حظرك مؤقتاً بسبب محاولات دخول فاشلة كثيرة. '
                f'حاول مرة أخرى بعد {minutes_left} دقيقة.',
                'danger'
            )
            settings = get_company_settings()
            return render_template('login.html', settings=settings), 429
        
        # ===== التحقق من بيانات الدخول =====
        conn = get_db()
        user = conn.execute('''
            SELECT * FROM users WHERE username = ? AND is_active = 1
        ''', (username,)).fetchone()
        conn.close()
        
        if user and verify_password(password, user['password']):
            # ✅ نجح الدخول
            record_login_attempt(username, ip_address, success=True)
            clear_login_attempts(username, ip_address)
            
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            session['username'] = user['username']
            session.permanent = True
            
            flash(f'مرحباً {user["name"]}! 👋', 'success')
            log_activity(session['user_id'], 'تسجيل دخول', f'IP: {ip_address}')
            
            if user['role'] == 'مدير':
                return redirect(url_for('index'))
            elif user['role'] == 'موظف':
                return redirect(url_for('tasks_bp.tasks'))
            else:
                return redirect(url_for('clients_bp.clients'))
        else:
            # ❌ فشل الدخول
            record_login_attempt(username, ip_address, success=False)
            
            # إعادة حساب المحاولات المتبقية
            is_blocked, remaining, minutes_left = check_rate_limit(username, ip_address)
            
            if is_blocked:
                flash(
                    f'⛔ تم حظرك مؤقتاً بسبب محاولات دخول فاشلة كثيرة. '
                    f'حاول مرة أخرى بعد {minutes_left} دقيقة.',
                    'danger'
                )
            elif remaining <= 2:
                flash(
                    f'❌ اسم المستخدم أو كلمة المرور غير صحيحة. '
                    f'⚠️ تحذير: باقي {remaining} محاولات فقط قبل الحظر المؤقت.',
                    'danger'
                )
            else:
                flash('❌ اسم المستخدم أو كلمة المرور غير صحيحة', 'danger')
    
    settings = get_company_settings()
    return render_template('login.html', settings=settings)


# ===== تسجيل الخروج =====
@auth_bp.route('/logout')
def logout():
    try:
        if 'user_id' in session:
            log_activity(session['user_id'], 'تسجيل خروج', '')
        session.clear()
        flash('✅ تم تسجيل الخروج بنجاح', 'success')
        return redirect(url_for('auth.login'))
    except Exception as e:
        print(f"Error in logout: {str(e)}")
        session.clear()
        return redirect(url_for('auth.login'))


@auth_bp.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']:
        session['lang'] = lang
        flash(f'✅ تم تغيير اللغة إلى {lang}', 'success')
    return redirect(request.referrer or url_for('index'))

# ===== Route تشخيصي مؤقت (امسحه بعد ما نخلص) =====
@auth_bp.route('/debug_login_attempts')
def debug_login_attempts():
    from models import get_db
    conn = get_db()
    attempts = conn.execute('''
        SELECT * FROM login_attempts 
        ORDER BY attempt_time DESC LIMIT 20
    ''').fetchall()
    conn.close()
    
    result = "<h2>Login Attempts (آخر 20)</h2><table border='1' cellpadding='5'>"
    result += "<tr><th>ID</th><th>Username</th><th>IP</th><th>Success</th><th>Time</th></tr>"
    for a in attempts:
        result += f"<tr><td>{a['id']}</td><td>{a['username']}</td><td>{a['ip_address']}</td><td>{a['success']}</td><td>{a['attempt_time']}</td></tr>"
    result += "</table>"
    result += f"<p>Total: {len(attempts)}</p>"
    return result
# ============================================================
# ===== تغيير كلمة المرور =====
# ============================================================

@auth_bp.route('/change_password', methods=['GET', 'POST'])
def change_password():
    """تغيير كلمة المرور للمستخدم الحالي"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # ✅ التحقق من المدخلات
        if not current_password or not new_password or not confirm_password:
            flash('❌ جميع الحقول مطلوبة', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # ✅ التحقق من تطابق كلمة المرور الجديدة
        if new_password != confirm_password:
            flash('❌ كلمة المرور الجديدة وتأكيدها غير متطابقين', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # ✅ التحقق من قوة كلمة المرور
        if len(new_password) < 8:
            flash('❌ كلمة المرور يجب أن تكون 8 أحرف على الأقل', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # ✅ التحقق من وجود حرف كبير، صغير، رقم
        import re
        if not re.search(r'[A-Z]', new_password):
            flash('❌ كلمة المرور يجب أن تحتوي على حرف كبير واحد على الأقل', 'danger')
            return redirect(url_for('auth.change_password'))
        
        if not re.search(r'[a-z]', new_password):
            flash('❌ كلمة المرور يجب أن تحتوي على حرف صغير واحد على الأقل', 'danger')
            return redirect(url_for('auth.change_password'))
        
        if not re.search(r'\d', new_password):
            flash('❌ كلمة المرور يجب أن تحتوي على رقم واحد على الأقل', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # ✅ التحقق من كلمة المرور الحالية
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', 
            (session['user_id'],)
        ).fetchone()
        
        if not user:
            conn.close()
            flash('❌ المستخدم غير موجود', 'danger')
            return redirect(url_for('auth.login'))
        
        if not verify_password(current_password, user['password']):
            conn.close()
            flash('❌ كلمة المرور الحالية غير صحيحة', 'danger')
            return redirect(url_for('auth.change_password'))
        
        # ✅ تحديث كلمة المرور
        try:
            conn.execute(
                'UPDATE users SET password = ? WHERE id = ?',
                (hash_password(new_password), session['user_id'])
            )
            conn.commit()
            
            flash('✅ تم تغيير كلمة المرور بنجاح', 'success')
            log_activity(session['user_id'], 'تغيير كلمة المرور', '')
            
            # ✅ إرسال إيميل إشعار
            try:
                from utils import send_email, email_base_template
                from config import Config
                
                content = f'''
                <p style="color: #475569; line-height: 1.8; font-size: 15px;">
                    مرحباً <strong>{user['name']}</strong>،
                </p>
                <p style="color: #475569; line-height: 1.8; font-size: 15px;">
                    تم تغيير كلمة المرور الخاصة بحسابك بنجاح.
                </p>
                <div style="background: #F0FDF4; padding: 20px; border-radius: 12px; 
                            border-right: 4px solid #22c55e; margin: 20px 0;">
                    <p style="margin: 0; color: #166534; font-weight: 600;">
                        ✅ إذا قمت أنت بهذا التغيير، فلا حاجة لفعل أي شيء.
                    </p>
                </div>
                <div style="background: #FEF2F2; padding: 20px; border-radius: 12px; 
                            border-right: 4px solid #ef4444; margin: 20px 0;">
                    <p style="margin: 0; color: #991b1b; font-weight: 600;">
                        ⚠️ إذا لم تقم أنت بهذا التغيير، يرجى التواصل معنا فوراً.
                    </p>
                </div>
                '''
                
                html = email_base_template('🔑 تم تغيير كلمة المرور', content)
                send_email(user['email'], '🔑 تم تغيير كلمة المرور', html)
            except Exception as e:
                print(f"⚠️ فشل إرسال إيميل: {e}")
            
        except Exception as e:
            print(f"❌ خطأ في تغيير كلمة المرور: {e}")
            flash(f'❌ حدث خطأ: {str(e)}', 'danger')
        finally:
            conn.close()
        
        return redirect(url_for('auth.change_password'))
    
    # ✅ GET → عرض الصفحة
    return render_template('change_password.html')