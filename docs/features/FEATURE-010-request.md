# FEATURE-010: Request clan castle troops

Opt-in (posts to the clan chat): farm.json `request_minutes` (0 = off), Settings field. Runs in farm
maintenance after walls. Uses the game's saved request text; the bot types nothing.

Flow (`cob/tasks/request.py`): home -> "Request" text over the clan castle (text-only template, scale search:
the dashed label picks up selection arrows and follows the zoom) -> tap the castle -> panel ->
Request -> "Request Reinforcements" -> Send -> dialog closed = sent.
No label = castle full, request pending or cooldown: nothing to do.

Safety: REQUEST_DIALOG towards home is Cancel, never Send. After a request the panel offers
"Request Now!" for gems; it scores 0.34 against the Request template (threshold 0.85) and has a test.

Live (2026-10-19): mapped and cancelled first; one real request sent with the user's OK; castle then showed
a 9m 57s cooldown and the gem button (not touched).

## Log
- 2026-10-19 (Claude Opus 5.5, Windows): request task, live send with user approval.
