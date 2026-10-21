import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("scrub", pathlib.Path(__file__).parents[1] / "common" / "scrub.py")
scrub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scrub)


def test_removes_names():
    text, hits = scrub.scrub_names("John Smith was found at the residence.")
    assert "Smith" not in text and hits


def test_spanish_particles():
    text, _ = scrub.scrub_names("María de la Cruz Sandoval murió en su casa.")
    assert "María" not in text and "Cruz" not in text


def test_titles_and_ages():
    text, _ = scrub.scrub_names("Mrs. Garcia said Lopez, 34, died.")
    assert "Garcia" not in text and "Lopez" not in text


def test_keeps_places():
    s = "A fatal crash was reported in Rio Rancho near Old Town in Bernalillo County, New Mexico."
    assert scrub.scrub_names(s) == (s, [])
