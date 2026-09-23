# utils/__init__.py
"""
الحزمة المساعدة (Utilities) للتطبيق
"""

from .utils import (
    log_activity,
    check_role,
    get_company_settings,
    get_trainers,
    get_lang,
    t,
    check_rate_limit,
    record_login_attempt,
    clear_login_attempts,
    cleanup_old_attempts,
    is_safe_path,
    get_safe_file_path,
)

from .excel_export import (
    export_to_excel,
    export_contracts_to_excel,
    export_payments_to_excel,
    export_tasks_to_excel,
    export_clients_to_excel,
    export_full_report,
)

# Email (بدون flask_mail)
from .email_utils import (
    send_email,
    email_base_template,
    send_welcome_email,
    send_task_assigned_email,
    send_task_status_update_email,
    send_payment_received_email,
    send_contract_created_email,
    send_password_reset_email,
    send_overdue_payment_reminder,
)

from .decorators import login_required, role_required, permission_required