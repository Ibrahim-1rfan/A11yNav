"""The voice dock's state machine: one state variable, one transition table.

idle -> listening -> thinking -> speaking -> done, with error and typing as side states. Events that are not
valid in the current state are ignored, so a late microphone or model result can never jump the dock around.
"""
IDLE, LISTENING, TYPING, THINKING, SPEAKING, DONE, ERROR, CLOSED = (
    "idle", "listening", "typing", "thinking", "speaking", "done", "error", "closed")

TRANSITIONS = {
    (IDLE, "start"): LISTENING, (DONE, "start"): LISTENING, (ERROR, "start"): LISTENING, (TYPING, "start"): LISTENING,
    (LISTENING, "heard"): THINKING,          # end of speech detected and transcribed; no Ask button
    (LISTENING, "type"): TYPING,             # a printable key switches to the keyboard
    (IDLE, "type"): TYPING, (DONE, "type"): TYPING, (ERROR, "type"): TYPING,
    (TYPING, "submit"): THINKING,
    (THINKING, "answer_read"): SPEAKING,     # auto read-aloud on
    (THINKING, "answer_quiet"): DONE,        # read-aloud off, or a screen reader will read it
    (SPEAKING, "finished"): DONE,
    (SPEAKING, "stop"): DONE,                # Esc or orb click while reading
    (SPEAKING, "barge_in"): LISTENING,       # the user started talking over the answer
    (LISTENING, "stop_listening"): IDLE,
    (LISTENING, "fail"): ERROR, (THINKING, "fail"): ERROR, (TYPING, "fail"): ERROR, (SPEAKING, "fail"): DONE,
    (LISTENING, "cancel"): CLOSED, (THINKING, "cancel"): CLOSED,   # Esc while listening or thinking closes
    (IDLE, "close"): CLOSED, (DONE, "close"): CLOSED, (ERROR, "close"): CLOSED, (TYPING, "close"): CLOSED,
    (SPEAKING, "close"): CLOSED,
    (CLOSED, "open"): IDLE,
}

CAPTIONS = {
    IDLE: "Press the hotkey and start talking",
    LISTENING: "Listening...",
    TYPING: "Type your question and press Enter",
    THINKING: "Got it, finding the answer...",
    SPEAKING: "",
    DONE: "",
    ERROR: "Couldn't hear that. Tap the orb to try again.",
}

ORB_LABELS = {
    IDLE: "Start listening", LISTENING: "Stop listening", TYPING: "Start listening", THINKING: "Finding the answer",
    SPEAKING: "Stop reading", DONE: "Ask another question", ERROR: "Try again", CLOSED: "Start listening",
}


class DockState:
    def __init__(self, on_change=lambda old, new, event: None):
        self.state = CLOSED
        self.on_change = on_change

    def fire(self, event):
        """Apply an event. Returns the new state, or None when the event does not apply now."""
        new = TRANSITIONS.get((self.state, event))
        if new is None:
            return None
        old, self.state = self.state, new
        self.on_change(old, new, event)
        return new
