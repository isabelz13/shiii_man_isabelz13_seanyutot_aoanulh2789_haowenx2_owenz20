# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-20m

from flask import Flask, render_template, request, flash, url_for, redirect, session
import folium
import utility
from pathlib import Path
import json

app = Flask(__name__)
app.secret_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*"

import auth
app.register_blueprint(auth.bp)

@app.before_request
def check_authentification():
    if 'username' not in session.keys() and request.blueprint != 'auth' and request.path != '/':
        flash("Please log in to view our website", "danger")
        return redirect(url_for("auth.login_get"))
    elif 'username' in session.keys():
        user = utility.get_user(session['username'])
        if user is None:
            session.pop('username', None)
            return redirect(url_for("auth.login_get"))

def build_map():
    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=11,
        tiles="CartoDB Positron"
    )

    folium.Marker(
        [40.7128, -74.0060],
        popup="New York City",
        tooltip="NYC"
    ).add_to(m)

    geojson_path = Path(__file__).resolve().parent.parent / "data" / "nyed_18d.geojson"

    with open(geojson_path, "r", encoding="utf-8") as f:
        geojson_data = json.load(f)

    folium.GeoJson(
        geojson_data,
        name="Election Districts",
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#3388ff",
            "weight": 1,
            "fillOpacity": 0.2
        },
    ).add_to(m)

    folium.LayerControl().add_to(m)

    return m

@app.get('/')
def home_get():
    m = build_map()
    map_html = m._repr_html_()
    return render_template('home.html', map_html=map_html)

@app.get('/game')
def game_get():
    m = build_map()
    map_html = m._repr_html_()
    return render_template('game.html', map_html=map_html)

@app.get('/profile')
def profile_get():
    user = utility.get_user(session["username"])

    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
