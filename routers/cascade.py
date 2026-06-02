def get_all_routes():
    return []

def get_all_router_states():
    return {}

def trigger_dead_letter_queue(target_payload):
    print(f"Dead letter queue triggered for: {target_payload}")

router_job_registry = {}
