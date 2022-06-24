import functools
from . import nile

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for, current_app
)

bp = Blueprint('auth', __name__, url_prefix='/auth')
nile_client = nile.getNileClient()

@bp.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        error = None

        if not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            try:
                nile_client.signup(email, password)

                # Temporary hack: right now schema is per org, and org is generated on signup (only, for now)
                # So we need to create the schema. Error handling is crappy because this is a terrible hack
                # While we are here, lets complete the login and let the user through
                token = nile_client.login(email, password)
                session['token'] =  token

                orgs = nile_client.get_orgs(token)

                with current_app.open_resource('tasks.json') as f:
                    for org in orgs:
                        print("Creating schema in org: ")
                        print(org)
                        print("token (for debugging:" + token)
                        nile_client.create_entity(f.read().decode('utf8'), org_id=org['id'], token=token)
                return redirect(url_for('index'))
            except nile.NileError as ne:
                flash(ne.message)

    return render_template('auth/signup.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            token = nile_client.login(email, password)
            session['token'] =  token
            return redirect(url_for('index'))
        except nile.NileError as ne:
            flash(ne.message)
        except nile.TokenValidationError as tve:
            flash(tve)

    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    nile_client.logout(session['token'])
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session['token'] is None:
            return redirect(url_for('auth.login'))
        else:
            try:
                nile_client.validate_token(session['token'])
            except nile.TokenValidationError as tve:
                return redirect(url_for('auth.login'))
        return view(**kwargs)
    return wrapped_view

@bp.before_app_request
def load_logged_in_user():
    token = session.get('token')
    if token is None:
        g.email = None
    else:
        g.email = nile_client.getUserEmail(token)
        g.orgs =  nile_client.get_orgs(token)
        g.current_org = nile_client.get_current_org(token)