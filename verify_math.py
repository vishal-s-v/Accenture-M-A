from orchestrator import calculate_synergy_score

def run_tests():
    print("Testing M&A Synergy Scoring Formula...")
    
    # Test case 1: Maximum scores (Risk = 1 - Very Low Risk)
    max_score = calculate_synergy_score(
        strategic_fit=10,
        revenue_synergy=10,
        product_synergy=10,
        technology_synergy=10,
        customer_synergy=10,
        geographic_synergy=10,
        financial_feasibility=10,
        risk_score=1,  # 1 is very low risk
        cultural_compatibility=10
    )
    print(f"Max Score (Risk=1): {max_score}/100 (Expected: 99.0)")
    assert abs(max_score - 99.0) < 0.01, f"Expected 99.0, got {max_score}"
    
    # Test case 2: Minimum scores (Risk = 10 - Very High Risk)
    min_score = calculate_synergy_score(
        strategic_fit=1,
        revenue_synergy=1,
        product_synergy=1,
        technology_synergy=1,
        customer_synergy=1,
        geographic_synergy=1,
        financial_feasibility=1,
        risk_score=10,  # 10 is very high risk
        cultural_compatibility=1
    )
    print(f"Min Score (Risk=10): {min_score}/100 (Expected: 9.0)")
    assert abs(min_score - 9.0) < 0.01, f"Expected 9.0, got {min_score}"
    
    # Test case 3: Mid-range scores (All 5s, Risk = 5)
    mid_score = calculate_synergy_score(
        strategic_fit=5,
        revenue_synergy=5,
        product_synergy=5,
        technology_synergy=5,
        customer_synergy=5,
        geographic_synergy=5,
        financial_feasibility=5,
        risk_score=5,
        cultural_compatibility=5
    )
    print(f"Mid-range Score: {mid_score}/100 (Expected: 50.0)")
    # (5*0.2) + (5*0.15) + (5*0.1) + (5*0.1) + (5*0.1) + (5*0.1) + (5*0.1) + ((10-5)*0.1) + (5*0.05)
    # = 1.0 + 0.75 + 0.5 + 0.5 + 0.5 + 0.5 + 0.5 + 0.5 + 0.25 = 5.0
    # 5.0 * 10 = 50.0
    assert abs(mid_score - 50.0) < 0.01, f"Expected 50.0, got {mid_score}"
    
    print("\nAll scoring math tests passed successfully!")

if __name__ == "__main__":
    run_tests()
