# Gerrymandering Simulator by shiii_man

## Roster/Roles:
- Isabel Zheng (PM): database management, general debugging 
- Araf Hoque: folium mapping
- Sean Takahashi: data management, data linkage to map using pandas, VM, game debugging
- Haowen Xiao: CSS, testing app, map configurations
- Owen Zeng: gerrymandering game

## Description:
Gerrymandering has been long part of American politics but is a complex process involving many demographic layers considered when redrawing district lines. This simulation attempts to educate users in understanding how their legislature may be considering their area's income level along with party registration data in order to determine how to draw district lines for the upcoming election taking into consideration trends of income with voting patterns.

## Live Site:
Our program is hosted live [here](http://161.35.189.176)

### FEATURE SPOTLIGHT
* Hover over election district to see stats breakdown
* Try to gerrymander through the 5000+ election districts in NYC

### KNOWN BUGS/ISSUES
* When loading previous maps, it may show 21/20 assigned districts but the DEM/REP counting is accurate.
* Non-residential areas(parks, graveyards, etc.) can show as election districts in the map due to the data we used.

## Install Guide:

Click the green button on the repo, and choose the SSH clone option. Copy the link and open a terminal session. 
```
$ git clone git@github.com:isabelz13/shiii_man_isabelz13_seanyutot_aoanulh2789_haowenx2_owenz20.git p4
$ cd p4
$ python -m venv venv
```
For Linux and Mac users

```
$ source venv/bin/activate
$ pip install -r requirements.txt
```

For Windows users

```
$ venv\Scripts\activate
$ pip install -r requirements.txt
```

Now open on [localhost](http://127.0.0.0:5000)

## Launch Codes:
In terminal, access project root directory and run the command:

```
~$ cd app
~$ python build_db.py
~$ python __init__.py
```


