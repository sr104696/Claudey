from radar.extract import IN_AREA, best_bucket, classify_location, is_metro_north, years_mentions


def test_age_requirement_is_not_experience():
    assert years_mentions("Applicants must be at least 18 years of age.") == []


def test_company_history_is_not_experience():
    assert years_mentions("For over 25 years, Axiom has placed lawyers in legal departments.") == []


def test_real_ten_plus_ask():
    ms = years_mentions("You have 10+ years of experience in litigation or investigations.")
    assert [m.lo for m in ms] == [10]


def test_band_ask():
    ms = years_mentions("3-5 years of experience at a law firm or regulator.")
    assert ms and ms[0].lo == 3 and ms[0].hi == 5


def test_jersey_city_and_hoboken_are_in_area():
    for loc in ("Jersey City, NJ", "Hoboken, New Jersey"):
        b = classify_location(loc)
        assert b == "nyc_commutable"
        assert b in IN_AREA
    assert best_bucket(["Chicago, IL", "Jersey City, NJ"]) == "nyc_commutable"
    assert best_bucket(["New York, NY", "Jersey City, NJ"]) == "nyc"


def test_metro_north_stays_out_of_area():
    for loc in ("Stamford, CT", "Greenwich, CT", "White Plains, NY", "Rye, New York"):
        assert classify_location(loc) == "us_other", loc
        assert is_metro_north([loc])
    assert not is_metro_north(["Chicago, IL"])
