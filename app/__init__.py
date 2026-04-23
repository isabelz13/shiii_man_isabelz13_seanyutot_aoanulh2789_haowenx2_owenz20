# Isabel Zheng, Araf Hoque, Sean Takahashi, Haowen Xiao, Owen Zeng
# shiii_man
# SoftDev
# P04
# 2026-04-22w

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

def get_election_game_data():
    """
    Pull all election district GeoJSON and voter counts from the database.
    Returns (election_data geojson dict, voter_counts dict)
    voter_counts: str(district_id) -> { "counts": {party: n}, "party": str, "margin": float }
    """
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
 
    voter_rows = cur.execute(
        "SELECT AssemblyDistrict, ElectionDistrict, PoliticalParty FROM voter"
    ).fetchall()
    elec_rows = cur.execute("SELECT geojson FROM election").fetchall()
    conn.close()
 
    voter_data = pd.DataFrame(
        voter_rows, columns=["AssemblyDistrict", "ElectionDistrict", "PoliticalParty"]
    )
    election_data = {
        "type": "FeatureCollection",
        "features": [json.loads(row[0]) for row in elec_rows]
    }
    election_data = clean_geojson(election_data)
 
    voter_counts = {}
 
    if not voter_data.empty:
        voter_data["DistrictID"] = (
            voter_data["AssemblyDistrict"].astype(int).astype(str).str.zfill(2) +
            voter_data["ElectionDistrict"].astype(int).astype(str).str.zfill(3)
        ).astype(int)
 
        party_counts = (
            voter_data.groupby(["DistrictID", "PoliticalParty"])
            .size()
            .reset_index(name="Count")
        )
 
        for district_id, group in party_counts.groupby("DistrictID"):
            total = group["Count"].sum()
            top_row = group.loc[group["Count"].idxmax()]
            voter_counts[str(district_id)] = {
                "counts": dict(zip(group["PoliticalParty"], group["Count"].astype(int))),
                "party": top_row["PoliticalParty"],
                "margin": round(float(top_row["Count"]) / total, 3) if total > 0 else 0.5
            }
 
    # Attach dominant party + margin to each GeoJSON feature for frontend coloring
    for feature in election_data["features"]:
        did = int(feature["properties"]["ElectDist"])
        info = voter_counts.get(str(did), {})
        feature["properties"]["party"] = info.get("party", "OTH")
        feature["properties"]["margin"] = info.get("margin", 0.5)
 
    return election_data, voter_counts
 
 
def build_adjacency_map(election_data):
    """
    Build a dict: str(district_id) -> [list of adjacent str(district_ids)].
    Two districts are adjacent when their bounding boxes overlap with a small buffer.
    """
    id_to_bbox = {}
    for f in election_data["features"]:
        did = int(f["properties"]["ElectDist"])
        id_to_bbox[did] = get_feature_bbox(f)
 
    adjacency = {did: [] for did in id_to_bbox}
    ids = list(id_to_bbox.keys())
    buffer = 0.002  # ~200m, catches shared edges
 
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            ba, bb = id_to_bbox[a], id_to_bbox[b]
            if ba is None or bb is None:
                continue
            if not (
                ba[1] + buffer < bb[0] or
                bb[1] + buffer < ba[0] or
                ba[3] + buffer < bb[2] or
                bb[3] + buffer < ba[2]
            ):
                adjacency[a].append(b)
                adjacency[b].append(a)
 
    return {str(k): [str(n) for n in v] for k, v in adjacency.items()}
 
 
def is_contiguous(district_ids, adjacency_map):
    """
    BFS contiguity check. Returns True if all district_ids form one connected group.
    """
    if not district_ids:
        return False
    if len(district_ids) == 1:
        return True
 
    district_set = set(str(x) for x in district_ids)
    visited = set()
    queue = [str(district_ids[0])]
    visited.add(str(district_ids[0]))
 
    while queue:
        current = queue.pop(0)
        for neighbor in adjacency_map.get(current, []):
            if neighbor in district_set and neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
 
    return len(visited) == len(district_set)
 
 
