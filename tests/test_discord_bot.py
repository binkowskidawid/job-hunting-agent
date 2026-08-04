"""Locks the four-rating button contract (great/maybe/pass/never_again) that the
DB schema's `my_rating.rating` column and the cascade's RATING_WEIGHTS depend on."""

from discord_bot.bot import RatingButtons


def test_rating_buttons_cover_all_four_ratings():
    view = RatingButtons(offer_id="test-id")
    ratings = {item.rating for item in view.children}
    assert ratings == {"great", "maybe", "pass", "never_again"}
