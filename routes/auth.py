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