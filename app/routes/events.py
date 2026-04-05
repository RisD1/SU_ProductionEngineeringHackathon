import json
from flask import Blueprint, jsonify, request
from app.models.event import Event
from app.models.url import URL
from app.models.user import User
from app.database import db

events_bp = Blueprint("events", __name__)


# auto grader sequence reseter for event id after seeding
def sync_event_id_sequence():
    db.execute_sql("""
        SELECT setval(
            pg_get_serial_sequence('"event"', 'id'),
            COALESCE((SELECT MAX(id) FROM "event"), 1),
            true
        );
    """)


def create_event_record(event_type, url, user, details=None):
    if details is not None and not isinstance(details, dict):
        raise ValueError("Details must be a JSON object")

    event = Event.create(
        event_type=event_type,
        url=url,
        user=user,
        details=json.dumps(details) if details is not None else None
    )
    return event


def create_event_record(event_type, url, user, details=None):
    if details is not None and not isinstance(details, dict):
        raise ValueError("Details must be a JSON object")

    sync_event_id_sequence()

    event = Event.create(
        event_type=event_type,
        url=url,
        user=user,
        details=json.dumps(details) if details is not None else None
    )
    return event

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
            user_id = int(user_id)
        except ValueError:
            return jsonify({"error": "user_id must be an integer"}), 400
        query = query.where(Event.user_id == user_id)

    if url_id is not None:
        try:
            url_id = int(url_id)
        except ValueError:
            return jsonify({"error": "url_id must be an integer"}), 400
        query = query.where(Event.url_id == url_id)

    query = query.order_by(Event.timestamp.desc())
    total = query.count()

    paginated = False

    if (page is None) != (per_page is None):
        return jsonify({"error": "page and per_page must be provided together"}), 400

    use_pagination = page is not None and per_page is not None

    if use_pagination:
        try:
            page = int(page)
            per_page = int(per_page)
        except ValueError:
            return jsonify({"error": "page and per_page must be integers"}), 400

        if page < 1 or per_page < 1 or per_page > 100:
            return jsonify({"error": "Invalid pagination parameters"}), 400

        max_page = (total + per_page - 1) // per_page if total > 0 else 1
        if page > max_page:
            events = []
            result = []
            response_page = page
            response_per_page = per_page
        else:
            query = query.paginate(page, per_page)
            events = query
            result = []
            for event in events:
                details = None
                if event.details:
                    try:
                        details = json.loads(event.details)
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
            response_page = page
            response_per_page = per_page
    else:
        events = query
        result = []
        for event in events:
            details = None
            if event.details:
                try:
                    details = json.loads(event.details)
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
        response_page = None
        response_per_page = None

    response_data = {"events": result, "total": total}
    if use_pagination and response_page is not None:
        response_data["page"] = response_page
        response_data["per_page"] = response_per_page

    return jsonify(response_data), 200


@events_bp.route("/events", methods=["POST"])
def create_event():
    data = request.get_json(silent=True)

    # Invalid JSON / no JSON body
    if data is None:
        return jsonify({"error": "Invalid JSON"}), 400

    # JSON exists but must be an object
    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object"}), 400

    event_type = data.get("event_type")
    url_id = data.get("url_id")
    user_id = data.get("user_id")
    details = data.get("details")

    if event_type is None:
        return jsonify({"error": "event_type is required"}), 400
    if url_id is None:
        return jsonify({"error": "url_id is required"}), 400
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    if not isinstance(user_id, int):
        return jsonify({"error": "user_id must be an integer"}), 400
    if not isinstance(url_id, int):
        return jsonify({"error": "url_id must be an integer"}), 400
    if not isinstance(event_type, str):
        return jsonify({"error": "event_type must be a string"}), 400

    if user_id <= 0:
        return jsonify({"error": "user_id must be a positive integer"}), 400
    if url_id <= 0:
        return jsonify({"error": "url_id must be a positive integer"}), 400

    if details is not None:
        if not isinstance(details, dict):
            return jsonify({"error": "Details must be a JSON object"}), 400
        try:
            json.dumps(details)
        except (TypeError, ValueError):
            return jsonify({"error": "Details contains non-serializable data"}), 400

    user = User.get_or_none(User.id == user_id)
    if not user:
        return jsonify({"error": f"User with id {user_id} not found"}), 404

    url = URL.get_or_none(URL.id == url_id)

    if not url:
        return jsonify({"error": f"URL with id {url_id} not found"}), 404

    try:
        event = create_event_record(
        event = create_event_record(
            event_type=event_type,
            url=url,
            user=user,
            details=details
            details=details
        )

        response_details = details if details is not None else None

        return jsonify({
            "id": event.id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "url_id": event.url_id,
            "user_id": event.user_id,
            "details": response_details
        }), 201

    except ValueError:
        return jsonify({"error": "Details must be a JSON object"}), 400
    except Exception:
        return jsonify({"error": "Could not create event"}), 500

    except Exception:
        return jsonify({"error": "Failed to create event"}), 500