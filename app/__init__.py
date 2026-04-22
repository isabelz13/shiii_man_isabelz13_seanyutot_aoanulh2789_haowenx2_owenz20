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
import pandas as pd
import sqlite3

app = Flask(__name__)

app.secret_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*"

import auth

app.register_blueprint(auth.bp)

BASE_DIR = Path(__file__).resolve().parent.parent

DB_FILE = "data.db"

@app.before_request
def check_authentification():
    # Routes people can access without being logged in
    allowed_paths = ['/', '/auth/login', '/auth/signup']

    # If they are not logged in and try to open a page to advise them to login
    if 'username' not in session.keys() and request.path not in allowed_paths:
        flash("Please log in to view our website", "danger")
        return redirect(url_for("auth.login_get"))

    # If they are logged in make sure the user still exists in the database
    elif 'username' in session:
        user = utility.get_user(session['username'])
        if user is None:
            session.pop('username', None)
            return redirect(url_for("auth.login_get"))

def clean_geojson(geojson_data):
    # Loop through every feature in the geojson
    for feature in geojson_data.get("features", []):
        # Grab the properties dictionary
        props = feature.get("properties", {})

        # Make a new cleaned properties dictionary
        cleaned_props = {}

        # Clean weird characters from property names so folium doesn't break
        for key, value in props.items():
            new_key = key.lstrip(":").replace(":", "_").replace("-", "_")
            cleaned_props[new_key] = value

        # Replace the old properties with the cleaned ones
        feature["properties"] = cleaned_props

    return geojson_data

