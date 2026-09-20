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
)

# استيراد الديكورات من decorators.py
from .decorators import login_required, role_required, permission_required