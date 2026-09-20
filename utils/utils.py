# utils.py
from models import get_db
from flask import session
import time
import sqlite3
from datetime import datetime, timedelta


def log_activity(user_id, action, details=None, retries=5):
    """تسجيل النشاط مع إعادة المحاولة في حالة القفل"""
    conn = None
    for attempt in range(retries):
        try:
            conn = get_db()
            conn.execute('PRAGMA busy_timeout = 30000')
            cursor = conn.cursor()
            cursor.execute('BEGIN IMMEDIATE')
            cursor.execute(
                'INSERT INTO activity_log (user_id, action, details) VALUES (?, ?, ?)',
                (user_id, action, details)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        except sqlite3.OperationalError as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                try:
                    conn.close()
                except:
                    pass
                
            if "database is locked" in str(e) and attempt < retries - 1:
                wait_time = 0.5 * (attempt + 1)
                print(f"⚠️ قاعدة البيانات مقفلة، محاولة {attempt + 1}/{retries} بعد {wait_time} ثانية")
                time.sleep(wait_time)
                continue
            else:
                print(f"❌ خطأ في تسجيل النشاط: {e}")
                return False
                
        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
                try:
                    conn.close()
                except:
                    pass
            print(f"❌ خطأ في تسجيل النشاط: {e}")
            return False
            
    return False


def check_role(allowed_roles):
    """التحقق من دور المستخدم - من الـ session مباشرة (أسرع)"""
    if 'user_role' not in session:
        return False
    return session['user_role'] in allowed_roles


def get_company_settings():
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 10000')
    settings = conn.execute('SELECT * FROM company_settings LIMIT 1').fetchone()
    conn.close()
    return settings


def get_trainers():
    """جلب المدربين النشطين فقط"""
    conn = get_db()
    conn.execute('PRAGMA busy_timeout = 10000')
    trainers = conn.execute('''
        SELECT id, name FROM trainers 
        WHERE is_active = 1
        ORDER BY name
    ''').fetchall()
    conn.close()
    return trainers


def get_lang():
    return session.get('lang', 'ar')


def t(key):
    try:
        from translations import get_text
        return get_text(key, get_lang())
    except:
        return key


# ===== Rate Limiting للـ Login =====

def check_rate_limit(username, ip_address, max_attempts=5, window_minutes=15):
    """
    التحقق من عدد محاولات الدخول الفاشلة
    
    Returns:
        (is_blocked, remaining_attempts, minutes_until_unblock)
    """
    try:
        conn = get_db()
        
        # حساب الوقت قبل كذا دقيقة
        window_start = (datetime.now() - timedelta(minutes=window_minutes)).strftime('%Y-%m-%d %H:%M:%S')
        
        # عدد المحاولات الفاشلة في النافذة الزمنية
        failed_attempts = conn.execute('''
            SELECT COUNT(*) as count FROM login_attempts
            WHERE (username = ? OR ip_address = ?)
              AND success = 0
              AND attempt_time >= ?
        ''', (username, ip_address, window_start)).fetchone()['count']
        
        # آخر محاولة فاشلة
        last_attempt = conn.execute('''
            SELECT attempt_time FROM login_attempts
            WHERE (username = ? OR ip_address = ?)
              AND success = 0
            ORDER BY attempt_time DESC
            LIMIT 1
        ''', (username, ip_address)).fetchone()
        
        conn.close()
        
        if failed_attempts >= max_attempts:
            if last_attempt:
                try:
                    last_time = datetime.strptime(last_attempt['attempt_time'], '%Y-%m-%d %H:%M:%S')
                except:
                    last_time = datetime.now()
                unblock_time = last_time + timedelta(minutes=window_minutes)
                minutes_left = max(0, int((unblock_time - datetime.now()).total_seconds() / 60))
                return True, 0, minutes_left
            return True, 0, window_minutes
        
        remaining = max_attempts - failed_attempts
        return False, remaining, 0
        
    except Exception as e:
        print(f"⚠️ خطأ في check_rate_limit: {e}")
        # في حالة الخطأ، نسمح بالمحاولة
        return False, 5, 0


def record_login_attempt(username, ip_address, success):
    """تسجيل محاولة دخول"""
    try:
        conn = get_db()
        conn.execute('''
            INSERT INTO login_attempts (username, ip_address, success)
            VALUES (?, ?, ?)
        ''', (username, ip_address, 1 if success else 0))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ خطأ في تسجيل محاولة الدخول: {e}")
        return False


def clear_login_attempts(username, ip_address):
    """مسح محاولات الدخول الفاشلة بعد نجاح الدخول"""
    try:
        conn = get_db()
        conn.execute('''
            DELETE FROM login_attempts
            WHERE (username = ? OR ip_address = ?) AND success = 0
        ''', (username, ip_address))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ خطأ في مسح محاولات الدخول: {e}")
        return False


def cleanup_old_attempts(days=7):
    """حذف محاولات الدخول القديمة (أكثر من X يوم)"""
    try:
        conn = get_db()
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('DELETE FROM login_attempts WHERE attempt_time < ?', (cutoff,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"⚠️ خطأ في تنظيف محاولات الدخول: {e}")
        return False