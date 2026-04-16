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

def clean_geojson(geojson_data):
    for feature in geojson_data.get("features", []):
        props = feature.get("properties", {})
        cleaned_props = {}

        for key, value in props.items():
            new_key = key.lstrip(":").replace(":", "_").replace("-", "_")
            cleaned_props[new_key] = value

        feature["properties"] = cleaned_props

    return geojson_data

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

    data_folder = Path(__file__).resolve().parent.parent / "data"

    election_path = data_folder / "nyed_18d.geojson"
    zipcode_path = data_folder / "ZipCode.geojson"

    with open(election_path, "r", encoding="utf-8") as f:
        election_data = json.load(f)

    with open(zipcode_path, "r", encoding="utf-8") as f:
        zipcode_data = json.load(f)
    zipcode_data = clean_geojson(zipcode_data)

    # Election districts layer
    election_fg = folium.FeatureGroup(name="Election Districts", show=True)

    folium.GeoJson(
        election_data,
        style_function=lambda feature: {
            "fillColor": "#3388ff",
            "color": "#3388ff",
            "weight": 1,
            "fillOpacity": 0.2
        },

    ).add_to(election_fg)

    election_fg.add_to(m)

    zipcode_fg = folium.FeatureGroup(name="Zip Codes", show=False)

    folium.GeoJson(
        zipcode_data,
        style_function=lambda feature: {
            "fillColor": "#7aff99",
            "color": "#418952",
            "weight": 1,
            "fillOpacity": 0.15
        },
    ).add_to(zipcode_fg)

    zipcode_fg.add_to(m)

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
