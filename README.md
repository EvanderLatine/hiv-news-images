# hiv-news-images

Public image bank for the HIV news bot (link previews). Files are served from
`https://raw.githubusercontent.com/EvanderLatine/hiv-news-images/main/data/image_bank/<file>.jpg`.
Source of truth: `hiv-news-bot/data/image_bank/` (synced by the bot maintainer).

The matching H+ logo versions for long post previews are in
`data/image_bank_branded/` with the same filenames. The bot generates them with
`python3 scripts/publish-branded-image-bank.py <this-repo>` from its own checkout.
They become available at the corresponding GitHub Raw URL after publication.
