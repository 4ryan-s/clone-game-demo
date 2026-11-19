"""Consent wording shown on the first screen. DRAFT: needs sign-off from whoever owns compliance before real participants.

Two separate choices: the first is needed to play; the second (keeping the data for model training) is optional and starts unticked.
Bump config.CONSENT_VERSION whenever any wording here changes. The version is stored with every session.
"""
import config

CONSENT = {
    "version": config.CONSENT_VERSION,
    "title": "Can you tell a real voice from a clone?",
    "intro": "You will read one sentence out loud. We will then make copies of your voice with voice-cloning systems, "
             "mix them with your real recording, and ask you to spot the real one. Then we will show how our system tells them apart.",
    "points": [
        "Your voice is personal data. We record you reading one short sentence.",
        "Two voice-cloning systems make three copies of your voice. One, Qwen3-TTS, runs on this computer. The other, Sarvam, is an outside company: "
        "your recording is sent to Sarvam over the internet, to turn what you say into text and to create its two copies. The copies say the words you spoke.",
        "Nothing else about you is collected. We do not ask for your name. You get a session code.",
        "You can stop at any point. The copies are always deleted when you finish. If you do not tick the second box below, "
        "your own recording is deleted too. If you do tick it, only your own recording is kept.",
        "You can ask for your data to be deleted later with your session code" +
        (f" by contacting {config.CONTACT}." if config.CONTACT else ". Ask the demo host how."),
    ],
    "required": {
        "id": "required",
        "label": "I am 18 or older. I agree that my voice is recorded and copied by voice-cloning systems, including Sarvam, for this demo.",
    },
    "optional": {
        "id": "retain",
        "label": "If you agree, we may use your recording to train and test our voice-fraud detection system. "
                 "It will be stored anonymously and will not be shared outside the company.",
    },
}
