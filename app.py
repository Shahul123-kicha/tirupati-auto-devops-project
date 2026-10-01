import os
from datetime import datetime, timedelta, timezone

from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import IntegrityError

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///tirupati_autos.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

STANDS = [
    {"key": "alipiri", "name": "Alipiri Toll Gate",
     "blurb": "Foot of the Alipiri footpath and the ghat road up to Tirumala."},
    {"key": "tirumala", "name": "Tirumala Bus Stand",
     "blurb": "The main bus hub in Tirumala, a short ride from the temple."},
    {"key": "station", "name": "Railway Station",
     "blurb": "Tirupati Railway Station, for trains in and out of the city."},
]
STAND_NAMES = [s["name"] for s in STANDS]


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AutoDriver(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    driver_name = db.Column(db.String(100), nullable=False)
    auto_number = db.Column(db.String(50), unique=True, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    stand_location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Available')
    created_at = db.Column(db.DateTime, default=now)
    last_trip = db.Column(db.DateTime)

    def to_dict(self):
        return {
            "id": self.id,
            "driver_name": self.driver_name,
            "auto_number": self.auto_number,
            "phone_number": self.phone_number,
            "stand_location": self.stand_location,
            "status": self.status,
        }


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    pickup = db.Column(db.String(100), nullable=False)
    destination = db.Column(db.String(150), nullable=False)
    driver_name = db.Column(db.String(100), nullable=False)
    auto_number = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=now)


@app.template_filter('ist')
def to_ist(value):
    """Show UTC timestamps in Indian Standard Time."""
    return (value + timedelta(hours=5, minutes=30)).strftime('%d %b, %I:%M %p')


def clean(value, limit):
    return str(value or '').strip()[:limit]


def valid_phone(phone):
    digits = ''.join(c for c in phone if c.isdigit())
    return 10 <= len(digits) <= 13


def fleet_stats():
    drivers = AutoDriver.query.all()
    stands = {}
    for s in STANDS:
        mine = [d for d in drivers if d.stand_location == s["name"]]
        free = sum(1 for d in mine if d.status == 'Available')
        stands[s["key"]] = {"available": free, "busy": len(mine) - free}
    available = sum(v["available"] for v in stands.values())
    total = sum(v["available"] + v["busy"] for v in stands.values())
    return {"total": total, "available": available, "busy": total - available, "stands": stands}


# ---------- pages ----------

@app.route('/')
def index():
    return render_template('index.html', stands=STANDS, stats=fleet_stats())


@app.route('/fleet')
def fleet():
    stand = request.args.get('stand')
    query = AutoDriver.query.order_by(AutoDriver.id.desc())
    if stand in STAND_NAMES:
        query = query.filter_by(stand_location=stand)
    else:
        stand = None
    bookings = Booking.query.order_by(Booking.id.desc()).limit(8).all()
    return render_template('fleet.html', drivers=query.all(), bookings=bookings,
                           stands=STANDS, current=stand, stats=fleet_stats())


# ---------- JSON API ----------

@app.get('/api/stats')
def api_stats():
    return jsonify(fleet_stats())


@app.post('/api/drivers')
def api_register():
    data = request.get_json(silent=True) or {}
    name = clean(data.get('driver_name'), 100)
    plate = ' '.join(clean(data.get('auto_number'), 20).upper().split())
    phone = clean(data.get('phone_number'), 20)
    stand = data.get('stand_location')

    if not name or not plate:
        return jsonify(error="Enter the driver name and auto number."), 400
    if not valid_phone(phone):
        return jsonify(error="Enter a phone number with 10 to 13 digits."), 400
    if stand not in STAND_NAMES:
        return jsonify(error="Choose a stand from the list."), 400

    driver = AutoDriver(driver_name=name, auto_number=plate, phone_number=phone, stand_location=stand)
    db.session.add(driver)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error=f"{plate} is already registered."), 409
    return jsonify(driver.to_dict()), 201


@app.post('/api/drivers/<int:driver_id>/status')
def api_toggle(driver_id):
    driver = db.session.get(AutoDriver, driver_id)
    if not driver:
        return jsonify(error="Driver not found."), 404
    driver.status = 'Busy' if driver.status == 'Available' else 'Available'
    db.session.commit()
    return jsonify(driver.to_dict())


@app.delete('/api/drivers/<int:driver_id>')
def api_remove(driver_id):
    driver = db.session.get(AutoDriver, driver_id)
    if not driver:
        return jsonify(error="Driver not found."), 404
    db.session.delete(driver)
    db.session.commit()
    return jsonify(ok=True)


@app.post('/api/book')
def api_book():
    data = request.get_json(silent=True) or {}
    name = clean(data.get('customer_name'), 100)
    phone = clean(data.get('customer_phone'), 20)
    pickup = data.get('pickup')
    destination = clean(data.get('destination'), 150)

    if not name or not destination:
        return jsonify(error="Enter your name and where you are going."), 400
    if not valid_phone(phone):
        return jsonify(error="Enter a phone number with 10 to 13 digits."), 400
    if pickup not in STAND_NAMES:
        return jsonify(error="Choose a pickup stand from the list."), 400

    # The driver who has waited longest (or never had a trip) gets the ride.
    driver = (AutoDriver.query
              .filter_by(stand_location=pickup, status='Available')
              .order_by(AutoDriver.last_trip.is_(None).desc(),
                        AutoDriver.last_trip.asc(),
                        AutoDriver.id.asc())
              .first())

    if not driver:
        stats = fleet_stats()
        others = [{"name": s["name"], "available": stats["stands"][s["key"]]["available"]}
                  for s in STANDS
                  if s["name"] != pickup and stats["stands"][s["key"]]["available"] > 0]
        return jsonify(error=f"No autos are free at {pickup} right now.", alternatives=others), 409

    driver.status = 'Busy'
    driver.last_trip = now()
    booking = Booking(customer_name=name, customer_phone=phone, pickup=pickup,
                      destination=destination, driver_name=driver.driver_name,
                      auto_number=driver.auto_number)
    db.session.add(booking)
    db.session.commit()
    return jsonify(booking_id=booking.id, pickup=pickup, destination=destination,
                   driver=driver.to_dict()), 201


@app.route('/health')
def health():
    return 'ok'


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)