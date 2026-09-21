# utils/__init__.py
"""
الحزمة المساعدة (Utilities) للتطبيق
"""

# استيراد الدوال من utils.py
from .utils import (
    log_activity,
    check_role,
    get_company_settings,
    get_trainers,
    get_lang,
    t,
    # ===== Rate Limiting =====
    check_rate_limit,
    record_login_attempt,
    clear_login_attempts,
    cleanup_old_attempts,
    # ===== File Security =====
    is_safe_path,
    get_safe_file_path,
)

# ===== Excel Export =====
from .excel_export import (
    export_to_excel,
    export_contracts_to_excel,
    export_payments_to_excel,
    export_tasks_to_excel,
    export_clients_to_excel,
    export_full_report,
)

# استيراد الديكورات من decorators.py
from .decorators import login_required, role_required, permission_required