"""Quick test for analysis pipeline."""
from data.dummy_data import get_dummy_data
from analysis.beneish import calculate_beneish_mscore, calculate_beneish_trend
from analysis.signals import detect_fraud_signals, get_signal_summary
from analysis.scorer import score_company, benchmark_against_peers

# Test with suspicious data
print("=" * 60)
print("TESTING WITH SUSPICIOUS DATA")
print("=" * 60)

data = get_dummy_data("TEST")

# Beneish M-Score
beneish = calculate_beneish_mscore(data)
print(f"\n--- Beneish M-Score ---")
print(f"M-Score: {beneish['m_score']}")
print(f"Likely Manipulator: {beneish['is_likely_manipulator']}")
print(f"Interpretation: {beneish['interpretation']}")
print(f"Components: {beneish['components']}")

# Fraud Signals
signals = detect_fraud_signals(data)
summary = get_signal_summary(signals)
print(f"\n--- Fraud Signals ---")
print(f"Total triggered: {summary['total']}")
print(f"High: {summary['high_count']}, Medium: {summary['medium_count']}, Low: {summary['low_count']}")
print(f"\nTop 5 signals:")
for s in signals[:5]:
    print(f"  [{s['severity'].upper()}] {s['year']} - {s['name']}: {s['explanation'][:80]}...")

# Risk Score
score = score_company(data, signals, beneish)
print(f"\n--- Risk Score ---")
print(f"Overall: {score['overall_score']}/100 ({score['risk_level']})")
print(f"Breakdown: {score['breakdown']}")

# Peer Benchmarking
peers = benchmark_against_peers("TEST", data)
print(f"\n--- Peer Benchmarking ---")
print(f"Sector: {peers['sector']}")
print(f"Company Metrics: {peers['company_metrics']}")
print(f"Flags: {len(peers['flags'])}")
for f in peers['flags']:
    print(f"  ⚠ {f['metric']}: {f['value']} — {f['concern']}")
