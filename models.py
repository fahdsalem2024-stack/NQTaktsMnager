# models.py
import os
import sqlite3
from datetime import datetime
import hashlib
import bcrypt
import re

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    USE_POSTGRES = True
    print("✅ Using PostgreSQL")
else:
    USE_POSTGRES = False
    DB_PATH = os.environ.get('DB_PATH', '/app/data/tasks.db')
    if not os.path.exists('/app'):
        DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tasks.db')
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    print(f"⚠️ Using SQLite at {DB_PATH}")


def format_date(dt, fmt='%Y-%m-%d'):
    if dt is None:
        return '-'
    if isinstance(dt, str):
        return dt[:10] if fmt == '%Y-%m-%d' else dt
    try:
        return dt.strftime(fmt)
    except:
        return str(dt)


def format_datetime(dt, fmt='%Y-%m-%d %H:%M'):
    if dt is None:
        return '-'
    if isinstance(dt, str):
        return dt[:16] if fmt == '%Y-%m-%d %H:%M' else dt
    try:
        return dt.strftime(fmt)
    except:
        return str(dt)


if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool

    _pg_pool = None

    def _get_pg_pool():
        global _pg_pool
        if _pg_pool is None:
            try:
                _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                    2, 50,
                    DATABASE_URL,
                    keepalives=1,
                    keepalives_idle=30,
                    keepalives_interval=10,
                    keepalives_count=5,
                )
                print("✅ PostgreSQL pool created (2-50 connections)")
            except Exception as e:
                print(f"❌ فشل إنشاء pool: {e}")
                raise
        return _pg_pool

    class PostgresCursor:
        def __init__(self, conn):
            self._conn = conn
            self._cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        def execute(self, query, params=None):
            stripped = query.strip()
            upper = stripped.upper()

            if upper.startswith('PRAGMA'):
                return self
            if upper.startswith(('VACUUM', 'ANALYZE')):
                return self
            if 'sqlite_sequence' in query:
                return self
            if 'BEGIN IMMEDIATE' in upper:
                return self
            if upper in ('COMMIT', 'ROLLBACK', 'BEGIN'):
                return self

            query = query.replace('?', '%s')
            query = self._translate_query(query)

            try:
                if params is not None:
                    if not isinstance(params, (tuple, list)):
                        params = (params,)
                    self._cursor.execute(query, params)
                else:
                    self._cursor.execute(query)
            except Exception as e:
                print(f"❌ خطأ في الاستعلام: {e}")
                print(f"   Query: {query[:300]}")
                print(f"   Params: {params}")
                raise

            return self

        def _translate_query(self, query):
            """تحويل استعلامات SQLite لـ PostgreSQL"""
            # 1. معالجة date() و datetime()
            query = re.sub(
                r"date\(\s*[\"']now[\"']\s*,\s*[\"']-(\d+)\s+days?[\"']\s*\)",
                r"(CURRENT_DATE - INTERVAL '\1 days')",
                query
            )
            query = re.sub(
                r"date\(\s*[\"']now[\"']\s*,\s*[\"']\+?(\d+)\s+days?[\"']\s*\)",
                r"(CURRENT_DATE + INTERVAL '\1 days')",
                query
            )
            query = re.sub(
                r"date\(\s*[\"']now[\"']\s*\)",
                r"CURRENT_DATE",
                query
            )
            query = re.sub(
                r"datetime\(\s*[\"']now[\"']\s*\)",
                r"NOW()",
                query
            )

            # 2. تحويل "text" إلى 'text' (النصوص العربية)
            query = re.sub(r'"([^"]*[\u0600-\u06FF]+[^"]*)"', r"'\1'", query)

            # 3. strftime
            query = re.sub(
                r"strftime\(['\"]%Y-%m['\"],\s*([^)]+)\)",
                r"TO_CHAR(\1, 'YYYY-MM')",
                query
            )

            # 4. GROUP_CONCAT → STRING_AGG
            query = re.sub(
                r"GROUP_CONCAT\(([^,]+),\s*['\"]([^'\"]+)['\"]\)",
                r"STRING_AGG(\1, '\2')",
                query,
                flags=re.IGNORECASE
            )
            query = re.sub(
                r"GROUP_CONCAT\(([^)]+)\)",
                r"STRING_AGG(\1, ',')",
                query,
                flags=re.IGNORECASE
            )

            # 5. INSERT OR IGNORE
            if 'INSERT OR IGNORE' in query:
                query = query.replace('INSERT OR IGNORE', 'INSERT')
                if 'ON CONFLICT' not in query:
                    query = query.rstrip(';').rstrip() + ' ON CONFLICT DO NOTHING'

            # 6. INSERT OR REPLACE
            if 'INSERT OR REPLACE' in query:
                query = query.replace('INSERT OR REPLACE', 'INSERT')

            return query

        def fetchone(self):
            return self._cursor.fetchone()

        def fetchall(self):
            return self._cursor.fetchall()

        def __iter__(self):
            return iter(self._cursor.fetchall())

        @property
        def lastrowid(self):
            self._cursor.execute('SELECT lastval() as id')
            row = self._cursor.fetchone()
            return row['id'] if row else None

        @property
        def rowcount(self):
            return self._cursor.rowcount

        def close(self):
            self._cursor.close()

    class PostgresConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, query, params=None):
            cursor = PostgresCursor(self._conn)
            return cursor.execute(query, params)

        def cursor(self):
            return PostgresCursor(self._conn)

        def commit(self):
            self._conn.commit()

        def rollback(self):
            self._conn.rollback()

        def close(self):
            try:
                if self._conn and not self._conn.closed:
                    try:
                        self._conn.rollback()
                    except:
                        pass
                    _get_pg_pool().putconn(self._conn)
            except Exception as e:
                print(f"⚠️ خطأ في إغلاق الاتصال: {e}")
                try:
                    self._conn.close()
                except:
                    pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def get_db():
        """إرجاع اتصال PostgreSQL (مع فحص صلاحية الاتصال)"""
        try:
            pool = _get_pg_pool()
            conn = pool.getconn()
            
            # ✅ فحص الاتصال قبل الإرجاع
            try:
                cur = conn.cursor()
                cur.execute('SELECT 1')
                cur.close()
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                print(f"⚠️ Connection ميت، بنستبدله: {e}")
                try:
                    pool.putconn(conn, close=True)
                except:
                    pass
                conn = pool.getconn()
            
            return PostgresConnection(conn)
        except Exception as e:
            print(f"❌ فشل الحصول على اتصال: {e}")
            raise