def get_user_id(username):
    """Return the integer id for a username, or None if not found."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id FROM profiles WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    return row[0] if row else None
 
 
def make_json_response(data, status=200):
    """Return a plain JSON response without jsonify (no new imports)."""
    return json.dumps(data), status, {"Content-Type": "application/json"}


@app.get('/game')
def game_get():
    """
    Render the game page. Embeds GeoJSON, adjacency map, and voter counts
    directly into the template. Also loads any previously saved maps for
    the logged-in user.
    """
    map_id = request.args.get("map_id")
    print("map_id:", map_id)

    election_data, voter_counts = get_election_game_data()
    adjacency_map = build_adjacency_map(election_data)
    total_districts = len(election_data["features"])
 
    # Load this user's saved maps
    username = session.get("username")
    saved_maps = []
 
    if username:
        user_id = get_user_id(username)
        if user_id:
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            rows = cur.execute(
                """
                SELECT map_id, map_name, player_party, created_at,
                       district1,  district2,  district3,
                       district4,  district5,  district6,
                       district7,  district8,  district9,
                       district10, district11, district12,
                       district13, district14, district15,
                       district16, district17, district18,
                       district19, district20
                FROM saved_maps
                WHERE user_id = ?
                ORDER BY created_at DESC
                """,
                (user_id,)
            ).fetchall()
            conn.close()
 
            for row in rows:
                map_id, map_name, player_party, created_at = row[0], row[1], row[2], row[3]
                # Columns 3-27 are district1..district25, each a JSON array of election IDs
                assembly_districts = []
                for i, raw in enumerate(row[3:], start=1):
                    if raw:
                        try:
                            election_ids = json.loads(raw)
                        except (ValueError, TypeError):
                            election_ids = []
                        assembly_districts.append({
                            "id": i,
                            "electionDistricts": election_ids
                        })
                saved_maps.append({
                    "map_id": map_id,
                    "map_name": map_name,
                    "created_at": created_at,
                    "player_party": player_party,
                    "assembly_districts": assembly_districts
                })
 
    return render_template(
        'game.html',
        election_geojson=json.dumps(election_data),
        adjacency_map=json.dumps(adjacency_map),
        voter_counts=json.dumps(voter_counts),
        total_districts=total_districts,
        saved_maps=json.dumps(saved_maps),
        saved_maps_parsed=saved_maps,   # raw Python list for Jinja {% for %} loop
        load_map_id = map_id
    )
 
 
@app.post('/game/validate')
def game_validate():
    """
    Check if a proposed assembly district is contiguous.
    Request:  { "district_ids": [1001, 1002, ...], "adjacency_map": {...} }
    Response: { "valid": true/false, "message": "..." }
    """
    data = request.get_json()
    district_ids = data.get("district_ids", [])
    adjacency_map = data.get("adjacency_map", {})
 
    if not district_ids:
        return make_json_response({"valid": False, "message": "No districts selected."}, 400)
 
    contiguous = is_contiguous(district_ids, adjacency_map)
 
    if contiguous:
        return make_json_response({"valid": True, "message": "District is contiguous."})
    else:
        return make_json_response({
            "valid": False,
            "message": "Districts are not contiguous. All election districts must touch."
        })
 
 
@app.post('/game/save')
def game_save():
    """
    Save a completed game to the database.
    Inserts one row into saved_maps and one row into map_gmed.
    Each of the 20 district columns stores a JSON array of election district IDs.
 
    Request: {
        "map_name": "My Map",
        "assembly_districts": [
            { "id": 1, "electionDistricts": [1001, 1002, ...], "winner": "DEM" },
            ... (20 total)
        ]
    }
    Response: { "success": true, "map_id": 5 }
              { "success": false, "message": "..." }
    """
 
    user = get_user_id(session["username"])

    data = request.get_json()
    map_name = data.get("map_name", "").strip()
    player_party = data.get("player_party", "DEM")
    assembly_districts = data.get("assembly_districts", [])
 
    if not map_name:
        return make_json_response({"success": False, "message": "Map name cannot be empty."}, 400)
 
    if len(assembly_districts) != 20:
        return make_json_response({"success": False, "message": "Must have exactly 20 assembly districts."}, 400)
 
    # Sort by id so district1 always = assembly district 1
    assembly_districts = sorted(assembly_districts, key=lambda d: d["id"])
 
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
 
    try:
        # Each district column gets a JSON array of the election district IDs it contains
        district_cols = [
            json.dumps([int(eid) for eid in ad["electionDistricts"]])
            for ad in assembly_districts
        ]
 
        cur.execute(
            """
            INSERT INTO saved_maps (
                user_id, map_name, player_party,
                district1,  district2,  district3,  district4,  district5,
                district6,  district7,  district8,  district9,  district10,
                district11, district12, district13, district14, district15,
                district16, district17, district18, district19, district20
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [user, map_name, player_party] + district_cols
        )
        map_id = cur.lastrowid
 
        conn.commit()
        conn.close()

        print("Saving map:", map_name, "for user:", user)
        return make_json_response({"success": True, "map_id": map_id})
 
    except sqlite3.IntegrityError:
        conn.rollback()
        conn.close()
        return make_json_response(
            {"success": False, "message": f'A map named "{map_name}" already exists.'},
            400
        )
 
 