def build_map():
    # Create the base map centered on NYC
    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=10,
        min_zoom=10,
        max_bounds=True,
        tiles="CartoDB Positron"
    )

    # Connect to the database
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Pull income data from the database
    income_rows = cur.execute("SELECT zip, median_income FROM income").fetchall()

    # Pull voter data from the database
    voter_rows = cur.execute("SELECT AssemblyDistrict, ElectionDistrict, PoliticalParty FROM voter").fetchall()

    # Pull zipcode geojson from the database
    zip_rows = cur.execute("SELECT geojson FROM zipcodes").fetchall()

    # Pull election geojson from the database
    elec_rows = cur.execute("SELECT geojson FROM election").fetchall()

    # Close the database connection since we already got what we need
    conn.close()

    # Turn the raw database rows into pandas dataframes
    income_data = pd.DataFrame(income_rows, columns=["ZIP", "MedianIncome"])
    voter_data = pd.DataFrame(voter_rows, columns=["AssemblyDistrict", "ElectionDistrict", "PoliticalParty"])

    # Rebuild the zipcode feature collection from the stored geojson
    zipcode_data = {"type": "FeatureCollection", "features": [json.loads(row[0]) for row in zip_rows]}

    # Rebuild the election feature collection from the stored geojson
    election_data = {"type": "FeatureCollection", "features": [json.loads(row[0]) for row in elec_rows]}

    # Cleaning up property names so its compatible with folium
    zipcode_data = clean_geojson(zipcode_data)
    election_data = clean_geojson(election_data)

    # Making a feature group for the election district layer
    election_fg = folium.FeatureGroup(name="Election Districts", show=True)

    # Start with an empty income lookup dictionary
    income_lookup = {}

    if not income_data.empty:
        # Making sure zip codes stay as 5 digit strings, since zipcodes are identifiers
        income_data["ZIP"] = income_data["ZIP"].astype(str).str.zfill(5)

        # Converting median income values into numbers
        income_data["MedianIncome"] = pd.to_numeric(income_data["MedianIncome"], errors="coerce")

        # Making a quick zip to income lookup
        income_lookup = dict(zip(income_data["ZIP"], income_data["MedianIncome"]))

    party_lookup = {}

    if not voter_data.empty:
        # Building the 5 digit district id by combining assembly and election district, since ElectDist in geojson is assembly + electiondistrict
        voter_data["DistrictID"] = (
            voter_data["AssemblyDistrict"].astype(int).astype(str).str.zfill(2) +
            voter_data["ElectionDistrict"].astype(int).astype(str).str.zfill(3)
        ).astype(int)

        # Counting how many voters belong to each party in each district
        party_counts = (
            voter_data.groupby(["DistrictID", "PoliticalParty"])
            .size()
            .reset_index(name="Count")
        )

        # Find the most popular party in each district
        popular_party = party_counts.loc[
            party_counts.groupby("DistrictID")["Count"].idxmax()
        ].copy()

        # Make a lookup from district id to most popular party
        party_lookup = dict(zip(popular_party["DistrictID"], popular_party["PoliticalParty"]))

    # Colors for parties. Red for republican and blue for dem, etc.
    party_colors = {
        "DEM": "blue",
        "REP": "red",
        "BLK": "green",
        "WEP": "purple",
        "IND": "orange",
        "CON": "pink",
        "GRE": "darkgreen",
        "WOR": "brown",
        "OTH": "gray"
    }

    # Adding the most popular party into each election district feature
    for feature in election_data["features"]:
        district_id = int(feature["properties"]["ElectDist"])
        feature["properties"]["PopularParty"] = party_lookup.get(district_id, "OTH")

    # Adding income info into each zipcode
    for feature in zipcode_data["features"]:
        # Grab the zipcode from the geojson and make it 5 digits
        zip_code = str(feature["properties"].get("modzcta", "")).zfill(5)

        # Looking up the income for that zipcode
        income = income_lookup.get(zip_code)

        # Store cleaned zipcode back into the properties
        feature["properties"]["modzcta"] = zip_code

        # Store formatted income text for the tooltip
        feature["properties"]["MedianIncome"] = "N/A" if income is None else f"${income:,.0f}"

    # Only add the election layer if the geojson actually has features
    if election_data["features"]:
        folium.GeoJson(
            election_data,
            style_function=lambda feature: {
                # Color each district by its most popular party
                "fillColor": party_colors.get(feature["properties"].get("PopularParty", "OTH"), "gray"),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.6
            },
            tooltip=folium.GeoJsonTooltip(
                # Show district id and most popular party on hover
                fields=["ElectDist", "PopularParty"],
                aliases=["Election District:", "Popular Party:"],
                labels=True
            )
        ).add_to(election_fg)

    # Add the election feature group onto the main map
    election_fg.add_to(m)

    # Only adding the choropleth if zipcode features and income data both exist
    if zipcode_data["features"] and not income_data.empty:
        folium.Choropleth(
            geo_data=zipcode_data,
            data=income_data,
            columns=["ZIP", "MedianIncome"],
            key_on="feature.properties.modzcta",
            fill_color="YlGnBu",
            fill_opacity=0.7,
            line_opacity=0.2,
            nan_fill_color="gray",
            legend_name="Median Income",
            name="Median Income Heat Map",
            show=True
        ).add_to(m)

    # Add a transparent zipcode layer just for hover tooltips, which presents more specific information when hovered over a zipcode.
    if zipcode_data["features"]:
        folium.GeoJson(
            zipcode_data,
            name="Zip Code ToolTip",
            style_function=lambda feature: {
                # Keep this layer invisible until hovered
                "fillColor": "transparent",
                "color": "black",
                "weight": 1,
                "fillOpacity": 0
            },
            highlight_function=lambda feature: {
                # Highlight the hovered zipcode boundary
                "weight": 3,
                "color": "yellow",
                "fillOpacity": 0.1
            },
            tooltip=folium.GeoJsonTooltip(
                # Show zipcode and income on hover
                fields=["modzcta", "MedianIncome"],
                aliases=["ZIP Code:", "Median Income:"],
                labels=True,
                sticky=False
            )
        ).add_to(m)

    folium.LayerControl().add_to(m)

    return m

@app.get('/')
def home_get():
    # Building the map for the home page
    m = build_map()

    # Render the map html into the template
    return render_template('home.html', map_html=m._repr_html_())

@app.get('/profile')
def profile_get():
    # Grabbing the current logged in user
    user = utility.get_user(session["username"])

    # Show the profile page
    return render_template('profile.html', user=user)

if __name__ == '__main__':
    # Run the Flask app in debug mode
    app.run(debug=True)

