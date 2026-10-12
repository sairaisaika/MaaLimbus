# Shop learning and current live evidence

The Maa Agent owns controller input and transactions. MaaFramework native OCR
and NN recognition produce observations; they do not themselves train a shopping
policy. Manual wanted/block lists, reserve coins and per-visit refresh limits
remain action gates. Economy priorities are explicit engineering settings.

Verified purchases and refreshes collect screenshots, JSON hashes, context,
execution traces, proposed labels and review files under
`build/learning-review`. A purchased gift is an execution label, not proof of
benefit. Unbought gifts are not negative examples. Delayed outcomes must belong
to the same run and have human-approved value labels before value training.

`shop_value_training.py` and `train_shop_value.py` provide an offline small MLP,
missing-value masks, independent-run train/test splits and plain JSON export.
The loader revalidates content addresses, retained bytes, full shelves, exact
currency deltas and ledger-bound outcomes. Malformed, altered, duplicate and
foreign-scope evidence is excluded. At least ten reviewed independent episodes
are required to export; this minimum does not establish adequate policy quality.
Weights carry the verified dataset digest. Every exported candidate has
`production_enabled: false`.

The runtime previews an audited candidate's numeric scores in shadow mode and
keeps the existing offer order. Missing/invalid candidates fall back to rules
without stopping gameplay. The actual readiness audit on 2026-10-12 found one
pending sample and zero trainable episodes. There is no trained buying-value
model, live neural purchasing policy, or optimal-shopping claim.

Live installed GUI evidence this day: Devil's Share Purchase once and GET once,
144 coins debited; retained Purchased card reconciled without repeating payment;
two regular refreshes debited 15 and 30, followed by Leave, MAP and a boss fight.
Later frames completed floor-3 gifts and entered floor 4. Native sinner NN ran
in shadow mode; identity teachers resolved only part of the roster.

The next encounter exposed a separate deployment failure: Hong Lu's card became
grayscale, native HP zero reads agreed at .950226/.962656 and capacity became 11.
The effective encounter order excludes only positively proven unavailable cards;
the permanent saved order stays intact. A pending unchanged selection attempt
on such a card is archived as a no-op, never credited as a selected participant.
Retained native replay and an isolated transaction pass; live continuation must
be checked after installation. Full five-floor one-click completion and payout
remain unverified for this run.
