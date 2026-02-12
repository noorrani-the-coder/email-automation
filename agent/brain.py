from agent.priority import compute_priority

def agent_reason(email):
    """
    Computes the priority reason for the given email.

    Input: emailObject
    Output: "Low priority"
    """
    return compute_priority(email)
