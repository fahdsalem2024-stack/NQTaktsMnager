# fix_db.py
"""
سكريبت إصلاح قاعدة البيانات:
- إعادة تعيين كلمات السر
- التأكد من وجود المستخدمين
- التأكد من ربط الصلاحيات بالأدوار
- إعطاء كل مستخدم الصلاحيات المناسبة لدوره
"""
import os
from models import get_db, hash_password


# ⚠️ غيّر كلمات السر دي لحاجة قوية!
NEW_PASSWORDS = {
    'Adminerp': '1234',
    'Fahd01': '1234',
    'employee1': '1234',
    'viewer1': '1234',
}


def fix_database():
    conn = get_db()
    
    print("=" * 60)
    print("🔧 بدء إصلاح قاعدة البيانات")
    print("=" * 60)
    
    # ===== 1. المستخدمين =====
    users = [
        ('Adminerp', 'مدير النظام', 'adminerp@company.com', 'مدير'),
        ('Fahd01', 'فهد المدير', 'fahd@company.com', 'مدير'),
        ('employee1', 'سارة موظف', 'sara@company.com', 'موظف'),
        ('viewer1', 'خالد مراقب', 'khalid@company.com', 'مراقب'),
    ]
    
    for username, name, email, role in users:
        password = NEW_PASSWORDS.get(username, '1234')
        
        # امسح المستخدم لو موجود
        conn.execute('DELETE FROM users WHERE username = ?', (username,))
        
        # ضيفه من جديد بـ bcrypt
        conn.execute('''
            INSERT INTO users (username, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        ''', (username, name, email, hash_password(password), role))
        
        print(f"✅ تم إعادة تعيين: {username} / {password} ({role})")
    
    conn.commit()
    
    # ===== 2. إعادة ربط الأدوار بالصلاحيات =====
    print("-" * 60)
    print("🔗 إعادة ربط الأدوار بالصلاحيات")
    
    roles_map = {}
    cursor = conn.execute("SELECT id, name FROM roles")
    for row in cursor.fetchall():
        roles_map[row['name']] = row['id']
    
    perms_map = {}
    cursor = conn.execute("SELECT id, name FROM permissions")
    for row in cursor.fetchall():
        perms_map[row['name']] = row['id']
    
    # امسح الربط القديم
    conn.execute('DELETE FROM role_permissions')
    
    # صلاحيات المدير (كل الصلاحيات)
    if 'مدير' in roles_map:
        for perm_id in perms_map.values():
            conn.execute('''
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (?, ?)
            ''', (roles_map['مدير'], perm_id))
        print(f"✅ تم ربط {len(perms_map)} صلاحية بدور المدير")
    
    # صلاحيات الموظف
    if 'موظف' in roles_map:
        employee_perms = [
            'tasks.view', 'tasks.create', 'tasks.edit', 'tasks.assign',
            'clients.view', 'clients.create', 'clients.edit',
            'contracts.view', 'contracts.create',
            'payments.view', 'payments.create',
            'reports.view'
        ]
        count = 0
        for perm_name in employee_perms:
            if perm_name in perms_map:
                conn.execute('''
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                ''', (roles_map['موظف'], perms_map[perm_name]))
                count += 1
        print(f"✅ تم ربط {count} صلاحية بدور الموظف")
    
    # صلاحيات المراقب
    if 'مراقب' in roles_map:
        viewer_perms = [
            'tasks.view', 'clients.view', 'contracts.view',
            'payments.view', 'reports.view', 'users.view'
        ]
        count = 0
        for perm_name in viewer_perms:
            if perm_name in perms_map:
                conn.execute('''
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (?, ?)
                ''', (roles_map['مراقب'], perms_map[perm_name]))
                count += 1
        print(f"✅ تم ربط {count} صلاحية بدور المراقب")
    
    conn.commit()
    
    # ===== 3. تأكد من إعدادات الشركة =====
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
    for username, password in NEW_PASSWORDS.items():
        print(f"   {username} / {password}")
    print("=" * 60)


if __name__ == '__main__':
    fix_database()