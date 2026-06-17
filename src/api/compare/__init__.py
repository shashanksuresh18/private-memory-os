"""Multi-Model Compare / Council mode (cloud-only, normal chat feature).

This package is deliberately SEPARATE from the S1/S2/S3 retrieval tier-routing
engine. It sends one prompt to two or more *cloud* models in parallel, one pane
per model, with blind/reveal, voting, a hash-only scoreboard, and an optional
Council synthesis step. No local Ollama models, and nothing here runs under the
S3 zero-egress fence -- it is a cloud feature gated by explicit user model
selection. Every outbound prompt is DLP-scrubbed before it leaves the device.

Design + UX inspired by the Compare feature of the AGPL project Odysseus
(https://github.com/pewdiepie-archdaemon/odysseus); reimplemented from scratch
in our stack (see ACKNOWLEDGMENTS.md). No source copied verbatim.
"""