@app.post('/game/score')
def game_score():
    """
    Score all 20 finalized assembly districts.
    Request: {
        "player_party": "DEM",
        "assembly_districts": [ { "id": 1, "election_districts": [1001, ...] }, ... ],
        "voter_counts": { "1001": { "counts": {"DEM": 120, "REP": 80}, ... }, ... }
    }
    Response: {
        "results": [ { "id": 1, "winner": "DEM", "totals": {...} }, ... ],
        "player_seats": 14,
        "total_seats": 20,
        "won": true
    }
    """
    user = get_user_id(session["username"])
    data = request.get_json()
    player_party = data.get("player_party", "DEM")
    assembly_districts = data.get("assembly_districts", [])
    voter_counts_raw = data.get("voter_counts", {})
 
    results = []
    player_seats = 0
 
    for ad in assembly_districts:
        ad_id = ad["id"]
        election_ids = [str(x) for x in ad["election_districts"]]
 
        # Sum all voter counts across the election districts in this assembly district
        totals = {}
        for eid in election_ids:
            counts = voter_counts_raw.get(eid, {}).get("counts", {})
            for party, count in counts.items():
                totals[party] = totals.get(party, 0) + count
 
        winner = max(totals, key=totals.get) if totals else "OTH"
        results.append({"id": ad_id, "winner": winner, "totals": totals})
 
        if winner == player_party:
            player_seats += 1
 
    win_int = int(player_seats > 10)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute(
            """
            UPDATE profiles SET total_maps = total_maps + 1, wins = wins + ? WHERE id = ?
            """,
            (win_int, user)
        )
 
    conn.commit()
    conn.close()

    return make_json_response({
        "results": results,
        "player_seats": player_seats,
        "total_seats": len(assembly_districts),
        "won": player_seats > len(assembly_districts) // 2
    })
    
@app.get('/')
def home_get():
    # Building the map for the home page
    m = build_map()

    # Render the map html into the template
    return render_template('home.html', map_html=m._repr_html_())

@app.get('/profile')
def profile_get():
    # Grabbing the current logged in user
    user = get_user_id(session["username"])

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cursor = cur.execute(
            """
            SELECT total_maps, wins FROM profiles WHERE id = ?
            """,
            (user,)
        )
    
    output = cursor.fetchone()
    
    total_maps, wins = output[0], output[1]

    cursor = cur.execute(
            """
            SELECT map_id, map_name, created_at FROM saved_maps WHERE user_id = ?
            """,
            (user,)
        )
    
    saved_maps = cursor.fetchall()

    conn.close()

    # Show the profile page
    return render_template('profile.html', user=user, total_maps=total_maps, wins=wins, saved_maps=saved_maps)

if __name__ == '__main__':
    # Run the Flask app in debug mode
    app.run(debug=True)

