from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for, session
)
from werkzeug.exceptions import abort
from datetime import datetime

from app.db import get_db
from app.auth import login_required

bp = Blueprint('todo', __name__)

@bp.route('/')
def index():
    creator = g.email
    db = get_db()
    todos = db.execute(
        'SELECT id, creator, task_name, status, created, due_date'
        ' FROM todo'
        ' where is_private = ? or creator = ? '
        ' ORDER BY created DESC',
        (False, creator)
    ).fetchall()
    return render_template('todo/index.html', todos=todos)

@bp.route('/add', methods=('GET', 'POST'))
@login_required
def create():
    if request.method == 'POST':
        task_name = request.form['task_name']
        due_date = request.form['due_date']
        status = request.form['status']
        is_private = 'is_private' in request.form.keys()
        error = None

        if not task_name:
            error = 'Task name is required.'

        try:
            parsed_due_date = datetime.strptime(due_date, "%d-%m-%Y")
        except ValueError:
           error = 'date "' + due_date + '" must follow dd-mm-YYYY format'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'INSERT INTO todo (task_name, creator, due_date, status, is_private)'
                ' VALUES (?, ?, ?, ?, ?)',
                (task_name, g.email, parsed_due_date.strftime("%Y-%m-%d %H:%M:%S.%f"), status, is_private)
            )
            db.commit()
            return redirect(url_for('todo.index'))

    return render_template('todo/create.html')

def get_task(id, check_creator=True):
    task = get_db().execute(
        'SELECT id, task_name, status, created, creator, due_date, is_private'
        ' FROM todo'
        ' WHERE id = ?',
        (id,)
    ).fetchone()

    if task is None:
        abort(404, f"Task id {id} doesn't exist.")

    if check_creator and task['creator'] != g.email:
        abort(403)

    return task

@bp.route('/<int:id>/update', methods=('GET', 'POST'))
@login_required
def update(id):
    task = get_task(id)
    if request.method == 'POST':
        task_name = request.form['task_name']
        due_date = request.form['due_date']
        status = request.form['status']
        is_private = 'is_private' in request.form.keys()
        error = None

        if not task_name:
            error = 'Task name is required.'

        try:
            parsed_due_date = datetime.strptime(due_date, "%d-%m-%Y")
        except ValueError:
           error = 'date "' + due_date + '" must follow dd-mm-YYYY format'

        if error is not None:
            flash(error)
        else:
            db = get_db()
            db.execute(
                'UPDATE todo SET task_name = ?, due_date = ?, status = ?, is_private = ?'
                ' WHERE id = ?',
                (task_name, parsed_due_date.strftime("%Y-%m-%d %H:%M:%S.%f"), status, is_private, id)
            )
            db.commit()
            return redirect(url_for('todo.index'))

    return render_template('todo/update.html', task=task)

@bp.route('/<int:id>/delete', methods=('POST',))
@login_required
def delete(id):
    get_task(id)
    db = get_db()
    db.execute('DELETE FROM todo WHERE id = ?', (id,))
    db.commit()
    return redirect(url_for('todo.index'))