else:
    def get_db():
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=NORMAL')
        conn.execute('PRAGMA cache_size=10000')
        conn.execute('PRAGMA busy_timeout=30000')
        return conn


def hash_password(password):
    if isinstance(password, str):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt(rounds=12)).decode('utf-8')


def verify_password(password, hashed):
    if not hashed:
        return False
    if hashed.startswith('$2b$') or hashed.startswith('$2a$') or hashed.startswith('$2y$'):
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            print(f"❌ خطأ في bcrypt: {e}")
            return False
    else:
        return hashlib.sha256(password.encode()).hexdigest() == hashed


def get_user_permissions(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT p.name
        FROM permissions p
        JOIN role_permissions rp ON p.id = rp.permission_id
        JOIN roles r ON r.id = rp.role_id
        JOIN users u ON u.role = r.name
        WHERE u.id = ?
    """, (user_id,))
    permissions = set()
    for row in cursor.fetchall():
        if isinstance(row, dict):
            permissions.add(row['name'])
        else:
            permissions.add(row[0])
    cursor.execute("""
        SELECT p.name FROM permissions p
        JOIN user_permissions up ON p.id = up.permission_id
        WHERE up.user_id = ?
    """, (user_id,))
    for row in cursor.fetchall():
        if isinstance(row, dict):
            permissions.add(row['name'])
        else:
            permissions.add(row[0])
    conn.close()
    return permissions


def has_permission(user_id, permission_name):
    return permission_name in get_user_permissions(user_id)


def add_permission_to_user(user_id, permission_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM permissions WHERE name = ?", (permission_name,))
    perm = cursor.fetchone()
    if perm:
        perm_id = perm['id'] if isinstance(perm, dict) else perm[0]
        try:
            if USE_POSTGRES:
                cursor.execute("""
                    INSERT INTO user_permissions (user_id, permission_id)
                    VALUES (%s, %s) ON CONFLICT (user_id, permission_id) DO NOTHING
                """, (user_id, perm_id))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO user_permissions (user_id, permission_id)
                    VALUES (?, ?)
                """, (user_id, perm_id))
            conn.commit()
        except Exception as e:
            print(f"⚠️ {e}")
    conn.close()


