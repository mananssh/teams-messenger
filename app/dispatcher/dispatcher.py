def dispatch_actions(parsed_data):
    print("\n🚀 Dispatching Actions...\n")

    # ✅ FIX 1: define action_items properly
    action_items = parsed_data.get("action_items", [])

    for action in action_items:
        action_type = action.get("type")
        assignee = action.get("assignee")
        message = action.get("notify_message")

        print(f"➡️ Processing {action_type} for {assignee}")

        if action_type == "send_notification":
            handle_notification(assignee, message)

        elif action_type == "send_email":
            handle_email(action)

        elif action_type == "create_jira_ticket":
            handle_jira(action)

        elif action_type == "escalate":
            handle_escalation(action)

        elif action_type == "create_document":
            handle_document(action)

        else:
            print(f"⚠️ Unsupported action type: {action_type}")


# 🔹 TEMP MOCK FUNCTIONS

def handle_notification(user, message):
    print(f"💬 [Teams] → {user}: {message}\n")


def handle_email(action):
    payload = action.get("payload", {})
    print(f"📧 Email to {payload.get('to_name')}: {payload.get('subject')}\n")


def handle_jira(action):
    print(f"🎫 Creating Jira Ticket: {action.get('title')}\n")


def handle_escalation(action):
    payload = action.get("payload", {})
    print(f"🚨 Escalation → {payload.get('escalate_to')}")
    print(f"Reason: {payload.get('reason')}\n")


def handle_document(action):
    payload = action.get("payload", {})
    print(f"📄 Create Document: {payload.get('title')}")
    print(f"Type: {payload.get('document_type')}\n")