from kavach import languages


def test_script_ratio_pure_scripts():
    assert languages.script_ratio("नमस्ते दुनिया", "Deva") == 1.0
    assert languages.script_ratio("hello world", "Latn") == 1.0
    assert languages.script_ratio("hello world", "Deva") == 0.0


def test_script_ratio_ignores_digits_and_punctuation():
    assert languages.script_ratio("123 ... !!!", "Latn") == 0.0
    assert languages.script_ratio("OTP 123456!", "Latn") == 1.0


def test_script_ratio_mixed():
    ratio = languages.script_ratio("नमस्ते hello", "Deva")
    assert 0.3 < ratio < 0.8


def test_is_in_language():
    assert languages.is_in_language("आपका खाता बंद कर दिया जाएगा", "hi-IN")
    assert not languages.is_in_language("Your account will be blocked today", "ta-IN")
    assert languages.is_in_language("உங்கள் கணக்கு முடக்கப்படும்", "ta-IN")
    # A mostly-Tamil sentence with an English acronym still counts as Tamil.
    assert languages.is_in_language("உங்கள் OTP எண்ணை யாரிடமும் சொல்ல வேண்டாம்", "ta-IN")


def test_detect_script_language():
    assert languages.detect_script_language("உங்கள் கேவைசி காலாவதியாகிவிட்டது") == "ta-IN"
    assert languages.detect_script_language("आपके नाम पर गिरफ्तारी वारंट जारी हुआ है") == "hi-IN"
    assert languages.detect_script_language("Your parcel contains drugs") == "en-IN"
    assert languages.detect_script_language("12345 !!!") is None


def test_language_catalogue():
    assert len(languages.LANGUAGES) == 23
    assert sum(1 for l in languages.LANGUAGES.values() if l.tts) == 11
    assert languages.get("nonsense").code == languages.DEFAULT_LANGUAGE
    assert languages.get(None).code == languages.DEFAULT_LANGUAGE
