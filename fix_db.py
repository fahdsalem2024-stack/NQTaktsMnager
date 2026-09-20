# fix_db.py
"""
سكريبت إصلاح قاعدة البيانات:
- إعادة تعيين كلمات السر
- التأكد من وجود المستخدمين
"""
import os
from models import get_db, hash_password

def fix_database():
    conn = get_db()
    
    print("=" * 60)
    print("🔧 بدء إصلاح قاعدة البيانات")
    print("=" * 60)
    
    # 1. المستخدمين المطلوبين
    users = [
        ('Adminerp', 'مدير النظام', 'adminerp@company.com', '1234', 'مدير'),
        ('Fahd01', 'فهد المدير', 'fahd@company.com', '1234', 'مدير'),
        ('employee1', 'سارة موظف', 'sara@company.com', '1234', 'موظف'),
        ('viewer1', 'خالد مراقب', 'khalid@company.com', '1234', 'مراقب'),
    ]
    
    for username, name, email, password, role in users:
        # امسح المستخدم لو موجود
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        
        # ضيفه من جديد بـ bcrypt
        conn.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, name, email, hash_password(password), role))
        
        print(f"✅ تم إعادة تعيين: {username} / {password}")
    
    conn.commit()
    
    # 2. تأكد من إعدادات الشركة
    settings = conn.execute('SELECT * FROM company_settings').fetchone()
    if not settings:
        conn.execute('''
            INSERT INTO company_settings (name, name_en, phone, address, email, website)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('NQ', 'NQ Company', '+966 50 123 4567', 'الرياض', 'info@NQ.com', 'www.NQ.com'))
        conn.commit()
        print("✅ تم إضافة إعدادات الشركة")
    
    conn.close()
    
    print("=" * 60)
    print("✅ تم إصلاح قاعدة البيانات بنجاح")
    print("=" * 60)
    print("👤 بيانات الدخول:")
    print("   Adminerp / 1234")
    print("   Fahd01 / 1234")
    print("   employee1 / 1234")
    print("   viewer1 / 1234")
    print("=" * 60)


if __name__ == '__main__':
    fix_database()