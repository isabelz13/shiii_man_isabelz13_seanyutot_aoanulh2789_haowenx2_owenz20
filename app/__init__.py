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
import pandas
import sqlite3

app = Flask(__name__)
app.secret_key = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*"

import auth
app.register_blueprint(auth.bp)

@app.before_request
def check_authentification():
    allowed_paths = ['/', '/auth/login', '/auth/signup']
    if 'username' not in session.keys() and request.path not in allowed_paths:
        flash("Please log in to view our website", "danger")
        return redirect(url_for("auth.login_get"))
    elif 'username' in session:
        user = utility.get_user(session['username'])
        if user is None:
            session.pop('username', None)
            return redirect(url_for("auth.login_get"))

def clean_geojson(geojson_data): # Clean GeoJSON
    for feature in geojson_data.get("features", []): # loop through every feature in the geoJSON
        props = feature.get("properties", {}) # get the properties dictionary from it
        cleaned_props = {}

        for key, value in props.items(): # Cleans up unwanted colons, underscores and stores cleaned properties
            new_key = key.lstrip(":").replace(":", "_").replace("-", "_")
            cleaned_props[new_key] = value

        feature["properties"] = cleaned_props

    return geojson_data

def build_map():
    m = folium.Map( # Creating the base map where we center in NYC
        location=[40.7128, -74.0060],
        zoom_start=10,
        min_zoom=10,
        max_bounds=True,
        tiles="CartoDB Positron"
    )


    conn = sqlite3.connect ("data.db") 
    cur = conn.cursor()
    income_rows = cur.execute ("SELECT zip, median_income FROM income").fetchall()
    income_data = pandas.DataFrame (income_rows, columns = ["ZIP", "MedianIncome"])
    voter_rows = cur.execute ("SELECT * FROM voter").fetchall()
    voter_cols = [desc[0] for desc in cur.description]
    voter_data = pandas.DataFrame (voter_rows, columns = voter_cols)
    zip_rows = cur.execute ("SELECT geojson FROM zipcodes").fetchall()
    zipcode_data = {"type": "FeatureCollection", "features": [json.loads(row[0]) for row in zip_rows]}
    elec_rows = cur.execute ("SELECT geojson FROM election").fetchall()
    election_data = {"type": "FeatureCollection", "features": [json.loads(row[0]) for row in elec_rows]}
    conn.close()
    print ("income rows:", len(income_rows))
    print ("zip rows:", len(zip_rows))
    print ("election rows:", len(elec_rows))
    print ("voter rows:", len(voter_rows))

    zipcode_data = clean_geojson(zipcode_data) # Zipcode GeoJSON wasn't compatible with 

    income_data["ZIP"] = income_data["ZIP"].astype(str) # Zipcode should be treated as a string, since it identifies NYC areas

    voter_data["DistrictID"] = (  # Since the ElectDist values in our election districts combine the assembly district and election district we have to create a new column where thats the case
        voter_data["AssemblyDistrict"].astype(str).str.zfill(2) +
        voter_data["ElectionDistrict"].astype(str).str.zfill(3) #  There should be 5 digits to match ElectDist property value
    ).astype(int)

    party_counts = ( # Groups voter data by district and party and counts
    voter_data.groupby(["DistrictID", "PoliticalParty.18"])
    .size()
    .reset_index(name="Count")
    )

    Popular_party = party_counts.loc[ # Finds the row with the highest count in each district
    party_counts.groupby("DistrictID")["Count"].idxmax() # groups party counts by district only and looks at the Count 
    ].copy()
    
    election_fg = folium.FeatureGroup(name="Election Districts", show=True) # Election Group
    income_data["MedianIncome"] = pandas.to_numeric(income_data["MedianIncome"], errors="coerce") # Median Income into ints
    income_lookup = dict(zip(income_data["ZIP"], income_data["MedianIncome"]))  # matches each zipcode to its median income
    party_lookup = dict(zip(Popular_party["DistrictID"], Popular_party["PoliticalParty.18"])) # creates a dictionary of district id: politcal  party

    party_colors = {  # party Colors. Blue for dem, red for republican. Makes sense.
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

    for feature in election_data["features"]:
        district_id = feature["properties"]["ElectDist"] #ElectDist in the geojson is the district id
        party = party_lookup.get(district_id, "OTH") #get the Popular party for that district id, and if u cant then assign other
        feature["properties"]["PopularParty"] = party  # Add the Popular party to district properties in the geojson
        
    for feature in zipcode_data["features"]: #loop through each modzcta in geojson

        zip_code = str(feature["properties"].get("modzcta", "")).zfill(5) # makes sure the modzcta is 5 digits for zipcode
        #print(zip_code)
        # print(income_lookup)
        income = income_lookup.get(zip_code) # get thei ncome for that zipcode

        feature["properties"]["modzcta"] = zip_code # modzcta refers to zipcode
        feature["properties"]["MedianIncome"] = "$" + str(income) # Concatenates $income

    folium.GeoJson( #GeoJSON map creation
        election_data,
        style_function=lambda feature: { # Styling
            "fillColor": party_colors.get(feature["properties"].get("PopularParty", "OTH"), "gray"),
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.6
        },
        tooltip=folium.GeoJsonTooltip( # Creating a tool tip to inform observers of the District ID and popular party
            fields=["ElectDist", "PopularParty"],
            aliases=["Election District:", "Popular Party:"],
            labels=True
        )
    ).add_to(election_fg) # Add to group

    election_fg.add_to(m)  # Add feature group to main map

    folium.Choropleth( # Create a chloropethm map for median income to zipcode
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

    folium.GeoJson( # Create a GeoJSON for zipcode tooltip since tooltip is only a feature for GeoJSON map
        zipcode_data,
        name="Zip Code ToolTip",
        style_function=lambda feature: {
            "fillColor": "transparent",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0
        },
        highlight_function=lambda feature: {
            "weight": 3,
            "color": "yellow",
            "fillOpacity": 0.1
        },
        tooltip=folium.GeoJsonTooltip(
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
    m = build_map()
    map_html = m._repr_html_()
    return render_template('home.html', map_html=map_html)

@app.get('/profile')
def profile_get():
    user = utility.get_user(session["username"])

    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)

