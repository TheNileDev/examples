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
    token = session.get('token')
    if token:
        nile_client.logout(token)
        session.clear()
    return redirect(url_for('todo.index'))

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

@bp.route('/invite', methods=('GET', 'POST'))
def invite():
    if request.method == 'POST':
        code = request.args.get('accept_invite')
        token = session.get('token')
        nile_client.accept_invite(code, token)
        nile_client.get_user(token, use_cache = False) #refresh cache for this user, so we'll see the new org
        return redirect(url_for('todo.index'))
    else:
        args = request.args
        invite_code = args.get('invite_code')
        token = session.get('token')
        # TODO: Once we have Nile API to get an invite by code, we'll want to render the invite page with inviter and org details
        #       At least for logged-in users
        return render_template('auth/invite.html', invite_code=invite_code)

@bp.before_app_request
def load_logged_in_user():
    token = session.get('token')
    g.user = nile_client.get_user(token)
    if g.user is None:
        session.clear() # We don't know who this is, so the token was useless
 