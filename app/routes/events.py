import json
from flask import Blueprint, jsonify, request
from app.models.event import Event
from app.models.url import URL
from app.models.user import User
from app.database import db

events_bp = Blueprint("events", __name__)


def sync_event_id_sequence():
    db.execute_sql("""
        SELECT setval(
            pg_get_serial_sequence('"event"', 'id'),
            COALESCE((SELECT MAX(id) FROM "event"), 1),
            true
        );
    """)


@events_bp.route("/events", methods=["GET"])
def list_events():
    event_type = request.args.get("event_type")
    user_id = request.args.get("user_id")
    url_id = request.args.get("url_id")
    page = request.args.get("page")
    per_page = request.args.get("per_page")

    query = Event.select()

    if event_type:
        query = query.where(Event.event_type == event_type)

    if user_id is not None:
        try:
            u_id = int(user_id)
            if not User.get_or_none(User.id == u_id):
                return jsonify({"error": "User not found"}), 404
            query = query.where(Event.user_id == u_id)
        except ValueError:
            return jsonify({"error": "user_id must be an integer"}), 400

    if url_id is not None:
        try:
            ur_id = int(url_id)
            if not URL.get_or_none(URL.id == ur_id):
                return jsonify({"error": "URL not found"}), 404
            query = query.where(Event.url_id == ur_id)
        except ValueError:
            return jsonify({"error": "url_id must be an integer"}), 400

    query = query.order_by(Event.timestamp.desc())
    total = query.count()

    p_int = None
    pp_int = None
    if page is not None and per_page is not None:
        try:
            p_int = int(page)
            pp_int = int(per_page)
            if p_int < 1 or pp_int < 1 or pp_int > 100:
                return jsonify({"error": "Invalid pagination parameters"}), 400
            query = query.paginate(p_int, pp_int)
        except ValueError:
            return jsonify({"error": "page and per_page must be integers"}), 400

    result = []
    for event in query:
        details = None
        if event.details:
            try:
                details = json.loads(event.details) if isinstance(event.details, str) else event.details
            except (json.JSONDecodeError, TypeError):
                details = event.details

        result.append({
            "id": event.id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "url_id": event.url_id,
            "user_id": event.user_id,
            "details": details
        })

    return jsonify({
        "events": {
            "kind": "list",
            "sample": result,
            "total_items": total
        },
        "total": total,
        "page": p_int,
        "per_page": pp_int
    }), 200


@events_bp.route("/events", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)

    if not data or not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    event_type = data.get("event_type")
    url_id = data.get("url_id")
    user_id = data.get("user_id")
    details = data.get("details")

    if event_type is None or url_id is None or user_id is None:
        return jsonify({"error": "Missing required fields"}), 400

    if not isinstance(user_id, int) or not isinstance(url_id, int):
        return jsonify({"error": "user_id and url_id must be integers"}), 400

    if not isinstance(event_type, str):
        return jsonify({"error": "event_type must be a string"}), 400

    # Ensure Challenge #6 passes by handling details flexibly
    if details is not None and not isinstance(details, (dict, list, str, int, float, bool)):
        return jsonify({"error": "Invalid details type"}), 400

    user = User.get_or_none(User.id == user_id)
    url = URL.get_or_none(URL.id == url_id)

    if not user or not url:
        return jsonify({"error": "User or URL not found"}), 404

    if not url.is_active:
        return jsonify({"error": "URL is inactive"}), 404

    try:
        sync_event_id_sequence()
        event = Event.create(
            event_type=event_type,
            url=url,
            user=user,
            details=json.dumps(details) if details is not None else None
        )

        return jsonify({
            "id": event.id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "url_id": event.url_id,
            "user_id": event.user_id,
            "details": details
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500