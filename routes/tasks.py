@tasks_bp.route('/add_note/<int:task_id>', methods=['POST'])
@login_required
@permission_required('tasks.edit')
def add_note(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    note = request.form.get('note', '')
    file = request.files.get('attachment')
    
    attachment_path = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        name_parts = filename.rsplit('.', 1)
        if len(name_parts) > 1:
            filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
        else:
            filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        # 🔒 التحقق من أمان المسار
        from utils import is_safe_path
        if not is_safe_path(file_path):
            flash('⛔ مسار الملف غير آمن', 'danger')
            return redirect(request.referrer or url_for('tasks.tasks'))
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        attachment_path = file_path
    
    conn = get_db()
    conn.execute('''
        INSERT INTO task_updates (task_id, user_id, note, attachment_path)
        VALUES (?, ?, ?, ?)
    ''', (task_id, session['user_id'], note, attachment_path))
    conn.commit()
    conn.close()
    
    flash('📝 تم إضافة الملاحظة بنجاح', 'success')
    log_activity(session['user_id'], 'إضافة ملاحظة', f'أضاف ملاحظة للتدريب {task_id}')
    return redirect(request.referrer or url_for('tasks.tasks'))


@tasks_bp.route('/add_note_form/<int:task_id>', methods=['GET', 'POST'])
@login_required
@permission_required('tasks.edit')
def add_note_form(task_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    if request.method == 'POST':
        note = request.form.get('note', '')
        file = request.files.get('attachment')
        
        attachment_path = None
        if file and file.filename:
            filename = secure_filename(file.filename)
            name_parts = filename.rsplit('.', 1)
            if len(name_parts) > 1:
                filename = f"{name_parts[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{name_parts[1]}"
            else:
                filename = f"{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            # 🔒 التحقق من أمان المسار
            from utils import is_safe_path
            if not is_safe_path(file_path):
                flash('⛔ مسار الملف غير آمن', 'danger')
                return redirect(url_for('tasks.tasks'))
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            file.save(file_path)
            attachment_path = file_path
        
        conn = get_db()
        conn.execute('''
            INSERT INTO task_updates (task_id, user_id, note, attachment_path)
            VALUES (?, ?, ?, ?)
        ''', (task_id, session['user_id'], note, attachment_path))
        conn.commit()
        conn.close()
        
        flash('📝 تم إضافة الملاحظة بنجاح', 'success')
        return redirect(url_for('tasks.tasks'))
    
    return render_template('add_note.html', task_id=task_id)