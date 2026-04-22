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

def get_feature_bbox(feature):
    # Get bounding box (min_lat, max_lat, min_lon, max_lon) of a GeoJSON feature
    coords = []
    geom = feature.get("geometry", {})
    geom_type = geom.get("type", "")
 
    if geom_type == "Polygon":
        for ring in geom.get("coordinates", []):
            coords.extend(ring)
    elif geom_type == "MultiPolygon":
        for polygon in geom.get("coordinates", []):
            for ring in polygon:
                coords.extend(ring)
 
    if not coords:
        return None
 
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lats), max(lats), min(lons), max(lons))
 
 
def get_feature_centroid(feature):
    # Compute the rough centroid of a GeoJSON feature from its coordinate bounds
    coords = []
    geom = feature.get("geometry", {})
    geom_type = geom.get("type", "")
 
    if geom_type == "Polygon":
        for ring in geom.get("coordinates", []):
            coords.extend(ring)
    elif geom_type == "MultiPolygon":
        for polygon in geom.get("coordinates", []):
            for ring in polygon:
                coords.extend(ring)
 
    if not coords:
        return None, None
 
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return sum(lats) / len(lats), sum(lons) / len(lons)
 
 
def point_in_bbox(lat, lon, bbox):
    # Gets the bounding box of a feature and checks if a point is within it
    min_lat, max_lat, min_lon, max_lon = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(c1, c2, t):
    return tuple(lerp(c1[i], c2[i], t) for i in range(3))

def bilinear_color_blend(party_hex, income_norm, margin_norm):
    """
    2D blend across four corner colors:

      margin=0, income=0 -> dark gray      (contested, poor)
      margin=0, income=1 -> light gray     (contested, wealthy)
      margin=1, income=0 -> deep party     (dominant, poor)
      margin=1, income=1 -> washed party   (dominant, wealthy)
    """
    party = hex_to_rgb(party_hex)

    # Build deep version: push RGB toward black by 60%
    deep = lerp_color(party, (0.0, 0.0, 0.0), 0.4)

    # Build washed version: push RGB toward white by 60%
    washed = lerp_color(party, (1.0, 1.0, 1.0), 0.6)

    gray_dark  = (0.25, 0.25, 0.25)
    gray_light = (0.80, 0.80, 0.80)

    # Interpolate along income axis for each margin extreme
    bottom = lerp_color(gray_dark, gray_light, income_norm)  # margin=0 edge
    top    = lerp_color(deep,      washed,     income_norm)  # margin=1 edge

    # Interpolate along margin axis
    final = lerp_color(bottom, top, margin_norm)

    return rgb_to_hex(*final)


