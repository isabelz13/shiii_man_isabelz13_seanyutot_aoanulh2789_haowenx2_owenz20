# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

bp = Blueprint('auth', __name__, url_prefix='/auth')

import utility

@bp.get('/signup')
def signup_get():
    return render_template('signup.html')

@bp.post('/signup')
def signup_post():
    username = request.form.get('username')
    password = request.form.get('password')

    if not password or not username:
        flash('Error: Username or password cannot be empty!', 'danger')
        return redirect(url_for('auth.signup_get'))

    #check if username exist
    row = utility.get_user(username)

    if not row:
        hashed_pswd = generate_password_hash(password)
        utility.insert_query("profiles", ({"username": username, "password": hashed_pswd}))
        user = utility.get_user(username)

        flash('Signup successful!', 'success')
        session['username'] = username
        return redirect(url_for('profile_get'))
    else:
        flash("Username already taken!", 'danger')
        return redirect(url_for('auth.signup_get'))

@bp.get('/logout')
def logout_get():
    session.pop('username', None)
    flash("Logout successful!", 'success')
    return render_template('login.html')

@bp.get('/login')
def login_get():
    return render_template('login.html')

@bp.post('/login')
def login_post():
    username = request.form.get('username')
    password = request.form.get('password')

    # check for username and pswd
    row = utility.get_user(username)

    if not row:
        flash('Error: Username or password incorrect', 'danger')
        return redirect(url_for('auth.login_get'))
    elif check_password_hash(row["password"], password):
        flash('Login successful!', 'success')
        session['username'] = username
        return redirect(url_for('profile_get'))
    else:
        flash('Error: Username or password incorrect', 'danger')
        return redirect(url_for('auth.login_get'))
