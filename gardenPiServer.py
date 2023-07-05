import sqlite3
from flask import Flask, jsonify, request, g

app = Flask(__name__)

DATABASE = "gardenpi.sqlite"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/channels')
def get_channels():
    try:
        res = []
        for row in query_db('SELECT * from configuration'):
            channel = {"channel":row['channel'],"enabled":row['enabled'],"period":row['period_s'],"duration":row['duration_s'],"start":row['startTimeOfDay']}
            res.append(channel)
        return jsonify(res)
    except Exception:
        app.logger.exception("Exception on channels query")
        return '{"error":"channels query failed"}', 500

@app.route('/channel/<int:chan>')
def get_channel(chan):
    try:
        res = query_db('SELECT * from configuration WHERE channel=?',(chan,))
        row = res[0]
        channel = {"channel":row['channel'],"enabled":row['enabled'],"period":row['period_s'],"duration":row['duration_s'],"start":row['startTimeOfDay']}
        return jsonify(channel)
    except Exception:
        app.logger.exception("Exception on channel query")
        return '{"error":"channel query failed"}', 500

@app.route('/channel/<int:chan>', methods=['POST'])
def post_channel(chan):
    try:
        req = request.get_json()
        query_db('UPDATE configuration set enabled=?,period_s=?,duration_s=?,startTimeOfDay=?,updated=1 WHERE channel=?',(req['enabled'],req['period'],req['duration'],req['start'],chan))
        get_db().commit()
        return '', 204
    except Exception:
        app.logger.exception("Exception on channel update")
        return '{"error":"channel update failed"}', 500