def remove_permission_from_user(user_id, permission_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM permissions WHERE name = ?", (permission_name,))
    perm = cursor.fetchone()
    if perm:
        perm_id = perm['id'] if isinstance(perm, dict) else perm[0]
        cursor.execute("""
            DELETE FROM user_permissions
            WHERE user_id = ? AND permission_id = ?
        """, (user_id, perm_id))
        conn.commit()
    conn.close()


def init_db():
    if USE_POSTGRES:
        _init_postgres()
    else:
        _init_sqlite()


def _init_postgres():
    conn = get_db()
    real_cursor = conn._conn.cursor()

    tables = [
        """CREATE TABLE IF NOT EXISTS company_settings (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, name_en TEXT,
            phone TEXT, address TEXT, logo_path TEXT, favicon_path TEXT,
            email TEXT, website TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
            role TEXT CHECK(role IN ('مدير','موظف','مراقب')) NOT NULL,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS trainers (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT,
            specialty TEXT, notes TEXT, is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, phone TEXT, email TEXT,
            address TEXT, company_name TEXT, notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS client_trainers (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            trainer_id INTEGER NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
            UNIQUE(client_id, trainer_id))""",
        """CREATE TABLE IF NOT EXISTS contract_types (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS client_contracts (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            contract_type_id INTEGER REFERENCES contract_types(id),
            contract_number TEXT UNIQUE NOT NULL, title TEXT NOT NULL, description TEXT,
            start_date DATE NOT NULL, end_date DATE NOT NULL,
            contract_value REAL DEFAULT 0, total_amount REAL DEFAULT 0, paid_amount REAL DEFAULT 0,
            payment_status TEXT DEFAULT 'غير مدفوع', status TEXT DEFAULT 'نشط',
            file_path TEXT, notes TEXT, created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS contract_payments (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES client_contracts(id) ON DELETE CASCADE,
            installment_number INTEGER NOT NULL, amount REAL NOT NULL,
            paid_amount REAL DEFAULT 0, due_date DATE NOT NULL, payment_date DATE,
            status TEXT DEFAULT 'مستحقة', notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS contract_attachments (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES client_contracts(id) ON DELETE CASCADE,
            file_name TEXT NOT NULL, file_path TEXT NOT NULL, file_size INTEGER DEFAULT 0,
            file_type TEXT, uploaded_by INTEGER NOT NULL REFERENCES users(id),
            description TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS module_types (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            price REAL DEFAULT 0, is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS client_modules (
            id SERIAL PRIMARY KEY, client_id INTEGER REFERENCES clients(id),
            name TEXT NOT NULL, description TEXT, price REAL DEFAULT 0,
            status TEXT DEFAULT 'نشط', start_date DATE, end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS contract_modules (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES client_contracts(id) ON DELETE CASCADE,
            module_type_id INTEGER NOT NULL REFERENCES module_types(id),
            quantity INTEGER DEFAULT 1, price REAL DEFAULT 0, notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS client_payments (
            id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            module_id INTEGER REFERENCES client_modules(id),
            amount REAL NOT NULL, payment_date DATE NOT NULL, due_date DATE,
            payment_method TEXT DEFAULT 'نقدي', status TEXT DEFAULT 'معلق',
            invoice_number TEXT, notes TEXT,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS payment_installments (
            id SERIAL PRIMARY KEY, payment_id INTEGER NOT NULL REFERENCES client_payments(id),
            installment_number INTEGER NOT NULL, amount REAL NOT NULL,
            due_date DATE NOT NULL, status TEXT DEFAULT 'مستحق',
            paid_date DATE, notes TEXT)""",
        """CREATE TABLE IF NOT EXISTS meetings (
            id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            title TEXT NOT NULL, description TEXT, meeting_date TIMESTAMP NOT NULL,
            duration INTEGER DEFAULT 60, location TEXT, meeting_link TEXT,
            status TEXT DEFAULT 'مجدول', reminder_sent INTEGER DEFAULT 0,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS meeting_reminders (
            id SERIAL PRIMARY KEY, meeting_id INTEGER NOT NULL REFERENCES meetings(id),
            reminder_time TIMESTAMP NOT NULL, sent INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY, client_id INTEGER NOT NULL REFERENCES clients(id),
            created_by INTEGER REFERENCES users(id),
            assigned_user_id INTEGER REFERENCES users(id),
            trainer_id INTEGER REFERENCES trainers(id), title TEXT NOT NULL, description TEXT,
            status TEXT DEFAULT 'لم تبدأ', priority TEXT DEFAULT 'متوسطة',
            due_date DATE NOT NULL, completion_percentage INTEGER DEFAULT 0,
            task_group TEXT, meeting_id INTEGER REFERENCES meetings(id),
            estimated_duration INTEGER DEFAULT 0, actual_duration INTEGER DEFAULT 0,
            contract_payment_id INTEGER REFERENCES contract_payments(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS task_updates (
            id SERIAL PRIMARY KEY, task_id INTEGER NOT NULL REFERENCES tasks(id),
            user_id INTEGER NOT NULL REFERENCES users(id), note TEXT, attachment_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS notifications (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            task_id INTEGER REFERENCES tasks(id), message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS activity_log (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            action TEXT NOT NULL, details TEXT, ip_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS login_attempts (
            id SERIAL PRIMARY KEY, username TEXT NOT NULL, ip_address TEXT,
            attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, success INTEGER DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, resource TEXT NOT NULL,
            action TEXT NOT NULL, description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, description TEXT,
            is_default INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""",
        """CREATE TABLE IF NOT EXISTS role_permissions (
            id SERIAL PRIMARY KEY, role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(role_id, permission_id))""",
        """CREATE TABLE IF NOT EXISTS user_permissions (
            id SERIAL PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
            granted_by INTEGER REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id, permission_id))""",
    ]

    for table_sql in tables:
        try:
            real_cursor.execute(table_sql)
        except Exception as e:
            print(f"⚠️ جدول: {e}")
            conn.rollback()

    conn.commit()

    default_permissions = [
        ('tasks.view', 'tasks', 'view', 'عرض المهام'),
        ('tasks.create', 'tasks', 'create', 'إنشاء مهام'),
        ('tasks.edit', 'tasks', 'edit', 'تعديل المهام'),
        ('tasks.delete', 'tasks', 'delete', 'حذف المهام'),
        ('tasks.assign', 'tasks', 'assign', 'تعيين المهام'),
        ('clients.view', 'clients', 'view', 'عرض العملاء'),
        ('clients.create', 'clients', 'create', 'إنشاء عملاء'),
        ('clients.edit', 'clients', 'edit', 'تعديل العملاء'),
        ('clients.delete', 'clients', 'delete', 'حذف العملاء'),
        ('contracts.view', 'contracts', 'view', 'عرض العقود'),
        ('contracts.create', 'contracts', 'create', 'إنشاء عقود'),
        ('contracts.edit', 'contracts', 'edit', 'تعديل العقود'),
        ('payments.view', 'payments', 'view', 'عرض المدفوعات'),
        ('payments.create', 'payments', 'create', 'إنشاء مدفوعات'),
        ('payments.edit', 'payments', 'edit', 'تعديل المدفوعات'),
        ('reports.view', 'reports', 'view', 'عرض التقارير'),
        ('reports.export', 'reports', 'export', 'تصدير التقارير'),
        ('users.view', 'users', 'view', 'عرض المستخدمين'),
        ('users.create', 'users', 'create', 'إنشاء مستخدمين'),
        ('users.edit', 'users', 'edit', 'تعديل المستخدمين'),
        ('users.delete', 'users', 'delete', 'حذف المستخدمين'),
    ]

    for perm in default_permissions:
        try:
            real_cursor.execute("""
                INSERT INTO permissions (name, resource, action, description)
                VALUES (%s, %s, %s, %s) ON CONFLICT (name) DO NOTHING
            """, perm)
        except:
            conn.rollback()

    conn.commit()

    default_roles = [
        ('مدير', 'مدير النظام', 0),
        ('موظف', 'موظف عادي', 1),
        ('مراقب', 'مشاهد', 0),
    ]

    for role in default_roles:
        try:
            real_cursor.execute("""
                INSERT INTO roles (name, description, is_default)
                VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING
            """, role)
        except:
            conn.rollback()

    conn.commit()

    real_cursor.execute("SELECT id, name FROM roles")
    roles_map = {r[1]: r[0] for r in real_cursor.fetchall()}
    real_cursor.execute("SELECT id, name FROM permissions")
    perms_map = {p[1]: p[0] for p in real_cursor.fetchall()}

    if 'مدير' in roles_map:
        for pid in perms_map.values():
            try:
                real_cursor.execute("""
                    INSERT INTO role_permissions (role_id, permission_id)
                    VALUES (%s, %s) ON CONFLICT DO NOTHING
                """, (roles_map['مدير'], pid))
            except:
                conn.rollback()

    employee_perms = ['tasks.view', 'tasks.create', 'tasks.edit', 'tasks.assign',
        'clients.view', 'clients.create', 'clients.edit',
        'contracts.view', 'contracts.create', 'payments.view', 'payments.create', 'reports.view']
    if 'موظف' in roles_map:
        for pn in employee_perms:
            if pn in perms_map:
                try:
                    real_cursor.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """, (roles_map['موظف'], perms_map[pn]))
                except:
                    conn.rollback()

    viewer_perms = ['tasks.view', 'clients.view', 'contracts.view',
        'payments.view', 'reports.view', 'users.view']
    if 'مراقب' in roles_map:
        for pn in viewer_perms:
            if pn in perms_map:
                try:
                    real_cursor.execute("""
                        INSERT INTO role_permissions (role_id, permission_id)
                        VALUES (%s, %s) ON CONFLICT DO NOTHING
                    """, (roles_map['مراقب'], perms_map[pn]))
                except:
                    conn.rollback()

    conn.commit()

    real_cursor.execute("SELECT * FROM company_settings LIMIT 1")
    if not real_cursor.fetchone():
        real_cursor.execute("""
            INSERT INTO company_settings (name, name_en, phone, address, email, website)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ('NQ', 'NQ Company', '+966 50 123 4567', 'الرياض', 'info@NQ.com', 'www.NQ.com'))
        conn.commit()

    for uname, nname, em, rl in [
        ('Adminerp', 'مدير النظام', 'adminerp@company.com', 'مدير'),
        ('Fahd01', 'فهد المدير', 'fahd@company.com', 'مدير'),
        ('employee1', 'سارة موظف', 'sara@company.com', 'موظف'),
        ('viewer1', 'خالد مراقب', 'khalid@company.com', 'مراقب'),
    ]:
        try:
            real_cursor.execute("SELECT * FROM users WHERE username = %s", (uname,))
            if not real_cursor.fetchone():
                real_cursor.execute("""
                    INSERT INTO users (username, name, email, password, role)
                    VALUES (%s, %s, %s, %s, %s)
                """, (uname, nname, em, hash_password('1234'), rl))
                conn.commit()
        except Exception as e:
            print(f"⚠️ مستخدم {uname}: {e}")
            conn.rollback()

    try:
        real_cursor.execute("SELECT COUNT(*) FROM trainers")
        if real_cursor.fetchone()[0] == 0:
            for t in [
                ('أحمد سليمان', '0551234567', 'ahmed@trainer.com', 'تدريب تقني', 'مدرب معتمد', 1),
                ('نورة القحطاني', '0552345678', 'noura@trainer.com', 'مهارات قيادية', 'مدربة معتمدة', 1),
                ('خالد المالكي', '0553456789', 'khalid@trainer.com', 'تطوير برمجيات', 'متخصص', 1)
            ]:
                real_cursor.execute("""
                    INSERT INTO trainers (name, phone, email, specialty, notes, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, t)
            conn.commit()
    except Exception as e:
        print(f"⚠️ trainers: {e}")
        conn.rollback()

    try:
        real_cursor.execute("SELECT COUNT(*) FROM contract_types")
        if real_cursor.fetchone()[0] == 0:
            for ct in [
                ('عقد خدمات', 'عقد تقديم خدمات استشارية'),
                ('عقد مقاولات', 'عقد أعمال مقاولات'),
                ('عقد توريد', 'عقد توريد مواد'),
                ('عقد تدريب', 'عقد دورات تدريبية')
            ]:
                real_cursor.execute("""
                    INSERT INTO contract_types (name, description) VALUES (%s, %s)
                """, ct)
            conn.commit()
    except Exception as e:
        print(f"⚠️ contract_types: {e}")
        conn.rollback()

    try:
        real_cursor.execute("SELECT COUNT(*) FROM module_types")
        if real_cursor.fetchone()[0] == 0:
            for mt in [
                ('نظام إدارة الموارد البشرية', 'نظام متكامل', 15000),
                ('نظام المحاسبة', 'نظام محاسبي', 20000),
                ('نظام إدارة العملاء CRM', 'نظام علاقات', 12000),
                ('نظام إدارة المشاريع', 'نظام مشاريع', 18000),
                ('نظام نقاط البيع POS', 'نظام نقاط بيع', 10000)
            ]:
                real_cursor.execute("""
                    INSERT INTO module_types (name, description, price) VALUES (%s, %s, %s)
                """, mt)
            conn.commit()
    except Exception as e:
        print(f"⚠️ module_types: {e}")
        conn.rollback()

    real_cursor.close()
    conn.close()
    print("✅ PostgreSQL initialized successfully")


def _init_sqlite():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS company_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, name_en TEXT,
        phone TEXT, address TEXT, logo_path TEXT, favicon_path TEXT,
        email TEXT, website TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        role TEXT CHECK(role IN ('مدير','موظف','مراقب')) NOT NULL,
        is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS trainers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, email TEXT,
        specialty TEXT, notes TEXT, is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, phone TEXT, email TEXT,
        address TEXT, company_name TEXT, notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS client_trainers (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
        trainer_id INTEGER NOT NULL, UNIQUE(client_id, trainer_id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
        created_by INTEGER, assigned_user_id INTEGER, trainer_id INTEGER,
        title TEXT NOT NULL, description TEXT, status TEXT DEFAULT 'لم تبدأ',
        priority TEXT DEFAULT 'متوسطة', due_date DATE NOT NULL,
        completion_percentage INTEGER DEFAULT 0, task_group TEXT, meeting_id INTEGER,
        estimated_duration INTEGER DEFAULT 0, actual_duration INTEGER DEFAULT 0,
        contract_payment_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS task_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, note TEXT, attachment_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        task_id INTEGER, message TEXT NOT NULL, is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        action TEXT NOT NULL, details TEXT, ip_address TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
        title TEXT NOT NULL, description TEXT, meeting_date DATETIME NOT NULL,
        duration INTEGER DEFAULT 60, location TEXT, meeting_link TEXT,
        status TEXT DEFAULT 'مجدول', reminder_sent INTEGER DEFAULT 0,
        created_by INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS meeting_reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, meeting_id INTEGER NOT NULL,
        reminder_time DATETIME NOT NULL, sent INTEGER DEFAULT 0)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS module_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
        price REAL DEFAULT 0, is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS contract_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL,
        module_type_id INTEGER NOT NULL, quantity INTEGER DEFAULT 1,
        price REAL DEFAULT 0, notes TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS client_modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, name TEXT NOT NULL,
        description TEXT, price REAL DEFAULT 0, status TEXT DEFAULT 'نشط',
        start_date DATE, end_date DATE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS client_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
        module_id INTEGER, amount REAL NOT NULL, payment_date DATE NOT NULL,
        due_date DATE, payment_method TEXT DEFAULT 'نقدي', status TEXT DEFAULT 'معلق',
        invoice_number TEXT, notes TEXT, created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS payment_installments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL,
        installment_number INTEGER NOT NULL, amount REAL NOT NULL,
        due_date DATE NOT NULL, status TEXT DEFAULT 'مستحق', paid_date DATE, notes TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL,
        ip_address TEXT, attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        success INTEGER DEFAULT 0)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS contract_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT,
        is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS client_contracts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER NOT NULL,
        contract_type_id INTEGER, contract_number TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL, description TEXT, start_date DATE NOT NULL,
        end_date DATE NOT NULL, contract_value REAL DEFAULT 0,
        total_amount REAL DEFAULT 0, paid_amount REAL DEFAULT 0,
        payment_status TEXT DEFAULT 'غير مدفوع', status TEXT DEFAULT 'نشط',
        file_path TEXT, notes TEXT, created_by INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS contract_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL,
        installment_number INTEGER NOT NULL, amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0, due_date DATE NOT NULL, payment_date DATE,
        status TEXT DEFAULT 'مستحقة', notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS contract_attachments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER NOT NULL,
        file_name TEXT NOT NULL, file_path TEXT NOT NULL, file_size INTEGER DEFAULT 0,
        file_type TEXT, uploaded_by INTEGER NOT NULL, description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        resource TEXT NOT NULL, action TEXT NOT NULL, description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL,
        description TEXT, is_default INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS role_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, role_id INTEGER NOT NULL,
        permission_id INTEGER NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(role_id, permission_id))""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS user_permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        permission_id INTEGER NOT NULL, granted_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, permission_id))""")

    conn.commit()
    conn.close()
    print(f"✅ SQLite initialized at {DB_PATH}")


try:
    init_db()
except Exception as e:
    print(f"❌ خطأ في تهيئة قاعدة البيانات: {e}")
    import traceback
    traceback.print_exc()