# Encouragements

**Type:** mini app
**URL:** `/encouragements`
**Storage:** `app/db/core.py` → `encouragements`, `encouragement_people`
**Routes:** `app/web_reference.py`
**Templates:** `encouragements.html`

## Purpose

Positive observations about people, with a delivered flag — so appreciation
actually gets said instead of only thought. The dashboard badge counts the
undelivered ones.

## Architecture

Two tables: the people and the observations about them. Per item a copy button
(clipboard) so the text can be pasted into a chat or a review; ticking
delivered takes it out of the badge count.

## Related

`[[contacts]]` · `[[teams-ping]]`
