# AutoJoin Application Editor Spec

## Overview
This document describes the future AutoJoin application editor used by the desktop client.

## Requirements
- Use **wangEditor** for rich text editing.
- The editor must include a **Requirement Text** section.
- The Requirement Text must support a Simplified/Traditional toggle **only for display**:
  - Use OpenCC for conversion.
  - Do **not** auto-convert user input.
  - The toggle only affects the Requirement Text preview.
- Image upload constraints:
  - Max **2 MB per image**.
  - Max **8 images total** across the editor and submission payload.

## Submission
- Submit HTML content from the editor (no auto-cleaning).
- Submit image URLs alongside the HTML body.
- The final submission payload should be validated against the size and count limits above.

## Notes
- This spec is documentation only; no runtime logic is implemented yet.
