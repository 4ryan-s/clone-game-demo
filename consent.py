"""Consent wording shown on the first screen. DRAFT: needs sign-off from whoever owns compliance before real participants.

Two separate choices: the first is needed to play; the second (keeping the data for model training) is optional and starts unticked.
Bump config.CONSENT_VERSION whenever any wording here changes. The version is stored with every session.
"""
import config

CONSENT = {
    "version": config.CONSENT_VERSION,
    "title": "Can you tell a real voice from a clone?",
    "intro": "You will read one sentence out loud. We will then make copies of your voice with three different systems, "
             "mix them with your real recording, and ask you to spot the real one. Then we will show how our system tells them apart.",
    "points": [
        "Your voice is personal data. We record you reading one sentence, about five seconds.",
        "Two voice-cloning systems copy your voice. One runs on this computer. The other, Sarvam, is an outside company: "
        "your recording and the sentence are sent to Sarvam over the internet to create its copy.",
        "Nothing else about you is collected. We do not ask for your name. You get a session code.",
        "You can stop at any point. If you do not tick the second box below, your recording and the copies are deleted when you finish.",
        "You can ask for your data to be deleted later with your session code" +
        (f" by contacting {config.CONTACT}." if config.CONTACT else ". Ask the demo host how."),
    ],
    "required": {
        "id": "required",
        "label": "I am 18 or older. I agree that my voice is recorded and copied by voice-cloning systems, including Sarvam, for this demo.",
    },
    "optional": {
        "id": "retain",
        "label": "Optional: you may keep my recording and the copies, and use them to train and test our voice-fraud detection. "
                 "They will be stored without my name and will not be shared outside the company.",
    },
}
