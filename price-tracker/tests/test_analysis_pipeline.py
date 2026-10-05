"""Regression checks for the detector, report and trainer on simulated data."""
from price_tracker.analysis.evaluate import evaluate
from price_tracker.analysis.report import write_report
from price_tracker.analysis.simulate import simulate_market
from price_tracker.analysis.train import train
from price_tracker.models import Product


def test_detector_quality_on_noisy_simulated_data():
    result = evaluate(n=300, hard=True)
    for flag, m in result["per_flag"].items():
        assert m["recall"] >= 0.9, flag
        assert m["precision"] >= 0.9, flag
    assert result["genuine_listings_rated_genuine"] >= 0.95


def test_report_is_written_and_labelled_simulated(tmp_path):
    listings, sale = simulate_market(n=40, seed=2)
    products = [Product(url=f"https://x.test/{i}", name=l.name, category=l.category, history=l.history)
                for i, l in enumerate(listings)]
    out = write_report(products, [sale], sale, tmp_path, simulated=True)
    text = (out / "report.md").read_text()
    assert "SIMULATED DATA" in text and "## Limitations" in text
    assert (out / "claimed_vs_real.png").exists()


def test_trainer_only_saves_model_that_beats_rules(tmp_path):
    listings, sale = simulate_market(n=80, seed=3, hard=True)
    path = tmp_path / "m.joblib"
    result = train([l.history for l in listings], [sale], model_path=path)
    assert path.exists() == result["model_beats_rules"]
    assert result["rows"]["test"] > 0
