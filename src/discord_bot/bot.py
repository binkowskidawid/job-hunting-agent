"""Discord bot: one-tap rating buttons on every offer card. Ergonomics here is a
correctness requirement, not UX polish — no ratings means no learning."""

from typing import Any

import discord

COLORS = {"great": 0x2ECC71, "worth_it": 0x3498DB, "borderline": 0xF1C40F, "exploration": 0x9B59B6}


class RatingButton(discord.ui.Button["RatingButtons"]):
    def __init__(
        self,
        offer_id: str,
        label: str,
        emoji: str,
        rating: str,
        style: discord.ButtonStyle,
    ) -> None:
        super().__init__(
            label=label, emoji=emoji, style=style, custom_id=f"rating:{rating}:{offer_id}"
        )
        self.offer_id, self.rating = offer_id, rating

    async def callback(self, interaction: discord.Interaction) -> None:
        raise NotImplementedError


class RatingButtons(discord.ui.View):
    def __init__(self, offer_id: str) -> None:
        super().__init__(timeout=None)
        for label, emoji, rating, style in [
            ("Great", "🔥", "great", discord.ButtonStyle.success),
            ("Maybe", "🤔", "maybe", discord.ButtonStyle.primary),
            ("Pass", "👎", "pass", discord.ButtonStyle.secondary),
            ("Never", "🚫", "never_again", discord.ButtonStyle.danger),
        ]:
            self.add_item(RatingButton(offer_id, label, emoji, rating, style))


def build_embed(offer: object, result: dict[str, Any]) -> discord.Embed:
    raise NotImplementedError
