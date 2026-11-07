# Safety controls and limitations

## Local text guard

Before local feature extraction, audit fingerprinting, or any optional provider call,
the application replaces structured high-risk identifiers (email addresses, SSNs,
date-of-birth labels, account identifiers, Luhn-valid card numbers, and US phone
numbers) with typed placeholders. It then applies a local, rule-based entity
candidate detector for narrowly phrased self-identified names and `City, ST`
locations. Entity values are not written to audit events, reports, model cards, or
curated analytics snapshots.

## Measured scope

The candidate detector is deliberately conservative and has not been validated as a
general named-entity recognizer. It can miss names without a self-identification
phrase, non-US locations, addresses, aliases, misspellings, and multilingual text.
It can also mask ordinary capitalized phrases after `I am`, `This is`, or an address
preposition. It is therefore a defense-in-depth control, not a guarantee that text is
anonymous. A production deployment needs a privacy review, an evaluated local NER
model or human-review workflow, and retention/access controls appropriate to the
data owner.

## Provider boundary

No restricted raw narrative is sent to a provider. Optional Gemini and Jev adapters
receive only the locally masked, length-bounded representation and cannot execute
queries, tools, or instructions supplied by complaint text.
