import functools
import urllib3
import json
from http.client import responses

from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash

bp = Blueprint('auth', __name__, url_prefix='/auth')
http = urllib3.PoolManager()
# TODO: Move to a central config file
nile = "http://localhost:8080"

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
            url = nile + "/users"
            payload = {
                'email' : email,
                'password' : password
            }
            encoded_data = json.dumps(payload).encode('utf-8')
            resp = http.request('POST',url,body=encoded_data, headers={'Content-Type': 'application/json'})
            if resp.status >= 200 and resp.status <= 299:
                data = json.loads(resp.data.decode('utf-8'))
                return redirect(url_for("auth.login"))
            else: 
                error = f"Signup failed for {email}. {resp.status} - {responses[resp.status]}"
                
        flash(error)

    return render_template('auth/signup.html')

@bp.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
    
        url = nile + "/login"
        payload = {
            'email' : email,
            'password' : password
        }
        encoded_data = json.dumps(payload).encode('utf-8')
        resp = http.request('POST',url,body=encoded_data, 
                headers={'Content-Type': 'application/json'})
        if resp.status >= 200 and resp.status <= 299:
            data = json.loads(resp.data.decode('utf-8'))
            session.clear()
            session['token'] = data['token']
            #TODO: need to parse JWT token for this
            session['email'] = request.form['email']
            return redirect(url_for('index'))
        else:
            error = f"Login failed for {email}. {resp.status} - {responses[resp.status]}"

        flash(error)

    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session['token'] is None:
            return redirect(url_for('auth.login'))

        return view(**kwargs)

    return wrapped_view