def build_map():
    """
    Opacity-encoded map:
    - Election districts colored by dominant party
    - Fill opacity driven by median income of the overlapping zip area
      (low income = 0.15 opacity, high income = 0.85 opacity)
    - Tooltip shows district, party, party share, and income
    """

    # Create the base map centered on NYC
    m = folium.Map(
        location=[40.7128, -74.0060],
        zoom_start=10,
        min_zoom=10,
        max_bounds=True,
        min_lat=40.4,
        max_lat=40.95,
        min_lon=-74.35,
        max_lon=-73.65,
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

    ### INCOME ###
    # Start with an empty income lookup dictionary
    income_lookup = {}
    zip_centroids = []

    if not income_data.empty:
        # Making sure zip codes stay as 5 digit strings, since zipcodes are identifiers
        income_data["ZIP"] = income_data["ZIP"].astype(str).str.zfill(5)

        # Converting median income values into numbers
        income_data["MedianIncome"] = pd.to_numeric(income_data["MedianIncome"], errors="coerce")

        # Making a quick zip to income lookup
        income_lookup = dict(zip(income_data["ZIP"], income_data["MedianIncome"]))

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

            if income is not None and not pd.isna(income):
                lat, lon = get_feature_centroid(feature)
                if lat is not None:
                    zip_centroids.append((lat, lon, income))
    
    all_incomes = [v for v in income_lookup.values() if v and not pd.isna(v)]
    min_income = min(all_incomes) if all_incomes else 0
    max_income = max(all_incomes) if all_incomes else 1
    income_range = max_income - min_income if max_income != min_income else 1


    ### PARTY ###

    party_lookup = {}
    margin_lookup = {}

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
        for district_id, group in party_counts.groupby("DistrictID"):
            total = group["Count"].sum()
            top_row = group.loc[group["Count"].idxmax()]
            party_lookup[district_id] = top_row["PoliticalParty"]
            margin_lookup[district_id] = top_row["Count"] / total if total > 0 else 0.5

    # Colors for parties. 
    party_colors = {
        "DEM": "#0047AB",   
        "REP": "#CC0000",   
        "BLK": "#00873E",   
        "WEP": "#6600CC",   
        "IND": "#FF6600",   
        "CON": "#FF1493",   
        "GRE": "#004d00",   
        "WOR": "#8B4513",   
        "OTH": "#555555",   
    }

    # Income-derived opacity for each district, based on the overlapping zipcode's median income

    # Adding the most popular party into each election district feature
    for feature in election_data["features"]:
        district_id = int(feature["properties"]["ElectDist"])
        feature["properties"]["PopularParty"] = party_lookup.get(district_id, "OTH")
        party = party_lookup.get(district_id, "OTH")
        margin = margin_lookup.get(district_id, 0.5)

        bbox = get_feature_bbox(feature)
        nearby_incomes = []


        if bbox and zip_centroids:
            for (z_lat, z_lon, z_income) in zip_centroids:
                if point_in_bbox(z_lat, z_lon, bbox):
                    nearby_incomes.append(z_income)

        if nearby_incomes:
            district_income = sum(nearby_incomes) / len(nearby_incomes)
        else:
            if zip_centroids and bbox:
                bbox_center_lat = (bbox[0] + bbox[1]) / 2
                bbox_center_lon = (bbox[2] + bbox[3]) / 2
                closest = min(
                    zip_centroids,
                    key=lambda zc: (zc[0] - bbox_center_lat)**2 + (zc[1] - bbox_center_lon)**2
                )
                district_income = closest[2]
            else:
                district_income = None

        income_norm = max(0.0, min(1.0, (district_income - min_income) / income_range)) if district_income is not None else 0.5
        margin_norm = margin
 
        feature["properties"]["PopularParty"] = party
        feature["properties"]["PartyMargin"] = f"{margin:.0%}"
        feature["properties"]["EstimatedIncome"] = (
            "N/A" if district_income is None else f"${district_income:,.0f}"
        )
        

        feature["properties"]["_fill_color"] = bilinear_color_blend(
            party_colors.get(party, "#555555"),
            income_norm,
            margin_norm
        )
        feature["properties"]["_fill_opacity"] = 0.85  # fixed — color now carries both signals
        feature["properties"]["_margin_raw"] = margin

    # Only add the election layer if the geojson actually has features
    if election_data["features"]:
        folium.GeoJson(
            election_data,
            style_function=lambda feature: {
                # Color each district by its most popular party
                "fillColor": feature["properties"].get("_fill_color", "#aaaaaa"),
                "color": "black",
                "weight": 0.5 * (feature["properties"].get("_margin_raw", 0.5) * 3.5),
                "fillOpacity": feature["properties"].get("_fill_opacity", 0.4),
            },
            highlight_function=lambda feature: {
                "weight": 2,
                "color": "yellow",
                # Briefly boost opacity on hover so user can clearly see the district
                "fillOpacity": min(
                    feature["properties"].get("_fill_opacity", 0.4) + 0.25, 1.0
                ),
            },
            tooltip=folium.GeoJsonTooltip(
                # Show district id and most popular party on hover
                fields=["ElectDist", "PopularParty", "PartyMargin", "EstimatedIncome"],
                aliases=["Election District:", "Popular Party:", "Party Margin:", "Estimated Median Income:"],
                labels=True,
                sticky=False
            )
        ).add_to(election_fg)

    # Add the election feature group onto the main map
    election_fg.add_to(m)

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

